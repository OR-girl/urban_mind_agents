"""
完整流程测试（Mock版本）：展示交通方式功能

使用Mock Intent来展示完整的Agent串联流程
"""

import asyncio
from typing import Any

from smartroute.schemas.state import SystemState
from smartroute.schemas.profile import UserProfile, CuisinePreference
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


async def test_with_mock_intent(transport_mode: TransportMode, mode_name: str):
    """
    使用Mock Intent测试完整流程

    Args:
        transport_mode: 交通方式
        mode_name: 交通方式名称
    """
    print("=" * 70)
    print(f"完整流程测试：{mode_name}模式")
    print("=" * 70)

    # Step 1: Mock Intent
    print("\n" + "=" * 70)
    print("Step 1: Intent Agent - 意图识别（Mock）")
    print("=" * 70)

    intent = IntentResult(
        intent_type=IntentType.FAMILY,
        confidence=0.95,
        spatial=SpatialConstraint(
            city="杭州",
            region="西湖",
            anchor_poi="西湖",
            radius_km=5.0,
        ),
        temporal=TemporalConstraint(
            date="2026-06-06",
            start_time="09:00",
            end_time="18:00",
            duration_hours=8.0,
            meal_preferences=["lunch"],
        ),
        party=PartyInfo(
            size=3,
            composition=["adult", "adult", "child"],
            child_ages=[6],
        ),
        preferences=Preferences(
            must_have=["餐厅"],
            nice_to_have=["亲子", "轻松"],
            themes=["家庭出游"],
        ),
        budget=BudgetInfo(per_person=200, level="mid"),
        transport=TransportPreference(
            primary_mode=transport_mode,
            car_available=True if transport_mode == TransportMode.CAR else None,
        ),
        poi_schedule=[
            {"poi_name": "西湖", "time_slot": "morning", "sequence": 1, "priority": 1},
            {"poi_name": "知味观", "time_slot": "noon", "sequence": 2, "priority": 1},
        ],
        raw_query=f"我们一家三口{mode_name}去杭州西湖玩一天",
    )

    print(f"\n意图识别结果:")
    print("-" * 40)
    print(f"  意图类型: {intent.intent_type.value}")
    print(f"  城市: {intent.spatial.city}")
    print(f"  锚点POI: {intent.spatial.anchor_poi}")
    print(f"  日期: {intent.temporal.date}")
    print(f"  时间: {intent.temporal.start_time} - {intent.temporal.end_time}")
    print(f"  人数: {intent.party.size}人（含{len(intent.party.child_ages)}个孩子）")
    print(f"  必须包含: {intent.preferences.must_have}")
    print(f"  预算: {intent.budget.per_person}元/人")

    print(f"\n  【交通方式】★重点展示★")
    print("-" * 40)
    print(f"  主要交通方式: {intent.transport.primary_mode.value}")
    if intent.transport.car_available:
        print(f"  是否有车: {intent.transport.car_available}")

    # Step 2: Profile Agent
    print("\n" + "=" * 70)
    print("Step 2: Profile Agent - 用户画像")
    print("=" * 70)

    profile = UserProfile(
        user_id="test_user_001",
        spending_level="mid",
        avg_spend_per_person=150.0,
        scene_preferences={"亲子": 0.7, "自然风光": 0.5},
        visited_poi_ids=["poi_xihu_001"],
    )

    print(f"\n用户画像:")
    print(f"  消费档位: {profile.spending_level}")
    print(f"  场景偏好: {profile.scene_preferences}")
    print(f"  已去过: {profile.visited_poi_ids}")

    # Step 3: Retrieval Agent
    print("\n" + "=" * 70)
    print("Step 3: Retrieval Agent - 多路召回")
    print("=" * 70)

    from smartroute.agents.retrieval import RetrievalAgent
    retrieval_agent = RetrievalAgent()

    state = SystemState(
        session_id="test_session",
        trace_id="test_trace",
        request_type="NEW",
        user_id="test_user",
        raw_query=f"我们一家三口{mode_name}去杭州西湖玩一天",
        intent=intent.model_dump(),
        profile=profile.model_dump(),
    )

    retrieval_result = await retrieval_agent.execute(state)
    candidates = retrieval_result.get("candidates", [])
    metadata = retrieval_result.get("retrieval_metadata", {})

    print(f"\n召回统计:")
    print(f"  召回路径: {metadata.get('path_counts', {})}")
    print(f"  最终候选: {metadata.get('final_count', 0)}个")

    # Step 4: UGC Agent（模拟）
    print("\n" + "=" * 70)
    print("Step 4: UGC Agent - 评论分析（模拟）")
    print("=" * 70)

    enriched_pois = []
    for poi in candidates[:6]:
        poi_copy = poi.copy()
        poi_copy["estimated_duration_min"] = 60 if "景点" in poi.get("category", "") else 90
        poi_copy["estimated_queue_minutes"] = 15
        poi_copy["ugc_sentiment"] = {"positive": 4.2}
        poi_copy["highlights"] = ["适合亲子", "风景优美"]
        enriched_pois.append(poi_copy)

    print(f"  Enriched POI数量: {len(enriched_pois)}")

    # Step 5: Route Agent（简化版，跳过OR-Tools）
    print("\n" + "=" * 70)
    print("Step 5: Route Agent - 路线规划（简化版）")
    print("=" * 70)

    from smartroute.agents.route.multi_plan import MultiPlanGenerator
    from smartroute.agents.route.solver import TRANSPORT_SPEEDS, TRANSPORT_COSTS

    # 构建时间轴（不使用OR-Tools）
    speed_kmh = TRANSPORT_SPEEDS.get(transport_mode, 4.0)
    cost_per_km = TRANSPORT_COSTS.get(transport_mode, 0.0)

    print(f"\n交通方式参数:")
    print(f"  速度: {speed_kmh}km/h")
    print(f"  费用: {cost_per_km}元/km")

    print(f"\n路线方案:")
    print("-" * 40)

    timeline = []
    current_time = 9 * 60  # 09:00
    total_transport_cost = 0

    for i, poi in enumerate(enriched_pois, 1):
        arrive_time = f"{current_time // 60:02d}:{current_time % 60:02d}"
        duration = poi.get("estimated_duration_min", 60)
        queue = poi.get("estimated_queue_minutes", 10)
        leave_time_minutes = current_time + duration + queue

        leave_time = f"{leave_time_minutes // 60:02d}:{leave_time_minutes % 60:02d}"

        print(f"\n{i}. {poi.get('name', '')}")
        print(f"   类目: {poi.get('category', '')}")
        print(f"   时间: {arrive_time} → {leave_time}")
        print(f"   停留: {duration}分钟 + 排队{queue}分钟")
        print(f"   人均: ¥{poi.get('avg_cost', 0)}")

        if i < len(enriched_pois):
            # 计算到下一个POI的交通
            distance_km = poi.get("distance_km", 3.0)
            if distance_km == 0:
                distance_km = 2.0

            travel_minutes = int(distance_km / speed_kmh * 60)
            if transport_mode == TransportMode.CAR:
                travel_minutes += 5  # 找停车位
            elif transport_mode == TransportMode.PUBLIC:
                travel_minutes += 10  # 换乘
            elif transport_mode == TransportMode.TAXI:
                travel_minutes += 3  # 等接单

            travel_cost = round(distance_km * cost_per_km, 1)

            mode_name_display = {
                TransportMode.WALK: "步行",
                TransportMode.BIKE: "骑行",
                TransportMode.CAR: "驾车",
                TransportMode.TAXI: "打车",
                TransportMode.PUBLIC: "公共交通",
            }.get(transport_mode, "步行")

            print(f"   ↓ {mode_name_display}到下一站:")
            print(f"   ↓ 通行时间: {travel_minutes}分钟")
            print(f"   ↓ 距离: {int(distance_km * 1000)}米")
            if travel_cost > 0:
                print(f"   ↓ 交通费用: ¥{travel_cost}")
                total_transport_cost += travel_cost

            current_time = leave_time_minutes + travel_minutes

    print(f"\n方案摘要:")
    print("-" * 40)
    print(f"  总时长: {(current_time - 9*60) / 60:.1f}小时")
    print(f"  总交通费用: ¥{total_transport_cost:.1f}")

    return total_transport_cost


