"""
SmartRoute Agent 异常定义模块

定义系统内使用的所有自定义异常类型
"""


class SmartRouteError(Exception):
    """SmartRoute Agent 基础异常类"""

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# ============================================
# LLM 相关异常
# ============================================


class LLMError(SmartRouteError):
    """LLM 服务异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "LLM_ERROR",
        provider: str | None = None,
    ) -> None:
        self.provider = provider
        super().__init__(message, code)


class LLMTimeoutError(LLMError):
    """LLM 调用超时"""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        super().__init__(
            f"LLM call timed out after {timeout_seconds}s (provider: {provider})",
            code="LLM_TIMEOUT",
            provider=provider,
        )


class LLMRateLimitError(LLMError):
    """LLM 速率限制"""

    def __init__(self, provider: str) -> None:
        super().__init__(
            f"LLM rate limit exceeded (provider: {provider})",
            code="LLM_RATE_LIMIT",
            provider=provider,
        )


class LLMContentFilterError(LLMError):
    """LLM 内容过滤触发"""

    def __init__(self, provider: str, reason: str | None = None) -> None:
        super().__init__(
            f"LLM content filter triggered (provider: {provider}, reason: {reason})",
            code="LLM_CONTENT_FILTER",
            provider=provider,
        )


class AllProvidersFailedError(LLMError):
    """所有 LLM 供应商均不可用"""

    def __init__(self) -> None:
        super().__init__(
            "All LLM providers are unavailable",
            code="LLM_ALL_PROVIDERS_FAILED",
        )


# ============================================
# Agent 相关异常
# ============================================


class AgentError(SmartRouteError):
    """Agent 异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "AGENT_ERROR",
        agent_name: str | None = None,
    ) -> None:
        self.agent_name = agent_name
        super().__init__(message, code)


class IntentExtractionError(AgentError):
    """意图抽取异常"""

    def __init__(self, message: str, raw_query: str | None = None) -> None:
        self.raw_query = raw_query
        super().__init__(
            message,
            code="INTENT_EXTRACTION_ERROR",
            agent_name="intent",
        )


class AmbiguityDetectedError(AgentError):
    """歧义检测触发（非错误，用于反问流程）"""

    def __init__(self, questions: list[str]) -> None:
        self.questions = questions
        super().__init__(
            "Ambiguity detected, clarification needed",
            code="AMBIGUITY_DETECTED",
            agent_name="intent",
        )


class ProfileNotFoundError(AgentError):
    """用户画像未找到"""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(
            f"User profile not found: {user_id}",
            code="PROFILE_NOT_FOUND",
            agent_name="profile",
        )


class RetrievalError(AgentError):
    """召回异常"""

    def __init__(self, message: str, recall_type: str | None = None) -> None:
        self.recall_type = recall_type
        super().__init__(
            message,
            code="RETRIEVAL_ERROR",
            agent_name="retrieval",
        )


class NoCandidatesError(RetrievalError):
    """无候选 POI"""

    def __init__(self, reason: str = "No POI found within constraints") -> None:
        super().__init__(reason, recall_type="all")


class UGCAnalysisError(AgentError):
    """UGC 分析异常"""

    def __init__(self, message: str, poi_id: str | None = None) -> None:
        self.poi_id = poi_id
        super().__init__(
            message,
            code="UGC_ANALYSIS_ERROR",
            agent_name="ugc",
        )


class RoutePlanningError(AgentError):
    """路径规划异常"""

    def __init__(self, message: str, constraint_type: str | None = None) -> None:
        self.constraint_type = constraint_type
        super().__init__(
            message,
            code="ROUTE_PLANNING_ERROR",
            agent_name="route",
        )


class NoFeasibleRouteError(RoutePlanningError):
    """无可行路线"""

    def __init__(self, reason: str = "No feasible route found") -> None:
        super().__init__(reason, constraint_type="hard")


class SolverTimeoutError(RoutePlanningError):
    """求解器超时"""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(
            f"Route solver timed out after {timeout_seconds}s",
            constraint_type="solver",
        )


class PresentationError(AgentError):
    """方案生成异常"""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="PRESENTATION_ERROR",
            agent_name="presentation",
        )


# ============================================
# 存储相关异常
# ============================================


class StorageError(SmartRouteError):
    """存储异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "STORAGE_ERROR",
        storage_type: str | None = None,
    ) -> None:
        self.storage_type = storage_type
        super().__init__(message, code)


class DatabaseError(StorageError):
    """数据库异常"""

    def __init__(self, message: str, db_name: str | None = None) -> None:
        super().__init__(message, code="DATABASE_ERROR", storage_type=db_name)


class CacheError(StorageError):
    """缓存异常"""

    def __init__(self, message: str, cache_type: str = "redis") -> None:
        super().__init__(message, code="CACHE_ERROR", storage_type=cache_type)


class VectorStoreError(StorageError):
    """向量库异常"""

    def __init__(self, message: str, collection: str | None = None) -> None:
        self.collection = collection
        super().__init__(message, code="VECTOR_STORE_ERROR", storage_type="milvus")


# ============================================
# 外部 API 相关异常
# ============================================


class ExternalAPIError(SmartRouteError):
    """外部 API 异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "EXTERNAL_API_ERROR",
        api_name: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(message, code)


class MapAPIError(ExternalAPIError):
    """地图 API 异常"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(
            message,
            code="MAP_API_ERROR",
            api_name="amap",
            status_code=status_code,
        )


class POIDataError(ExternalAPIError):
    """POI 数据异常"""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="POI_DATA_ERROR",
            api_name="dianping",
        )


# ============================================
# 验证相关异常
# ============================================


class ValidationError(SmartRouteError):
    """数据验证异常"""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")


class SchemaValidationError(ValidationError):
    """Schema 校验失败"""

    def __init__(self, message: str, schema_name: str | None = None) -> None:
        self.schema_name = schema_name
        super().__init__(message)


# ============================================
# 降级相关异常
# ============================================


class FallbackTriggeredError(SmartRouteError):
    """降级触发（非错误，用于标识降级流程）"""

    def __init__(
        self,
        level: str,
        reason: str,
        original_error: Exception | None = None,
    ) -> None:
        self.level = level  # L1/L2/L3
        self.reason = reason
        self.original_error = original_error
        super().__init__(
            f"Fallback triggered (level={level}): {reason}",
            code="FALLBACK_TRIGGERED",
        )