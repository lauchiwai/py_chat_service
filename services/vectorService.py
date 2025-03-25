from common.models.dto.resultdto import ResultDTO
from common.models.dto.response import CollectionInfo, VectorSearchResult
from common.models.dto.request import GenerateCollectionRequest, VectorSearchRequest, UpsertCollectionRequest
from common.core.qdrant_client_init import qdrant_client
from common.core.embedding_init import embedding
from qdrant_client.models import PointStruct 
from qdrant_client.models import VectorParams, Distance
from typing import List

class VectorService:
    def get_all_collections(self) -> ResultDTO[List[CollectionInfo]]:
        try:
            response = qdrant_client.client.get_collections().collections
            converted = [
                CollectionInfo(name=col.name)
                for col in response
            ]
            
            return ResultDTO.ok(data=converted)
        except Exception as e:
            return ResultDTO.fail(code=500, message=str(e))
        
    def vector_semantic_search(self, request: VectorSearchRequest) -> ResultDTO[List[VectorSearchResult]]:
        """语义相似度搜索"""
        try:
            if not qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=404, message="集合不存在")
        
            query_vector = embedding.model.encode(request.query_text).tolist()
            
            hits = qdrant_client.client.search(
                collection_name=request.collection_name,
                query_vector=query_vector,
                limit=request.limit
            )

            filtered_results = [
                VectorSearchResult(text=hit.payload["text"], score=hit.score)
                for hit in hits
                if hit.score >= request.min_score  
            ]

            top_results = filtered_results[:request.top_k]
            
            return ResultDTO.ok(data=top_results)
        except Exception as e:
            return ResultDTO.fail(code=500, message=str(e))
        
    def upsert_texts(self, request: UpsertCollectionRequest) -> ResultDTO:
        """批量插入文本数据"""
        if not qdrant_client.client.collection_exists(request.collection_name):
            return ResultDTO.fail(code=404, message="集合不存在")
        
        try:
            # 生成向量
            texts = [p.text for p in request.points]
            vectors = embedding.model.encode(texts).tolist()
            
            request.points = [
                PointStruct(
                    id=p.id or idx,
                    vector=vector,
                    payload={"text": p.text}
                )
                for idx, (p, vector) in enumerate(zip(request.points, vectors))
            ]
            
            qdrant_client.client.upsert(
                collection_name=request.collection_name,
                points=request.points
            )
            return ResultDTO.ok(message=f"成功插入 {len(request.points)} 条数据")
        except Exception as e:
            return ResultDTO.fail(code=500, message=str(e))
            
    def generate_collection(self,request: GenerateCollectionRequest) -> ResultDTO:
        """generate collections"""
        try:
            if qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=400, message="集合已存在")
            
            qdrant_client.client.create_collection(
                collection_name=request.collection_name,
                vectors_config=VectorParams(
                    size=request.vector_size,
                    distance=Distance[request.distance]
                )
            )
            return ResultDTO.ok(message=f"集合 {request.collection_name} 创建成功")
        except Exception as e:
            return ResultDTO.fail(code=500, message=str(e))