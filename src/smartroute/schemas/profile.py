"""
SmartRoute Agent 用户画像 Schema 定义

UserProfile 及相关子结构
"""

from pydantic import BaseModel, Field


class CuisinePreference(BaseModel):
    """菜系偏好"""

    cuisine_type: str = Field(
        ...,
        description="菜系名称",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="偏好分（0-1）",
    )
    order_count: int = Field(
        default=0,
        description="历史下单次数",
    )


class SpendingLevel(str):
    """消费档位"""

    BUDGET = "budget"
    MID = "mid"
    PREMIUM = "premium"
    LUXURY = "luxury"


class UserProfile(BaseModel):
    """
    用户画像

    包含用户的长期偏好和短期信号
    """

    user_id: str = Field(
        ...,
        description="用户 ID",
    )
    is_cold_start: bool = Field(
        default=False,
        description="是否为冷启动用户",
    )

    # ============================================
    # 菜系偏好
    # ============================================
    cuisine_preferences: list[CuisinePreference] = Field(
        default_factory=list,
        description="菜系偏好列表",
    )

    # ============================================
    # 消费档位
    # ============================================
    spending_level: str = Field(
        default="mid",
        description="消费档位：budget/mid/premium/luxury",
    )
    avg_spend_per_person: float = Field(
        default=100.0,
        description="人均消费客单价",
    )

    # ============================================
    # 场景偏好
    # ============================================
    scene_preferences: dict[str, float] = Field(
        default_factory=dict,
        description="场景偏好标签（含权重）",
        examples=[{"亲子": 0.8, "网红": 0.3}],
    )

    # ============================================
    # 步行耐受度
    # ============================================
    walk_tolerance_km: float = Field(
        default=5.0,
        description="步行耐受度（公里）",
    )

    # ============================================
    # 饮食禁忌（硬约束）
    # ============================================
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        description="饮食禁忌",
        examples=[["海鲜", "花生"]],
    )

    # ============================================
    # 时段偏好
    # ============================================
    preferred_start_hour: int = Field(
        default=9,
        description="偏好出发时间（小时）",
    )
    is_night_owl: bool = Field(
        default=False,
        description="是否偏好夜间活动",
    )

    # ============================================
    # POI 风格偏好
    # ============================================
    niche_preference_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="小众偏好评分（0=网红，1=小众）",
    )

    # ============================================
    # 已去过的 POI（用于过滤）
    # ============================================
    visited_poi_ids: list[str] = Field(
        default_factory=list,
        description="已去过的 POI ID 列表",
    )

    # ============================================
    # 画像向量（用于相似用户检索）
    # ============================================
    profile_vector: list[float] | None = Field(
        default=None,
        description="用户画像向量",
    )

    # ============================================
    # 元数据
    # ============================================
    data_freshness: str = Field(
        default="",
        description="数据新鲜度（T+1 日期）",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="画像置信度（冷启动时较低）",
    )

    def get_top_cuisines(self, top_k: int = 3) -> list[str]:
        """获取偏好最高的菜系"""
        sorted_prefs = sorted(
            self.cuisine_preferences,
            key=lambda x: x.score,
            reverse=True,
        )
        return [p.cuisine_type for p in sorted_prefs[:top_k]]

    def get_top_scenes(self, top_k: int = 3) -> list[str]:
        """获取偏好最高的场景"""
        sorted_scenes = sorted(
            self.scene_preferences.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [s[0] for s in sorted_scenes[:top_k]]

    def is_poi_visited(self, poi_id: str) -> bool:
        """检查是否去过该 POI"""
        return poi_id in self.visited_poi_ids

    def get_budget_range(self) -> tuple[float, float]:
        """获取预算范围"""
        level_ranges = {
            "budget": (0, 50),
            "mid": (50, 200),
            "premium": (200, 500),
            "luxury": (500, 2000),
        }
        return level_ranges.get(self.spending_level, (50, 200))


class ShortTermSignals(BaseModel):
    """
    短期 Session 信号

    基于当前对话会话的实时偏好信号
    """

    browsed_cuisines: list[str] = Field(
        default_factory=list,
        description="Session 内浏览的菜系",
    )
    rejected_poi_ids: list[str] = Field(
        default_factory=list,
        description="Session 内拒绝的 POI",
    )
    accepted_poi_ids: list[str] = Field(
        default_factory=list,
        description="Session 内接受的 POI",
    )
    explicit_budget: str | None = Field(
        default=None,
        description="Session 内明确表达的预算档位",
    )
    explicit_preferences: list[str] = Field(
        default_factory=list,
        description="Session 内明确表达的偏好",
    )