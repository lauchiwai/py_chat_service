from services.chatService import ChatService
from services.dependencies import get_chat_service

from common.core.auth import get_current_user
from common.models.request.chatRequest import ChatRequest, SummaryRequest

from fastapi import APIRouter, HTTPException, Depends, Security

router = APIRouter(prefix="/Chat", tags=["Chat Management"])
@router.get("/getChatHistoryBySessionId/{chat_session_id}")
async def get_chat_history_by_session_id(
    chat_session_id: str,
    service: ChatService = Depends(get_chat_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
):
    """ get chat histoty by session_id from mongodb """
    result = await service.get_chat_history_by_session_id(chat_session_id)
    if (result.code == 200):
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)
    
@router.delete("/deleteChatHistoryBySessionId/{chat_session_id}")
async def delete(
    chat_session_id: str,
    service: ChatService = Depends(get_chat_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
):
    """ get chat histoty by session_id from mongodb """
    result = await service.delete_chat_history_by_session_id(chat_session_id)
    if (result.code == 200):
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)
    
@router.post("/chat_stream")
async def chat_stream(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"])
):
    return await service.chat_stream_endpoint(request)

@router.post("/summary_stream")
async def summary_stream(
    request: SummaryRequest,
    service: ChatService = Depends(get_chat_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"])
):
    return await service.summary_stream_endpoint(request)