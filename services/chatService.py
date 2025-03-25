from datetime import datetime
from services.vectorService import VectorService
from common.core.llm_init import deepseek
from common.models.dto.resultdto import ResultDTO
from common.core.llm_init.modal_config import ChatRequest
from common.models.dto.request import VectorSearchRequest
class ChatService:
    def __init__(self, db, vector_service: VectorService):
        self.db = db
        self.vector_service = vector_service

    async def get_chat_history_by_session_id(self, chat_session_id: str):
        try:
            chat_history = await self.db.chat_histories.find_one({"chat_session_id": chat_session_id})
            if not chat_history:
                return ResultDTO.fail(code=404, message="chat history from session_id is not found")

            return ResultDTO.ok(data={
                "response": chat_history["messages"],
                "chat_session_id": chat_history["chat_session_id"]
            })
            
        except Exception as e:
            return ResultDTO.fail(code=500, message=str(e))
        
    async def chat_endpoint(self, request: ChatRequest):
        try:
            chat_history = await self.db.chat_histories.find_one({"chat_session_id": request.chat_session_id})
            # check chat history exist
            if not chat_history:
                chat_history = {
                    "chat_session_id": request.chat_session_id,
                    "user_id": request.user_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": request.system_prompt,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        },
                        {
                            "role": "user",
                            "content": request.message,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    ],
                    "metadata": {
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens
                    }
                }
            else:
                chat_history["messages"].append({
                    "role": "user",
                    "content": request.message,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
            enhanced_messages = chat_history["messages"]
            
            if request.collection_name is not None:
                search_result = self.vector_service.vector_semantic_search(
                    VectorSearchRequest(
                        collection_name=request.collection_name,
                        query_text=request.message,
                        limit=3
                    )
                )
                if search_result.code != 200:
                    return ResultDTO.fail(code=search_result.code, message=search_result.message)
                 
                context_str = "\n".join(
                    [f"[相關資料 {i+1}] {item.text}" for i, item in enumerate(search_result.data)]
                )
                
                enhanced_messages = [
                    {
                        "role": "system",
                        "content": f"請基於以下上下文回答使用者的問題：\n{context_str}\n若上下文與問題無關，請根據自身知識回答。"
                    },
                    *chat_history["messages"] 
                ]

            response = deepseek.client.chat.completions.create(
                model="deepseek-chat",
                messages=enhanced_messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=False
            )

            assistant_msg = response.choices[0].message.content

            chat_history["messages"].append({
                "role": "assistant",
                "content": assistant_msg,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            if chat_history.get("_id"):  
                await self.db.histories.replace_one({"_id": chat_history["_id"]}, chat_history)
            else:  
                await self.db.histories.insert_one(chat_history)

            return ResultDTO.ok(data={
                "response": assistant_msg,
                "chat_session_id": request.chat_session_id
            })

        except Exception as e:
            return ResultDTO.fail(code=500, message=str(e))
