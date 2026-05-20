"""
Mock Profile Service - 本地用户画像 Mock 服务

根据用户 ID 生成模拟画像数据，用于开发和测试
"""

import hashlib
import random
from datetime import datetime
from typing import Any

from smartroute.schemas.profile import (
    UserProfile,
    CuisinePreference,
    ShortTermSignals,
)
from smartroute.services.profile.templates import (
    TEMPLATES,
    TEMPLATE_KEYS,
    HOT_POIS_HANGZHOU,
)


class MockProfileService:
    """
    本地 Mock 用户画像服务

    特点:
    - 确定性: 同一 user_id 每次返回相同画像
    - 多样性: 多种模板覆盖典型用户群体
    - 真实性: 模拟真实历史数据
    """

    def __init__(self) -> None:
        self.templates = TEMPLATES
        self.template_keys = TEMPLATE_KEYS
        self.hot_pois = HOT_POIS_HANGZHOU

    def generate_profile(self, user_id: str) -> UserProfile:
        """
        根据用户 ID 生成模拟画像

        Args:
            user_id: 用户唯一标识

        Returns:
            UserProfile
        """
        if not user_id:
            return self._generate_anonymous_profile()

        # 根据 user_id hash 选择模板（确定性）
        template_key = self._select_template_key(user_id)
        template = self.templates[template_key]

        # 使用 user_id 作为随机种子（确定性）
        seed = self._generate_seed(user_id)
        random.seed(seed)

        # 在模板基础上生成画像
        profile = self._build_profile_from_template(user_id, template)

        return profile

    def generate_short_term_signals(self, user_id: str) -> ShortTermSignals:
        """
        生成短期 Session 信号

        Args:
            user_id: 用户 ID

        Returns:
            ShortTermSignals
        """
        seed = self._generate_seed(f"short_{user_id}")
        random.seed(seed)

        profile = self.generate_profile(user_id)

        # 从画像中随机选取菜系作为浏览过的
        browsed = []
        if profile.cuisine_preferences:
            count = min(2, len(profile.cuisine_preferences))
            browsed = [p.cuisine_type for p in random.sample(profile.cuisine_preferences, count)]

        # 随机生成一些拒绝的 POI
        rejected_count = random.randint(0, 2)
        rejected = random.sample(self.hot_pois, rejected_count) if rejected_count > 0 else []

        return ShortTermSignals(
            browsed_cuisines=browsed,
            rejected_poi_ids=rejected,
            accepted_poi_ids=[],
            explicit_budget=None,
            explicit_preferences=[],
        )

    def _generate_anonymous_profile(self) -> UserProfile:
        """生成匿名用户画像"""
        return UserProfile(
            user_id="anonymous",
            is_cold_start=True,
            confidence=0.3,
            spending_level="mid",
            avg_spend_per_person=100.0,
            walk_tolerance_km=5.0,
            scene_preferences={},
            cuisine_preferences=[],
            visited_poi_ids=[],
        )

    def _select_template_key(self, user_id: str) -> str:
        """
        根据 user_id hash 选择模板

        Args:
            user_id: 用户 ID

        Returns:
            模板 key
        """
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        index = hash_val % len(self.template_keys)
        return self.template_keys[index]

    def _generate_seed(self, user_id: str) -> int:
        """
        根据 user_id 生成随机种子

        Args:
            user_id: 用户 ID

        Returns:
            随机种子整数
        """
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        return hash_val % (2**31)

    def _build_profile_from_template(
        self,
        user_id: str,
        template: dict[str, Any],
    ) -> UserProfile:
        """
        从模板构建画像

        Args:
            user_id: 用户 ID
            template: 模板数据

        Returns:
            UserProfile
        """
        # 应用 ±10% 随机变化
        avg_spend = template["avg_spend_base"] * (0.9 + random.random() * 0.2)
        walk_tolerance = template["walk_tolerance_base"] * (0.9 + random.random() * 0.2)
        niche_preference = template["niche_preference_base"] * (0.9 + random.random() * 0.2)

        # 生成场景偏好（添加随机变化）
        scene_preferences = {}
        for scene, score in template["scene_preferences"].items():
            scene_preferences[scene] = score * (0.85 + random.random() * 0.3)

        # 生成菜系偏好历史
        cuisine_preferences = self._generate_cuisine_preferences(template)

        # 生成去过的地方
        visited_pois = self._generate_visited_pois()

        # 生成饮食禁忌
        dietary_restrictions = self._generate_dietary_restrictions(template)

        return UserProfile(
            user_id=user_id,
            is_cold_start=False,
            confidence=0.8,
            spending_level=template["spending_level"],
            avg_spend_per_person=avg_spend,
            walk_tolerance_km=walk_tolerance,
            niche_preference_score=niche_preference,
            scene_preferences=scene_preferences,
            cuisine_preferences=cuisine_preferences,
            visited_poi_ids=visited_pois,
            dietary_restrictions=dietary_restrictions,
            preferred_start_hour=template["preferred_start_hour"],
            is_night_owl=template["is_night_owl"],
            data_freshness=datetime.now().strftime("%Y-%m-%d"),
        )

    def _generate_cuisine_preferences(
        self,
        template: dict[str, Any],
    ) -> list[CuisinePreference]:
        """
        生成菜系偏好

        Args:
            template: 模板数据

        Returns:
            CuisinePreference 列表
        """
        cuisine_pool = template["cuisine_pool"]
        preferences = []

        # 随机选择 3-5 个菜系
        count = random.randint(3, min(5, len(cuisine_pool)))
        selected = random.sample(cuisine_pool, count)

        for i, cuisine in enumerate(selected):
            # 第一个菜系分数最高
            if i == 0:
                score = random.uniform(0.7, 0.95)
                order_count = random.randint(8, 15)
            elif i == 1:
                score = random.uniform(0.5, 0.75)
                order_count = random.randint(4, 10)
            else:
                score = random.uniform(0.3, 0.6)
                order_count = random.randint(1, 5)

            preferences.append(
                CuisinePreference(
                    cuisine_type=cuisine,
                    score=score,
                    order_count=order_count,
                )
            )

        return preferences

    def _generate_visited_pois(self) -> list[str]:
        """
        生成去过的地方

        Returns:
            POI ID 列表
        """
        # 随机选择 3-8 个去过的地方
        count = random.randint(3, min(8, len(self.hot_pois)))
        return random.sample(self.hot_pois, count)

    def _generate_dietary_restrictions(
        self,
        template: dict[str, Any],
    ) -> list[str]:
        """
        生成饮食禁忌

        Args:
            template: 模板数据

        Returns:
            饮食禁忌列表
        """
        pool = template.get("dietary_restrictions_pool", [])
        if not pool:
            return []

        # 30% 概率有饮食禁忌
        if random.random() > 0.3:
            return []

        # 随机选择 1-2 个禁忌
        count = random.randint(1, min(2, len(pool)))
        return random.sample(pool, count)


# 全局实例
mock_profile_service = MockProfileService()


def get_mock_profile_service() -> MockProfileService:
    """获取 Mock Profile Service 实例"""
    return mock_profile_service


if __name__ == "__main__":
    # 测试
    service = get_mock_profile_service()
    profile = service.generate_profile("user_001")
    print(profile)