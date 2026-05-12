"""
SmartRoute Agent POI 相关 Schema 定义

POI 数据结构及增强后的 POI 结构
"""

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    """地理坐标"""

    lat: float = Field(
        ...,
        description="纬度",
    )
    lng: float = Field(
        ...,
        description="经度",
    )


class BusinessHours(BaseModel):
    """营业时间"""

    open: str = Field(
        ...,
        description="开门时间",
    )
    close: str = Field(
        ...,
        description="关门时间",
    )
    weekday: str | None = Field(
        default=None,
        description="适用星期",
    )
    note: str | None = Field(
        default=None,
        description="备注（节假日等）",
    )


class POI(BaseModel):
    """
    POI（兴趣点）基础结构

    来自召回模块的基础 POI 信息
    """

    poi_id: str = Field(
        ...,
        description="POI 唯一标识",
    )
    name: str = Field(
        ...,
        description="POI 名称",
    )
    category: str = Field(
        ...,
        description="类目（餐厅/景点/购物等）",
    )
    location: GeoPoint = Field(
        ...,
        description="经纬度坐标",
    )
    address: str = Field(
        default="",
        description="详细地址",
    )
    business_hours: list[BusinessHours] = Field(
        default_factory=list,
        description="营业时间（含节假日）",
    )
    avg_cost: float = Field(
        default=0.0,
        description="人均消费",
    )
    rating: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="综合评分",
    )
    review_count: int = Field(
        default=0,
        description="评论数量",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="场景标签",
    )

    # 召回相关字段
    retrieval_score: float = Field(
        default=0.0,
        description="召回综合得分",
    )
    semantic_similarity: float = Field(
        default=0.0,
        description="语义相关度",
    )
    distance_km: float = Field(
        default=0.0,
        description="距离中心点距离（公里）",
    )
    retrieval_source: str = Field(
        default="",
        description="召回来源：semantic/geo/collaborative/category/hot",
    )

    def get_major_category(self) -> str:
        """获取大类"""
        return self.category.split("/")[0] if "/" in self.category else self.category

    def is_restaurant(self) -> bool:
        """是否为餐厅"""
        major = self.get_major_category()
        return major in ["餐厅", "美食", "餐饮", "饭店"]

    def is_attraction(self) -> bool:
        """是否为景点"""
        major = self.get_major_category()
        return major in ["景点", "景区", "公园", "博物馆", "古迹"]


class UGCSentiment(BaseModel):
    """
    UGC 评论情感评分

    分维度的用户评论评分
    """

    food: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="食物/产品评分",
    )
    service: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="服务评分",
    )
    environment: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="环境评分",
    )
    wait_time: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="等待时间评分（越高越短）",
    )
    value_for_money: float = Field(
        default=0.0,
        ge=0.0,
        le=5.0,
        description="性价比评分",
    )


class EnrichedPOI(POI):
    """
    增强后的 POI 结构

    包含 UGC 洞察和额外分析结果
    """

    # ============================================
    # UGC 洞察
    # ============================================
    highlights: list[str] = Field(
        default_factory=list,
        description="亮点（≤3条）",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="避雷提示（≤3条）",
    )
    best_time: str = Field(
        default="",
        description="最佳游览时段",
    )
    crowd_match_score: float = Field(
        default=0.5,
        description="与当前用户群体的匹配度",
    )
    ugc_sentiment: UGCSentiment = Field(
        default_factory=UGCSentiment,
        description="维度化情感评分",
    )
    scene_tags: list[str] = Field(
        default_factory=list,
        description="场景标签（亲子/约会/商务等）",
    )

    # ============================================
    # 时间相关洞察
    # ============================================
    peak_hours: list[str] = Field(
        default_factory=list,
        description="高峰时段",
    )
    queue_warning: str = Field(
        default="",
        description="排队预警",
    )
    estimated_duration_min: int = Field(
        default=60,
        description="建议游览时长（分钟）",
    )

    # ============================================
    # 排队时间预测
    # ============================================
    predicted_queue_min: int = Field(
        default=0,
        description="预测排队时间（分钟）",
    )

    # ============================================
    # 元数据
    # ============================================
    analysis_channel: str = Field(
        default="nlp",
        description="分析通道：llm/nlp",
    )
    data_freshness: str = Field(
        default="",
        description="分析基于的最新评论日期",
    )
    review_count_analyzed: int = Field(
        default=0,
        description="分析的评论数量",
    )
    confidence: float = Field(
        default=0.8,
        description="分析置信度",
    )

    def get_overall_sentiment(self) -> float:
        """获取综合情感评分"""
        sentiments = [
            self.ugc_sentiment.food,
            self.ugc_sentiment.service,
            self.ugc_sentiment.environment,
            self.ugc_sentiment.value_for_money,
        ]
        return sum(sentiments) / len(sentiments) if sentiments else 0.0

    def has_queue_warning(self) -> bool:
        """是否有排队预警"""
        return bool(self.queue_warning) or self.predicted_queue_min > 30

    def get_visit_time_window(self) -> tuple[str, str]:
        """获取推荐访问时间窗口"""
        if self.best_time:
            # 解析最佳时间
            parts = self.best_time.split("-")
            if len(parts) == 2:
                return parts[0], parts[1]
        # 默认使用营业时间
        if self.business_hours:
            return self.business_hours[0].open, self.business_hours[0].close
        return "09:00", "18:00"


class POICandidate(BaseModel):
    """
    POI 候选项

    用于路线规划的 POI 候选数据结构
    """

    poi: EnrichedPOI = Field(
        ...,
        description="增强后的 POI",
    )
    coarse_rank_score: float = Field(
        default=0.0,
        description="粗排得分",
    )
    final_score: float = Field(
        default=0.0,
        description="最终综合得分",
    )
    is_selected: bool = Field(
        default=False,
        description="是否被选中进入最终方案",
    )

    # 匹配度信息
    intent_match_score: float = Field(
        default=0.0,
        description="与意图的匹配度",
    )
    profile_match_score: float = Field(
        default=0.0,
        description="与画像的匹配度",
    )
    budget_match_score: float = Field(
        default=0.0,
        description="与预算的匹配度",
    )
    time_match_score: float = Field(
        default=0.0,
        description="与时间约束的匹配度",
    )