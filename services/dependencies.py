from fastapi import Depends
from common.dependencies import get_db
from .vectorService import VectorService
from common.core.mongodb_init import mongodb 

async def get_vector_service():
    return VectorService()

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