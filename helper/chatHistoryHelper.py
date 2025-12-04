from datetime import datetime
from typing import Optional, Union
from models.request.chatRequest import ChatRequest, SummaryRequest
from functools import partial
from core.llm_init.prompt import PromptTemplates
import asyncio

class ChatHistoryHelper:
    def __init__(self, db, prompt_templates: PromptTemplates, temperature=0.7, max_tokens=3000):
        self.db = db
        self.prompt_templates = prompt_templates
        self.temperature = temperature
        self.max_tokens = max_tokens

    @staticmethod
    def get_current_timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def create_message(self, role: str, content: str) -> dict:
        msg = {
            "role": role,
            "content": content.strip(),
            "timestamp": self.get_current_timestamp()
        }
        return msg

    def generate_chat_history(self, chat_session_id: int, user_id: int, prompt: str, message: Optional[str] = None) -> dict:
        messages = [
            self.create_message("system", prompt)
        ]
        
        if message and message.strip():
            messages.append(self.create_message("user", message))

        return {
            "chat_session_id": chat_session_id,
            "user_id": user_id,
            "messages": messages,
            "metadata": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
        }

    async def get_or_create(self, request: Union[ChatRequest, SummaryRequest]) -> dict:
        chat_history = await self.db.histories.find_one(
            {"chat_session_id": request.chat_session_id}
        )
        
        if not chat_history:
            if isinstance(request, ChatRequest):
                chat_history = self.CreateChatHistory(request)
            elif isinstance(request, SummaryRequest):
                chat_history = self.CreateSummaryHistory(request)
        
        return chat_history
    
    def CreateChatHistory(self, request: ChatRequest) :
        return self.generate_chat_history(
            request.chat_session_id,
            request.user_id,
            self.prompt_templates.general_assistant(),
            request.message
        )
        
    def CreateSummaryHistory(self, request: SummaryRequest) :
        return self.generate_chat_history(
            request.chat_session_id,
            request.user_id,
            self.prompt_templates.general_assistant(),
            None
        )
    
    def append_message(self, chat_history: dict, content: str, role: str):
        chat_history["messages"].append(self.create_message(role, content))

    async def async_save(self, chat_history: dict):
        if not chat_history:
            return
        
        try:
            session_id = chat_history.get("chat_session_id", "unknown")
            if "_id" in chat_history:
                await self.db.histories.replace_one(
                    {"_id": chat_history["_id"]},
                    chat_history,
                    upsert=True 
                )
            else:
                await self.db.histories.insert_one(chat_history)
        except Exception as e:
            raise

    def log_save_result(self, task, chat_history: dict):
        session_id = chat_history.get("chat_session_id", "unknown")
        try:
            task.result() 
        except asyncio.CancelledError:
            pass
        except Exception as e:
            pass

    async def finalize(self, chat_history: dict, full_response: str):
        if not chat_history:
            return
            
        if full_response:
            self.append_message(chat_history, full_response, "assistant")
        
        save_task = asyncio.create_task(self.async_save(chat_history))
        save_task.add_done_callback(
            partial(self.log_save_result, chat_history=chat_history)
        )
