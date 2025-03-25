from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    collection_name: str 
    chat_session_id: str
    user_id: str
    
class GenerateCollectionRequest(BaseModel):
    collection_name: str
    vector_size: int = 384
    distance: str = "COSINE"

class TextPoint(BaseModel):
    text: str
    id: Optional[int] = None
    
class UpsertCollectionRequest(BaseModel):
    collection_name: str
    points: List[TextPoint]
    
class VectorSearchRequest(BaseModel):
    collection_name: str
    query_text: str
    min_score:float = 0.7
    limit: int = 3
    top_k:int = 10