"""
SmartRoute Agent 路线规划相关 Schema 定义

RoutePlan 及相关子结构
"""

from pydantic import BaseModel, Field


class TransportInfo(BaseModel):
    """
    交通方式信息

    POI 之间的交通方式详情
    """

    mode: str = Field(
        default="步行",
        description="交通方式：步行/公交/地铁/驾车/骑行",
    )
    duration_min: int = Field(
        default=0,
        description="预计耗时（分钟）",
    )
    distance_m: int = Field(
        default=0,
        description="距离（米）",
    )
    route_hint: str | None = Field(
        default=None,
        description="路线提示（如'沿XX路向北'）",
    )
    cost_yuan: float = Field(
        default=0.0,
        description="交通费用（元）",
    )


class POITimelineItem(BaseModel):
    """
    POI 时间轴项

    路线中单个 POI 的访问安排详情
    """

    poi_id: str = Field(
        ...,
        description="POI ID",
    )
    poi_name: str = Field(
        ...,
        description="POI 名称",
    )
    category: str = Field(
        ...,
        description="POI 类目",
    )
    location: dict = Field(
        default_factory=dict,
        description="POI 坐标",
    )

    # ============================================
    # 时间安排
    # ============================================
    arrive_time: str = Field(
        ...,
        description="到达时间",
    )
    leave_time: str = Field(
        ...,
        description="离开时间",
    )
    duration_min: int = Field(
        default=60,
        description="建议游览/用餐时长（分钟）",
    )
    queue_time_min: int = Field(
        default=0,
        description="预估排队时间（分钟）",
    )

    # ============================================
    # 交通信息
    # ============================================
    transport_to_next: TransportInfo | None = Field(
        default=None,
        description="到下一 POI 的交通方式",
    )
    transport_from_prev: TransportInfo | None = Field(
        default=None,
        description="从上一 POI 来的交通方式",
    )

    # ============================================
    # 费用信息
    # ============================================
    estimated_cost: float = Field(
        default=0.0,
        description="预估费用（元/人）",
    )
    transport_cost: float = Field(
        default=0.0,
        description="交通费用",
    )

    # ============================================
    # 推荐信息
    # ============================================
    why_for_you: str = Field(
        default="",
        description="个性化推荐理由",
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="POI 亮点",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="注意事项/避雷提示",
    )
    queue_warning: str = Field(
        default="",
        description="排队预警",
    )

    # ============================================
    # 序号
    # ============================================
    sequence: int = Field(
        default=0,
        description="访问顺序序号",
    )

    def get_total_time_min(self) -> int:
        """获取总耗时（含排队）"""
        return self.duration_min + self.queue_time_min


class RouteSummary(BaseModel):
    """
    路线摘要

    整条路线的统计信息
    """

    total_poi_count: int = Field(
        default=0,
        description="总 POI 数量",
    )
    total_duration_h: float = Field(
        default=0.0,
        description="总时长（小时）",
    )
    total_distance_km: float = Field(
        default=0.0,
        description="总步行距离（公里）",
    )
    total_cost: float = Field(
        default=0.0,
        description="总费用（元/人）",
    )
    total_transport_cost: float = Field(
        default=0.0,
        description="总交通费用",
    )
    total_queue_time_min: int = Field(
        default=0,
        description="总排队时间（分钟）",
    )
    avg_poi_rating: float = Field(
        default=0.0,
        description="平均 POI 评分",
    )
    restaurant_count: int = Field(
        default=0,
        description="餐厅数量",
    )


class RoutePlan(BaseModel):
    """
    路线方案

    一条完整的路线规划方案
    """

    plan_id: str = Field(
        ...,
        description="方案 ID：plan_a/plan_b/plan_c",
    )
    name: str = Field(
        ...,
        description="方案名称：经典稳妥/避峰省时/极致体验",
    )
    tagline: str = Field(
        default="",
        description="方案标语",
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="方案亮点（3条）",
    )
    timeline: list[POITimelineItem] = Field(
        default_factory=list,
        description="时间轴详情",
    )
    summary: RouteSummary = Field(
        default_factory=RouteSummary,
        description="路线摘要",
    )

    # ============================================
    # 个性化信息
    # ============================================
    why_for_you: str = Field(
        default="",
        description="整体个性化说明",
    )
    suitable_for: list[str] = Field(
        default_factory=list,
        description="适合人群",
    )

    # ============================================
    # 权重配置
    # ============================================
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="权重配置",
    )

    # ============================================
    # 地图渲染数据
    # ============================================
    map_data: dict = Field(
        default_factory=dict,
        description="地图渲染数据",
    )

    # ============================================
    # 可行性
    # ============================================
    is_feasible: bool = Field(
        default=True,
        description="是否可行",
    )
    feasibility_issues: list[str] = Field(
        default_factory=list,
        description="可行性问题列表",
    )

    def get_poi_ids(self) -> set[str]:
        """获取所有 POI ID"""
        return set(item.poi_id for item in self.timeline)

    def get_restaurants(self) -> list[POITimelineItem]:
        """获取餐厅项"""
        return [
            item
            for item in self.timeline
            if item.category.split("/")[0]
            in ["餐厅", "美食", "餐饮", "饭店", "小吃"]
        ]

    def get_start_time(self) -> str:
        """获取出发时间"""
        return self.timeline[0].arrive_time if self.timeline else "09:00"

    def get_end_time(self) -> str:
        """获取结束时间"""
        return self.timeline[-1].leave_time if self.timeline else "18:00"

    def calculate_summary(self) -> RouteSummary:
        """计算路线摘要"""
        if not self.timeline:
            return RouteSummary()

        total_cost = sum(item.estimated_cost for item in self.timeline)
        total_transport_cost = sum(
            item.transport_to_next.cost_yuan if item.transport_to_next else 0
            for item in self.timeline[:-1]
        )
        total_queue_time = sum(item.queue_time_min for item in self.timeline)
        total_distance = sum(
            item.transport_to_next.distance_m if item.transport_to_next else 0
            for item in self.timeline[:-1]
        ) / 1000
        avg_rating = sum(
            item.estimated_cost  # 这里应该用实际的 rating
            for item in self.timeline
        ) / len(self.timeline) if self.timeline else 0
        restaurant_count = len(self.get_restaurants())

        total_duration_min = 0
        for i, item in enumerate(self.timeline):
            total_duration_min += item.get_total_time_min()
            if i < len(self.timeline) - 1 and item.transport_to_next:
                total_duration_min += item.transport_to_next.duration_min

        return RouteSummary(
            total_poi_count=len(self.timeline),
            total_duration_h=total_duration_min / 60,
            total_distance_km=total_distance,
            total_cost=total_cost + total_transport_cost,
            total_transport_cost=total_transport_cost,
            total_queue_time_min=total_queue_time,
            avg_poi_rating=avg_rating,
            restaurant_count=restaurant_count,
        )


class PlanComparison(BaseModel):
    """
    方案对比矩阵

    用于突出各方案的差异点
    """

    dimensions: list[str] = Field(
        default_factory=lambda: [
            "餐厅选择",
            "路线风格",
            "总费用",
            "总步行",
            "预计排队",
        ],
        description="对比维度",
    )
    plans: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="各方案在各维度的对比值",
    )

    def get_comparison_text(self) -> str:
        """生成对比文本"""
        lines = []
        for dim in self.dimensions:
            values = []
            for plan_id, plan_data in self.plans.items():
                value = plan_data.get(dim, "-")
                values.append(f"{plan_id}: {value}")
            lines.append(f"{dim}: " + " | ".join(values))
        return "\n".join(lines)