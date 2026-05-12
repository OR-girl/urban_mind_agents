"""
Schema 数据模型测试

测试所有核心Schema的正确性和验证逻辑
"""

import pytest
from pydantic import ValidationError

from smartroute.schemas.intent import (
    IntentResult,
    IntentType,
    SpatialConstraint,
    TemporalConstraint,
    PartyInfo,
    Preferences,
    BudgetInfo,
    TimeFlexibility,
    POIStyle,
    BudgetLevel,
)
from smartroute.schemas.profile import (
    UserProfile,
    CuisinePreference,
)
from smartroute.schemas.state import SystemState
from smartroute.schemas.response import FinalResponse


class TestIntentSchemas:
    """Intent Schema 测试类"""

    def test_intent_result_creation(self):
        """测试IntentResult创建"""
        intent = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.95,
            spatial=SpatialConstraint(
                city="杭州",
                region="西湖区",
            ),
            temporal=TemporalConstraint(
                date="2026-05-13",
            ),
            raw_query="明天去西湖玩",
        )

        assert intent.intent_type == IntentType.TOUR
        assert intent.confidence == 0.95
        assert intent.spatial.city == "杭州"

    def test_intent_result_validation_confidence(self):
        """测试IntentResult置信度验证"""
        # 置信度应该在0-1之间
        with pytest.raises(ValidationError):
            IntentResult(
                intent_type=IntentType.TOUR,
                confidence=1.5,  # 超出范围
                spatial=SpatialConstraint(city="杭州"),
                temporal=TemporalConstraint(date="2026-05-13"),
                raw_query="测试",
            )

    def test_spatial_constraint_required_fields(self):
        """测试SpatialConstraint必填字段"""
        # city是必填的
        with pytest.raises(ValidationError):
            SpatialConstraint()

        # 有city应该成功
        constraint = SpatialConstraint(city="杭州")
        assert constraint.city == "杭州"

    def test_temporal_constraint_defaults(self):
        """测试TemporalConstraint默认值"""
        constraint = TemporalConstraint(date="2026-05-13")

        assert constraint.start_time == "09:00"
        assert constraint.end_time == "18:00"
        assert constraint.duration_hours == 8.0
        assert constraint.flexibility == TimeFlexibility.FLEXIBLE

    def test_party_info_defaults(self):
        """测试PartyInfo默认值"""
        party = PartyInfo()

        assert party.size == 1
        assert party.composition == []
        assert party.child_ages == []

    def test_needs_clarification_method(self):
        """测试needs_clarification方法"""
        # 高置信度，无歧义
        intent1 = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.95,
            spatial=SpatialConstraint(city="杭州"),
            temporal=TemporalConstraint(date="2026-05-13"),
            raw_query="测试",
        )
        assert intent1.needs_clarification() is False

        # 低置信度
        intent2 = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.6,
            spatial=SpatialConstraint(city="杭州"),
            temporal=TemporalConstraint(date="2026-05-13"),
            raw_query="测试",
        )
        assert intent2.needs_clarification() is True

        # 有歧义标记
        intent3 = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.95,
            spatial=SpatialConstraint(city="杭州"),
            temporal=TemporalConstraint(date="2026-05-13"),
            ambiguity_flags=["city_missing"],
            raw_query="测试",
        )
        assert intent3.needs_clarification() is True

    def test_get_constraint_summary_method(self):
        """测试get_constraint_summary方法"""
        intent = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.95,
            spatial=SpatialConstraint(
                city="杭州",
                region="西湖区",
            ),
            temporal=TemporalConstraint(
                date="2026-05-13",
                start_time="09:00",
                end_time="18:00",
            ),
            party=PartyInfo(size=3),
            raw_query="测试",
        )

        summary = intent.get_constraint_summary()

        assert "杭州" in summary
        assert "西湖区" in summary
        assert "2026-05-13" in summary
        assert "09:00-18:00" in summary


