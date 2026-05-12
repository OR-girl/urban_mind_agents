"""
SmartRoute Agent 系统状态定义模块

SystemState 是贯穿所有 Agent 的统一数据容器
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SystemState(BaseModel):
    """
    系统状态 - 所有 Agent 共享的数据容器

    所有 Agent 只读取自己需要的字段，只写入自己负责的字段
    """

    # ============================================
    # 请求元信息
    # ============================================
    session_id: str = Field(default="", description="会话 ID")
    trace_id: str = Field(default="", description="追踪 ID，用于链路追踪")
    request_type: str = Field(
        default="NEW",
        description="请求类型: NEW/MODIFY_POI/MODIFY_TIME/MODIFY_PREFER/REDO/CLARIFY",
    )
    user_id: Optional[str] = Field(default=None, description="用户 ID（可选）")
    raw_query: str = Field(default="", description="用户原始输入")
    dialog_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="多轮对话历史",
    )

    # ============================================
    # Intent Agent 输出
    # ============================================
    intent: Optional[dict[str, Any]] = Field(
        default=None,
        description="IntentResult 意图解析结果",
    )
    clarification_needed: bool = Field(
        default=False,
        description="是否需要反问",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="反问内容",
    )

    # ============================================
    # Profile Agent 输出
    # ============================================
    profile: Optional[dict[str, Any]] = Field(
        default=None,
        description="UserProfile 用户画像",
    )
    profile_vector: Optional[list[float]] = Field(
        default=None,
        description="用户画像向量",
    )

    # ============================================
    # Retrieval Agent 输出
    # ============================================
    candidates: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="候选 POI 列表",
    )
    retrieval_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="召回路径统计",
    )

    # ============================================
    # UGC Agent 输出
    # ============================================
    enriched_pois: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="增强后的 POI 列表（含 UGC 洞察）",
    )

    # ============================================
    # Route Agent 输出
    # ============================================
    routes: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="3 个差异化路线方案",
    )

    # ============================================
    # Presentation Agent 输出
    # ============================================
    final_response: Optional[dict[str, Any]] = Field(
        default=None,
        description="最终输出结构",
    )

    # ============================================
    # 运行时元数据
    # ============================================
    error_info: Optional[dict[str, Any]] = Field(
        default=None,
        description="错误信息",
    )
    fallback_triggered: bool = Field(
        default=False,
        description="是否触发降级",
    )
    fallback_level: Optional[str] = Field(
        default=None,
        description="降级级别: L1/L2/L3",
    )
    llm_cost_total: float = Field(
        default=0.0,
        description="本次请求 LLM 成本（元）",
    )
    stage_timings: dict[str, float] = Field(
        default_factory=dict,
        description="各 Agent 耗时（毫秒）",
    )

    def get_intent(self) -> Optional["IntentResult"]:
        """获取 IntentResult 对象"""
        if self.intent:
            # 导入延迟，避免循环依赖
            from smartroute.schemas.intent import IntentResult
            return IntentResult.model_validate(self.intent)
        return None

    def get_profile(self) -> Optional["UserProfile"]:
        """获取 UserProfile 对象"""
        if self.profile:
            from smartroute.schemas.profile import UserProfile
            return UserProfile.model_validate(self.profile)
        return None

    def get_routes(self) -> list["RoutePlan"]:
        """获取 RoutePlan 对象列表"""
        if self.routes:
            from smartroute.schemas.route import RoutePlan
            return [RoutePlan.model_validate(r) for r in self.routes]
        return []

    def update_timing(self, stage: str, duration_ms: float) -> None:
        """更新阶段耗时"""
        self.stage_timings[stage] = duration_ms

    def add_dialog_history(self, role: str, content: str) -> None:
        """添加对话历史"""
        self.dialog_history.append({"role": role, "content": content})

    def to_persist_dict(self) -> dict[str, Any]:
        """转换为需要持久化的字段"""
        persist_fields = [
            "session_id",
            "user_id",
            "intent",
            "profile",
            "candidates",
            "enriched_pois",
            "routes",
            "dialog_history",
        ]
        return {k: self.__dict__.get(k) for k in persist_fields if k in self.__dict__}


# 为了类型检查，需要延迟导入
# 在实际使用时会从对应的模块导入


class IntentResult(BaseModel):
    """占位类型，实际定义在 intent.py"""
    pass


class UserProfile(BaseModel):
    """占位类型，实际定义在 profile.py"""
    pass


class RoutePlan(BaseModel):
    """占位类型，实际定义在 route.py"""
    pass