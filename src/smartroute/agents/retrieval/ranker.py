"""
Coarse Ranker and Diversity Reranker

粗排模型（LightGBM）和MMR多样性重排器
"""

import numpy as np
import lightgbm as lgb
from typing import Any

from smartroute.schemas.intent import IntentResult
from smartroute.schemas.profile import UserProfile


class CoarseRanker:
    """
    粗排模型
    
    使用 LightGBM 对候选POI进行打分
    """

    def __init__(self, model_path: str = "") -> None:
        self.model = None
        if model_path:
            try:
                self.model = lgb.Booster(model_file=model_path)
            except Exception:
                # 模型文件不存在时使用默认打分
                pass

        # 默认权重
        self.weights = {
            "semantic": 0.35,
            "profile_match": 0.30,
            "popularity": 0.20,
            "distance": 0.15,
        }

    async def rank(
        self,
        candidates: list[Any],
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> list[Any]:
        """
        粗排打分
        
        Args:
            candidates: 候选POI列表
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            打分排序后的候选列表
        """
        if not candidates:
            return []

        # 提取特征并打分
        for poi in candidates:
            poi_dict = poi if isinstance(poi, dict) else poi.model_dump()
            score = self._compute_score(poi_dict, intent, profile)

            if isinstance(poi, dict):
                poi["coarse_rank_score"] = score
            else:
                poi.coarse_rank_score = score

        # 按分数排序
        return sorted(
            candidates,
            key=lambda x: x.get("coarse_rank_score", 0) if isinstance(x, dict) else getattr(x, "coarse_rank_score", 0),
            reverse=True,
        )

    def _compute_score(
        self,
        poi: dict[str, Any],
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> float:
        """
        计算综合得分
        
        Args:
            poi: POI字典
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            得分
        """
        if self.model:
            features = self._extract_features(poi, intent, profile)
            return float(self.model.predict([features])[0])

        # 无模型时使用加权打分
        semantic_sim = poi.get("semantic_similarity", 0.5)
        distance_km = poi.get("distance_km", 5.0)
        rating = poi.get("rating", 3.0)
        review_count = poi.get("review_count", 0)

        # 距离归一化（越小越好）
        distance_score = 1.0 / (1.0 + distance_km)

        # 热度归一化
        popularity_score = np.log1p(review_count) / 10.0

        # 画像匹配度
        profile_match = self._compute_profile_match(poi, profile)

        # 预算匹配度
        budget_match = self._compute_budget_match(poi, intent)

        # 综合得分
        score = (
            self.weights["semantic"] * semantic_sim
            + self.weights["profile_match"] * profile_match
            + self.weights["popularity"] * popularity_score
            + self.weights["distance"] * distance_score
            + 0.1 * budget_match  # 预算作为额外因子
        )

        return min(1.0, max(0.0, score))

    def _extract_features(
        self,
        poi: dict[str, Any],
        intent: IntentResult,
        profile: UserProfile | None,
    ) -> list[float]:
        """
        提取特征向量
        
        Args:
            poi: POI字典
            intent: IntentResult
            profile: UserProfile
            
        Returns:
            特征列表
        """
        return [
            poi.get("semantic_similarity", 0.0),
            poi.get("distance_km", 10.0),
            poi.get("rating", 3.0),
            np.log1p(poi.get("review_count", 0)),
            self._compute_profile_match(poi, profile),
            self._compute_budget_match(poi, intent),
            1.0 if poi.get("poi_id") in (profile.visited_poi_ids if profile else []) else 0.0,
        ]

    def _compute_profile_match(
        self,
        poi: dict[str, Any],
        profile: UserProfile | None,
    ) -> float:
        """
        计算画像匹配度
        
        Args:
            poi: POI字典
            profile: UserProfile
            
        Returns:
            匹配度得分
        """
        if not profile:
            return 0.5

        score = 0.0
        poi_tags = set(poi.get("tags", []))

        # 场景偏好匹配
        for scene, weight in profile.scene_preferences.items():
            if scene in poi_tags:
                score += weight * 0.5

        # 消费档位匹配
        avg_cost = poi.get("avg_cost", 100)
        if profile.spending_level == "budget" and avg_cost < 50:
            score += 0.3
        elif profile.spending_level == "mid" and 50 <= avg_cost <= 200:
            score += 0.3
        elif profile.spending_level == "premium" and avg_cost > 200:
            score += 0.3

        return min(1.0, score)

    def _compute_budget_match(
        self,
        poi: dict[str, Any],
        intent: IntentResult,
    ) -> float:
        """
        计算预算匹配度
        
        Args:
            poi: POI字典
            intent: IntentResult
            
        Returns:
            匹配度得分
        """
        if not intent.budget.per_person:
            return 1.0

        avg_cost = poi.get("avg_cost", 0)
        ratio = avg_cost / intent.budget.per_person

        if ratio <= 1.0:
            return 1.0
        elif ratio <= 1.2:
            return 0.5
        else:
            return 0.0


class DiversityReranker:
    """
    MMR多样性重排器
    
    使用最大边际相关性算法确保候选集的类目多样性
    """

    def __init__(
        self,
        lambda_param: float = 0.6,
        top_k: int = 20,
    ) -> None:
        self.lambda_param = lambda_param
        self.top_k = top_k

    def rerank(self, candidates: list[Any]) -> list[Any]:
        """
        MMR多样性重排
        
        Args:
            candidates: 候选POI列表
            
        Returns:
            重排后的候选列表
        """
        if not candidates:
            return []

        selected = []
        remaining = candidates.copy()

        # 第一个选最高分的
        best = max(
            remaining,
            key=lambda x: x.get("coarse_rank_score", 0) if isinstance(x, dict) else getattr(x, "coarse_rank_score", 0),
        )
        selected.append(best)
        remaining.remove(best)

        while len(selected) < self.top_k and remaining:
            best_mmr_score = -float("inf")
            best_candidate = None

            for candidate in remaining:
                # 相关性分数
                relevance = (
                    candidate.get("coarse_rank_score", 0)
                    if isinstance(candidate, dict)
                    else getattr(candidate, "coarse_rank_score", 0)
                )

                # 与已选集合的最大相似度
                max_sim = max(
                    self._compute_category_similarity(candidate, sel)
                    for sel in selected
                )

                # MMR分数
                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * max_sim

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                remaining.remove(best_candidate)

        return selected

    def _compute_category_similarity(
        self,
        poi_a: Any,
        poi_b: Any,
    ) -> float:
        """
        计算类目相似度
        
        Args:
            poi_a: POI A
            poi_b: POI B
            
        Returns:
            相似度得分
        """
        dict_a = poi_a if isinstance(poi_a, dict) else poi_a.model_dump()
        dict_b = poi_b if isinstance(poi_b, dict) else poi_b.model_dump()

        cat_a = dict_a.get("category", "")
        cat_b = dict_b.get("category", "")

        # 同一大类相似度高
        major_cat_a = cat_a.split("/")[0] if "/" in cat_a else cat_a
        major_cat_b = cat_b.split("/")[0] if "/" in cat_b else cat_b

        if major_cat_a == major_cat_b:
            return 0.8

        return 0.1