class TestProfileSchemas:
    """Profile Schema 测试类"""

    def test_user_profile_creation(self):
        """测试UserProfile创建"""
        profile = UserProfile(
            user_id="user_001",
            cuisine_preferences=[
                CuisinePreference(cuisine_type="杭帮菜", score=0.9, order_count=10),
            ],
        )

        assert profile.user_id == "user_001"
        assert len(profile.cuisine_preferences) == 1

    def test_user_profile_defaults(self):
        """测试UserProfile默认值"""
        profile = UserProfile(user_id="user_001")

        assert profile.is_cold_start is False
        assert profile.spending_level == "mid"
        assert profile.avg_spend_per_person == 100.0
        assert profile.walk_tolerance_km == 5.0

    def test_cuisine_preference_validation(self):
        """测试CuisinePreference验证"""
        # score应该在0-1之间
        with pytest.raises(ValidationError):
            CuisinePreference(
                cuisine_type="杭帮菜",
                score=1.5,  # 超出范围
                order_count=10,
            )


class TestStateSchemas:
    """State Schema 测试类"""

    def test_system_state_creation(self):
        """测试SystemState创建"""
        state = SystemState(
            session_id="session_001",
            trace_id="trace_001",
            request_type="NEW",
            raw_query="测试查询",
        )

        assert state.session_id == "session_001"
        assert state.request_type == "NEW"

    def test_system_state_optional_fields(self):
        """测试SystemState可选字段"""
        state = SystemState(
            session_id="session_001",
            trace_id="trace_001",
            request_type="NEW",
            raw_query="测试",
        )

        # 可选字段应该为None或默认值
        assert state.user_id is None
        assert state.intent is None
        assert state.profile is None
        assert state.candidates is None


class TestResponseSchemas:
    """Response Schema 测试类"""

    def test_final_response_creation(self):
        """测试FinalResponse创建"""
        response = FinalResponse(
            session_id="session_001",
            summary="为您定制了3套方案",
            plans=[],
        )

        assert response.session_id == "session_001"
        assert response.summary == "为您定制了3套方案"


class TestEnumSchemas:
    """Enum Schema 测试类"""

    def test_intent_type_enum(self):
        """测试IntentType枚举"""
        assert IntentType.TOUR == "tour"
        assert IntentType.FOOD_TOUR == "food_tour"
        assert IntentType.CITY_WALK == "city_walk"

    def test_time_flexibility_enum(self):
        """测试TimeFlexibility枚举"""
        assert TimeFlexibility.STRICT == "strict"
        assert TimeFlexibility.FLEXIBLE == "flexible"

    def test_budget_level_enum(self):
        """测试BudgetLevel枚举"""
        assert BudgetLevel.BUDGET == "budget"
        assert BudgetLevel.MID == "mid"
        assert BudgetLevel.PREMIUM == "premium"
        assert BudgetLevel.LUXURY == "luxury"


class TestSchemaSerialization:
    """Schema 序列化测试"""

    def test_intent_result_serialization(self):
        """测试IntentResult序列化"""
        intent = IntentResult(
            intent_type=IntentType.TOUR,
            confidence=0.95,
            spatial=SpatialConstraint(city="杭州"),
            temporal=TemporalConstraint(date="2026-05-13"),
            raw_query="测试",
        )

        # 序列化为JSON
        json_data = intent.model_dump()
        assert json_data["intent_type"] == "tour"
        assert json_data["confidence"] == 0.95

        # 从JSON反序列化
        intent2 = IntentResult.model_validate(json_data)
        assert intent2.intent_type == IntentType.TOUR

    def test_user_profile_serialization(self):
        """测试UserProfile序列化"""
        profile = UserProfile(
            user_id="user_001",
            cuisine_preferences=[
                CuisinePreference(cuisine_type="杭帮菜", score=0.9, order_count=10),
            ],
        )

        json_data = profile.model_dump()
        assert json_data["user_id"] == "user_001"
        assert len(json_data["cuisine_preferences"]) == 1
