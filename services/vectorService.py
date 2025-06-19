from models.dto.resultdto import ResultDTO
from models.response.vectorResponse import CollectionInfo, VectorSearchResult
from models.request.vectorRequest import CheckVectorDataExistRequest, DeleteVectorDataRequest, GenerateCollectionRequest, UpsertCollectionRequest
from core.qdrant_client_init import qdrant_client
from core.embedding_init import embedding

import asyncio, os, hashlib
from qdrant_client.http import models
from concurrent.futures import ThreadPoolExecutor
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue
from typing import List, Dict, Optional
from qdrant_client.http import models as qdrant_models

max_workers = min(32, (os.cpu_count() or 4) + 4) 
embedding_executor = ThreadPoolExecutor(max_workers=max_workers)

class VectorService:
    def __init__(self):
        self.thread_pool = embedding_executor 
        self.HARDCODE_LIMIT = 5
        self.HARDCODE_MIN_SCORE = 0.4
        self.VECTOR_DIM = 768
        self._verify_embedding_dimension()
        
    def _verify_embedding_dimension(self):
        test_text = "dimension test"
        test_vector = embedding.model.encode([test_text]).tolist()[0]
        actual_dim = len(test_vector)
        
        if actual_dim != self.VECTOR_DIM:
            print(f"警告: 嵌入模型維度({actual_dim})不匹配固定維度({self.VECTOR_DIM})")
            print("系統將繼續運行，但向量操作可能失敗")
            print("解決方案: 更換嵌入模型或修改FIXED_VECTOR_DIMENSION")
        else:
            print(f"嵌入模型維度驗證通過: {actual_dim}維")
    
    async def close(self):
        print("關閉線程池...")
        self.thread_pool.shutdown(wait=True) 

    async def get_all_collections(self) -> ResultDTO[List[CollectionInfo]]:
        try:
            response = await qdrant_client.client.get_collections() 
            collections = response.collections
            print(f"找到集合數量: {len(collections)}")
            converted = [CollectionInfo(name=col.name) for col in collections]
            return ResultDTO.ok(data=converted)
        except Exception as e:
            print(f"獲取集合失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))

    async def delete_vector_data(self, request: DeleteVectorDataRequest) -> ResultDTO:
        try:
            if not await qdrant_client.client.collection_exists(request.collection_name):
                print(f"集合不存在: {request.collection_name}")
                return ResultDTO.fail(code=404, message="Collection not found")

            filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="id",  
                        match=models.MatchValue(value=request.id),
                    )
                ]
            )

            await qdrant_client.client.delete(
                collection_name=request.collection_name,
                points_selector=qdrant_models.FilterSelector(
                    filter=filter_condition
                )
            )
            print(f"已刪除向量資料 ID {request.id} 從集合 '{request.collection_name}'")
            return ResultDTO.ok(message=f"Deleted vector data ID {request.id}")
        except Exception as e:
            print(f"刪除失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=f"Deletion failed: {str(e)}")
        
    async def check_vector_data_exist(self, request: CheckVectorDataExistRequest) -> ResultDTO[bool]:
        try:
            if not await qdrant_client.client.collection_exists(request.collection_name):
                print(f"集合不存在: {request.collection_name}")
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
            print(f"檢查結果: 存在={exists}")
            return ResultDTO.ok(data=exists)
        except Exception as e:
            print(f"檢查失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))
     
    def generate_base_id(self, id: int) -> int:
        try:
            return int(id)
        except ValueError:
            print(f"ID非整數，進行雜湊: {id}")
            hash_obj = hashlib.sha256(str(id).encode())
            hashed = int(hash_obj.hexdigest()[:8], 16)
            print(f"雜湊後ID: {id} -> {hashed}")
            return hashed
           
    async def upsert_texts(self, request: UpsertCollectionRequest) -> ResultDTO:
        if not await qdrant_client.client.collection_exists(request.collection_name):
            print(f"集合不存在: {request.collection_name}")
            return ResultDTO.fail(code=404, message="Collection not found")
        
        try:
            base_id = self.generate_base_id(request.id)
            point_ids = [base_id + idx for idx in range(len(request.points))]
            texts = [p.text for p in request.points]
            
            loop = asyncio.get_running_loop()
            print("產生嵌入向量...")
            vectors = await loop.run_in_executor(
                self.thread_pool,
                lambda: embedding.model.encode(texts).tolist()
            )
            
            if vectors and len(vectors[0]) != self.VECTOR_DIM:
                actual_dim = len(vectors[0])
                print(f"向量維度錯誤! 實際={actual_dim}, 預期={self.VECTOR_DIM}")
                return ResultDTO.fail(
                    code=400,
                    message=f"Vector dimension mismatch"
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
            
            print(f"已插入 {len(points)} 個點")
            return ResultDTO.ok(message=f"Inserted {len(points)} points")
            
        except Exception as e:
            print(f"更新失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=f"Upsert failed: {str(e)}")
            
    async def generate_collection(self, request: GenerateCollectionRequest) -> ResultDTO:
        try:
            if await qdrant_client.client.collection_exists(request.collection_name):
                collection_info = await qdrant_client.client.get_collection(request.collection_name)
                existing_dim = collection_info.config.params.vectors.size
                
                if existing_dim != self.VECTOR_DIM:
                    print(f"維度不匹配! 現有維度={existing_dim}, 需要={self.VECTOR_DIM}")
                    return ResultDTO.fail(
                        code=400, 
                        message=f"Collection dimension mismatch"
                    )
                print(f"集合已存在且維度正確: {self.VECTOR_DIM}")
                return ResultDTO.ok(message="Collection already exists")
            
            vector_size = self.VECTOR_DIM
            distance = "COSINE"
            
            await qdrant_client.client.create_collection(
                collection_name=request.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance[distance]
                )
            )
            print(f"集合 {request.collection_name} 建立成功")
            return ResultDTO.ok(message=f"Collection created")
        except Exception as e:
            print(f"集合建立失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))
        
    def expand_query(self, query: str) -> str:
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
        exists = await qdrant_client.client.collection_exists(collection_name)
        if not exists:
            print(f"集合不存在: {collection_name}")
            return ResultDTO.fail(code=404, message="Collection not found")
        return None

    def build_search_filter(self, id: int) -> Filter:
        must_conditions = [
            FieldCondition(
                key="id",
                match=MatchValue(value=id)
            )
        ]
        return Filter(must=must_conditions)
    
    def format_result_text(self, point_id: int, original_text: str, max_length: int = 300) -> str:
        prefix = f"[相關資料 {point_id}] "
        available_length = max_length - len(prefix)
        result = f"{prefix}{original_text[:available_length]}" 
        if len(original_text) > available_length:
            result += "..."
        return result

    def process_record(self, record, default_score: float = 1.0) -> Optional[VectorSearchResult]:
        try:
            text = record.payload.get("text", "")
            if not text.strip():
                print(f"跳過空文本記錄: {record.id}")
                return None
            
            formatted = self.format_result_text(
                point_id=record.id,
                original_text=text
            )
            score = getattr(record, "score", default_score)
            return VectorSearchResult(text=formatted, score=score)
        except Exception as e:
            print(f"跳過無效記錄: {str(e)}")
            return None
        
    def encode_text(self, text: str):
        return embedding.model.encode([text]).tolist()[0]
    
    async def enhance_encoding(self, text: str) -> List[float]:
        loop = asyncio.get_running_loop()
        vector = await loop.run_in_executor(
            self.thread_pool,
            self.encode_text,  
            text
        )
        
        if len(vector) != self.VECTOR_DIM:
            actual_dim = len(vector)
            if actual_dim > self.VECTOR_DIM:
                vector = vector[:self.VECTOR_DIM]
            else:
                vector = vector + [0.0] * (self.VECTOR_DIM - actual_dim)
            print(f"已調整查詢向量維度至 {self.VECTOR_DIM}")
        
        return vector

    async def scroll_all_records(self, collection_name: str, search_filter: Filter) -> List:
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

    async def vector_semantic_search(self, collection_name: str, query_text: str, id: int) -> ResultDTO[List[VectorSearchResult]]:
        try:
            if error := await self.check_collection_exists(collection_name):
                return error
            
            search_filter = self.build_search_filter(id=id)
            expanded_query = self.expand_query(query_text)
            query_vector = await self.enhance_encoding(expanded_query)

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
            
            final_results = filtered_results[:self.HARDCODE_LIMIT]
            return ResultDTO.ok(data=final_results)
        
        except Exception as e:
            print(f"語義搜尋失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))

    async def vector_article_all_text_query(self, collection_name: str, id: int) -> ResultDTO[List[VectorSearchResult]]:
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
            print(f"文章文本查詢失敗: {str(e)}")
            return ResultDTO.fail(code=500, message="Internal server error")