async def main():
    """对比不同交通方式"""

    print("=" * 70)
    print("对比不同交通方式的路线规划效果")
    print("=" * 70)

    modes = [
        (TransportMode.WALK, "步行"),
        (TransportMode.BIKE, "骑行"),
        (TransportMode.CAR, "驾车"),
        (TransportMode.TAXI, "打车"),
        (TransportMode.PUBLIC, "公共交通"),
    ]

    costs = {}
    for mode, name in modes:
        cost = await test_with_mock_intent(mode, name)
        costs[name] = cost
        print("\n")

    # 对比总结
    print("=" * 70)
    print("交通方式对比总结")
    print("=" * 70)
    print("""
| 交通方式 | 速度(km/h) | 费用(元/km) | 总交通费用 | 适合场景 |
|---------|-----------|------------|-----------|---------|
| 步行    | 4.0       | 0.0        | ¥0        | 短距离、慢节奏 |
| 骑行    | 15.0      | 0.0        | ¥0        | 中距离、环保 |
| 驾车    | 35.0      | 0.8        | ¥~5       | 家庭出行、远距离 |
| 打车    | 35.0      | 3.0        | ¥~18      | 方便快捷、无车 |
| 公共交通 | 25.0      | 0.3        | ¥~2       | 经济实惠 |

关键设计点:
1. Intent Agent解析交通方式关键词（开车→car，打车→taxi）
2. Route Agent根据交通方式构建距离矩阵
3. 不同交通方式有不同的通行时间和费用
4. 驾车/打车有额外时间开销（找停车位、等待接单）
5. 交通费用纳入总预算计算
    """)


if __name__ == "__main__":
    asyncio.run(main())