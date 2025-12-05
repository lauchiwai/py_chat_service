from typing import List
from models.dto.resultdto import ResultDTO
from models.response.vectorResponse import VectorSearchResult
from core.qdrant_client_init import qdrant_client  
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
from qdrant_client.http import models as qdrant_models

class HybridSearchHelper:
    def __init__(self, vector_service):
        self.vector_service = vector_service
        self.HARDCODE_LIMIT = 5
        self.HARDCODE_MIN_SCORE = 0.2
        self.VECTOR_DIM = 768
      
    async def hybrid_search(
        self,
        collection_name: str,
        query_text: str,
        article_id: int,
        alpha: float = 0.7,
        use_keyword_search: bool = True,
        keyword_weight: float = 0.3
    ) -> ResultDTO[List[VectorSearchResult]]:
        """
        混合搜尋：結合向量搜尋和關鍵字搜尋
        """
        try:
            # 1. 執行向量搜尋
            vector_results = await self._vector_search(
                collection_name, query_text, article_id
            )
          
            # 2. 執行關鍵字搜尋 
            keyword_results = None
            if use_keyword_search:
                keyword_results = await self._keyword_search(
                    collection_name, query_text, article_id
                )
          
            # 3. 合併結果
            final_results = await self._merge_results(
                vector_results=vector_results.data if vector_results and vector_results.data else [],
                keyword_results=keyword_results.data if keyword_results and keyword_results.data else [],
                alpha=alpha,
                keyword_weight=keyword_weight
            )
          
            return ResultDTO.ok(data=final_results)
          
        except Exception as e:
            print(f"混合搜尋失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))
  
    async def _vector_search(
        self,
        collection_name: str,
        query_text: str,
        article_id: int
    ) -> ResultDTO[List[VectorSearchResult]]:
        """純向量搜尋"""
        try:
            # 檢查集合是否存在
            if error := await self.vector_service.check_collection_exists(collection_name):
                print(f"[ERROR] 集合檢查失敗: {error}")
                return error
          
            # 使用 VectorService 的方法構建搜索過濾條件
            search_filter = self.vector_service.build_search_filter(article_id)
            print(f"[DEBUG] 搜索過濾條件: {search_filter}")
          
            # 使用 VectorService 的方法擴展查詢
            expanded_query = self.vector_service.expand_query(query_text)
            print(f"[DEBUG] 擴展後的查詢: '{expanded_query}'")
          
            # 使用 VectorService 的方法增強編碼
            query_vector = await self.vector_service.enhance_encoding(expanded_query)
            print(f"[DEBUG] 查詢向量維度: {len(query_vector)}")
          
            # 直接使用 qdrant_client 執行搜索
            print(f"[DEBUG] 執行 Qdrant 搜索: 集合={collection_name}, 限制={self.HARDCODE_LIMIT*3}, 分數閾值={self.HARDCODE_MIN_SCORE}")
            hits = await qdrant_client.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=self.HARDCODE_LIMIT * 3,  # 取更多結果用於混合
                score_threshold=self.HARDCODE_MIN_SCORE
            )
          
            print(f"[DEBUG] 搜索完成，找到 {len(hits)} 個結果")
          
            results = []
            for hit in hits:
                if hit.score < self.HARDCODE_MIN_SCORE:
                    continue
                if result := self.vector_service.process_record(hit):
                    results.append(result)
          
            return ResultDTO.ok(data=results)
          
        except Exception as e:
            print(f"向量搜尋失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))
  
    async def _keyword_search(
        self,
        collection_name: str,
        query_text: str,
        article_id: int
    ) -> ResultDTO[List[VectorSearchResult]]:
        """關鍵字搜尋"""
        try:
            # 檢查集合是否存在
            if error := await self.vector_service.check_collection_exists(collection_name):
                print(f"[ERROR] 集合檢查失敗: {error}")
                return error
          
            # 建立關鍵字搜尋過濾條件
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="id",
                        match=MatchValue(value=article_id)
                    ),
                    FieldCondition(
                        key="text",
                        match=MatchText(text=query_text)
                    )
                ]
            )
          
            # 使用 qdrant_client 執行 scroll
            all_records = []
            next_offset = None
          
            while True:
                response = await qdrant_client.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=search_filter,
                    limit=100,
                    offset=next_offset,
                    with_payload=True
                )
              
                records, next_offset = response
                if not records:
                    break
                  
                all_records.extend(records)
                if next_offset is None:
                    break
          
            # 計算關鍵字相關性分數
            results = []
            for record in all_records:
                text = record.payload.get("text", "")
                if not text.strip():
                    continue
              
                # 計算關鍵字匹配分數
                score = self._calculate_keyword_score(query_text, text)
                if score > 0.1:  # 設定關鍵字分數閾值
                    formatted = self.vector_service.format_result_text(
                        point_id=record.id,
                        original_text=text
                    )
                    results.append(VectorSearchResult(
                        text=formatted,
                        score=score
                    ))
          
            return ResultDTO.ok(data=results)
          
        except Exception as e:
            print(f"關鍵字搜尋失敗: {str(e)}")
            return ResultDTO.fail(code=500, message=str(e))
  
    def _calculate_keyword_score(self, query: str, text: str) -> float:
        """計算關鍵字匹配分數"""
        query_terms = set(query.lower().split())
        text_terms = set(text.lower().split())
      
        if not query_terms:
            return 0.0
      
        # 計算 Jaccard 相似度
        intersection = query_terms.intersection(text_terms)
        union = query_terms.union(text_terms)
      
        jaccard_sim = len(intersection) / len(union) if union else 0.0
      
        # 計算詞頻分數
        tf_score = 0.0
        text_words = text.lower().split()
        total_words = len(text_words)
      
        if total_words > 0:
            for term in query_terms:
                term_count = text_words.count(term)
                tf_score += term_count / total_words
      
        # 綜合分數
        final_score = (jaccard_sim * 0.6) + (tf_score * 0.4)
        return min(final_score, 1.0)
  
    async def _merge_results(
        self,
        vector_results: List[VectorSearchResult],
        keyword_results: List[VectorSearchResult],
        alpha: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[VectorSearchResult]:
        """合併向量和關鍵字搜尋結果"""
      
        # 建立點 ID 到結果的映射
        vector_dict = {self._extract_point_id(r.text): (r, 'vector') for r in vector_results}
        keyword_dict = {self._extract_point_id(r.text): (r, 'keyword') for r in keyword_results}
      
        # 收集所有唯一的點 ID
        all_point_ids = set(vector_dict.keys()) | set(keyword_dict.keys())
      
        merged_results = []
      
        for point_id in all_point_ids:
            vector_item = vector_dict.get(point_id)
            keyword_item = keyword_dict.get(point_id)
          
            if vector_item and keyword_item:
                # 兩邊都有：混合分數
                vector_score = vector_item[0].score
                keyword_score = keyword_item[0].score
              
                # 使用加權平均
                final_score = (alpha * vector_score) + (keyword_weight * keyword_score)
                final_text = vector_item[0].text  # 使用向量搜尋的格式化文本
              
                merged_results.append(VectorSearchResult(
                    text=final_text,
                    score=final_score
                ))
              
            elif vector_item:
                # 只有向量搜尋有
                merged_results.append(VectorSearchResult(
                    text=vector_item[0].text,
                    score=vector_item[0].score * alpha  # 降低分數
                ))
              
            elif keyword_item:
                # 只有關鍵字搜尋有
                merged_results.append(VectorSearchResult(
                    text=keyword_item[0].text,
                    score=keyword_item[0].score * keyword_weight  # 降低分數
                ))
      
        # 按分數降序排序
        merged_results.sort(key=lambda x: x.score, reverse=True)
      
        # 限制返回數量
        return merged_results[:self.HARDCODE_LIMIT]
  
    def _extract_point_id(self, formatted_text: str) -> int:
        """從格式化文本中提取點 ID"""
        try:
            # 格式: [相關資料 {point_id}] 文本內容
            if formatted_text.startswith("[相關資料 "):
                start = formatted_text.find("[相關資料 ") + 6
                end = formatted_text.find("]", start)
                point_id_str = formatted_text[start:end].strip()
                return int(point_id_str)
        except:
            pass
        return 0
  
    async def hybrid_search_with_rerank(
        self,
        collection_name: str,
        query_text: str,
        article_id: int,
        use_rerank: bool = True,
        rerank_threshold: float = 0.5
    ) -> ResultDTO[List[VectorSearchResult]]:
        """
        混合搜尋 + 重新排序
        """
        # 執行基本混合搜尋
        hybrid_result = await self.hybrid_search(
            collection_name=collection_name,
            query_text=query_text,
            article_id=article_id,
            alpha=0.7,
            use_keyword_search=True,
            keyword_weight=0.3
        )
      
        if not hybrid_result.data or not use_rerank:
            return hybrid_result
      
        # 重新排序邏輯
        reranked_results = await self._rerank_results(
            query_text=query_text,
            results=hybrid_result.data,
            threshold=rerank_threshold
        )
      
        return ResultDTO.ok(data=reranked_results)
  
    async def _rerank_results(
        self,
        query_text: str,
        results: List[VectorSearchResult],
        threshold: float = 0.5
    ) -> List[VectorSearchResult]:
        """重新排序結果基於更複雜的相關性計算"""
        if not results:
            return []
      
        reranked = []
        for result in results:
            # 提取原始文本
            original_text = self._extract_original_text(result.text)
          
            # 計算額外的相關性分數
            semantic_score = result.score
            length_score = self._calculate_length_score(original_text)
            position_score = self._calculate_position_score(original_text)
          
            # 綜合分數
            final_score = (
                semantic_score * 0.6 +
                length_score * 0.2 +
                position_score * 0.2
            )
          
            if final_score >= threshold:
                reranked.append(VectorSearchResult(
                    text=result.text,
                    score=final_score
                ))
      
        # 重新排序
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked
  
    def _extract_original_text(self, formatted_text: str) -> str:
        """從格式化文本中提取原始文本"""
        try:
            # 移除 "[相關資料 X] " 前綴
            if "] " in formatted_text:
                return formatted_text.split("] ", 1)[1]
        except:
            pass
        return formatted_text
  
    def _calculate_length_score(self, text: str) -> float:
        """計算文本長度分數（中等長度最佳）"""
        length = len(text)
        # 理想長度範圍：100-500字元
        if 100 <= length <= 500:
            return 1.0
        elif length < 100:
            return length / 100
        else:
            return max(0, 1 - (length - 500) / 1000)
  
    def _calculate_position_score(self, text: str) -> float:
        """計算文本位置分數"""
        return 0.5  # 預設值