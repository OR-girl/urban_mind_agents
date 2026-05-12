"""
Profile Agent - 用户画像Agent主类

构建动态个性化偏好画像，融合长期历史偏好与短期Session信号
"""

from typing import Any

from smartroute.agents.base import CacheableAgent
from smartroute.agents.profile.builder import ProfileBuilder
from smartroute.agents.profile.cold_start import ColdStartHandler
from smartroute.schemas import SystemState
from smartroute.schemas.profile import UserProfile


class ProfileAgent(CacheableAgent):
    """
    用户画像Agent
    
    处理流程：
    1. 长期画像加载（Feast特征服务）
    2. 短期行为聚合（当前Session）
    3. 长短期融合
    4. 冷启动判断与处理
    5. 偏好向量化
    """

    agent_name = "profile"

    def __init__(self) -> None:
        super().__init__()
        self.builder = ProfileBuilder(
            long_weight=self.get_config_value("long_term_weight", 0.7),
            short_weight=self.get_config_value("short_term_weight", 0.3),
        )
        self.cold_start_handler = ColdStartHandler(
            threshold=self.get_config_value("cold_start_threshold", 5),
        )
        self._cache_ttl = 3600  # 画像缓存1小时

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行画像构建
        
        Args:
            state: 系统状态
            
        Returns:
            包含 UserProfile 的字典
        """
        user_id = state.user_id

        if not user_id:
            # 无用户ID时使用默认画像
            return {"profile": self._default_profile().model_dump(), "profile_vector": None}

        # 尝试从缓存加载
        cache_key = f"profile:user:{user_id}"
        cached = await self.get_cached(cache_key)

        if cached:
            self.logger.debug("profile_cache_hit", user_id=user_id)
            profile = UserProfile.model_validate(cached)
            profile_vector = cached.get("profile_vector")
            return {
                "profile": profile.model_dump(),
                "profile_vector": profile_vector,
            }

        # 加载长期画像
        long_term_profile = await self.builder.load_long_term_profile(user_id)

        # 判断是否冷启动
        is_cold_start = self.cold_start_handler.is_cold_start(long_term_profile)

        if is_cold_start:
            self.logger.info("cold_start_detected", user_id=user_id)
            profile = await self.cold_start_handler.handle(user_id, state.intent)
        else:
            # 融合短期信号
            short_term_signals = self._extract_short_term_signals(state)
            profile = self.builder.merge_long_short_term(
                long_term_profile,
                short_term_signals,
            )

        # 生成画像向量
        profile_vector = await self.builder.vectorize(profile)

        # 缓存结果
        cache_data = profile.model_dump()
        cache_data["profile_vector"] = profile_vector
        await self.set_cached(cache_key, cache_data)

        return {
            "profile": profile.model_dump(),
            "profile_vector": profile_vector,
        }

    def _default_profile(self) -> UserProfile:
        """
        默认画像（匿名用户）
        """
        return UserProfile(
            user_id="anonymous",
            is_cold_start=True,
            confidence=0.3,
        )

    def _extract_short_term_signals(self, state: SystemState) -> dict[str, Any]:
        """
        提取短期Session信号
        
        Args:
            state: 系统状态
            
        Returns:
            短期信号字典
        """
        signals = {}

        if state.intent:
            intent = state.get_intent()
            if intent:
                # 从意图中提取偏好信号
                if intent.preferences.cuisine_types:
                    signals["browsed_cuisines"] = intent.preferences.cuisine_types

                if intent.preferences.poi_style:
                    signals["poi_style_preference"] = intent.preferences.poi_style

                if intent.budget.level:
                    signals["explicit_budget"] = intent.budget.level

        # 从对话历史中提取负反馈
        rejected_pois = []
        for item in state.dialog_history:
            if item.get("role") == "user":
                content = item.get("content", "")
                if "不要" in content or "换" in content:
                    # 简化版：提取POI名称（实际需要更复杂的解析）
                    pass

        if rejected_pois:
            signals["rejected_poi_ids"] = rejected_pois

        return signals

    async def update_profile(
        self,
        user_id: str,
        updates: dict[str, Any],
    ) -> UserProfile:
        """
        更新用户画像
        
        Args:
            user_id: 用户ID
            updates: 更新内容
            
        Returns:
            更新后的 UserProfile
        """
        cache_key = f"profile:user:{user_id}"
        cached = await self.get_cached(cache_key)

        if cached:
            profile = UserProfile.model_validate(cached)
            profile_dict = profile.model_dump()

            # 应用更新
            for key, value in updates.items():
                if key in profile_dict:
                    profile_dict[key] = value

            profile = UserProfile.model_validate(profile_dict)

            # 更新缓存
            cache_data = profile.model_dump()
            cache_data["profile_vector"] = cached.get("profile_vector")
            await self.set_cached(cache_key, cache_data)

            return profile

        return await self.builder.load_long_term_profile(user_id)
