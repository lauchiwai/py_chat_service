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
        self.max_tokens: Optional[int] = 1024
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
        
    def generate_chat_history(self, request: ChatRequest):
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
        
    def chat_history_append(self, chat_history: any, content: str, role: str):
        chat_history["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    def vector_semantic_search(self, request: ChatRequest):
        return self.vector_service.vector_semantic_search(
            VectorSearchRequest(
                collection_name=request.collection_name,
                query_text=request.message,
                limit=3
            )
        )
    
    def generate_enhanced_messages_by_vector_search(self, search_result: ResultDTO[List[VectorSearchResult]], chat_history: any):
        context_str = "\n".join(
            [f"[相關資料 {i+1}] {item.text}" for i, item in enumerate(search_result.data)]
        )
        
        system_prompt = self.prompt_templates.rag_analyst(context_str)
        filtered_messages = [msg for msg in chat_history["messages"] if msg["role"] != "system"]
        
        return [
            {
                "role": "system",
                "content": system_prompt  
            },
            *filtered_messages
        ]

    def llm_deepseek_endpoint(self, enhanced_messages) :
        return deepseek.client.chat.completions.create(
            model="deepseek-chat",
            messages=enhanced_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=False
        )
         
    async def chat_endpoint(self, request: ChatRequest):
        try:
            chat_history = await self.db.histories.find_one({"chat_session_id": request.chat_session_id})
            
            if not chat_history:
                chat_history = self.generate_chat_history(request)
            else:
                self.chat_history_append(chat_history, request.message, "user")
            
            if request.collection_name is not None:
                search_result = self.vector_semantic_search(request)
                
                if search_result.code != 200:
                    return ResultDTO.fail(code=search_result.code, message=search_result.message)
                else : 
                    enhanced_messages = self.generate_enhanced_messages_by_vector_search(search_result, chat_history)
            else :
                enhanced_messages = chat_history["messages"]
                    
            response = self.llm_deepseek_endpoint(enhanced_messages)

            assistant_msg = response.choices[0].message.content

            self.chat_history_append(chat_history, assistant_msg, "assistant")

            if chat_history.get("_id"):  
                await self.db.histories.replace_one({"_id": chat_history["_id"]}, chat_history)
            else:  
                await self.db.histories.insert_one(chat_history)

            return ResultDTO.ok(data={
                "response": assistant_msg,
                "chat_session_id": request.chat_session_id
            })

        except Exception as e:
            return ResultDTO.fail(code=400, message=str(e))
    
    def llm_deepseek_steam_endpoint(self, enhanced_messages, stream=False):
        return deepseek.client.chat.completions.create(
            model="deepseek-chat",
            messages=enhanced_messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=stream  
        )
    
    async def chat_stream_endpoint(self, request: ChatRequest):
        async def event_stream():
            chat_history = None
            full_response = ""
            try:
                chat_history = await self.db.histories.find_one({"chat_session_id": request.chat_session_id})
                
                if not chat_history:
                    chat_history = self.generate_chat_history(request)
                else:
                    self.chat_history_append(chat_history, request.message, "user")
                    
                if request.collection_name is not None:
                    search_result = self.vector_semantic_search(request)
                    
                    if search_result.code != 200:
                        yield f"event: error\ndata: {json.dumps({'message': search_result.message})}\n\n"
                        return
                    else : 
                        enhanced_messages = self.generate_enhanced_messages_by_vector_search(search_result, chat_history)
                else :
                    enhanced_messages = chat_history["messages"]
                    
                    
                stream = await asyncio.to_thread(
                    self.llm_deepseek_steam_endpoint, 
                    enhanced_messages=enhanced_messages,
                    stream=True
                )
                
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        full_response += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
                
                self.chat_history_append(chat_history, full_response, "assistant")
                if chat_history.get("_id"):
                    await self.db.histories.replace_one({"_id": chat_history["_id"]}, chat_history)
                else:
                    await self.db.histories.insert_one(chat_history)
                
                yield "event: end\ndata: {}\n\n"
                
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
