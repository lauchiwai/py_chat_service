from services.articleService import ArticleService
from services.dependencies import get_article_service
from models.request.articleRequest import ArticleGenerationRequest

from fastapi import APIRouter, HTTPException, Depends

router = APIRouter(prefix="/Article", tags=["Article Management"])
    
@router.post("/stream_generate_article")
async def stream_generate_article(
    request: ArticleGenerationRequest,
    service: ArticleService = Depends(get_article_service),
):
    return await service.stream_generate_article(request)
    
@router.post("/split_article/")
def split_article(
    article: str,
    service: ArticleService = Depends(get_article_service),
):
    result = service.split_article(article)
    if (result.code == 200):
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)  