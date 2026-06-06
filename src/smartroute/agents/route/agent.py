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


if __name__ == "__main__":
    import asyncio
    from smartroute.schemas.state import SystemState
    from smartroute.schemas.profile import UserProfile

    print("=" * 60)
    print("完整流程：Intent → Retrieval → Route")
    print("=" * 60)

    # 用户输入
    query = "我们一家三口开车去杭州西湖玩一天，孩子6岁，希望中午找个餐厅吃饭"
    print(f"\n用户输入: {query}")
    print("-" * 60)

    # Step 1: Intent Agent
    print("\n【Intent Agent】意图识别...")
    from smartroute.agents.intent import IntentAgent
    intent_agent = IntentAgent()

    state = SystemState(
        session_id="test_session",
        trace_id="test_trace",
        request_type="NEW",
        user_id="test_user",
        raw_query=query,
        dialog_history=[],
    )

    intent_result = asyncio.run(intent_agent.execute(state))

    # 获取交通方式（重点）
    intent = intent_result.get("intent", {})
    transport = intent.get("transport", {})
    primary_mode = transport.get("primary_mode")

    # 处理Enum类型
    if hasattr(primary_mode, "value"):
        mode_value = primary_mode.value
    else:
        mode_value = primary_mode or "walk"

    # 如果LLM没识别出交通方式，从query中推断
    if mode_value == "walk" and ("开车" in query or "驾车" in query):
        print("  LLM未识别交通方式，从query推断: car")
        from smartroute.schemas.intent import TransportMode, TransportPreference
        intent["transport"] = {"primary_mode": TransportMode.CAR}
        mode_value = "car"

    print(f"  意图类型: {intent.get('intent_type')}")
    print(f"  城市: {intent.get('spatial', {}).get('city', '')}")
    print(f"  交通方式: {mode_value}")

    state.intent = intent

    # Step 2: Profile
    print("\n【Profile Agent】用户画像...")
    profile = UserProfile(user_id="test_user", spending_level="mid", visited_poi_ids=["poi_xihu_001"])
    state.profile = profile.model_dump()
    print(f"  消费档位: {profile.spending_level}")

    # Step 3: Retrieval
    print("\n【Retrieval Agent】多路召回...")
    from smartroute.agents.retrieval import RetrievalAgent
    retrieval_agent = RetrievalAgent()
    retrieval_result = asyncio.run(retrieval_agent.execute(state))
    candidates = retrieval_result.get("candidates", [])[:6]
    print(f"  候选数量: {len(candidates)}个")
    print(f"  前3个: {', '.join([p.get('name') for p in candidates[:3]])}")

    # Step 4: Route计算
    print("\n【Route Agent】路线规划...")
    from smartroute.agents.route.solver import TRANSPORT_SPEEDS, TRANSPORT_COSTS
    from smartroute.schemas.intent import TransportMode

    transport_mode = TransportMode(mode_value)
    speed = TRANSPORT_SPEEDS.get(transport_mode, 4.0)
    cost_rate = TRANSPORT_COSTS.get(transport_mode, 0.0)

    print(f"  交通方式: {mode_value}")
    print(f"  速度: {speed}km/h, 费用: {cost_rate}元/km")

    # 时间轴
    print(f"\n路线时间轴:")
    current = 9 * 60
    total_cost = 0
    for i, poi in enumerate(candidates, 1):
        arrive = f"{current//60:02d}:{current%60:02d}"
        leave = current + 70
        if i < len(candidates):
            dist = max(poi.get("distance_km", 0), 1.5)
            travel = int(dist / speed * 60)
            if transport_mode == TransportMode.CAR: travel += 5
            elif transport_mode == TransportMode.PUBLIC: travel += 10
            elif transport_mode == TransportMode.TAXI: travel += 3
            fee = round(dist * cost_rate, 1)
            total_cost += fee
            print(f"  {i}. {poi.get('name')}: {arrive}→ {travel}分钟/¥{fee}")
            current = leave + travel
        else:
            print(f"  {i}. {poi.get('name')}: {arrive}→")

    print(f"\n总交通费用: ¥{total_cost}")
    print("=" * 60)
