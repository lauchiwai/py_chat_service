from common.models.dto.resultdto import ResultDTO
from common.models.response.vectorResponse import CollectionInfo, VectorSearchResult
from common.models.request.vectorRequest import CheckVectorDataExistRequest, GenerateCollectionRequest, UpsertCollectionRequest
from common.core.qdrant_client_init import qdrant_client
from common.core.embedding_init import embedding

import asyncio, os, hashlib
from qdrant_client.http import models
from concurrent.futures import ThreadPoolExecutor
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

max_workers = min(32, (os.cpu_count() or 4) + 4) 
embedding_executor = ThreadPoolExecutor(max_workers=max_workers)
class VectorService:
    def __init__(self):
        self.thread_pool = embedding_executor 
        self.HARDCODE_LIMIT = 5
        self.HARDCODE_MIN_SCORE = 0.4
        
    async def close(self):
        """close thread pool"""
        self.thread_pool.shutdown(wait=True) 

    async def get_all_collections(self) -> ResultDTO[List[CollectionInfo]]:
        try:
            response = await qdrant_client.client.get_collections() 
            collections = response.collections  
            converted = [CollectionInfo(name=col.name) for col in collections]
            return ResultDTO.ok(data=converted)
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
        
    async def check_vector_data_exist(self, request: CheckVectorDataExistRequest) -> ResultDTO[bool]:
        try:
            
            if not await qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=404, message="Collection not found")
        
            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="id",  
                        match=models.MatchValue(value=request.id),
                    )
                ]
            )
            
            search_result = await qdrant_client.client.scroll(
                collection_name=request.collection_name,
                scroll_filter=filter_condition,
                limit=1
            )

            exists = len(search_result[0]) > 0

            return ResultDTO.ok(data=exists)
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
     
    def generate_base_id(self, id: str) -> int:
        """ string base id switch int"""
        try:
            return int(id)
        except ValueError:
            hash_obj = hashlib.sha256(id.encode())
            return int(hash_obj.hexdigest()[:8], 16)
           
    async def upsert_texts(self, request: UpsertCollectionRequest) -> ResultDTO:
        """upsert texts"""
        if not await qdrant_client.client.collection_exists(request.collection_name):
            return ResultDTO.fail(code=404, message="Collection not found")
        
        try:
            base_id = self.generate_base_id(request.id)
            
            point_ids = [base_id + idx for idx in range(len(request.points))]
            
            texts = [p.text for p in request.points]
            loop = asyncio.get_running_loop()
            vectors = await loop.run_in_executor(
                self.thread_pool,
                lambda: embedding.model.encode(texts).tolist()
            )

            points = [
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "text": p.text,
                        "id": request.id,
                        "point_index": idx
                    }
                )
                for idx, (p, vector, point_id) in enumerate(zip(request.points, vectors, point_ids))
            ]

            await qdrant_client.client.upsert(
                collection_name=request.collection_name,
                points=points
            )
            
            return ResultDTO.ok(message=f"Inserted {len(points)} points under article {request.id}")
            
        except Exception as e:
            return ResultDTO.fail(code=500, message=f"Upsert failed: {str(e)}")
            
    async def generate_collection(self,request: GenerateCollectionRequest) -> ResultDTO:
        """generate collections"""
        try:
            if await qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=400, message="Collection already exists")
            
            vector_size: int = 768
            distance: str = "COSINE"
            await qdrant_client.client.create_collection(
                collection_name=request.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance[distance]
                )
            )
            return ResultDTO.ok(message=f"Collection {request.collection_name} create Successful")
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
        
    def expand_query(self, query: str) -> str:
        """expand query"""
        synonym_map: Dict[str, List[str]] = {
            "邊個": ["誰"],
            "幾時": ["什么時候"],
        }
        
        expanded_terms = [query]
        for term, synonyms in synonym_map.items():
            if term in query:
                expanded_terms.extend(synonyms)
        
        return " ".join(list(set(expanded_terms)))

    async def check_collection_exists(self, collection_name: str) -> Optional[ResultDTO]:
        """check collection exists"""
        if not await qdrant_client.client.collection_exists(collection_name):
            return ResultDTO.fail(code=404, message="Collection not found")
        return None

    def build_search_filter(self, id: str) -> Filter:
        """build search filter"""
        must_conditions = [
            FieldCondition(
                key="id",
                match=MatchValue(value=id)
            )
        ]
        
        return Filter(must=must_conditions)
    
    def format_result_text(self, point_id: int, original_text: str, max_length: int = 300) -> str:
        prefix = f"[Related Data {point_id}] "
        available_length = max_length - len(prefix)
        return f"{prefix}{original_text[:available_length]}" 

    def process_record(self, record, default_score: float = 1.0) -> Optional[VectorSearchResult]:
        """process record"""
        try:
            text = record.payload.get("text", "")
            if not text.strip():
                return None
            
            return VectorSearchResult(
                text=self.format_result_text(
                    point_id=record.id,
                    original_text=text
                ),
                score=getattr(record, "score", default_score)
            )
        except Exception as e:
            print(f"Skipping invalid record: {str(e)}")
            return None
        
    def encode_text(self, text: str):
        return embedding.model.encode(text).tolist()
    
    async def enhance_encoding(self, text: str) -> List[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.thread_pool,
            self.encode_text,  
            text
        )

    async def scroll_all_records(self, collection_name: str, search_filter: Filter) -> List:
        """scroll all records"""
        all_records = []
        next_offset = None
        
        while True:
            response = await qdrant_client.client.scroll(
                collection_name=collection_name,
                scroll_filter=search_filter,
                limit=500,
                offset=next_offset,
                with_payload=True
            )
            
            records, next_offset = response
            if not records:
                break
                
            all_records.extend(records)
            if next_offset is None:
                break
        
        return all_records

    async def vector_semantic_search(self, collection_name: str, query_text: str, id: str) -> ResultDTO[List[VectorSearchResult]]:
        """vector semantic search"""
        try:
            if error := await self.check_collection_exists(collection_name):
                return error
            
            search_filter = self.build_search_filter(id=id)

            query_vector = await self.enhance_encoding(self.expand_query(query_text))

            hits = await qdrant_client.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=self.HARDCODE_LIMIT * 2,
                score_threshold=self.HARDCODE_MIN_SCORE
            )
            
            filtered_results = []
            for hit in hits:
                if hit.score < self.HARDCODE_MIN_SCORE:
                    continue
                
                if result := self.process_record(hit):
                    filtered_results.append(result)
            
            return ResultDTO.ok(data=filtered_results[:self.HARDCODE_LIMIT])
        
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))

    async def vector_article_all_text_query(self, collection_name: str, id: str) -> ResultDTO[List[VectorSearchResult]]:
        """vector article all text query"""
        try:
            if error := await self.check_collection_exists(collection_name):
                return error
            
            search_filter = self.build_search_filter(id=id)
            
            all_records = await self.scroll_all_records(
                collection_name=collection_name,
                search_filter=search_filter
            )
            
            results = []
            for record in all_records:
                if result := self.process_record(record, default_score=1.0):
                    results.append(result)
            
            return ResultDTO.ok(data=results)
        
        except Exception as e:
            return ResultDTO.fail(code=500, message="Internal server error")