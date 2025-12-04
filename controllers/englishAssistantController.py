from core.auth import get_current_user
from models.request.englishAssistantRequest import WordAssistantRequest, TextLinguisticAssistantRequest
from services.englishAssistantService import EnglishAssistantService
from services.dependencies import get_english_assistant_service
from fastapi import APIRouter, Depends, Security

router = APIRouter(prefix="/EnglishAssistant", tags=["English Assistant Management"])
@router.post("/stream_english_word_translate")
async def stream_english_word_translate(
    request: WordAssistantRequest,
    service: EnglishAssistantService = Depends(get_english_assistant_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"])
):
    return await service.stream_english_word_translate(request)
    
@router.post("/stream_english_word_analysis")
async def stream_english_word_analysis(
    request: WordAssistantRequest,
    service: EnglishAssistantService = Depends(get_english_assistant_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"])
):
    return await service.stream_english_word_analysis(request)

@router.post("/stream_english_text_linguistic_analysis")
async def stream_english_text_linguistic_analysis(
    request: TextLinguisticAssistantRequest,
    service: EnglishAssistantService = Depends(get_english_assistant_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"])
):
    return await service.stream_english_text_linguistic_analysis(request)