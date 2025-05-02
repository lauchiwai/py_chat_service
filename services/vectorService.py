import asyncio, os
from concurrent.futures import ThreadPoolExecutor
from common.models.dto.resultdto import ResultDTO
from common.models.dto.response import CollectionInfo, VectorSearchResult
from common.models.dto.request import GenerateCollectionRequest, VectorSearchRequest, UpsertCollectionRequest
from common.core.qdrant_client_init import qdrant_client
from common.core.embedding_init import embedding
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchText
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

max_workers = min(32, (os.cpu_count() or 4) + 4) 
embedding_executor = ThreadPoolExecutor(max_workers=max_workers)
class VectorService:
    def __init__(self):
        self.thread_pool = embedding_executor 
        
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
        
    def expand_query(self, query: str) -> str:
        synonym_map: Dict[str, List[str]] = {
            "資產": ["資產", "土地", "非自住物業", "現金", "銀行儲蓄", "股票及股份的投資"]
        }
        
        expanded_terms = [query]
        for term, synonyms in synonym_map.items():
            if term in query:
                expanded_terms.extend(synonyms)
        
        return " ".join(list(set(expanded_terms)))
    
    def encode_text(self, text: str):
        return embedding.model.encode(text).tolist()

    async def enhance_encoding(self, text: str) -> List[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.thread_pool,
            self.encode_text,  
            text
        )
    
    async def hybrid_search(self, collection: str, vector: List[float], query: str, limit: int) -> List:
        keyword_filter = Filter(
            must=[FieldCondition(key="text", match=MatchText(text=query))]
        )
        
        return await qdrant_client.client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=keyword_filter,  
            limit=limit * 2,  
            score_threshold=0.5
        )
        
    def format_result_text(self, point_id: int, original_text: str, max_length: int = 300) -> str:
        prefix = f"[相關資料 {point_id}] "
        available_length = max_length - len(prefix)
        return f"{prefix}{original_text[:available_length]}" 
        
    async def vector_semantic_search(self, request: VectorSearchRequest) -> ResultDTO[List[VectorSearchResult]]:
        """vector semantic search"""
        try:
            if not await qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=404, message="Collection not found")
            
            HARDCODE_LIMIT = 5
            HARDCODE_MIN_SCORE = 0.5
            
            expanded_query = self.expand_query(request.query_text)
            
            query_vector = await self.enhance_encoding(expanded_query)
            
            hits = await self.hybrid_search(
                collection=request.collection_name,
                vector=query_vector,
                query=expanded_query,  
                limit=HARDCODE_LIMIT
            )

            filtered_results = []
            for hit in hits:
                if hit.score < HARDCODE_MIN_SCORE:
                    continue
                if 'text' not in hit.payload:
                    continue 
                
                formatted_text = self.format_result_text(
                    point_id=hit.id,
                    original_text=hit.payload["text"]
                )
                
                filtered_results.append(
                    VectorSearchResult(text=formatted_text, score=hit.score)
                )

            return ResultDTO.ok(data=filtered_results[:HARDCODE_LIMIT])
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
        
    async def upsert_texts(self, request: UpsertCollectionRequest) -> ResultDTO:
        """upsert texts"""
        if not await qdrant_client.client.collection_exists(request.collection_name):
            return ResultDTO.fail(code=404, message="Collection not found")
        
        try:
            texts = [p.text for p in request.points]
            loop = asyncio.get_running_loop()
            vectors = await loop.run_in_executor(
                self.thread_pool,
                lambda: embedding.model.encode(texts).tolist()
            )
            request.points = [
                PointStruct(
                    id=p.id or idx,
                    vector=vector,
                    payload={"text": p.text}
                )
                for idx, (p, vector) in enumerate(zip(request.points, vectors))
            ]
            
            await qdrant_client.client.upsert(
                collection_name=request.collection_name,
                points=request.points
            )
            return ResultDTO.ok(message=f"Successfully inserted {len(request.points)} data")
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
            
    async def generate_collection(self,request: GenerateCollectionRequest) -> ResultDTO:
        """generate collections"""
        try:
            if await qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=400, message="Collection already exists")
            
            vector_size: int = 384
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