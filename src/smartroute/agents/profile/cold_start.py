"""
Cold Start Handler - 冷启动处理器

处理新用户的画像构建，包括引导式偏好收集和相似人群映射
"""

from typing import Any

from smartroute.schemas.profile import UserProfile, CuisinePreference
from smartroute.schemas.intent import IntentResult


# 预定义的偏好标签
DEFAULT_PREFERENCE_TAGS = [
    "喜欢小众",
    "偏爱网红",
    "自然风光",
    "历史文化",
    "美食探索",
    "亲子友好",
    "商务宴请",
    "浪漫约会",
    "户外运动",
    "文艺气息",
]

# 相似人群默认画像
GROUP_DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "youth_18_25": {
        "spending_level": "budget",
        "niche_preference_score": 0.7,
        "walk_tolerance_km": 8.0,
        "scene_preferences": {"文艺": 0.6, "美食": 0.5, "网红": 0.4},
    },
    "adult_25_40": {
        "spending_level": "mid",
        "niche_preference_score": 0.5,
        "walk_tolerance_km": 5.0,
        "scene_preferences": {"商务": 0.5, "亲子": 0.4, "美食": 0.5},
    },
    "elder_40_plus": {
        "spending_level": "mid",
        "niche_preference_score": 0.3,
        "walk_tolerance_km": 3.0,
        "scene_preferences": {"历史文化": 0.6, "自然风光": 0.5},
    },
}


class ColdStartHandler:
    """
    冷启动处理器
    
    三层策略：
    1. 引导式偏好收集
    2. 人群标签映射
    3. Session内实时学习
    """

    def __init__(
        self,
        threshold: int = 5,
        preference_tags: list[str] | None = None,
    ) -> None:
        self.threshold = threshold
        self.preference_tags = preference_tags or DEFAULT_PREFERENCE_TAGS
        self._vector_client = None

    def is_cold_start(self, profile: UserProfile) -> bool:
        """
        判断是否为冷启动用户
        
        Args:
            profile: UserProfile
            
        Returns:
            是否为冷启动
        """
        # 历史行为少于阈值
        total_actions = sum(
            pref.order_count for pref in profile.cuisine_preferences
        ) + len(profile.visited_poi_ids)

        return total_actions < self.threshold or profile.is_cold_start

    async def handle(
        self,
        user_id: str,
        intent: dict[str, Any] | None = None,
    ) -> UserProfile:
        """
        处理冷启动用户
        
        Args:
            user_id: 用户ID
            intent: 意图信息
            
        Returns:
            UserProfile
        """
        # 尝试从意图中推断偏好
        inferred_profile = self._infer_from_intent(intent)

        if inferred_profile:
            return inferred_profile

        # 使用人群标签映射
        return self._get_group_default("adult_25_40", user_id)

    def _infer_from_intent(self, intent: dict[str, Any] | None) -> UserProfile | None:
        """
        从意图中推断画像
        
        Args:
            intent: 意图字典
            
        Returns:
            推断的 UserProfile 或 None
        """
        if not intent:
            return None

        try:
            intent_obj = IntentResult.model_validate(intent)
        except Exception:
            return None

        profile = UserProfile(
            user_id="inferred",
            is_cold_start=True,
            confidence=0.4,
        )

        # 从意图类型推断场景偏好
        intent_scene_map = {
            "tour": {"历史文化": 0.5, "自然风光": 0.5},
            "food_tour": {"美食": 0.8, "文艺": 0.3},
            "city_walk": {"文艺": 0.6, "历史": 0.4},
            "business": {"商务": 0.7, "美食": 0.5},
            "date": {"浪漫": 0.7, "美食": 0.6},
            "family": {"亲子": 0.7, "自然": 0.5},
        }

        intent_type = intent_obj.intent_type.value
        if intent_type in intent_scene_map:
            profile.scene_preferences = intent_scene_map[intent_type]

        # 从人员构成推断
        if "elder" in intent_obj.party.composition:
            profile.walk_tolerance_km = 3.0
            profile.scene_preferences["休闲"] = 0.5

        if intent_obj.party.child_ages and any(age < 6 for age in intent_obj.party.child_ages):
            profile.scene_preferences["亲子友好"] = 0.7

        # 从预算推断消费档位
        if intent_obj.budget.level:
            profile.spending_level = intent_obj.budget.level

        if intent_obj.budget.per_person:
            if intent_obj.budget.per_person < 50:
                profile.spending_level = "budget"
            elif intent_obj.budget.per_person < 200:
                profile.spending_level = "mid"
            else:
                profile.spending_level = "premium"

        return profile

    def _get_group_default(
        self,
        group_key: str,
        user_id: str,
    ) -> UserProfile:
        """
        获取人群默认画像
        
        Args:
            group_key: 人群标识
            user_id: 用户ID
            
        Returns:
            UserProfile
        """
        group_data = GROUP_DEFAULT_PROFILES.get(group_key, GROUP_DEFAULT_PROFILES["adult_25_40"])

        return UserProfile(
            user_id=user_id,
            is_cold_start=True,
            confidence=0.4,
            spending_level=group_data.get("spending_level", "mid"),
            niche_preference_score=group_data.get("niche_preference_score", 0.5),
            walk_tolerance_km=group_data.get("walk_tolerance_km", 5.0),
            scene_preferences=group_data.get("scene_preferences", {}),
        )

    def get_preference_tags_for_collection(self) -> list[str]:
        """
        获取引导式偏好收集的标签列表
        
        Returns:
            标签列表
        """
        return self.preference_tags[:8]  # 返回前8个标签

    def build_profile_from_selected_tags(
        self,
        user_id: str,
        selected_tags: list[str],
    ) -> UserProfile:
        """
        从用户选择的标签构建画像
        
        Args:
            user_id: 用户ID
            selected_tags: 用户选择的标签
            
        Returns:
            UserProfile
        """
        profile = UserProfile(
            user_id=user_id,
            is_cold_start=True,
            confidence=0.6,
        )

        tag_scene_map = {
            "喜欢小众": ("niche_preference_score", 0.8),
            "偏爱网红": ("niche_preference_score", 0.2),
            "自然风光": ("scene_preferences.natural", 0.6),
            "历史文化": ("scene_preferences.history", 0.6),
            "美食探索": ("scene_preferences.food", 0.7),
            "亲子友好": ("scene_preferences.family", 0.7),
            "商务宴请": ("scene_preferences.business", 0.6),
            "浪漫约会": ("scene_preferences.romantic", 0.6),
            "户外运动": ("scene_preferences.outdoor", 0.5),
            "文艺气息": ("scene_preferences.artistic", 0.6),
        }

        for tag in selected_tags:
            if tag in tag_scene_map:
                field, value = tag_scene_map[tag]
                if field.startswith("scene_preferences."):
                    scene_key = field.split(".")[-1]
                    profile.scene_preferences[scene_key] = value
                elif field == "niche_preference_score":
                    profile.niche_preference_score = value

        return profile
