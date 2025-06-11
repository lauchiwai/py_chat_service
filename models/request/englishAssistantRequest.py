from pydantic import BaseModel

class WordAssistantRequest(BaseModel):
    word: str
    message: str
    
class TextLinguisticAssistantRequest(BaseModel):
    text: str
    message: str 