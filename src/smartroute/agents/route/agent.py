"""
Route Planning Agent - 路径规划Agent主类

使用OR-Tools求解VRPTW问题，生成多个差异化路线方案
"""

import asyncio
from typing import Any

from smartroute.agents.base import BaseAgent
from smartroute.agents.route.solver import VRPTWSolver
from smartroute.agents.route.multi_plan import MultiPlanGenerator
from smartroute.agents.route.queue_predictor import QueueTimePredictor
from smartroute.schemas import SystemState


# 默认方案配置
PLAN_CONFIGS = [
    {
        "name": "经典稳妥",
        "tagline": "兼顾体验与效率，适合首次到访",
        "weights": {"travel": 0.3, "wait": 0.2, "experience": 0.4, "cost": 0.1},
    },
    {
        "name": "避峰省时",
        "tagline": "规避排队高峰，时间利用率最高",
        "weights": {"travel": 0.2, "wait": 0.5, "experience": 0.2, "cost": 0.1},
    },
    {
        "name": "极致体验",
        "tagline": "不惜排队，追求最佳体验",
        "weights": {"travel": 0.1, "wait": 0.1, "experience": 0.7, "cost": 0.1},
    },
]


class RoutePlanningAgent(BaseAgent):
    """
    路径规划Agent
    
    处理流程：
    1. 构建距离矩阵
    2. 构建时间窗
    3. 排队时间预测
    4. OR-Tools求解（3套权重）
    5. 可行性校验
    6. 多方案差异化保证
    """

    agent_name = "route_planning"

    def __init__(self) -> None:
        super().__init__()
        self.solver = VRPTWSolver(
            timeout_seconds=self.get_config_value("solver", {}).get("timeout_seconds", 2),
        )
        self.multi_plan_generator = MultiPlanGenerator(
            plan_configs=PLAN_CONFIGS,
            max_overlap_ratio=self.get_config_value("max_poi_overlap_ratio", 0.5),
        )
        self.queue_predictor = QueueTimePredictor(
            model_path=self.get_config_value("queue_predictor", {}).get("model_path", ""),
        )

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行路径规划
        
        Args:
            state: 系统状态
            
        Returns:
            包含多个路线方案的字典
        """
        enriched_pois = state.enriched_pois or []
        intent = state.get_intent()
        profile = state.get_profile()

        if not enriched_pois:
            self.logger.warning("no_enriched_pois_for_routing")
            return {"routes": [], "error": "no_pois"}

        if not intent:
            self.logger.warning("no_intent_for_routing")
            return {"routes": [], "error": "no_intent"}

        # 排队时间预测
        pois_with_queue = await self._predict_queue_times(enriched_pois, intent)

        # 多方案生成
        routes = await self.multi_plan_generator.generate(
            pois=pois_with_queue,
            intent=intent,
            profile=profile,
            solver=self.solver,
        )

        # 可行性校验
        validated_routes = []
        for route in routes:
            if await self._validate_route(route, intent):
                validated_routes.append(route)
            else:
                self.logger.warning("route_validation_failed", plan_name=route.get("name", ""))

        # 如果没有可行方案，触发降级
        if not validated_routes:
            self.logger.warning("all_routes_invalid_fallback")
            fallback_route = await self._fallback_plan(pois_with_queue, intent)
            if fallback_route:
                validated_routes.append(fallback_route)

        return {"routes": validated_routes}

    async def _predict_queue_times(
        self,
        pois: list[Any],
        intent: Any,
    ) -> list[Any]:
        """
        预测排队时间
        
        Args:
            pois: POI列表
            intent: IntentResult
            
        Returns:
            包含排队预测的POI列表
        """
        from datetime import datetime

        for poi in pois:
            poi_dict = poi if isinstance(poi, dict) else poi.model_dump()

            # 获取预测时段
            visit_hour = intent.temporal.start_time.split(":")[0]
            visit_datetime = datetime.strptime(
                f"{intent.temporal.date} {visit_hour}",
                "%Y-%m-%d %H",
            )

            # 预测排队时间
            queue_minutes = await self.queue_predictor.predict(
                poi_id=poi_dict.get("poi_id", ""),
                visit_datetime=visit_datetime,
            )

            if isinstance(poi, dict):
                poi["estimated_queue_minutes"] = queue_minutes
            else:
                poi.estimated_queue_minutes = queue_minutes

        return pois

    async def _validate_route(
        self,
        route: dict[str, Any],
        intent: Any,
    ) -> bool:
        """
        校验路线可行性
        
        Args:
            route: 路线字典
            intent: IntentResult
            
        Returns:
            是否可行
        """
        timeline = route.get("timeline", [])

        # 检查营业时间（简化版）
        for item in timeline:
            arrive_time = item.get("arrive_time", "")
            # TODO: 实际实现需要精确的营业时间校验

        # 检查用餐时段
        has_lunch = False
        for item in timeline:
            category = item.get("category", "")
            arrive_time = item.get("arrive_time", "")

            if "餐" in category or "餐厅" in category:
                hour = int(arrive_time.split(":")[0])
                if 11 <= hour <= 14:
                    has_lunch = True

        # 用餐时段检查
        if not has_lunch:
            self.logger.debug("route_missing_lunch")
            # 不强制失败，只是记录

        return True

    async def _fallback_plan(
        self,
        pois: list[Any],
        intent: Any,
    ) -> dict[str, Any] | None:
        """
        降级方案生成
        
        Args:
            pois: POI列表
            intent: IntentResult
            
        Returns:
            降级路线或None
        """
        # 使用LLM进行启发式排序
        # TODO: 实现LLM兜底逻辑
        return None
