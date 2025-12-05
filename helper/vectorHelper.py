from models.request.chatRequest import ChatRequest
from services.vectorService import VectorService
from helper.hybridSearchHelper import HybridSearchHelper
from typing import Optional

class VectorHelper:
    def __init__(self, vector_service: VectorService):
        self.vector_service = vector_service
        self.hybrid_helper = HybridSearchHelper(vector_service)
        self.search_mode = "hybrid"  
    
    async def semantic_search(self, request: ChatRequest):
        try:
            # 根據模式選擇搜尋方法 vector (default)
            if self.search_mode == "hybrid":
                result = await self.hybrid_search(request)
            elif self.search_mode == "keyword":
                result = await self.keyword_search(request)
            else:
                result = await self.vector_search(request)
            
            return result
            
        except Exception as e:
            print(f"語義搜尋失敗: {str(e)}")
            raise
    
    async def vector_search(self, request: ChatRequest):
        """純向量搜尋"""
        try:
            result = await self.vector_service.vector_semantic_search(
                collection_name=request.collection_name,
                query_text=request.message,
                id=request.article_id
            )
            
            self._log_search_result(result, "向量搜尋")
            return result
            
        except Exception as e:
            print(f"向量搜尋失敗: {str(e)}")
            raise
    
    async def keyword_search(self, request: ChatRequest):
        """純關鍵字搜尋"""
        try:
            result = await self.hybrid_helper._keyword_search(
                collection_name=request.collection_name,
                query_text=request.message,
                article_id=request.article_id
            )
            
            self._log_search_result(result, "關鍵字搜尋")
            return result
            
        except Exception as e:
            print(f"關鍵字搜尋失敗: {str(e)}")
            raise
    
    async def hybrid_search(self, request: ChatRequest):
        """混合搜尋"""
        try:
            result = await self.hybrid_helper.hybrid_search(
                collection_name=request.collection_name,
                query_text=request.message,
                article_id=request.article_id,
                alpha=0.7,  # 向量搜尋權重
                use_keyword_search=True,
                keyword_weight=0.3  # 關鍵字搜尋權重
            )
            
            self._log_search_result(result, "混合搜尋")
            return result
            
        except Exception as e:
            print(f"混合搜尋失敗: {str(e)}")
            raise
    
    async def hybrid_search_with_rerank(self, request: ChatRequest):
        """混合搜尋 + 重新排序"""
        try:
            result = await self.hybrid_helper.hybrid_search_with_rerank(
                collection_name=request.collection_name,
                query_text=request.message,
                article_id=request.article_id,
                use_rerank=True,
                rerank_threshold=0.3
            )
            
            self._log_search_result(result, "混合搜尋(重新排序)")
            return result
            
        except Exception as e:
            print(f"混合搜尋(重新排序)失敗: {str(e)}")
            raise
    
    def _log_search_result(self, result, search_type: str):
        """記錄搜尋結果"""
        if result is None:
            print(f"{search_type}返回 None")
            return
            
        if not hasattr(result, 'data'):
            print(f"{search_type}結果缺少資料屬性: {type(result)}")
            return
            
        if result.data is None:
            print(f"{search_type}未返回資料")
        else:
            print(f"{search_type}結果: {len(result.data)} 條")
            
            # 顯示前幾個結果的分數
            for i, item in enumerate(result.data[:3]):
                if hasattr(item, 'score'):
                    print(f"  結果 {i+1}: 分數={item.score:.4f}")
    
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
    
    def set_search_mode(self, mode: str):
        """設定搜尋模式"""
        valid_modes = ["vector", "keyword", "hybrid"]
        if mode in valid_modes:
            self.search_mode = mode
            print(f"搜尋模式已設定為: {mode}")
        else:
            print(f"無效的搜尋模式: {mode}，請使用 {valid_modes}")