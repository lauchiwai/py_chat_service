from pydantic import BaseModel, Field
from typing import Union

class BaseRequest(BaseModel):
    chat_session_id: int
    user_id:int
    article_id: Union[int, None] = None
    collection_name: Union[str, None] = Field(default=None)
    
class ChatRequest(BaseRequest) :
    message: str
    
class SummaryRequest(BaseRequest):
    pass