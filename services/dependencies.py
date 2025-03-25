from fastapi import Depends
from common.dependencies import get_db

async def get_chat_service(
    db = Depends(get_db),
):
    from .chatService import ChatService 
    return ChatService(db, vector_service)