from pydantic import BaseModel, Field
from typing import List, Optional
    
class GenerateCollectionRequest(BaseModel):
    collection_name: str

class TextPoint(BaseModel):
    text: str
    id: Optional[int] = Field(None, gt=0)
    
class UpsertCollectionRequest(BaseModel):
    collection_name: str
    id: str
    points: List[TextPoint]
    
class VectorSearchRequest(BaseModel):
    collection_name: str
    query_text: str
    id: str
    
class CheckVectorDataExistRequest(BaseModel):
    collection_name: str
    id: str
