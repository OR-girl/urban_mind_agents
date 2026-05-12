"""
SmartRoute Agent Orchestrator 模块

主控调度器，负责 Agent 编排、状态管理、降级策略
"""

from smartroute.orchestrator.fallback import (
    FallbackHandler,
    FallbackLevel,
    get_fallback_handler,
)
from smartroute.orchestrator.graph import (
    OrchestratorGraph,
    get_orchestrator,
)
from smartroute.orchestrator.router import (
    classify_request,
    estimate_request_duration,
    get_agents_for_request_type,
    route_decision,
    check_clarification_needed,
    check_route_feasibility,
)
from smartroute.orchestrator.session import (
    SessionManager,
    get_session_manager,
)

__all__ = [
    # Graph
    "OrchestratorGraph",
    "get_orchestrator",
    # Router
    "classify_request",
    "route_decision",
    "check_clarification_needed",
    "check_route_feasibility",
    "get_agents_for_request_type",
    "estimate_request_duration",
    # Session
    "SessionManager",
    "get_session_manager",
    # Fallback
    "FallbackHandler",
    "FallbackLevel",
    "get_fallback_handler",
]