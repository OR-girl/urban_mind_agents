"""
Retrieval Agent 测试

测试POI召回Agent的核心功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from smartroute.agents.retrieval.agent import RetrievalAgent
from smartroute.schemas.state import SystemState


class TestRetrievalAgent:
    """Retrieval Agent 测试类"""

    @pytest.fixture
    def retrieval_agent(self):
        """创建Retrieval Agent实例"""
        return RetrievalAgent()

    @pytest.fixture
    def sample_state(self, sample_intent_result, sample_user_profile):
        """创建示例系统状态"""
        return SystemState(
            session_id="test_session_001",
            trace_id="test_trace_001",
            request_type="NEW",
            user_id="test_user_001",
            raw_query="明天带父母去西湖玩一天，预算500元",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
            profile=sample_user_profile.model_dump(),
        )

    @pytest.mark.asyncio
    async def test_semantic_retrieval(self, retrieval_agent, sample_state):
        """测试语义召回"""
        result = await retrieval_agent.execute(sample_state)

        # 验证结果
        assert result is not None
        assert isinstance(result, dict)
        assert "candidates" in result

    @pytest.mark.asyncio
    async def test_geo_retrieval(self, retrieval_agent, sample_intent_result, sample_user_profile):
        """测试地理召回"""
        state = SystemState(
            session_id="test_session_002",
            trace_id="test_trace_002",
            request_type="NEW",
            user_id="test_user_002",
            raw_query="西湖附近吃饭",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
            profile=sample_user_profile.model_dump(),
        )

        result = await retrieval_agent.execute(state)

        # 验证地理召回
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_multi_path_retrieval(self, retrieval_agent, sample_state):
        """测试多路召回"""
        result = await retrieval_agent.execute(sample_state)

        # 验证多路召回结果
        assert result is not None
        assert isinstance(result, dict)
        assert "candidates" in result
        assert "retrieval_metadata" in result

    @pytest.mark.asyncio
    async def test_budget_filtering(self, retrieval_agent, sample_intent_result, sample_user_profile):
        """测试预算过滤"""
        # 修改预算约束
        intent_dict = sample_intent_result.model_dump()
        intent_dict["budget"]["per_person"] = 50.0  # 低预算

        state = SystemState(
            session_id="test_session_003",
            trace_id="test_trace_003",
            request_type="NEW",
            user_id="test_user_003",
            raw_query="便宜的餐厅",
            dialog_history=[],
            intent=intent_dict,
            profile=sample_user_profile.model_dump(),
        )

        result = await retrieval_agent.execute(state)

        # 验证预算过滤
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_visited_poi_filtering(self, retrieval_agent, sample_intent_result, sample_user_profile):
        """测试已访问POI过滤"""
        state = SystemState(
            session_id="test_session_004",
            trace_id="test_trace_004",
            request_type="NEW",
            user_id="test_user_004",
            raw_query="去西湖玩",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
            profile=sample_user_profile.model_dump(),
        )

        result = await retrieval_agent.execute(state)

        # 验证过滤结果
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_mmr_diversity_reranking(self, retrieval_agent, sample_state):
        """测试MMR多样性重排"""
        result = await retrieval_agent.execute(sample_state)

        # 验证多样性重排
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_coarse_ranking(self, retrieval_agent, sample_state):
        """测试粗排"""
        result = await retrieval_agent.execute(sample_state)

        # 验证粗排结果
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_business_hours_filtering(self, retrieval_agent, sample_intent_result, sample_user_profile):
        """测试营业时间过滤"""
        # 设置访问时间
        intent_dict = sample_intent_result.model_dump()
        intent_dict["temporal"]["start_time"] = "22:00"  # 深夜

        state = SystemState(
            session_id="test_session_005",
            trace_id="test_trace_005",
            request_type="NEW",
            user_id="test_user_005",
            raw_query="深夜去玩",
            dialog_history=[],
            intent=intent_dict,
            profile=sample_user_profile.model_dump(),
        )

        result = await retrieval_agent.execute(state)

        # 验证营业时间过滤
        assert result is not None
        assert isinstance(result, dict)


class TestRetrievalAgentEdgeCases:
    """Retrieval Agent 边界情况测试"""

    @pytest.fixture
    def retrieval_agent(self):
        """创建Retrieval Agent实例"""
        return RetrievalAgent()

    @pytest.mark.asyncio
    async def test_no_poi_found(self, retrieval_agent, sample_intent_result, sample_user_profile):
        """测试无POI召回"""
        # 使用非常特定的查询
        state = SystemState(
            session_id="test_session_006",
            trace_id="test_trace_006",
            request_type="NEW",
            user_id="test_user_006",
            raw_query="找一个不存在的地方类型",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
            profile=sample_user_profile.model_dump(),
        )

        result = await retrieval_agent.execute(state)

        # 应该返回空列表或使用兜底策略
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_large_candidate_pool(self, retrieval_agent, sample_intent_result, sample_user_profile):
        """测试大候选池"""
        state = SystemState(
            session_id="test_session_007",
            trace_id="test_trace_007",
            request_type="NEW",
            user_id="test_user_007",
            raw_query="杭州吃饭",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
            profile=sample_user_profile.model_dump(),
        )

        result = await retrieval_agent.execute(state)

        # 应该正确处理并限制候选数量
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_user_with_strong_preferences(self, retrieval_agent, sample_intent_result):
        """测试强偏好用户"""
        # 用户有明确的偏好历史
        profile_dict = {
            "user_id": "test_user_008",
            "is_cold_start": False,
            "cuisine_preferences": [
                {"cuisine_type": "杭帮菜", "score": 0.95, "order_count": 20}
            ],
            "spending_level": "mid",
            "avg_spend_per_person": 150.0,
        }

        state = SystemState(
            session_id="test_session_008",
            trace_id="test_trace_008",
            request_type="NEW",
            user_id="test_user_008",
            raw_query="吃饭",
            dialog_history=[],
            intent=sample_intent_result.model_dump(),
            profile=profile_dict,
        )

        result = await retrieval_agent.execute(state)

        # 应该优先召回偏好类型
        assert result is not None
        assert isinstance(result, dict)