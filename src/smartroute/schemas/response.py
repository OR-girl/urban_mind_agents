"""
SmartRoute Agent API 响应 Schema 定义

API 接口的请求和响应结构
"""

from typing import Any

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    """
    路线规划请求

    首次规划或全新规划的请求结构
    """

    session_id: str | None = Field(
        default=None,
        description="会话 ID（新会话不传）",
    )
    user_id: str | None = Field(
        default=None,
        description="用户 ID（匿名用户不传）",
    )
    query: str = Field(
        ...,
        description="用户自然语言输入",
        min_length=1,
        max_length=500,
    )


class AdjustRequest(BaseModel):
    """
    路线调整请求

    多轮对话中的调整请求结构
    """

    session_id: str = Field(
        ...,
        description="会话 ID（必填）",
    )
    query: str = Field(
        ...,
        description="调整需求（自然语言）",
        min_length=1,
        max_length=500,
    )
    target_plan_id: str | None = Field(
        default=None,
        description="目标方案 ID（可选）",
    )


class ClarifyRequest(BaseModel):
    """
    反问回答请求

    用户回答系统反问的请求结构
    """

    session_id: str = Field(
        ...,
        description="会话 ID",
    )
    answers: dict[str, str] = Field(
        ...,
        description="问题答案（问题字段 -> 答案）",
    )


class UserPreferencesRequest(BaseModel):
    """
    用户偏好设置请求

    用户主动设置偏好的请求结构
    """

    dietary_restrictions: list[str] | None = Field(
        default=None,
        description="饮食禁忌",
    )
    spending_level: str | None = Field(
        default=None,
        description="消费档位",
    )
    personalization_enabled: bool | None = Field(
        default=None,
        description="是否启用个性化",
    )
    scene_preferences: dict[str, float] | None = Field(
        default=None,
        description="场景偏好",
    )
    walk_tolerance_km: float | None = Field(
        default=None,
        description="步行耐受度",
    )


class SSEStatusMessage(BaseModel):
    """
    SSE 状态消息

    流式输出的状态更新消息
    """

    type: str = Field(
        default="status",
        description="消息类型",
    )
    stage: str = Field(
        ...,
        description="当前阶段：intent/profile/retrieval/ugc/route/presentation",
    )
    message: str = Field(
        ...,
        description="状态消息",
    )
    progress: float | None = Field(
        default=None,
        description="进度百分比",
    )


class SSETextMessage(BaseModel):
    """
    SSE 文本消息

    流式输出的文本 Token 消息
    """

    type: str = Field(
        default="text",
        description="消息类型",
    )
    token: str = Field(
        ...,
        description="文本 Token",
    )


class SSEStructuredMessage(BaseModel):
    """
    SSE 结构化消息

    流式输出的完整结构化数据消息
    """

    type: str = Field(
        default="structured",
        description="消息类型",
    )
    plans: list[dict[str, Any]] = Field(
        default_factory=list,
        description="路线方案列表",
    )
    session_id: str = Field(
        ...,
        description="会话 ID",
    )
    plan_comparison: dict[str, Any] | None = Field(
        default=None,
        description="方案对比矩阵",
    )


class SSEClarificationMessage(BaseModel):
    """
    SSE 反问消息

    流式输出的反问消息
    """

    type: str = Field(
        default="clarification",
        description="消息类型",
    )
    questions: list[str] = Field(
        ...,
        description="需要反问的问题列表",
    )
    session_id: str = Field(
        ...,
        description="会话 ID",
    )


class SSEErrorMessage(BaseModel):
    """
    SSE 错误消息

    流式输出的错误消息
    """

    type: str = Field(
        default="error",
        description="消息类型",
    )
    code: str = Field(
        ...,
        description="错误码",
    )
    message: str = Field(
        ...,
        description="错误消息",
    )
    fallback_level: str | None = Field(
        default=None,
        description="降级级别",
    )


class SSEDoneMessage(BaseModel):
    """
    SSE 完成消息

    流式输出结束标记
    """

    type: str = Field(
        default="done",
        description="消息类型",
    )


class FinalResponse(BaseModel):
    """
    最终响应

    完整的路线规划响应结构
    """

    session_id: str = Field(
        ...,
        description="会话 ID",
    )
    summary: str = Field(
        default="",
        description="整体介绍文本",
    )
    plans: list[dict[str, Any]] = Field(
        default_factory=list,
        description="路线方案列表（RoutePlan）",
    )
    plan_comparison: dict[str, Any] = Field(
        default_factory=dict,
        description="方案对比矩阵",
    )
    adjustable_hints: list[str] = Field(
        default_factory=list,
        description="可调整提示",
    )

    # ============================================
    # 元数据
    # ============================================
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="生成元数据",
    )

    # ============================================
    # 状态
    # ============================================
    success: bool = Field(
        default=True,
        description="是否成功",
    )
    fallback_triggered: bool = Field(
        default=False,
        description="是否触发降级",
    )
    fallback_level: str | None = Field(
        default=None,
        description="降级级别",
    )
    error_message: str | None = Field(
        default=None,
        description="错误消息",
    )

    def get_first_plan(self) -> dict[str, Any] | None:
        """获取第一个方案"""
        return self.plans[0] if self.plans else None

    def get_plan_by_id(self, plan_id: str) -> dict[str, Any] | None:
        """根据 ID 获取方案"""
        for plan in self.plans:
            if plan.get("plan_id") == plan_id:
                return plan
        return None


class HealthCheckResponse(BaseModel):
    """
    健康检查响应
    """

    status: str = Field(
        default="ok",
        description="服务状态",
    )
    version: str = Field(
        default="1.0.0",
        description="版本号",
    )
    timestamp: str = Field(
        default="",
        description="时间戳",
    )
    components: dict[str, str] = Field(
        default_factory=lambda: {
            "database": "ok",
            "redis": "ok",
            "milvus": "ok",
            "elasticsearch": "ok",
        },
        description="组件状态",
    )


class ErrorResponse(BaseModel):
    """
    错误响应
    """

    code: str = Field(
        ...,
        description="错误码",
    )
    message: str = Field(
        ...,
        description="错误消息",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="错误详情",
    )
    session_id: str | None = Field(
        default=None,
        description="会话 ID（如有）",
    )