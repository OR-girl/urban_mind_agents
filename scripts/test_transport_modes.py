"""
测试交通方式识别和路线规划

验证Intent Agent能正确解析交通方式
验证Route Agent能根据交通方式生成路线
"""

import asyncio

from smartroute.schemas.intent import (
    IntentResult,
    IntentType,
    SpatialConstraint,
    TemporalConstraint,
    PartyInfo,
    Preferences,
    BudgetInfo,
    TransportPreference,
    TransportMode,
)
from smartroute.schemas.profile import UserProfile
from smartroute.schemas.state import SystemState
from smartroute.mock.data import HANGZHOU_POIS


async def test_transport_modes():
    """测试不同交通方式下的路线规划"""

    # 构建测试POI（模拟enriched_pois）
    enriched_pois = []
    for poi in HANGZHOU_POIS[:8]:
        poi_copy = poi.copy()
        poi_copy["estimated_duration_min"] = 60
        poi_copy["estimated_queue_minutes"] = 10
        poi_copy["ugc_sentiment"] = {"positive": 4.5}
        enriched_pois.append(poi_copy)

    # 测试不同交通方式
    transport_modes = [
        (TransportMode.WALK, "步行"),
        (TransportMode.BIKE, "骑行"),
        (TransportMode.CAR, "驾车"),
        (TransportMode.TAXI, "打车"),
        (TransportMode.PUBLIC, "公共交通"),
    ]

    print("=" * 60)
    print("测试不同交通方式下的路线规划")
    print("=" * 60)

    for mode, mode_name in transport_modes:
        print(f"\n{'='*40}")
        print(f"交通方式: {mode_name}")
        print(f"{'='*40}")

        # 构建IntentResult
        intent = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.95,
            spatial=SpatialConstraint(
                city="杭州",
                anchor_poi="西湖",
                radius_km=5.0,
            ),
            temporal=TemporalConstraint(
                date="2026-06-05",
                start_time="09:00",
                end_time="18:00",
                duration_hours=8.0,
            ),
            party=PartyInfo(size=2),
            preferences=Preferences(must_have=["景点"]),
            budget=BudgetInfo(per_person=200),
            transport=TransportPreference(primary_mode=mode),
            raw_query=f"测试{mode_name}路线",
        )

        # 构建UserProfile
        profile = UserProfile(
            user_id="test_user",
            spending_level="mid",
            scene_preferences={"自然风光": 0.5},
        )

        # 构建SystemState
        state = SystemState(
            session_id="test_session",
            trace_id="test_trace",
            request_type="NEW",
            user_id="test_user",
            raw_query=f"测试{mode_name}路线",
            enriched_pois=enriched_pois,
            intent=intent.model_dump(),
            profile=profile.model_dump(),
        )

        # 执行Route Agent
        from smartroute.agents.route import RoutePlanningAgent
        agent = RoutePlanningAgent()
        result = await agent.execute(state)

        routes = result.get("routes", [])

        if routes:
            plan = routes[0]
            print(f"\n方案名称: {plan.get('name', '')}")
            print(f"方案标签: {plan.get('tagline', '')}")

            timeline = plan.get("timeline", [])
            print(f"\n路线时间轴（共{len(timeline)}个POI）:")
            print("-" * 40)

            total_transport_cost = 0
            for i, item in enumerate(timeline, 1):
                print(f"{i}. {item.get('poi_name', '')}")
                print(f"   时间: {item.get('arrive_time', '')} → {item.get('leave_time', '')}")
                print(f"   停留: {item.get('duration_min', 0)}分钟")

                transport = item.get("transport_to_next")
                if transport:
                    print(f"   → 下一站: {transport.get('mode', '')}, {transport.get('duration_min', 0)}分钟, {transport.get('distance_m', 0)}米")
                    if transport.get("cost", 0) > 0:
                        print(f"   → 交通费用: ¥{transport.get('cost', 0)}")
                        total_transport_cost += transport.get("cost", 0)

            summary = plan.get("summary", {})
            print(f"\n方案摘要:")
            print(f"   总时长: {summary.get('total_duration_h', 0)}小时")
            print(f"   总距离: {summary.get('total_distance_km', 0)}km")
            print(f"   交通费用: ¥{total_transport_cost}")
        else:
            print("未生成路线方案")


if __name__ == "__main__":
    asyncio.run(test_transport_modes())