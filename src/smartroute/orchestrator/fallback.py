"""
SmartRoute Agent Orchestrator 降级策略模块

三级降级策略实现
"""

from typing import Any

from smartroute.core.exceptions import (
    FallbackTriggeredError,
    NoCandidatesError,
    NoFeasibleRouteError,
    SolverTimeoutError,
)
from smartroute.core.logging import get_logger
from smartroute.schemas import SystemState

logger = get_logger("orchestrator.fallback")


class FallbackLevel:
    """降级级别"""

    L1 = "L1"  # 软降级：单个 Agent 超时，使用缓存/默认值
    L2 = "L2"  # 部分降级：关键 Agent 失败，跳过使用简化逻辑
    L3 = "L3"  # 完全降级：多个 Agent 失败，返回 Top-K POI 列表


class FallbackHandler:
    """
    降级处理器

    实现三级降级策略
    """

    def __init__(self) -> None:
        self.l1_threshold_seconds = 5.0
        self.l2_max_retries = 2

    def should_trigger_l1(self, state: SystemState) -> bool:
        """
        检查是否需要触发 L1 降级

        L1 降级条件：单个 Agent 执行时间超过阈值

        Args:
            state: 系统状态

        Returns:
            是否需要降级
        """
        for stage, duration in state.stage_timings.items():
            if duration > self.l1_threshold_seconds * 1000:
                return True

        return False

    def should_trigger_l2(self, state: SystemState) -> bool:
        """
        检查是否需要触发 L2 降级

        L2 降级条件：关键 Agent（Route/UGC）失败

        Args:
            state: 系统状态

        Returns:
            是否需要降级
        """
        # Route Agent 失败
        if state.routes is None or len(state.routes) == 0:
            return True

        # UGC Agent 失败导致数据缺失
        if state.enriched_pois is None and state.candidates is not None:
            return True

        return False

    def should_trigger_l3(self, state: SystemState) -> bool:
        """
        检查是否需要触发 L3 降级

        L3 降级条件：多个 Agent 失败，无法生成有效方案

        Args:
            state: 系统状态

        Returns:
            是否需要降级
        """
        # 同时缺失多个关键数据
        missing_count = 0
        if state.intent is None:
            missing_count += 1
        if state.candidates is None:
            missing_count += 1
        if state.routes is None:
            missing_count += 1

        return missing_count >= 2

    def handle_l1_fallback(self, state: SystemState) -> SystemState:
        """
        处理 L1 降级

        使用缓存结果或默认值继续执行

        Args:
            state: 系统状态

        Returns:
            更新后的状态
        """
        logger.info(
            "l1_fallback_triggered",
            session_id=state.session_id,
            stage_timings=state.stage_timings,
        )

        state.fallback_triggered = True
        state.fallback_level = FallbackLevel.L1

        # 使用默认画像
        if state.profile is None:
            state.profile = self._get_default_profile(state.user_id)

        # 使用简化候选集
        if state.candidates is None and state.intent is not None:
            state.candidates = self._get_fallback_candidates()

        return state

    def handle_l2_fallback(self, state: SystemState) -> SystemState:
        """
        处理 L2 降级

        跳过失败的 Agent，使用简化逻辑

        Args:
            state: 系统状态

        Returns:
            更新后的状态
        """
        logger.warning(
            "l2_fallback_triggered",
            session_id=state.session_id,
        )

        state.fallback_triggered = True
        state.fallback_level = FallbackLevel.L2

        # 如果 Route 失败，使用简化排序
        if state.routes is None and state.enriched_pois is not None:
            state.routes = self._generate_simple_routes(state)

        # 如果 UGC 失败，使用基础 POI 信息
        if state.enriched_pois is None and state.candidates is not None:
            state.enriched_pois = self._convert_to_enriched_pois(state.candidates)

        return state

    def handle_l3_fallback(self, state: SystemState) -> SystemState:
        """
        处理 L3 降级

        返回 Top-K POI 列表，无法生成完整路线

        Args:
            state: 系统状态

        Returns:
            更新后的状态
        """
        logger.error(
            "l3_fallback_triggered",
            session_id=state.session_id,
        )

        state.fallback_triggered = True
        state.fallback_level = FallbackLevel.L3

        # 生成简化的 POI 列表输出
        state.final_response = self._generate_poi_list_response(state)

        return state

    def determine_fallback_level(
        self,
        state: SystemState,
        error: Exception | None = None,
    ) -> str | None:
        """
        根据状态和错误确定降级级别

        Args:
            state: 系统状态
            error: 触发降级的错误

        Returns:
            降级级别或 None
        """
        if error:
            # 根据错误类型直接判断
            if isinstance(error, SolverTimeoutError):
                return FallbackLevel.L2
            if isinstance(error, NoFeasibleRouteError):
                return FallbackLevel.L2
            if isinstance(error, NoCandidatesError):
                return FallbackLevel.L3

        # 根据状态判断
        if self.should_trigger_l3(state):
            return FallbackLevel.L3
        if self.should_trigger_l2(state):
            return FallbackLevel.L2
        if self.should_trigger_l1(state):
            return FallbackLevel.L1

        return None

    def apply_fallback(
        self,
        state: SystemState,
        error: Exception | None = None,
    ) -> SystemState:
        """
        应用适当的降级策略

        Args:
            state: 系统状态
            error: 触发降级的错误

        Returns:
            更新后的状态
        """
        level = self.determine_fallback_level(state, error)

        if level is None:
            return state

        if level == FallbackLevel.L1:
            return self.handle_l1_fallback(state)
        elif level == FallbackLevel.L2:
            return self.handle_l2_fallback(state)
        else:
            return self.handle_l3_fallback(state)

    def _get_default_profile(self, user_id: str | None) -> dict[str, Any]:
        """获取默认用户画像"""
        return {
            "user_id": user_id or "anonymous",
            "is_cold_start": True,
            "spending_level": "mid",
            "avg_spend_per_person": 150.0,
            "walk_tolerance_km": 5.0,
            "niche_preference_score": 0.5,
            "confidence": 0.3,
        }

    def _get_fallback_candidates(self) -> list[dict[str, Any]]:
        """获取兜底候选 POI"""
        # 实际实现需要从缓存或热门榜单获取
        return []

    def _generate_simple_routes(self, state: SystemState) -> list[dict[str, Any]]:
        """
        生成简化路线方案

        使用简单的启发式排序
        """
        if not state.enriched_pois:
            return []

        # 按评分排序取 Top 5
        sorted_pois = sorted(
            state.enriched_pois,
            key=lambda p: p.get("rating", 0),
            reverse=True,
        )[:5]

        # 生成单一方案
        route = {
            "plan_id": "plan_a",
            "name": "推荐方案",
            "tagline": "精选推荐地点",
            "timeline": [
                {
                    "poi_id": p.get("poi_id"),
                    "poi_name": p.get("name"),
                    "category": p.get("category"),
                    "arrive_time": "09:00",
                    "leave_time": "10:00",
                    "sequence": i,
                }
                for i, p in enumerate(sorted_pois)
            ],
            "is_feasible": True,
        }

        return [route]

    def _convert_to_enriched_pois(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将候选 POI 转换为增强 POI（使用默认值）"""
        enriched = []
        for poi in candidates:
            enriched_poi = poi.copy()
            enriched_poi.setdefault("highlights", [])
            enriched_poi.setdefault("warnings", [])
            enriched_poi.setdefault("ugc_sentiment", {})
            enriched_poi.setdefault("confidence", 0.5)
            enriched_poi.setdefault("analysis_channel", "fallback")
            enriched.append(enriched_poi)
        return enriched

    def _generate_poi_list_response(
        self,
        state: SystemState,
    ) -> dict[str, Any]:
        """生成 POI 列表响应（完全降级）"""
        poi_list = []

        if state.candidates:
            poi_list = [
                {
                    "poi_id": p.get("poi_id"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "rating": p.get("rating"),
                    "address": p.get("address"),
                }
                for p in state.candidates[:10]
            ]

        return {
            "session_id": state.session_id,
            "summary": "由于时间约束或数据限制，无法生成完整路线，以下是推荐地点列表：",
            "plans": [],
            "poi_list": poi_list,
            "fallback_triggered": True,
            "fallback_level": FallbackLevel.L3,
            "error_message": "路线生成受限，已返回推荐的地点列表供您参考",
            "adjustable_hints": [
                "可以放宽时间约束重新尝试",
                "可以扩大搜索范围",
                "可以减少必去景点数量",
            ],
        }


# 全局降级处理器
fallback_handler = FallbackHandler()


def get_fallback_handler() -> FallbackHandler:
    """获取全局降级处理器"""
    return fallback_handler