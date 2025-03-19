from pydantic import BaseModel
from typing import Optional
from .prompt import llm_prompt

class ChatRequest(BaseModel):
    message: str
    system_prompt: Optional[str] = llm_prompt
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024

class ChatResponse(BaseModel):
    response: str
    conversation_id: str