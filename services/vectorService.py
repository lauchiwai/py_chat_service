from common.models.dto.resultdto import ResultDTO
from common.models.dto.response import CollectionInfo, VectorSearchResult
from common.models.dto.request import GenerateCollectionRequest, VectorSearchRequest, UpsertCollectionRequest
from common.core.qdrant_client_init import qdrant_client
from common.core.embedding_init import embedding
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchText
from typing import List, Dict
import re

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
        
    def _expand_query(self, query: str) -> str:
        synonym_map: Dict[str, List[str]] = {
            "資產": ["資產", "土地", "非自住物業", "現金", "銀行儲蓄", "股票及股份的投資"]
        }
        
        expanded_terms = [query]
        for term, synonyms in synonym_map.items():
            if term in query:
                expanded_terms.extend(synonyms)
        
        return " ".join(list(set(expanded_terms)))
    

    def _enhance_encoding(self, text: str) -> List[float]:
        processed_text = f"問題：{text.strip()}"  
        cleaned_text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', processed_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  
        return embedding.model.encode(cleaned_text).tolist()
    
    def _hybrid_search(self, collection: str, vector: List[float], query: str, limit: int) -> List:
        keyword_filter = Filter(
            must=[FieldCondition(key="text", match=MatchText(text=query))]
        )
        
        return qdrant_client.client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=keyword_filter,  
            limit=limit * 2,  
            score_threshold=0.5
        )
        
    def _format_result_text(self, point_id: int, original_text: str, max_length: int = 300) -> str:
        prefix = f"[相關資料 {point_id}] "
        available_length = max_length - len(prefix)
        return f"{prefix}{original_text[:available_length]}" 
        
    def vector_semantic_search(self, request: VectorSearchRequest) -> ResultDTO[List[VectorSearchResult]]:
        """vector semantic search"""
        try:
            if not qdrant_client.client.collection_exists(request.collection_name):
                return ResultDTO.fail(code=404, message="Collection not found")
            
            HARDCODE_LIMIT = 5
            HARDCODE_MIN_SCORE = 0.5
            
            expanded_query = self._expand_query(request.query_text)
            
            query_vector = self._enhance_encoding(expanded_query)
            
            hits = self._hybrid_search(
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
                
                formatted_text = self._format_result_text(
                    point_id=hit.id,
                    original_text=hit.payload["text"]
                )
                
                filtered_results.append(
                    VectorSearchResult(text=formatted_text, score=hit.score)
                )

            return ResultDTO.ok(data=filtered_results[:HARDCODE_LIMIT])
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