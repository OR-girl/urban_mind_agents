"""
SmartRoute Agent Schemas 模块

导出所有 Schema 定义
"""

from smartroute.schemas.intent import (
    BudgetInfo,
    BudgetLevel,
    IntentResult,
    IntentType,
    PartyInfo,
    POIStyle,
    Preferences,
    SpatialConstraint,
    TemporalConstraint,
    TimeFlexibility,
)
from smartroute.schemas.poi import (
    BusinessHours,
    EnrichedPOI,
    GeoPoint,
    POI,
    POICandidate,
    UGCSentiment,
)
from smartroute.schemas.profile import (
    CuisinePreference,
    ShortTermSignals,
    UserProfile,
)
from smartroute.schemas.response import (
    AdjustRequest,
    ClarifyRequest,
    ErrorResponse,
    FinalResponse,
    HealthCheckResponse,
    PlanRequest,
    SSEDoneMessage,
    SSEErrorMessage,
    SSEStructuredMessage,
    SSEStatusMessage,
    SSETextMessage,
    UserPreferencesRequest,
)
from smartroute.schemas.route import (
    PlanComparison,
    POITimelineItem,
    RoutePlan,
    RouteSummary,
    TransportInfo,
)
from smartroute.schemas.state import SystemState

__all__ = [
    # Intent
    "IntentResult",
    "IntentType",
    "SpatialConstraint",
    "TemporalConstraint",
    "PartyInfo",
    "Preferences",
    "BudgetInfo",
    "BudgetLevel",
    "POIStyle",
    "TimeFlexibility",
    # Profile
    "UserProfile",
    "CuisinePreference",
    "ShortTermSignals",
    # POI
    "POI",
    "EnrichedPOI",
    "POICandidate",
    "GeoPoint",
    "BusinessHours",
    "UGCSentiment",
    # Route
    "RoutePlan",
    "RouteSummary",
    "POITimelineItem",
    "TransportInfo",
    "PlanComparison",
    # Response
    "PlanRequest",
    "AdjustRequest",
    "ClarifyRequest",
    "UserPreferencesRequest",
    "FinalResponse",
    "HealthCheckResponse",
    "ErrorResponse",
    "SSEStatusMessage",
    "SSETextMessage",
    "SSEStructuredMessage",
    "SSEErrorMessage",
    "SSEDoneMessage",
    # State
    "SystemState",
]