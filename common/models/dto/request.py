from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    collection_name: str 
    chat_session_id: str
    user_id: str
class TextPoint(BaseModel):
    text: str
    id: Optional[int] = None
