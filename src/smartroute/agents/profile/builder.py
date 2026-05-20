"""
Profile Builder - 画像构建器

负责长期画像加载、短期信号融合和偏好向量化
"""

import numpy as np
from datetime import datetime
from typing import Any

from smartroute.schemas.profile import UserProfile, CuisinePreference
from smartroute.services.profile.mock_service import get_mock_profile_service


class ProfileBuilder:
    """
    画像构建器

    支持时间衰减加权计算长期偏好
    """

    def __init__(
        self,
        long_weight: float = 0.7,
        short_weight: float = 0.3,
        decay_lambda: float = 0.01,
    ) -> None:
        self.long_weight = long_weight
        self.short_weight = short_weight
        self.decay_lambda = decay_lambda
        self._embedding_service = None
        self._mock_service = get_mock_profile_service()

    async def load_long_term_profile(self, user_id: str) -> UserProfile:
        """
        加载长期画像

        Args:
            user_id: 用户ID

        Returns:
            UserProfile
        """
        # 使用本地 Mock 服务生成画像
        return self._mock_service.generate_profile(user_id)

    def compute_cuisine_preference(
        self,
        order_history: list[dict[str, Any]],
        current_date: datetime,
    ) -> dict[str, float]:
        """
        计算菜系偏好分（时间衰减加权）
        
        Args:
            order_history: 历史订单列表
            current_date: 当前日期
            
        Returns:
            菜系偏好分字典
        """
        cuisine_weights: dict[str, float] = {}
        total_weight = 0.0

        for order in order_history:
            order_date_str = order.get("date", "")
            if not order_date_str:
                continue

            try:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
            except ValueError:
                continue

            days_ago = (current_date - order_date).days
            weight = np.exp(-self.decay_lambda * days_ago)

            cuisine = order.get("cuisine", "")
            if cuisine:
                cuisine_weights[cuisine] = cuisine_weights.get(cuisine, 0.0) + weight
                total_weight += weight

        if total_weight == 0:
            return {}

        # 归一化
        return {k: v / total_weight for k, v in cuisine_weights.items()}

    def merge_long_short_term(
        self,
        long_term: UserProfile,
        short_term_signals: dict[str, Any],
    ) -> UserProfile:
        """
        融合长期画像与短期Session信号
        
        Args:
            long_term: 长期画像
            short_term_signals: 短期信号
            
        Returns:
            融合后的 UserProfile
        """
        merged = long_term.model_copy(deep=True)

        # 融合菜系偏好
        if "browsed_cuisines" in short_term_signals:
            for cuisine in short_term_signals["browsed_cuisines"]:
                # 查找是否已有该菜系偏好
                existing = None
                for pref in merged.cuisine_preferences:
                    if pref.cuisine_type == cuisine:
                        existing = pref
                        break

                if existing:
                    # 融合权重
                    existing.score = (
                        self.long_weight * existing.score + self.short_weight * 1.0
                    )
                else:
                    # 新增菜系偏好
                    merged.cuisine_preferences.append(
                        CuisinePreference(
                            cuisine_type=cuisine,
                            score=self.short_weight,
                            order_count=0,
                        )
                    )

        # 融合已拒绝的POI
        if "rejected_poi_ids" in short_term_signals:
            merged.visited_poi_ids.extend(short_term_signals["rejected_poi_ids"])

        # 融合消费档位
        if "explicit_budget" in short_term_signals:
            merged.spending_level = short_term_signals["explicit_budget"]

        # 融合POI风格偏好
        if "poi_style_preference" in short_term_signals:
            style = short_term_signals["poi_style_preference"]
            if style == "popular":
                merged.niche_preference_score = 0.2
            elif style == "niche":
                merged.niche_preference_score = 0.8
            elif style == "balanced":
                merged.niche_preference_score = 0.5

        merged.is_cold_start = False
        merged.confidence = min(1.0, long_term.confidence + 0.2)

        return merged

    async def vectorize(self, profile: UserProfile) -> list[float]:
        """
        将画像向量化
        
        Args:
            profile: UserProfile
            
        Returns:
            向量列表
        """
        # TODO: 实际实现需要调用 Embedding 服务
        # 这里返回模拟向量用于框架完整性
        dim = 1024
        return [0.0] * dim

    def get_profile_summary(self, profile: UserProfile) -> str:
        """
        获取画像摘要文本
        
        Args:
            profile: UserProfile
            
        Returns:
            摘要文本
        """
        parts = []

        if profile.cuisine_preferences:
            top_cuisines = sorted(
                profile.cuisine_preferences,
                key=lambda x: x.score,
                reverse=True,
            )[:3]
            parts.append(f"菜系偏好: {', '.join([c.cuisine_type for c in top_cuisines])}")

        parts.append(f"消费档位: {profile.spending_level}")

        if profile.scene_preferences:
            top_scenes = sorted(
                profile.scene_preferences.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            parts.append(f"场景偏好: {', '.join([s[0] for s in top_scenes])}")

        if profile.walk_tolerance_km:
            parts.append(f"步行耐受: {profile.walk_tolerance_km}km")

        return " | ".join(parts)
