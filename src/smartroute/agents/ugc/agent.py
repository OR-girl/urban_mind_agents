"""
UGC Insight Agent - 评论洞察Agent主类

双通道处理架构：LLM通道（高精度）和NLP通道（低成本）
"""

import asyncio
from typing import Any

from smartroute.agents.base import LLMBasedAgent, CacheableAgent
from smartroute.agents.ugc.llm_channel import get_llm_channel
from smartroute.agents.ugc.cache import get_ugc_cache_manager
from smartroute.core.logging import get_logger
from smartroute.schemas import SystemState

logger = get_logger("agent.ugc")


class UGCInsightAgent(LLMBasedAgent, CacheableAgent):
    """
    评论洞察Agent

    处理流程：
    1. 缓存检查（Redis，TTL 7天）
    2. 评论拉取（近3月）
    3. 路由判断（头部POI → LLM通道，长尾 → NLP通道）
    4. 结果融合与缓存
    """

    agent_name = "ugc_insight"

    def __init__(self) -> None:
        LLMBasedAgent.__init__(self)
        CacheableAgent.__init__(self)

        self.llm_channel = get_llm_channel()
        self.cache_manager = get_ugc_cache_manager()

        self.llm_threshold_reviews = self.get_config_value(
            "channel_router", {}
        ).get("llm_threshold_reviews", 100)
        self.llm_max_pois = self.get_config_value(
            "channel_router", {}
        ).get("llm_max_pois", 5)

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行UGC洞察分析

        Args:
            state: 系统状态

        Returns:
            包含 EnrichedPOI 列表的字典
        """
        candidates = state.candidates or []

        if not candidates:
            logger.warning("no_candidates_for_ugc")
            return {"enriched_pois": []}

        # 批量缓存检查
        cached_results, missed_poi_ids = await self.cache_manager.batch_get(
            [c.get("poi_id", "") for c in candidates]
        )

        logger.info(
            "ugc_cache_check",
            total=len(candidates),
            cached=len(cached_results),
            missed=len(missed_poi_ids),
        )

        # 处理未缓存的POI
        missed_pois = [
            c for c in candidates
            if c.get("poi_id", "") in missed_poi_ids
        ]

        # 路由判断：头部POI用LLM，长尾用NLP（简化版）
        llm_pois = self._route_by_channel(missed_pois)

        # 获取评论并分析
        reviews_map = {}
        for poi in llm_pois:
            poi_id = poi.get("poi_id", "")
            reviews_map[poi_id] = await self._fetch_reviews(poi)

        # LLM分析
        llm_results = await self.llm_channel.batch_analyze(
            pois=llm_pois[:self.llm_max_pois],
            reviews_map=reviews_map,
        )

        # 合合结果
        enriched_pois = []

        # 添加缓存结果
        for poi_id, cached_data in cached_results.items():
            enriched_pois.append(cached_data)

        # 添加新分析结果并缓存
        for poi_id, result in llm_results.items():
            enriched_pois.append(result)
            await self.cache_manager.set_cache(poi_id, result)

        return {"enriched_pois": enriched_pois}

    def _route_by_channel(
        self,
        pois: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        路由判断 - 简化版：全部通过LLM通道

        Args:
            pois: POI列表

        Returns:
            需要LLM分析的POI列表
        """
        llm_pois = []

        for poi in pois:
            review_count = poi.get("review_count", 0)

            # 头部POI用LLM，长尾暂时也用LLM（简化）
            if review_count >= self.llm_threshold_reviews:
                llm_pois.append(poi)
            elif review_count >= 20:  # 有足够评论也用LLM
                llm_pois.append(poi)

        return llm_pois

    async def _fetch_reviews(self, poi: dict[str, Any]) -> list[dict[str, Any]]:
        """
        获取POI评论

        Args:
            poi: POI字典

        Returns:
            评论列表
        """
        # TODO: 实际实现需要调用大众点评API
        poi_id = poi.get("poi_id", "")
        return []

    def _merge_analysis_result(
        self,
        poi: dict[str, Any],
        analysis: dict[str, Any],
        channel: str,
    ) -> dict[str, Any]:
        """
        合合分析结果

        Args:
            poi: POI字典
            analysis: 分析结果
            channel: 分析通道

        Returns:
            EnrichedPOI字典
        """
        return {
            "poi_id": poi.get("poi_id", ""),
            "name": poi.get("name", ""),
            "category": poi.get("category", ""),
            "location": poi.get("location", {}),
            "avg_cost": poi.get("avg_cost", 0),
            "rating": poi.get("rating", 0),
            "highlights": analysis.get("highlights", []),
            "warnings": analysis.get("warnings", []),
            "best_time": analysis.get("best_time", ""),
            "ugc_sentiment": analysis.get("ugc_sentiment", {}),
            "scene_tags": analysis.get("scene_tags", []),
            "queue_warning": analysis.get("queue_warning", ""),
            "analysis_channel": channel,
            "confidence": analysis.get("confidence", 0.8),
        }