from datetime import datetime
from typing import Optional, Union
from models.request.chatRequest import ChatRequest, SummaryRequest
import asyncio
from functools import partial

class ChatHistoryHelper:
    def __init__(self, db, prompt_templates, temperature=0.7, max_tokens=3000):
        self.db = db
        self.prompt_templates = prompt_templates
        self.temperature = temperature
        self.max_tokens = max_tokens

    @staticmethod
    def get_current_timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def create_message(self, role: str, content: str) -> dict:
        return {
            "role": role,
            "content": content.strip(),
            "timestamp": self.get_current_timestamp()
        }

    def generate_chat_history(self, chat_session_id: str, user_id: str, message: Optional[str] = None) -> dict:
        messages = [
            self.create_message("system", self.prompt_templates.general_assistant)
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
            return self.create(request)
        
        return chat_history
    
    def create(self, request: Union[ChatRequest, SummaryRequest]) :
        message = request.message if isinstance(request, ChatRequest) else None
        return self.generate_chat_history(
            request.chat_session_id,
            request.user_id,
            message
        )

    def append_message(self, chat_history: dict, content: str, role: str):
        chat_history["messages"].append(self.create_message(role, content))

    async def async_save(self, chat_history: dict):
        if not chat_history:
            return
        
        try:
            if "_id" in chat_history:
                await self.db.histories.replace_one(
                    {"_id": chat_history["_id"]},
                    chat_history,
                    upsert=True 
                )
            else:
                await self.db.histories.insert_one(chat_history)
        except Exception as e:
            print(f"Database save error: {str(e)}")
            raise

    def log_save_result(self, task, chat_history: dict):
        try:
            task.result() 
            print(f"[Success] Saved: {chat_history['chat_session_id']}")
        except asyncio.CancelledError:
            print(f"[Error] Save cancelled: {chat_history['chat_session_id']}")
        except Exception as e:
            print(f"[Error] Save failed: {str(e)}")

    async def finalize(self, chat_history: dict, full_response: str):
        self.append_message(chat_history, full_response, "assistant")
        save_task = asyncio.create_task(self.async_save(chat_history))
        save_task.add_done_callback(
            partial(self.log_save_result, chat_history=chat_history)
        )
