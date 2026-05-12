"""
Retrieval Agent - POI召回Agent主类

多路召回候选POI，包括语义召回、地理召回、协同过滤、类目召回和热门兜底
"""

from typing import Any

from smartroute.agents.base import VectorBasedAgent, CacheableAgent
from smartroute.agents.retrieval.retriever import MultiPathRetriever
from smartroute.agents.retrieval.ranker import CoarseRanker, DiversityReranker
from smartroute.schemas import SystemState


class RetrievalAgent(VectorBasedAgent, CacheableAgent):
    """
    POI召回Agent
    
    处理流程：
    1. 多路并行召回（5路）
    2. 召回融合与去重
    3. 粗排（LightGBM打分）
    4. 硬过滤（营业时间/饮食禁忌）
    5. MMR多样性重排
    """

    agent_name = "retrieval"

    def __init__(self) -> None:
        # 需要先初始化父类
        VectorBasedAgent.__init__(self)
        CacheableAgent.__init__(self)

        self.retriever = MultiPathRetriever(
            semantic_top_k=self.get_config_value("semantic", {}).get("top_k", 50),
            geo_top_k=100,
            collab_top_k=self.get_config_value("collaborative", {}).get("top_k", 30),
            hot_top_k=self.get_config_value("hot_fallback", {}).get("top_k", 20),
        )
        self.ranker = CoarseRanker(
            model_path=self.get_config_value("coarse_rank", {}).get("model_path", ""),
        )
        self.diversity_reranker = DiversityReranker(
            lambda_param=self.get_config_value("mmr", {}).get("lambda_param", 0.6),
            top_k=self.get_config_value("mmr", {}).get("candidate_pool_size", 20),
        )

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行POI召回
        
        Args:
            state: 系统状态
            
        Returns:
            包含候选POI列表的字典
        """
        intent = state.get_intent()
        profile = state.get_profile()

        if not intent:
            self.logger.warning("intent_missing_for_retrieval")
            return {"candidates": [], "retrieval_metadata": {"error": "no_intent"}}

        # 多路并行召回
        candidates, metadata = await self.retriever.retrieve_multi_path(
            intent=intent,
            profile=profile,
        )

        self.logger.info(
            "multi_path_retrieval_completed",
            total_candidates=len(candidates),
            paths=metadata.get("path_counts", {}),
        )

        if not candidates:
            self.logger.warning("no_candidates_retrieved")
            return {"candidates": [], "retrieval_metadata": metadata}

        # 粗排
        ranked_candidates = await self.ranker.rank(
            candidates=candidates,
            intent=intent,
            profile=profile,
        )

        # 硬过滤
        filtered_candidates = await self._apply_hard_filters(
            ranked_candidates,
            intent,
            profile,
        )

        # MMR多样性重排
        final_candidates = self.diversity_reranker.rerank(filtered_candidates)

        metadata["final_count"] = len(final_candidates)
        metadata["filtered_count"] = len(filtered_candidates)

        return {
            "candidates": [c.model_dump() if hasattr(c, "model_dump") else c for c in final_candidates],
            "retrieval_metadata": metadata,
        }

    async def _apply_hard_filters(
        self,
        candidates: list[Any],
        intent: Any,
        profile: Any,
    ) -> list[Any]:
        """
        应用硬过滤
        
        Args:
            candidates: 候选POI列表
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            过滤后的候选列表
        """
        filtered = []

        for poi in candidates:
            poi_dict = poi.model_dump() if hasattr(poi, "model_dump") else poi

            # 营业时间过滤（简化版，实际需要更精确的校验）
            # TODO: 实际实现需要解析营业时间并与出行时段对比

            # 饮食禁忌过滤
            if profile and profile.dietary_restrictions:
                poi_tags = poi_dict.get("tags", [])
                for restriction in profile.dietary_restrictions:
                    if restriction in str(poi_tags):
                        continue  # 跳过不符合饮食禁忌的POI

            # 已去过的POI过滤（可选）
            if profile and profile.visited_poi_ids:
                poi_id = poi_dict.get("poi_id", "")
                if poi_id in profile.visited_poi_ids:
                    continue  # 跳过已去过的POI

            filtered.append(poi)

        return filtered
