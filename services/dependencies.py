from fastapi import Depends
from common.dependencies import get_db
from .vectorService import VectorService

async def get_vector_service():
    return VectorService()

async def get_chat_service(
    db = Depends(get_db),
    vector_service: VectorService = Depends(get_vector_service)
):
    from .chatService import ChatService 
    return ChatService(db, vector_service)