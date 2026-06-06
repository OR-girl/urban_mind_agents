"""
完整流程测试：从意图识别到路线生成

展示完整的Agent串联流程：
1. Intent Agent → 解析用户意图（包含交通方式）
2. Retrieval Agent → 多路召回候选POI
3. Route Agent → 根据交通方式生成路线方案
"""

import asyncio
from typing import Any

from smartroute.schemas.state import SystemState
from smartroute.schemas.profile import UserProfile, CuisinePreference


async def test_full_pipeline(query: str, transport_query: str = None):
    """
    测试完整流程

    Args:
        query: 用户输入
        transport_query: 交通方式相关输入（可选）
    """
    print("=" * 70)
    print("完整流程测试：从意图识别到路线生成")
    print("=" * 70)
    print(f"\n用户输入: {query}")

    # Step 1: Intent Agent - 意图识别
    print("\n" + "=" * 70)
    print("Step 1: Intent Agent - 意图识别")
    print("=" * 70)

    from smartroute.agents.intent import IntentAgent
    intent_agent = IntentAgent()

    initial_state = SystemState(
        session_id="test_session_001",
        trace_id="test_trace_001",
        request_type="NEW",
        user_id="test_user_001",
        raw_query=query,
        dialog_history=[],
    )

    intent_result = await intent_agent.execute(initial_state)
    intent = intent_result.get("intent")

    if intent:
        print("\n意图识别结果:")
        print("-" * 40)
        print(f"  意图类型: {intent.get('intent_type', '')}")
        print(f"  城市: {intent.get('spatial', {}).get('city', '')}")
        print(f"  锚点POI: {intent.get('spatial', {}).get('anchor_poi', '')}")
        print(f"  日期: {intent.get('temporal', {}).get('date', '')}")
        print(f"  时间: {intent.get('temporal', {}).get('start_time', '')} - {intent.get('temporal', {}).get('end_time', '')}")
        print(f"  人数: {intent.get('party', {}).get('size', 1)}人")
        print(f"  必须包含: {intent.get('preferences', {}).get('must_have', [])}")
        print(f"  预算: {intent.get('budget', {}).get('per_person', 0)}元/人")

        # 交通方式（重点展示）
        transport = intent.get('transport', {})
        print(f"\n  【交通方式】")
        print(f"  主要交通方式: {transport.get('primary_mode', 'walk')}")
        if transport.get('secondary_mode'):
            print(f"  备选交通方式: {transport.get('secondary_mode')}")
        if transport.get('avoid_modes'):
            print(f"  避免的交通方式: {transport.get('avoid_modes')}")
        if transport.get('car_available'):
            print(f"  是否有车: {transport.get('car_available')}")

        # POI时间安排
        poi_schedule = intent.get('poi_schedule', [])
        if poi_schedule:
            print(f"\n  【POI时间安排】")
            for item in poi_schedule:
                print(f"    - {item.get('poi_name')}: {item.get('time_slot', '未指定时间段')}")
                if item.get('sequence'):
                    print(f"      顺序: 第{item.get('sequence')}站")

    # Step 2: Profile Agent - 用户画像（模拟）
    print("\n" + "=" * 70)
    print("Step 2: Profile Agent - 用户画像（模拟）")
    print("=" * 70)

    profile = UserProfile(
        user_id="test_user_001",
        is_cold_start=False,
        cuisine_preferences=[
            CuisinePreference(cuisine_type="杭帮菜", score=0.8, order_count=5),
        ],
        spending_level="mid",
        avg_spend_per_person=150.0,
        scene_preferences={"亲子": 0.7, "自然风光": 0.5},
        walk_tolerance_km=3.0,
        dietary_restrictions=[],
        visited_poi_ids=["poi_xihu_001"],
        niche_preference_score=0.3,
    )

    print("\n用户画像:")
    print("-" * 40)
    print(f"  消费档位: {profile.spending_level}")
    print(f"  场景偏好: {profile.scene_preferences}")
    print(f"  已去过: {profile.visited_poi_ids}")

    # Step 3: Retrieval Agent - 多路召回
    print("\n" + "=" * 70)
    print("Step 3: Retrieval Agent - 多路召回")
    print("=" * 70)

    from smartroute.agents.retrieval import RetrievalAgent
    retrieval_agent = RetrievalAgent()

    # 更新state
    initial_state.intent = intent
    initial_state.profile = profile.model_dump()

    retrieval_result = await retrieval_agent.execute(initial_state)
    candidates = retrieval_result.get("candidates", [])
    metadata = retrieval_result.get("retrieval_metadata", {})

    print(f"\n召回统计:")
    print("-" * 40)
    print(f"  召回路径: {metadata.get('path_counts', {})}")
    print(f"  最终候选: {metadata.get('final_count', 0)}个")

    if candidates:
        print(f"\n候选POI列表（前10个）:")
        print("-" * 40)
        for i, poi in enumerate(candidates[:10], 1):
            print(f"{i}. {poi.get('name', '')}")
            print(f"   类目: {poi.get('category', '')} | 评分: {poi.get('rating', 0)} | 人均: ¥{poi.get('avg_cost', 0)}")
            print(f"   距离: {poi.get('distance_km', 0):.1f}km | 召回来源: {poi.get('retrieval_path', '')}")

    # Step 4: UGC Agent - 评论分析（模拟）
    print("\n" + "=" * 70)
    print("Step 4: UGC Agent - 评论分析（模拟）")
    print("=" * 70)

    # 模拟UGC分析结果
    enriched_pois = []
    for poi in candidates[:8]:
        poi_copy = poi.copy()
        poi_copy["estimated_duration_min"] = 60 if "景点" in poi.get("category", "") else 90
        poi_copy["estimated_queue_minutes"] = 15 if poi.get("rating", 0) >= 4.5 else 5
        poi_copy["ugc_sentiment"] = {"positive": 4.2, "neutral": 3.5}
        poi_copy["highlights"] = ["适合亲子", "风景优美"][:2]
        poi_copy["warnings"] = []
        enriched_pois.append(poi_copy)

    print(f"\nEnriched POI数量: {len(enriched_pois)}")

    # Step 5: Route Agent - 路线规划
    print("\n" + "=" * 70)
    print("Step 5: Route Agent - 路线规划")
    print("=" * 70)

    from smartroute.agents.route import RoutePlanningAgent
    route_agent = RoutePlanningAgent()

    initial_state.enriched_pois = enriched_pois

    route_result = await route_agent.execute(initial_state)
    routes = route_result.get("routes", [])

    if routes:
        print(f"\n生成{len(routes)}个路线方案:")
        print("=" * 70)

        for i, route in enumerate(routes, 1):
            print(f"\n方案{i}: {route.get('name', '')}")
            print(f"特点: {route.get('tagline', '')}")
            print("-" * 40)

            timeline = route.get("timeline", [])
            total_transport_cost = 0

            print("\n时间轴:")
            for j, item in enumerate(timeline, 1):
                print(f"\n{j}. {item.get('poi_name', '')}")
                print(f"   类目: {item.get('category', '')}")
                print(f"   时间: {item.get('arrive_time', '')} → {item.get('leave_time', '')}")
                print(f"   停留: {item.get('duration_min', 0)}分钟")
                print(f"   门票/人均: ¥{item.get('estimated_cost', 0)}")

                transport = item.get("transport_to_next")
                if transport:
                    print(f"   ────────────────────────")
                    print(f"   ↓ 交通方式: {transport.get('mode', '')}")
                    print(f"   ↓ 通行时间: {transport.get('duration_min', 0)}分钟")
                    print(f"   ↓ 距离: {transport.get('distance_m', 0)}米")
                    cost = transport.get('cost', 0)
                    if cost > 0:
                        print(f"   ↓ 交通费用: ¥{cost}")
                        total_transport_cost += cost

            summary = route.get("summary", {})
            print(f"\n方案摘要:")
            print("-" * 40)
            print(f"  总时长: {summary.get('total_duration_h', 0)}小时")
            print(f"  总距离: {summary.get('total_distance_km', 0)}km")
            print(f"  交通费用: ¥{total_transport_cost:.1f}")
            print(f"  门票/餐饮费用: ¥{summary.get('total_cost', 0)}")

    # 总结
    print("\n" + "=" * 70)
    print("流程总结")
    print("=" * 70)
    print("""
Agent串联流程:
┌─────────────┐
│ 用户输入    │ "我们一家三口开车去西湖玩一天"
└──────┬──────┘
       ↓
┌─────────────┐
│ Intent Agent│ 解析意图 → 交通方式: car
│             │ 城市: 杭州 | 锚点: 西湖
│             │ 时间: 09:00-18:00 | 人数: 3人
└──────┬──────┘
       ↓ IntentResult.transport.primary_mode = "car"
       ↓
┌─────────────┐
│ Retrieval   │ 5路召回 → 16个候选POI
│ Agent       │ 过滤已去过的西湖
└──────┬──────┘
       ↓ candidates
       ↓
┌─────────────┐
│ UGC Agent   │ 评论分析 → enriched_pois
└──────┬──────┘
       ↓ enriched_pois
       ↓
┌─────────────┐
│ Route Agent │ 根据交通方式(car)构建距离矩阵
│             │ 驾车速度35km/h, 费用0.8元/km
│             │ OR-Tools求解 → 3个路线方案
└──────┬──────┘
       ↓ 路线方案（包含驾车时间、交通费用）
       ↓
┌─────────────┐
│ Presentation│ 生成最终输出
└─────────────┘
    """)


async def main():
    """测试不同场景"""

    # 场景1: 驾车出游
    print("\n" + "=" * 80)
    print("场景1: 驾车出游")
    print("=" * 80)

    query1 = "我们一家三口开车去杭州西湖玩一天，孩子6岁，希望中午找个餐厅吃饭，下午轻松一点"
    await test_full_pipeline(query1)

    # 场景2: 步行漫步
    print("\n" + "=" * 80)
    print("场景2: 步行漫步（默认）")
    print("=" * 80)

    query2 = "明天一个人去西湖逛逛，上午看看风景，下午找个茶楼喝茶"
    await test_full_pipeline(query2)


if __name__ == "__main__":
    asyncio.run(main())