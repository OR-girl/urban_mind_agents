"""
测试脚本 - 体验 Intent Agent 和 Profile Agent

使用方式:
  python test_agents.py --intent      # 测试 Intent Agent
  python test_agents.py --profile     # 测试 Profile Agent
  python test_agents.py --interactive # 交互式对话
  python test_agents.py               # 全部测试
"""

import argparse
import asyncio
import sys
sys.path.insert(0, 'src')

from smartroute.agents.intent.agent import IntentAgent
from smartroute.agents.profile.agent import ProfileAgent
from smartroute.schemas.state import SystemState


async def test_intent_agent():
    """测试 Intent Agent"""
    print("\n" + "="*60)
    print("【Intent Agent 测试】")
    print("="*60)

    agent = IntentAgent()

    test_queries = [
        "明天带父母去西湖玩一天",
        "这周六和女朋友约会，想去小众一点的地方",
        "下周出差杭州，中午有空逛一下，预算有限",
    ]

    for query in test_queries:
        print(f"\n用户输入: {query}")
        print("-"*40)

        state = SystemState(
            session_id="test_intent",
            trace_id="test_trace",
            user_id="user_001",
            raw_query=query,
            request_type="NEW",
            dialog_history=[],
        )

        result = await agent.execute(state)

        intent = result.get("intent", {})
        clarify_needed = result.get("clarification_needed", False)
        clarify_question = result.get("clarification_question", "")

        print(f"意图类型: {intent.get('intent_type', 'N/A')}")
        print(f"置信度: {intent.get('confidence', 0):.2f}")

        spatial = intent.get("spatial", {})
        print(f"城市: {spatial.get('city', 'N/A')}")
        if spatial.get("anchor_poi"):
            print(f"锚点POI: {spatial.get('anchor_poi')}")

        temporal = intent.get("temporal", {})
        print(f"日期: {temporal.get('date', 'N/A')}")
        print(f"时间段: {temporal.get('start_time', 'N/A')} - {temporal.get('end_time', 'N/A')}")
        print(f"时长: {temporal.get('duration_hours', 0)}小时")

        party = intent.get("party", {})
        if party.get("size", 1) > 1:
            print(f"人数: {party.get('size')}人")
            if party.get("composition"):
                print(f"构成: {party.get('composition')}")

        preferences = intent.get("preferences", {})
        if preferences.get("themes"):
            print(f"主题偏好: {preferences.get('themes')}")

        budget = intent.get("budget", {})
        if budget.get("level"):
            print(f"预算档位: {budget.get('level')}")

        if intent.get("inferred_fields"):
            print(f"规则推断: {intent.get('inferred_fields')}")

        if clarify_needed:
            print(f"\n⚠️ 需要反问: {clarify_question}")


async def test_profile_agent():
    """测试 Profile Agent"""
    print("\n" + "="*60)
    print("【Profile Agent 测试】")
    print("="*60)

    agent = ProfileAgent()

    test_users = [
        ("user_001", "年轻学生"),
        ("user_002", "美食探索者"),
        ("user_003", "家庭用户"),
        ("user_005", "银发族"),
        ("user_007", "商务人士"),
    ]

    for user_id, expected_type in test_users:
        print(f"\n用户ID: {user_id} (预期: {expected_type})")
        print("-"*40)

        state = SystemState(
            session_id="test_profile",
            trace_id="test_trace",
            user_id=user_id,
            raw_query="去西湖玩",
            request_type="NEW",
        )

        result = await agent.execute(state)
        profile = result.get("profile", {})

        print(f"消费档位: {profile.get('spending_level', 'N/A')}")
        print(f"人均消费: {profile.get('avg_spend_per_person', 0):.0f}元")
        print(f"步行耐受: {profile.get('walk_tolerance_km', 0):.1f}km")
        print(f"小众偏好: {profile.get('niche_preference_score', 0):.2f} (0=网红, 1=小众)")
        print(f"夜猫子: {profile.get('is_night_owl', False)}")
        print(f"偏好出发时间: {profile.get('preferred_start_hour', 9)}点")

        scenes = profile.get("scene_preference", {})
        if scenes:
            top_scenes = sorted(scenes.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"场景偏好: {[f'{s[0]}({s[1]:.1f})' for s in top_scenes]}")

        cuisines = profile.get("cuisine_preferences", [])
        if cuisines:
            print(f"菜系偏好: {[c['cuisine_type'] for c in cuisines[:4]]}")

        visited = profile.get("visited_poi_ids", [])
        if visited:
            print(f"去过的地方: {visited[:4]}")

        restrictions = profile.get("dietary_restrictions", [])
        if restrictions:
            print(f"饮食禁忌: {restrictions}")


