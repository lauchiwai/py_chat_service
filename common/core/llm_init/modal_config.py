from pydantic import BaseModel, Field
from typing import Optional, Union
from .prompt import llm_prompt

class ChatRequest(BaseModel):
    chat_session_id: str
    user_id:str
    message: str
    collection_name: Union[str, None] = Field(default=None)
    system_prompt: Optional[str] = llm_prompt
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024

class ChatResponse(BaseModel):
    response: str
    conversation_id: str