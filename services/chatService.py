from helper.chatHistoryHelper import ChatHistoryHelper
from helper.llmStreamHelper import LLMStreamHelper
from helper.vectorHelper import VectorHelper
from services.vectorService import VectorService
from typing import Optional

from core.llm_init.prompt import PromptTemplates
from models.dto.resultdto import ResultDTO
from models.request.chatRequest import ChatRequest, SummaryRequest
import asyncio

class ChatService:
    def __init__(self, db, vector_service: VectorService):
        self.db = db
        self.vector_service = vector_service
        self.temperature: Optional[float] = 0.7
        self.max_tokens: Optional[int] = 3000
        self.prompt_templates = PromptTemplates()
        
        self.history_helper = ChatHistoryHelper(
            db=db,
            prompt_templates=self.prompt_templates,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        self.vector_helper = VectorHelper(vector_service)
        self.vector_helper.set_search_mode("hybrid")
        self.llm_stream_helper = LLMStreamHelper(
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

    async def get_chat_history_by_session_id(self, chat_session_id: int):
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
            return ResultDTO.fail(code=500, message=str(e))
        
    async def delete_chat_history_by_session_id(self, chat_session_id: int):
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
            return ResultDTO.fail(code=500, message=str(e))

    async def chat_stream_endpoint(self, request: ChatRequest):
        async def event_stream():
            full_response = ""
            client_disconnected = [False]
            chat_history = None

            try:
                chat_history = await self.history_helper.get_or_create(request)

                if request.message:
                    self.history_helper.append_message(chat_history, request.message, "user")
                
                if not request.collection_name:
                    enhanced_messages = chat_history["messages"]
                else:
                    # 使用混合搜尋
                    search_result = await self.vector_helper.hybrid_search_with_rerank(request)
                    enhanced_messages = self.llm_stream_helper.generate_enhanced_messages(
                        search_result, 
                        chat_history, 
                        self.prompt_templates.rag_analyst
                    )
                
                async for data_chunk, content in self.llm_stream_helper.handle_stream_response(
                    enhanced_messages=enhanced_messages,
                    task=asyncio.current_task(),
                    client_disconnected=client_disconnected
                ):
                    full_response += content
                    yield data_chunk
                
                yield "event: end\ndata: {}\n\n"

            except Exception as e:
                error_msg = str(e)
                yield self.llm_stream_helper.generate_error_event(error_msg)

            finally:
                if chat_history:
                    await self.history_helper.finalize(chat_history, full_response)

        return self.llm_stream_helper.create_streaming_response(event_stream())
    
    async def summary_stream_endpoint(self, request: SummaryRequest):
        async def event_stream():
            full_response = ""
            client_disconnected = [False]
            chat_history = None

            try:
                chat_history = await self.history_helper.get_or_create(request)
                
                article_all_text = await self.vector_helper.get_article_text(
                    request.collection_name,
                    request.article_id
                )

                context_str = "\n".join([item.text for item in article_all_text.data])
                system_prompt = self.prompt_templates.summary_engineer()
                enhanced_messages = [
                    {"role": "system", "content": context_str.strip()},
                    {"role": "system", "content": system_prompt.strip()}
                ]
                
                async for data_chunk, content in self.llm_stream_helper.handle_stream_response(
                    enhanced_messages=enhanced_messages,
                    task=asyncio.current_task(),
                    client_disconnected=client_disconnected
                ):
                    full_response += content
                    yield data_chunk
                
                yield "event: end\ndata: {}\n\n"

            except Exception as e:
                error_msg = str(e)
                yield self.llm_stream_helper.generate_error_event(error_msg)
                
            finally:
                if chat_history:
                    await self.history_helper.finalize(chat_history, full_response)

        return self.llm_stream_helper.create_streaming_response(event_stream())