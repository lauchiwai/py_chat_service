from common.models.request.chatRequest import ChatRequest
from services.vectorService import VectorService

class VectorHelper:
    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service

    async def semantic_search(self, request: ChatRequest):
        return await self.vector_service.vector_semantic_search(
            collection_name=request.collection_name,
            query_text=request.message,
            id=request.article_id
        )

    async def get_article_text(self, collection_name: str, article_id: int):
        return await self.vector_service.vector_article_all_text_query(
            collection_name=collection_name,
            id=article_id
        )