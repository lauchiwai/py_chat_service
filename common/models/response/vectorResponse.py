from pydantic import BaseModel

class CollectionInfo(BaseModel):
    name: str
    
class VectorSearchResult(BaseModel):
    text: str
    score: float