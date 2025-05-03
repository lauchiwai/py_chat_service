from pydantic import BaseModel, Field
from typing import Union

class BaseRequest(BaseModel):
    chat_session_id: str
    user_id:str
    article_id: str
    collection_name: Union[str, None] = Field(default=None)
    
    
class ChatRequest(BaseRequest) :
    message: str
    
class SummaryRequest(BaseRequest):
    pass