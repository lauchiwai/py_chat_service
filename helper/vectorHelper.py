from common.models.request.chatRequest import ChatRequest

class VectorHelper:
    def __init__(self, vector_service):
        self.vector_service = vector_service

    async def semantic_search(self, request: ChatRequest):
        return await self.vector_service.vector_semantic_search(
            collection_name=request.collection_name,
            query_text=request.message,
            article_id=request.article_id
        )

    async def get_article_text(self, collection_name: str, article_id: str):
        return await self.vector_service.vector_article_all_text_query(
            collection_name=collection_name,
            article_id=article_id
        )