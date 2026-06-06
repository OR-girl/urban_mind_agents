"""
简化测试：验证交通方式计算逻辑

不使用OR-Tools，直接验证距离矩阵和时间计算
"""

from smartroute.schemas.intent import TransportMode, IntentResult, IntentType, SpatialConstraint, TemporalConstraint, TransportPreference
from smartroute.agents.route.solver import TRANSPORT_SPEEDS, TRANSPORT_COSTS
from smartroute.mock.data import HANGZHOU_POIS, DISTANCE_MATRIX


def test_transport_speed_and_cost():
    """测试不同交通方式的速度和费用"""

    print("=" * 60)
    print("交通方式速度和费用参数")
    print("=" * 60)

    for mode in TransportMode:
        speed = TRANSPORT_SPEEDS.get(mode, 4.0)
        cost = TRANSPORT_COSTS.get(mode, 0.0)
        print(f"{mode.value}: 速度={speed}km/h, 费用={cost}元/km")


def test_distance_calculation():
    """测试距离计算"""

    print("\n" + "=" * 60)
    print("Mock距离矩阵验证")
    print("=" * 60)

    # 取两个POI
    poi_a = HANGZHOU_POIS[0]  # 西湖
    poi_b = HANGZHOU_POIS[1]  # 三潭印月

    print(f"\nPOI A: {poi_a['name']} ({poi_a['poi_id']})")
    print(f"POI B: {poi_b['name']} ({poi_b['poi_id']})")

    # 从DISTANCE_MATRIX获取步行时间
    walk_minutes = DISTANCE_MATRIX.get(poi_a['poi_id'], {}).get(poi_b['poi_id'], 30)
    print(f"步行时间: {walk_minutes}分钟")

    # 计算距离（步行速度4km/h，12分钟≈1km）
    distance_km = walk_minutes / 12.0
    print(f"预估距离: {distance_km:.2f}km")

    # 不同交通方式的通行时间
    print("\n不同交通方式通行时间:")
    for mode in TransportMode:
        speed = TRANSPORT_SPEEDS.get(mode, 4.0)
        travel_time = distance_km / speed * 60

        # 额外开销
        if mode == TransportMode.CAR:
            travel_time += 5
        elif mode == TransportMode.PUBLIC:
            travel_time += 10
        elif mode == TransportMode.TAXI:
            travel_time += 3

        travel_cost = distance_km * TRANSPORT_COSTS.get(mode, 0.0)

        print(f"  {mode.value}: {int(travel_time)}分钟, ¥{travel_cost:.1f}")


def test_timeline_building():
    """测试时间轴构建"""

    print("\n" + "=" * 60)
    print("时间轴构建验证")
    print("=" * 60)

    from smartroute.agents.route.multi_plan import MultiPlanGenerator

    # 模拟POI序列
    pois = [
        {"poi_id": "poi_xihu_001", "name": "西湖", "category": "景点", "estimated_duration_min": 90, "avg_cost": 0},
        {"poi_id": "poi_santan_002", "name": "三潭印月", "category": "景点", "estimated_duration_min": 60, "avg_cost": 55},
        {"poi_id": "poi_leifeng_003", "name": "雷峰塔", "category": "景点", "estimated_duration_min": 60, "avg_cost": 40},
    ]

    # 不同交通方式
    modes = [
        (TransportMode.WALK, "步行"),
        (TransportMode.CAR, "驾车"),
        (TransportMode.TAXI, "打车"),
    ]

    for mode, mode_name in modes:
        print(f"\n交通方式: {mode_name}")

        intent = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.9,
            spatial=SpatialConstraint(city="杭州"),
            temporal=TemporalConstraint(
                date="2026-06-05",
                start_time="09:00",
                end_time="18:00",
            ),
            transport=TransportPreference(primary_mode=mode),
            raw_query="测试",
        )

        generator = MultiPlanGenerator(plan_configs=[{"name": "test", "tagline": "test", "weights": {}}], max_overlap_ratio=0.5)

        timeline = generator._build_timeline(pois, intent)

        total_transport_cost = 0
        for i, item in enumerate(timeline, 1):
            print(f"{i}. {item['poi_name']}: {item['arrive_time']} → {item['leave_time']}")
            transport = item.get("transport_to_next")
            if transport:
                print(f"   → {transport['mode']}, {transport['duration_min']}分钟, {transport['distance_m']}米, ¥{transport['cost']}")
                total_transport_cost += transport['cost']

        print(f"   总交通费用: ¥{total_transport_cost:.1f}")


if __name__ == "__main__":
    test_transport_speed_and_cost()
    test_distance_calculation()
    test_timeline_building()