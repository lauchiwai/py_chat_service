from fastapi import Depends
from dependencies import get_db
from services.vectorService import VectorService
from services.articleService import ArticleService
from services.englishAssistantService import EnglishAssistantService

def get_vector_service():
    return VectorService()

def get_article_service():
    return ArticleService()

def get_english_assistant_service():
    return EnglishAssistantService()

def get_chat_service(
    db = Depends(get_db),
    vector_service: VectorService = Depends(get_vector_service)
):
    from .chatService import ChatService 
    return ChatService(db, vector_service)

async def get_chat_service_async():
    db = await get_db()  
    vector_service = VectorService()
    from .chatService import ChatService
    return ChatService(db, vector_service)