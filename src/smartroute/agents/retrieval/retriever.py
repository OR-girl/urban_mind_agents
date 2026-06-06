"""
Multi-Path Retriever - 多路召回器

支持5路并行召回：语义、地理、协同过滤、类目和热门兜底
使用 Mock 数据实现基础召回功能
"""

import asyncio
import random
from typing import Any

from smartroute.schemas.intent import IntentResult
from smartroute.schemas.profile import UserProfile
from smartroute.schemas.poi import POI
from smartroute.mock.data import HANGZHOU_POIS, DISTANCE_MATRIX


class MultiPathRetriever:
    """
    多路召回器

    并行执行5路召回策略（使用 Mock 数据）
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
        # 随机种子保证可复现
        self._rng = random.Random(42)

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
        语义召回（Mock 实现）

        根据意图主题和用户偏好，模拟语义匹配返回相关 POI
        """
        query_text = self._build_query_text(intent, profile)

        # Mock 实现：根据关键词匹配 POI 的 tags
        candidates = []
        query_keywords = query_text.split()

        for poi in HANGZHOU_POIS:
            poi_tags = poi.get("tags", [])
            # 计算匹配度（简单的关键词匹配）
            match_score = sum(1 for kw in query_keywords if any(kw in tag for tag in poi_tags))

            if match_score > 0:
                poi_copy = poi.copy()
                poi_copy["semantic_similarity"] = match_score / max(len(query_keywords), 1)
                poi_copy["retrieval_path"] = "semantic"
                candidates.append(poi_copy)

        # 按匹配度排序，返回 top_k
        candidates.sort(key=lambda p: p.get("semantic_similarity", 0), reverse=True)
        return candidates[:self.semantic_top_k]

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
        地理召回（Mock 实现）

        返回指定城市内的 POI，按锚点距离排序
        """
        city = intent.spatial.city

        # Mock 实现：目前只有杭州数据
        if city and "杭州" not in city:
            # 其他城市暂无数据，返回空
            return []

        candidates = []
        anchor_poi = intent.spatial.anchor_poi

        for poi in HANGZHOU_POIS:
            poi_copy = poi.copy()
            poi_copy["retrieval_path"] = "geo"

            # 计算距离（如果有锚点）
            if anchor_poi:
                # 从距离矩阵获取距离
                anchor_id = self._find_poi_id_by_name(anchor_poi)
                if anchor_id and anchor_id in DISTANCE_MATRIX:
                    walk_minutes = DISTANCE_MATRIX[anchor_id].get(poi["poi_id"], 60)
                    poi_copy["distance_km"] = walk_minutes / 12  # 粗略换算：步行12分钟≈1km
                    poi_copy["walk_minutes"] = walk_minutes
                else:
                    # 没有锚点时，随机给一个距离
                    poi_copy["distance_km"] = self._rng.uniform(0.5, 10.0)
            else:
                # 无锚点时，以西湖为中心
                xihu_id = "poi_xihu_001"
                walk_minutes = DISTANCE_MATRIX[xihu_id].get(poi["poi_id"], 30)
                poi_copy["distance_km"] = walk_minutes / 12
                poi_copy["walk_minutes"] = walk_minutes

            # 半径过滤
            radius_km = intent.spatial.radius_km or 10.0
            if poi_copy.get("distance_km", 0) <= radius_km:
                candidates.append(poi_copy)

        # 按距离排序
        candidates.sort(key=lambda p: p.get("distance_km", 10))
        return candidates[:self.geo_top_k]

    def _find_poi_id_by_name(self, name: str) -> str | None:
        """根据名称查找 POI ID"""
        for poi in HANGZHOU_POIS:
            if poi["name"] == name or name in poi["name"]:
                return poi["poi_id"]
        return None

    async def _collaborative_retrieval(
        self,
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> list[dict[str, Any]]:
        """
        协同过滤召回（Mock 实现）

        模拟"相似用户也喜欢"的推荐
        """
        # Mock 实现：基于用户画像偏好选择 POI
        if not profile:
            return []

        candidates = []

        # 根据用户消费档位筛选
        spending_level = profile.spending_level
        avg_cost_range = {
            "budget": (0, 80),
            "mid": (50, 200),
            "premium": (100, 400),
            "luxury": (200, 1000),
        }
        cost_min, cost_max = avg_cost_range.get(spending_level, (0, 500))

        for poi in HANGZHOU_POIS:
            avg_cost = poi.get("avg_cost", 0)

            # 消费档位匹配
            if cost_min <= avg_cost <= cost_max:
                poi_copy = poi.copy()
                poi_copy["retrieval_path"] = "collaborative"
                poi_copy["collab_score"] = self._rng.uniform(0.5, 1.0)

                # 场景偏好匹配加分
                if profile.scene_preferences:
                    poi_tags = set(poi.get("tags", []))
                    match_score = sum(
                        weight for scene, weight in profile.scene_preferences.items()
                        if scene in poi_tags
                    )
                    poi_copy["collab_score"] += match_score

                candidates.append(poi_copy)

        # 按协同分数排序
        candidates.sort(key=lambda p: p.get("collab_score", 0), reverse=True)
        return candidates[:self.collab_top_k]

    async def _category_retrieval(
        self,
        intent: IntentResult,
    ) -> list[dict[str, Any]]:
        """
        类目硬约束召回（Mock 实现）

        根据用户指定的 must_have 精确匹配
        """
        must_have = intent.preferences.must_have
        if not must_have:
            return []

        candidates = []

        for poi in HANGZHOU_POIS:
            poi_category = poi.get("category", "")
            poi_tags = poi.get("tags", [])

            # 检查是否匹配 must_have
            matched = False
            for item in must_have:
                # 类目匹配（如"餐厅"、"景点"）
                if item in poi_category:
                    matched = True
                    break
                # 标签匹配（如"杭帮菜"、"亲子"）
                if any(item in tag for tag in poi_tags):
                    matched = True
                    break

            if matched:
                poi_copy = poi.copy()
                poi_copy["retrieval_path"] = "category"
                poi_copy["category_match"] = True
                candidates.append(poi_copy)

        # 按评分排序
        candidates.sort(key=lambda p: p.get("rating", 3.0), reverse=True)
        return candidates

    async def _hot_fallback_retrieval(
        self,
        intent: IntentResult,
    ) -> list[dict[str, Any]]:
        """
        热门兜底召回（Mock 实现）

        返回评分最高的热门 POI
        """
        city = intent.spatial.city

        # 目前只有杭州数据
        if city and "杭州" not in city:
            return []

        # 按评分和评论数排序
        sorted_pois = sorted(
            HANGZHOU_POIS,
            key=lambda p: (p.get("rating", 3.0), p.get("review_count", 0)),
            reverse=True,
        )

        candidates = []
        for poi in sorted_pois[:self.hot_top_k]:
            poi_copy = poi.copy()
            poi_copy["retrieval_path"] = "hot"
            poi_copy["hot_rank"] = len(candidates) + 1
            candidates.append(poi_copy)

        return candidates
