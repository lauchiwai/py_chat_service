from datetime import datetime
from services.vectorService import VectorService
from typing import Optional
from fastapi.responses import StreamingResponse
from functools import partial

from common.core.llm_init.prompt import PromptTemplates
from common.core.llm_init import deepseek
from common.models.dto.resultdto import ResultDTO
from common.models.dto.request import VectorSearchRequest

import json, asyncio

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
        
        if "_id" in chat_history:
            await self.db.histories.replace_one(
                {"_id": chat_history["_id"]},
                chat_history,
                upsert=True 
            )
        else:
            await self.db.histories.insert_one(chat_history)
        
    async def vector_semantic_search(self, request):
        return await self.vector_service.vector_semantic_search(
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
        
    async def llm_deepseek_steam_endpoint(self, enhanced_messages, stream=False, timeout=30):
        try:
            response = await asyncio.wait_for(
                deepseek.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=enhanced_messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=stream
                ),
                timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            print("Deepseek request timed out")
            raise
        
    async def prepare_conversation_context(self, request, chat_history):
        if not request.collection_name:
            return chat_history["messages"]
        
        search_result = await self.vector_semantic_search(request)
        
        return self.generate_enhanced_messages_by_vector_search(
            search_result, 
            chat_history
        )
        
    async def handle_llm_stream(self, enhanced_messages, task, client_disconnected):
        buffer = ""
        llm_task = None
        
        try:
            llm_task = asyncio.create_task(
                self.llm_deepseek_steam_endpoint(
                    enhanced_messages,
                    stream=True,
                    timeout=30
                )
            )
            stream = await llm_task
            
            async for chunk in stream:
                if task.done() or client_disconnected[0]:
                    break
                    
                if not chunk.choices:
                    continue
                    
                content = chunk.choices[0].delta.content
                if content:
                    buffer += content
                    try:
                        data = await asyncio.to_thread(json.dumps, {"content": buffer})
                        yield f"data: {data}\n\n", buffer
                        buffer = ""
                    except Exception as e:
                        client_disconnected[0] = True
                        raise e

            if buffer:
                data = await asyncio.to_thread(json.dumps, {"content": buffer})
                yield f"data: {data}\n\n", buffer

        finally:
            if llm_task and not llm_task.done():
                llm_task.cancel()
                try:
                    await llm_task
                except asyncio.CancelledError:
                    pass
            
    def log_save_result(self, task, chat_history):
        try:
            task.result() 
            print(f"[Success] 保存成功: {chat_history['chat_session_id']}")
        except asyncio.CancelledError:
            print(f"[Error] 保存取消: {chat_history['chat_session_id']}")
        except Exception as e:
            print(f"[Error] 保存失敗: {str(e)}")
    
    async def chat_stream_endpoint(self, request):
        async def event_stream():
            chat_history = None
            full_response = ""
            client_disconnected = [False]

            try:
                client_disconnected[0] = False
                
                chat_history = await self.db.histories.find_one({"chat_session_id": request.chat_session_id})
                if not chat_history:
                    chat_history = self.generate_chat_history(request)
                else:
                    self.chat_history_append(chat_history, request.message, "user")

                try:
                    enhanced_messages = await self.prepare_conversation_context(
                        request, chat_history
                    )
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
                    yield "event: end\ndata: {}\n\n"
                    return

                async for data_chunk, content in self.handle_llm_stream(
                    enhanced_messages=enhanced_messages,
                    task=asyncio.current_task(),
                    client_disconnected=client_disconnected
                ):
                    full_response += content
                    yield data_chunk
                            
                yield "event: end\ndata: {}\n\n"
                
            except asyncio.CancelledError:
                print("Streaming request cancelled")
                client_disconnected[0] = True 
            
            except Exception as e:
                error_msg = str(e)
                self.chat_history_append(chat_history, f"系統錯誤: {error_msg}", "system")
                yield f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"

            finally:
                if chat_history:
                    self.chat_history_append(chat_history, full_response, "assistant")
                    save_task = asyncio.create_task(self.save_chat_history(chat_history))
                    save_task.add_done_callback(
                        partial(self.log_save_result, chat_history=chat_history)
                    )
                    
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        