async def interactive_chat():
    """交互式对话体验"""
    print("\n" + "="*60)
    print("【交互式对话体验】")
    print("="*60)
    print("输入 'quit' 退出")

    intent_agent = IntentAgent()
    profile_agent = ProfileAgent()

    session_id = "interactive_session"

    try:
        user_id = input("请输入用户ID (如 user_001): ").strip() or "user_001"
    except EOFError:
        user_id = "user_001"

    print(f"\n正在加载用户 {user_id} 的画像...")
    profile_state = SystemState(
        session_id=session_id,
        trace_id="trace_001",
        user_id=user_id,
        raw_query="",
        request_type="NEW",
    )
    profile_result = await profile_agent.execute(profile_state)
    profile = profile_result.get("profile", {})

    print(f"画像加载完成:")
    print(f"  消费档位: {profile.get('spending_level')}")
    print(f"  人均消费: {profile.get('avg_spend_per_person', 0):.0f}元")
    print(f"  步行耐受: {profile.get('walk_tolerance_km', 0):.1f}km")
    print(f"  小众偏好: {profile.get('niche_preference_score', 0):.2f}")

    dialog_history = []
    existing_intent = None  # 保存已有意图

    # 检测修改意图的关键词
    modify_keywords = ["增加", "加", "加上", "添加", "去掉", "删除", "换", "改成", "修改", "调整"]

    while True:
        print("\n" + "-"*40)
        try:
            query = input("请输入您的需求: ").strip()
        except EOFError:
            print("无法获取输入，退出交互模式")
            break

        if query == "quit":
            break

        if not query:
            continue

        # 清理可能的乱码字符
        query = query.encode('utf-8', errors='replace').decode('utf-8')

        # 判断请求类型
        request_type = "NEW"
        if existing_intent:
            for kw in modify_keywords:
                if kw in query:
                    request_type = "MODIFY"
                    break

        intent_state = SystemState(
            session_id=session_id,
            trace_id="trace_002",
            user_id=user_id,
            raw_query=query,
            request_type=request_type,
            dialog_history=dialog_history,
            intent=existing_intent,  # 传递已有意图
        )

        intent_result = await intent_agent.execute(intent_state)
        intent = intent_result.get("intent", {})

        # 更新已有意图（用于下一轮）
        existing_intent = intent

        print(f"\n【Intent Agent 分析结果】")
        print(f"请求类型: {request_type}")
        print(f"意图类型: {intent.get('intent_type')}")
        print(f"置信度: {intent.get('confidence', 0):.2f}")

        spatial = intent.get("spatial", {})
        print(f"城市: {spatial.get('city')}")
        if spatial.get("anchor_poi"):
            print(f"锚点POI: {spatial.get('anchor_poi')}")

        temporal = intent.get("temporal", {})
        print(f"日期: {temporal.get('date')}")
        print(f"出发时间: {temporal.get('start_time')}")
        print(f"结束时间: {temporal.get('end_time')}")
        print(f"时长: {temporal.get('duration_hours', 0)}小时")

        preferences = intent.get("preferences", {})
        if preferences.get("must_have"):
            print(f"必须包含: {preferences.get('must_have')}")
        if preferences.get("themes"):
            print(f"主题: {preferences.get('themes')}")

        # 显示 POI 时间安排
        poi_schedule = intent.get("poi_schedule", [])
        if poi_schedule:
            print(f"\n【POI 时间安排】")
            # 检查是否有顺序信息
            has_sequence = any(item.get("sequence") for item in poi_schedule)
            if has_sequence:
                # 按顺序排序显示
                sorted_schedule = sorted(poi_schedule, key=lambda x: x.get("sequence", 999))
                for item in sorted_schedule:
                    poi_name = item.get("poi_name", "未知")
                    seq = item.get("sequence", "")
                    time_slot = item.get("time_slot", "")
                    start_time = item.get("start_time", "")
                    msg = f"  {seq}. {poi_name}" if seq else f"  • {poi_name}"
                    if time_slot:
                        msg += f" [{time_slot}]"
                    if start_time:
                        msg += f" ({start_time})"
                    print(msg)
            else:
                # 无顺序信息，直接显示
                for item in poi_schedule:
                    poi_name = item.get("poi_name", "未知")
                    time_slot = item.get("time_slot", "")
                    start_time = item.get("start_time", "")
                    msg = f"  • {poi_name}"
                    if time_slot:
                        msg += f" [{time_slot}]"
                    if start_time:
                        msg += f" ({start_time})"
                    print(msg)

        party = intent.get("party", {})
        if party.get("composition"):
            print(f"出行人员: {party.get('composition')}")

        if intent.get("inferred_fields"):
            print(f"规则推断: {intent.get('inferred_fields')}")

        if intent_result.get("clarification_needed"):
            print(f"\n⚠️ 系统反问: {intent_result.get('clarification_question')}")

        # 记录对话历史
        dialog_history.append({"role": "user", "content": query})

        print(f"\n【您的画像将影响推荐】")
        cuisines = profile.get("cuisine_preferences", [])
        if cuisines:
            print(f"  推荐餐厅时会优先: {[c['cuisine_type'] for c in cuisines[:3]]}")

        visited = profile.get("visited_poi_ids", [])
        if visited:
            print(f"  会避开您去过的地方: {visited[:3]}")


def main():
    parser = argparse.ArgumentParser(description="SmartRoute Agent 测试")
    parser.add_argument("--intent", action="store_true", help="测试 Intent Agent")
    parser.add_argument("--profile", action="store_true", help="测试 Profile Agent")
    parser.add_argument("--interactive", action="store_true", help="交互式对话")

    args = parser.parse_args()

    if args.intent:
        asyncio.run(test_intent_agent())
    elif args.profile:
        asyncio.run(test_profile_agent())
    elif args.interactive:
        asyncio.run(interactive_chat())
    else:
        # 默认运行全部
        asyncio.run(test_intent_agent())
        asyncio.run(test_profile_agent())


if __name__ == "__main__":
    main()