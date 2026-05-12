"""
Multi-Path Retriever - 多路召回器

支持5路并行召回：语义、地理、协同过滤、类目和热门兜底
"""

import asyncio
from typing import Any

from smartroute.schemas.intent import IntentResult
from smartroute.schemas.profile import UserProfile
from smartroute.schemas.poi import POI


class MultiPathRetriever:
    """
    多路召回器
    
    并行执行5路召回策略
    """

    def __init__(
        self,
        semantic_top_k: int = 50,
        geo_top_k: int = 100,
        collab_top_k: int = 30,
        hot_top_k: int = 20,
    ) -> None:
        self.semantic_top_k = semantic_top_k
        self.geo_top_k = geo_top_k
        self.collab_top_k = collab_top_k
        self.hot_top_k = hot_top_k

    async def retrieve_multi_path(
        self,
        intent: IntentResult,
        profile: UserProfile | None = None,
    ) -> tuple[list[Any], dict[str, Any]]:
        """
        多路并行召回
        
        Args:
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            (候选POI列表, 召回元数据)
        """
        tasks = [
            self._semantic_retrieval(intent, profile),
            self._geo_retrieval(intent),
            self._collaborative_retrieval(intent, profile),
            self._category_retrieval(intent),
            self._hot_fallback_retrieval(intent),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        metadata = {"path_counts": {}}
        all_candidates = []
        seen_ids = set()

        for i, result in enumerate(results):
            path_name = ["semantic", "geo", "collaborative", "category", "hot"][i]

            if isinstance(result, Exception):
                metadata["path_counts"][path_name] = 0
                metadata[f"{path_name}_error"] = str(result)
                continue

            path_candidates = result if result else []
            metadata["path_counts"][path_name] = len(path_candidates)

            # 去重并合并
            for poi in path_candidates:
                poi_id = poi.get("poi_id", "") if isinstance(poi, dict) else poi.poi_id
                if poi_id not in seen_ids:
                    seen_ids.add(poi_id)
                    all_candidates.append(poi)

        return all_candidates, metadata

    async def _semantic_retrieval(
        self,
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> list[dict[str, Any]]:
        """
        语义召回
        
        Args:
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            POI列表
        """
        # TODO: 实际实现需要调用 Milvus 向量检索
        # 这里返回空列表，实际部署时需要实现
        query_text = self._build_query_text(intent, profile)
        # 模拟返回
        return []

    def _build_query_text(
        self,
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> str:
        """
        构建融合意图和画像的查询文本
        
        Args:
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            查询文本
        """
        parts = []

        # 意图主题
        if intent.preferences.themes:
            parts.extend(intent.preferences.themes)

        # 必须包含的类型
        if intent.preferences.must_have:
            parts.extend(intent.preferences.must_have)

        # 用户偏好场景
        if profile and profile.scene_preferences:
            top_scenes = sorted(
                profile.scene_preferences.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            parts.extend([s[0] for s in top_scenes])

        # 意图类型描述
        intent_desc = {
            "tour": "景点游览 文化体验",
            "food_tour": "美食探索 特色餐厅",
            "city_walk": "城市漫步 街区探索",
            "date": "浪漫约会 精致环境",
            "family": "亲子友好 家庭活动",
            "business": "商务出行 高效便捷",
        }
        parts.append(intent_desc.get(intent.intent_type.value, ""))

        return " ".join(filter(None, parts))

    async def _geo_retrieval(
        self,
        intent: IntentResult,
    ) -> list[dict[str, Any]]:
        """
        地理召回
        
        Args:
            intent: IntentResult
            
        Returns:
            POI列表
        """
        # TODO: 实际实现需要调用 PostGIS 空间查询
        # 这里返回空列表
        return []

    async def _collaborative_retrieval(
        self,
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> list[dict[str, Any]]:
        """
        协同过滤召回
        
        Args:
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            POI列表
        """
        # TODO: 实际实现需要调用协同过滤服务
        return []

    async def _category_retrieval(
        self,
        intent: IntentResult,
    ) -> list[dict[str, Any]]:
        """
        类目硬约束召回
        
        Args:
            intent: IntentResult
            
        Returns:
            POI列表
        """
        # TODO: 实际实现需要调用 Elasticsearch 倒排索引
        must_have = intent.preferences.must_have
        if not must_have:
            return []

        return []

    async def _hot_fallback_retrieval(
        self,
        intent: IntentResult,
    ) -> list[dict[str, Any]]:
        """
        热门兜底召回
        
        Args:
            intent: IntentResult
            
        Returns:
            POI列表
        """
        # TODO: 实际实现需要从 Redis 缓存获取热门POI列表
        city = intent.spatial.city
        return []
