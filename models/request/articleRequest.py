from pydantic import BaseModel

class ArticleGenerationRequest(BaseModel):
    prompt: str  