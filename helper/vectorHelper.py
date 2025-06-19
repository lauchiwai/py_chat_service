from models.request.chatRequest import ChatRequest
from services.vectorService import VectorService

class VectorHelper:
    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service

    async def semantic_search(self, request: ChatRequest):
        try:
            result = await self.vector_service.vector_semantic_search(
                collection_name=request.collection_name,
                query_text=request.message,
                id=request.article_id
            )
            
            if result is None:
                print("搜尋返回 None")
                return None
                
            if not hasattr(result, 'data'):
                print(f"結果缺少資料屬性: {type(result)}")
                return result
                
            if result.data is None:
                print("搜尋未返回資料")
            else:
                print(f"搜尋結果: {len(result.data)} 條")
            
            return result
            
        except Exception as e:
            print(f"語義搜尋失敗: {str(e)}")
            raise

    async def get_article_text(self, collection_name: str, article_id: int):
        try:
            result = await self.vector_service.vector_article_all_text_query(
                collection_name=collection_name,
                id=article_id
            )
            
            if hasattr(result, 'data'):
                print(f"取得文字片段: {len(result.data)} 個")
                if result.data:
                    print(f"首個片段: {result.data[0].text[:80]}{'...' if len(result.data[0].text) > 80 else ''}")
            else:
                print(f"意外結果格式: {type(result)}")
                
            return result
            
        except Exception as e:
            print(f"文章取得失敗: {str(e)}")
            raise
