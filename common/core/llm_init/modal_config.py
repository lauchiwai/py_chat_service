from pydantic import BaseModel, Field
from typing import Union

class ChatRequest(BaseModel):
    chat_session_id: str
    user_id:str
    message: str
    collection_name: Union[str, None] = Field(default=None)

class ChatResponse(BaseModel):
    response: str
    conversation_id: str