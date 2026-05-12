"""
SmartRoute Agent 意图相关 Schema 定义

IntentResult 及相关子结构
"""

from enum import Enum

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """意图类型"""

    TOUR = "tour"               # 景点游览
    FOOD_TOUR = "food_tour"     # 美食探索
    CITY_WALK = "city_walk"     # 城市漫步
    BUSINESS = "business"       # 商务出行
    DATE = "date"               # 约会
    FAMILY = "family"           # 家庭出游
    NATURE = "nature"           # 自然探索
    CULTURE = "culture"         # 文化历史


class TimeFlexibility(str, Enum):
    """时间灵活性"""

    STRICT = "strict"           # 时间严格（商务等）
    FLEXIBLE = "flexible"       # 时间灵活


class POIStyle(str, Enum):
    """POI 风格偏好"""

    POPULAR = "popular"         # 网红热门
    NICHE = "niche"             # 小众冷门
    BALANCED = "balanced"       # 平衡


class BudgetLevel(str, Enum):
    """预算档位"""

    BUDGET = "budget"           # 经济实惠
    MID = "mid"                 # 中档
    PREMIUM = "premium"         # 高档
    LUXURY = "luxury"           # 奢华


class SpatialConstraint(BaseModel):
    """空间约束"""

    city: str = Field(
        ...,
        description="城市（必填）",
    )
    region: str | None = Field(
        default=None,
        description="区域/商圈",
    )
    anchor_poi: str | None = Field(
        default=None,
        description="锚点 POI（如'西湖'）",
    )
    radius_km: float | None = Field(
        default=None,
        description="搜索半径（公里）",
    )
    exclude_areas: list[str] = Field(
        default_factory=list,
        description="排除区域",
    )


class TemporalConstraint(BaseModel):
    """时间约束"""

    date: str = Field(
        ...,
        description="日期（YYYY-MM-DD）",
    )
    start_time: str = Field(
        default="09:00",
        description="出发时间",
    )
    end_time: str = Field(
        default="18:00",
        description="结束时间",
    )
    duration_hours: float = Field(
        default=8.0,
        description="总时长（小时）",
    )
    flexibility: TimeFlexibility = Field(
        default=TimeFlexibility.FLEXIBLE,
        description="时间灵活性",
    )
    meal_preferences: list[str] = Field(
        default_factory=list,
        description="用餐时段偏好",
    )


class PartyInfo(BaseModel):
    """出行人员信息"""

    size: int = Field(
        default=1,
        description="人数",
    )
    composition: list[str] = Field(
        default_factory=list,
        description="构成：elder/child/adult/teen",
    )
    child_ages: list[int] = Field(
        default_factory=list,
        description="儿童年龄列表",
    )
    special_needs: list[str] = Field(
        default_factory=list,
        description="特殊需求：wheelchair/stroller/pet",
    )


class Preferences(BaseModel):
    """偏好设置"""

    must_have: list[str] = Field(
        default_factory=list,
        description="必须包含的类型/主题",
    )
    nice_to_have: list[str] = Field(
        default_factory=list,
        description="希望包含",
    )
    avoid: list[str] = Field(
        default_factory=list,
        description="明确排除",
    )
    themes: list[str] = Field(
        default_factory=list,
        description="主题标签",
    )
    cuisine_types: list[str] = Field(
        default_factory=list,
        description="菜系偏好",
    )
    poi_style: POIStyle | None = Field(
        default=None,
        description="POI 风格偏好：popular/niche/balanced",
    )


class BudgetInfo(BaseModel):
    """预算信息"""

    per_person: float | None = Field(
        default=None,
        description="人均预算（元）",
    )
    level: BudgetLevel | None = Field(
        default=None,
        description="预算档位",
    )


class IntentResult(BaseModel):
    """
    意图解析结果

    从用户自然语言输入中提取的结构化信息
    """

    intent_type: IntentType = Field(
        ...,
        description="意图类型",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="意图识别置信度",
    )
    spatial: SpatialConstraint = Field(
        ...,
        description="空间约束",
    )
    temporal: TemporalConstraint = Field(
        ...,
        description="时间约束",
    )
    party: PartyInfo = Field(
        default_factory=PartyInfo,
        description="出行人员信息",
    )
    preferences: Preferences = Field(
        default_factory=Preferences,
        description="偏好设置",
    )
    budget: BudgetInfo = Field(
        default_factory=BudgetInfo,
        description="预算信息",
    )
    ambiguity_flags: list[str] = Field(
        default_factory=list,
        description="需要反问的字段",
    )
    inferred_fields: list[str] = Field(
        default_factory=list,
        description="系统自动推断的字段（规则 ID）",
    )
    raw_query: str = Field(
        ...,
        description="原始输入留存",
    )

    def needs_clarification(self) -> bool:
        """是否需要反问"""
        return len(self.ambiguity_flags) > 0 or self.confidence < 0.7

    def get_constraint_summary(self) -> str:
        """获取约束摘要"""
        parts = []
        parts.append(f"{self.spatial.city}")
        if self.spatial.region:
            parts.append(self.spatial.region)
        parts.append(f"{self.temporal.date}")
        parts.append(f"{self.temporal.start_time}-{self.temporal.end_time}")
        if self.party.size > 1:
            parts.append(f"{self.party.size}人")
        return " ".join(parts)