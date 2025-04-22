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
            return ResultDTO.fail(code=400, message=str(e))
        
    def vector_semantic_search(self, request: VectorSearchRequest) -> ResultDTO[List[VectorSearchResult]]:
        """vector semantic search"""
        try:
            if not qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=404, message="Collection not found")
            
            min_score:float = 0.7
            limit: int = 3
            top_k:int = 10
        
            query_vector = embedding.model.encode(request.query_text).tolist()
            
            hits = qdrant_client.client.search(
                collection_name=request.collection_name,
                query_vector=query_vector,
                limit=limit
            )

            filtered_results = [
                VectorSearchResult(text=hit.payload["text"], score=hit.score)
                for hit in hits
                if hit.score >= min_score
            ]

            top_results = filtered_results[:top_k]
            
            return ResultDTO.ok(data=top_results)
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
        
    def upsert_texts(self, request: UpsertCollectionRequest) -> ResultDTO:
        """upsert texts"""
        if not qdrant_client.client.collection_exists(request.collection_name):
            return ResultDTO.fail(code=404, message="Collection not found")
        
        try:
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
            return ResultDTO.ok(message=f"Successfully inserted {len(request.points)} data")
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
            
    def generate_collection(self,request: GenerateCollectionRequest) -> ResultDTO:
        """generate collections"""
        try:
            if qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=400, message="Collection already exists")
            
            vector_size: int = 384
            distance: str = "COSINE"
            qdrant_client.client.create_collection(
                collection_name=request.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance[distance]
                )
            )
            return ResultDTO.ok(message=f"Collection {request.collection_name} create Successful")
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))