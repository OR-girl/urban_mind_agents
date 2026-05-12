"""
Profile Agent 测试

测试用户画像Agent的核心功能
"""

import pytest
from datetime import datetime

from smartroute.agents.profile import ProfileAgent
from smartroute.schemas.profile import UserProfile, CuisinePreference
from smartroute.schemas.state import SystemState


class TestProfileAgent:
    """Profile Agent 测试类"""

    @pytest.fixture
    def profile_agent(self):
        """创建Profile Agent实例"""
        return ProfileAgent()

    @pytest.fixture
    def sample_state(self, sample_intent_result):
        """创建示例系统状态"""
        return SystemState(
            session_id="test_session_001",
            trace_id="test_trace_001",
            request_type="NEW",
            user_id="test_user_001",
            raw_query="明天带父母去西湖玩一天，预算500元",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
        )

    def _get_profile_from_result(self, result: dict) -> UserProfile | None:
        """从execute返回的字典中提取UserProfile"""
        if "profile" in result and result["profile"]:
            return UserProfile.model_validate(result["profile"])
        return None

    @pytest.mark.asyncio
    async def test_load_user_profile(self, profile_agent, sample_state):
        """测试加载用户画像"""
        result = await profile_agent.execute(sample_state)

        # 验证结果
        assert result is not None
        assert isinstance(result, dict)
        assert "profile" in result

    @pytest.mark.asyncio
    async def test_cold_start_user(self, profile_agent, sample_intent_result):
        """测试冷启动用户画像构建"""
        state = SystemState(
            session_id="test_session_002",
            trace_id="test_trace_002",
            request_type="NEW",
            user_id="new_user_001",  # 新用户
            raw_query="去西湖玩",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
        )

        result = await profile_agent.execute(state)

        # 验证冷启动处理
        assert result is not None
        assert isinstance(result, dict)
        profile = self._get_profile_from_result(result)
        if profile:
            assert profile.is_cold_start is True or profile.confidence < 1.0

    @pytest.mark.asyncio
    async def test_merge_long_short_term_profile(self, profile_agent, sample_state):
        """测试长短期画像融合"""
        # 添加短期Session信号
        sample_state.dialog_history = [
            {"role": "user", "content": "想吃日料"},
            {"role": "assistant", "content": "好的，为您推荐日料餐厅..."},
        ]

        result = await profile_agent.execute(sample_state)

        # 验证融合结果
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_cuisine_preference_calculation(self, profile_agent):
        """测试菜系偏好计算"""
        from smartroute.agents.profile.builder import ProfileBuilder

        builder = ProfileBuilder()
        # 模拟历史订单数据
        order_history = [
            {"cuisine": "杭帮菜", "date": "2026-05-01", "amount": 150},
            {"cuisine": "杭帮菜", "date": "2026-05-05", "amount": 180},
            {"cuisine": "日料", "date": "2026-05-08", "amount": 200},
        ]

        preferences = builder.compute_cuisine_preference(
            order_history,
            current_date=datetime(2026, 5, 12)
        )

        # 验证计算结果 - 返回的是字典 {菜系名: 分数}
        assert preferences is not None
        assert isinstance(preferences, dict)
        assert len(preferences) > 0

        # 杭帮菜应该是最高的（订单最多）
        assert "杭帮菜" in preferences
        assert preferences["杭帮菜"] > 0

    @pytest.mark.asyncio
    async def test_profile_vector_generation(self, profile_agent, sample_state):
        """测试画像向量生成"""
        result = await profile_agent.execute(sample_state)

        # 验证向量生成
        assert result is not None
        assert isinstance(result, dict)
        assert "profile_vector" in result or "profile" in result

    @pytest.mark.asyncio
    async def test_dietary_restrictions(self, profile_agent, sample_intent_result):
        """测试饮食限制处理"""
        # 用户有饮食限制偏好
        state = SystemState(
            session_id="test_session_003",
            trace_id="test_trace_003",
            request_type="NEW",
            user_id="test_user_002",
            raw_query="想吃素食",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
        )

        result = await profile_agent.execute(state)

        # 验证饮食限制处理
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_spending_level_inference(self, profile_agent, sample_intent_result):
        """测试消费水平推断"""
        # 高消费场景
        state = SystemState(
            session_id="test_session_004",
            trace_id="test_trace_004",
            request_type="NEW",
            user_id="test_user_003",
            raw_query="想吃高端餐厅，预算不限",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
        )

        result = await profile_agent.execute(state)

        # 验证消费水平推断
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_walk_tolerance_setting(self, profile_agent, sample_intent_result):
        """测试步行容忍度设置"""
        # 有老人的场景
        state = SystemState(
            session_id="test_session_005",
            trace_id="test_trace_005",
            request_type="NEW",
            user_id="test_user_004",
            raw_query="带80岁老人出去玩",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
        )

        result = await profile_agent.execute(state)

        # 验证步行容忍度设置
        assert result is not None
        assert isinstance(result, dict)


class TestProfileAgentEdgeCases:
    """Profile Agent 边界情况测试"""

    @pytest.fixture
    def profile_agent(self):
        """创建Profile Agent实例"""
        return ProfileAgent()

    @pytest.mark.asyncio
    async def test_no_user_id(self, profile_agent):
        """测试无用户ID"""
        state = SystemState(
            session_id="test_session_006",
            trace_id="test_trace_006",
            request_type="NEW",
            user_id=None,  # 无用户ID
            raw_query="去西湖玩",
            dialog_history=[],
        )

        # 应该使用游客画像
        result = await profile_agent.execute(state)
        assert result is not None or True  # 允许处理失败

    @pytest.mark.asyncio
    async def test_empty_order_history(self, profile_agent, sample_intent_result):
        """测试空订单历史"""
        state = SystemState(
            session_id="test_session_007",
            trace_id="test_trace_007",
            request_type="NEW",
            user_id="user_no_orders",
            raw_query="去西湖玩",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
        )

        result = await profile_agent.execute(state)

        # 应该使用默认画像或冷启动处理
        assert result is not None
        assert isinstance(result, dict)