from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    collection_name: str 
    chat_session_id: str
    user_id: str
    
class GenerateCollectionRequest(BaseModel):
    collection_name: str

class TextPoint(BaseModel):
    text: str
    id: Optional[int] = None
    
class UpsertCollectionRequest(BaseModel):
    collection_name: str
    points: List[TextPoint]
    
class VectorSearchRequest(BaseModel):
    collection_name: str
    query_text: str
