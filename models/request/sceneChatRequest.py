from pydantic import BaseModel

class SceneChatRequest(BaseModel):
    chat_session_id: int
    user_id:int
    message: str