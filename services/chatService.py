from datetime import datetime
from services.vectorService import VectorService
from typing import Optional, List, AsyncGenerator
from fastapi.responses import StreamingResponse

from common.core.llm_init.prompt import PromptTemplates
from common.core.llm_init import deepseek
from common.models.dto.resultdto import ResultDTO
from common.core.llm_init.modal_config import ChatRequest
from common.models.dto.request import VectorSearchRequest
from common.models.dto.response import VectorSearchResult

import json
import asyncio
class ChatService:
    def __init__(self, db, vector_service: VectorService):
        self.db = db
        self.vector_service = vector_service
        self.temperature: Optional[float] = 0.7
        self.max_tokens: Optional[int] = 3000
        self.prompt_templates = PromptTemplates()

    async def get_chat_history_by_session_id(self, chat_session_id: str):
        try:
            chat_history = await self.db.histories.find_one({"chat_session_id": chat_session_id})
            if not chat_history:
                return ResultDTO.ok(data={
                    "response": [],
                    "chat_session_id": chat_session_id
                })

            return ResultDTO.ok(data={
                "response": chat_history["messages"],
                "chat_session_id": chat_history["chat_session_id"]
            })
            
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
        
    async def delete_chat_history_by_session_id(self, chat_session_id: str):
        try:
            chat_history = await self.db.histories.find_one({"chat_session_id": chat_session_id})
            if not chat_history:
                return ResultDTO.ok(
                    message=f"sessionId {chat_session_id} have not chat history"
                )
            else :
                delete_result = await self.db.histories.delete_one({"_id": chat_history["_id"]})
                if delete_result.deleted_count == 0:
                    return ResultDTO.fail(
                        code=500,
                        message="Failed to delete chat history"
                    )
                return ResultDTO.ok(
                    message=f"sessionId {chat_session_id} is delete"
                )
            
        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
        
    def generate_chat_history(self, request):
        return {
            "chat_session_id": request.chat_session_id,
            "user_id": request.user_id,
            "messages": [
                {
                    "role": "system",
                    "content": self.prompt_templates.general_assistant,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                {
                    "role": "user",
                    "content": request.message,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            ],
            "metadata": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
        }
        
    def chat_history_append(self, chat_history, content, role):
        chat_history["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    async def save_chat_history(self, chat_history):
        if not chat_history:
            return
            
        if chat_history.get("_id"):
            await self.db.histories.replace_one({"_id": chat_history["_id"]}, chat_history)
        else:
            await self.db.histories.insert_one(chat_history)
                
    def vector_semantic_search(self, request):
        return self.vector_service.vector_semantic_search(
            VectorSearchRequest(
                collection_name=request.collection_name,
                query_text=request.message
            )
        )
    
    def generate_enhanced_messages_by_vector_search(self, search_result, chat_history):
        context_str = "\n".join(
            [f"{item.text}" for i, item in enumerate(search_result.data)]
        )
        system_prompt = self.prompt_templates.rag_analyst(context_str)
        filtered_messages = [msg for msg in chat_history["messages"] if msg["role"] != "system"]
        return [{"role": "system", "content": system_prompt}, *filtered_messages]
    
    def llm_deepseek_steam_endpoint(self, enhanced_messages, stream=False):
        return deepseek.client.chat.completions.create(
            model="deepseek-chat",
            messages=enhanced_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=stream  
        )
    
    async def chat_stream_endpoint(self, request):
        async def event_stream():
            chat_history = None
            full_response = ""
            try:
                chat_history = await self.db.histories.find_one({"chat_session_id": request.chat_session_id})
                if not chat_history:
                    chat_history = self.generate_chat_history(request)
                else:
                    self.chat_history_append(chat_history, request.message, "user")

                enhanced_messages = []
                if request.collection_name:
                    search_result = self.vector_semantic_search(request)
                    if search_result.code != 200:
                        yield f"event: error\ndata: {json.dumps({'message': search_result.message})}\n\n"
                        yield "event: end\ndata: {}\n\n"
                        return
                    enhanced_messages = self.generate_enhanced_messages_by_vector_search(search_result, chat_history)
                else:
                    enhanced_messages = chat_history["messages"]

                stream = self.llm_deepseek_steam_endpoint(enhanced_messages, stream=True)
                
                buffer = ""                
                for chunk in stream:
                    if not chunk.choices:
                        continue
                        
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response += content
                        buffer += content
                        yield f"data: {json.dumps({'content': buffer})}\n\n"
                        buffer = ""

                if buffer:
                    yield f"data: {json.dumps({'content': buffer})}\n\n"
                
                self.chat_history_append(chat_history, full_response, "assistant")
                yield "event: end\ndata: {}\n\n"

            except Exception as e:
                error_msg = str(e)
                if not chat_history:
                    chat_history = self.generate_chat_history(request)
                self.chat_history_append(chat_history, f"系統錯誤: {error_msg}", "system")
                yield f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"
                yield "event: end\ndata: {}\n\n"

            finally:
                if chat_history:
                    asyncio.create_task(self.save_chat_history(chat_history))

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )