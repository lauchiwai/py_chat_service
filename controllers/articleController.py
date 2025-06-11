from core.auth import get_current_user
from services.articleService import ArticleService
from services.dependencies import get_article_service
from models.request.articleRequest import ArticleGenerationRequest

from fastapi import APIRouter, Depends, Security

router = APIRouter(prefix="/Article", tags=["Article Management"])
    
@router.post("/stream_generate_article")
async def stream_generate_article(
    request: ArticleGenerationRequest,
    service: ArticleService = Depends(get_article_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"])
):
    return await service.stream_generate_article(request)