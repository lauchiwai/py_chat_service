from datetime import datetime
from services.vectorService import VectorService
from fastapi.responses import StreamingResponse
from functools import partial
from typing import Optional, Union

from common.core.llm_init.prompt import PromptTemplates
from common.core.llm_init import deepseek
from common.models.dto.resultdto import ResultDTO
from common.core.llm_init.modal_config import ChatRequest, SummaryRequest

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
        
    def get_current_timestamp(self) -> str:
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

    async def get_or_create_chat_history(self, request: Union[ChatRequest, SummaryRequest]) -> dict:
        chat_history = await self.db.histories.find_one(
            {"chat_session_id": request.chat_session_id}
        )
        if not chat_history:
            message = request.message if isinstance(request, ChatRequest) else None
            return self.generate_chat_history(
                request.chat_session_id,
                request.user_id,
                message
            )
            
        return chat_history

    def chat_history_append(self, chat_history: dict, content: str, role: str):
        chat_history["messages"].append(self.create_message(role, content))

    async def async_save_chat_history(self, chat_history: dict):
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

    async def vector_semantic_search(self, request: ChatRequest):
        return await self.vector_service.vector_semantic_search(
            collection_name=request.collection_name,
            query_text=request.message,
            article_id=request.article_id
        )

    def generate_enhanced_messages(self, search_result, chat_history: dict):
        context_str = "\n".join([item.text for item in search_result.data])
        system_prompt = self.prompt_templates.rag_analyst(context_str)
        filtered_messages = [msg for msg in chat_history["messages"] if msg["role"] != "system"]
        return [self.create_message("system", system_prompt), *filtered_messages]

    async def llm_deepseek_stream(self, enhanced_messages: list, stream: bool = True, timeout: int = 30):
        try:
            return await asyncio.wait_for(
                deepseek.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=enhanced_messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=stream
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print("LLM request timeout")
            raise
        except Exception as e:
            print(f"LLM API error: {str(e)}")
            raise

    async def handle_llm_stream(self, enhanced_messages: list, task, client_disconnected: list):
        buffer = ""
        llm_task = None
        
        try:
            llm_task = asyncio.create_task(
                self.llm_deepseek_stream(enhanced_messages, stream=True)
            )
            stream = await llm_task
            
            async for chunk in stream:
                if task.done() or client_disconnected[0]:
                    break
                    
                if content := getattr(chunk.choices[0].delta, 'content', None):
                    buffer += content
                    try:
                        yield await self.generate_event_data(buffer), buffer
                        buffer = ""
                    except Exception as e:
                        client_disconnected[0] = True
                        raise e

            if buffer:
                yield await self.generate_event_data(buffer), buffer

        finally:
            if llm_task and not llm_task.done():
                llm_task.cancel()
                try:
                    await llm_task
                except asyncio.CancelledError:
                    pass

    async def generate_event_data(self, content: str) -> str:
        data = await asyncio.to_thread(json.dumps, {"content": content})
        return f"data: {data}\n\n"

    def generate_error_event(self, error_msg: str) -> str:
        return f"event: error\ndata: {json.dumps({'message': error_msg})}\n\n"

    def create_streaming_response(self, event_stream):
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    async def prepare_enhanced_messages(self, request, chat_history: dict):
        if not request.collection_name:
            return chat_history["messages"]
        
        search_result = await self.vector_semantic_search(request)
        return self.generate_enhanced_messages(search_result, chat_history)

    async def finalize_chat_history(self, chat_history: dict, full_response: str):
        self.chat_history_append(chat_history, full_response, "assistant")
        save_task = asyncio.create_task(self.async_save_chat_history(chat_history))
        save_task.add_done_callback(
            partial(self.log_save_result, chat_history=chat_history)
        )

    async def chat_stream_endpoint(self, request: ChatRequest):
        async def event_stream():
            full_response = ""
            client_disconnected = [False]

            try:
                chat_history = await self.get_or_create_chat_history(request)
                if (request.message):
                    self.chat_history_append(chat_history, request.message, "user")
                enhanced_messages = await self.prepare_enhanced_messages(request, chat_history)
                
                async for data_chunk, content in self.handle_llm_stream(
                    enhanced_messages=enhanced_messages,
                    task=asyncio.current_task(),
                    client_disconnected=client_disconnected
                ):
                    full_response += content
                    yield data_chunk
                
                yield "event: end\ndata: {}\n\n"

            except Exception as e:
                error_msg = str(e)
                yield self.generate_error_event(error_msg)
                self.chat_history_append(chat_history, f"系統錯誤: {error_msg}", "system")

            finally:
                if chat_history:
                    await self.finalize_chat_history(chat_history, full_response)

        return self.create_streaming_response(event_stream())

    async def summary_stream_endpoint(self, request: SummaryRequest):
        async def event_stream():
            full_response = ""
            client_disconnected = [False]

            try:
                chat_history = await self.get_or_create_chat_history(request)
                if request.collection_name:
                    article_all_text = await self.vector_service.vector_article_all_text_query(
                        collection_name=request.collection_name,
                        article_id=request.article_id
                    )
                    enhanced_messages = self.generate_enhanced_messages(article_all_text, chat_history)
                else:
                    enhanced_messages = chat_history["messages"]

                async for data_chunk, content in self.handle_llm_stream(
                    enhanced_messages=enhanced_messages,
                    task=asyncio.current_task(),
                    client_disconnected=client_disconnected
                ):
                    full_response += content
                    yield data_chunk
                
                yield "event: end\ndata: {}\n\n"

            except Exception as e:
                error_msg = str(e)
                yield self.generate_error_event(error_msg)
                
            finally:
                if chat_history:
                    await self.finalize_chat_history(chat_history, full_response)

        return self.create_streaming_response(event_stream())
        