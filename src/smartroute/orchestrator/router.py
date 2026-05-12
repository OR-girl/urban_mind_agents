"""
SmartRoute Agent Orchestrator 请求路由模块

根据请求类型决定执行路径
"""

from typing import Literal

from smartroute.core.logging import get_logger
from smartroute.schemas import SystemState

logger = get_logger("orchestrator.router")

RequestType = Literal[
    "NEW",
    "MODIFY_POI",
    "MODIFY_TIME",
    "MODIFY_PREFER",
    "REDO",
    "CLARIFY",
]


def classify_request(state: SystemState) -> RequestType:
    """
    根据状态信息分类请求类型

    Args:
        state: 系统状态

    Returns:
        请求类型枚举
    """
    raw_query = state.raw_query.lower()

    # 如果是新会话，一定是 NEW
    if not state.session_id or state.session_id == "":
        return "NEW"

    # 检查是否为反问回答
    if state.dialog_history and state.dialog_history[-1].get("role") == "system":
        last_msg = state.dialog_history[-1].get("content", "")
        if "请" in last_msg or "?" in last_msg:
            return "CLARIFY"

    # 检查关键词判断请求类型
    replace_keywords = ["换成", "换一个", "换掉", "替换", "不要这个", "换家"]
    if any(kw in raw_query for kw in replace_keywords):
        return "MODIFY_POI"

    time_keywords = ["早点", "晚点", "提前", "延后", "缩短", "延长", "时间"]
    time_phrases = ["几点要", "要走", "要回去", "结束"]
    if any(kw in raw_query for kw in time_keywords) or any(ph in raw_query for ph in time_phrases):
        return "MODIFY_TIME"

    preference_keywords = ["想吃", "想吃辣", "想吃清淡", "喜欢", "不想要", "去掉", "加一个", "再加"]
    if any(kw in raw_query for kw in preference_keywords):
        return "MODIFY_PREFER"

    redo_keywords = ["重新", "换地方", "不去了", "换个城市", "换个区域", "重来"]
    if any(kw in raw_query for kw in redo_keywords):
        return "REDO"

    # 默认为 NEW
    return "NEW"


def route_decision(state: SystemState) -> str:
    """
    根据请求类型决定执行路径

    Args:
        state: 系统状态

    Returns:
        下一个节点名称
    """
    request_type = state.request_type

    logger.debug(
        "routing_request",
        request_type=request_type,
        session_id=state.session_id,
    )

    route_map = {
        "NEW": "intent",
        "MODIFY_POI": "retrieval",
        "MODIFY_TIME": "route",
        "MODIFY_PREFER": "profile",
        "REDO": "intent",
        "CLARIFY": "intent",
    }

    return route_map.get(request_type, "intent")


def check_clarification_needed(state: SystemState) -> str:
    """
    检查 Intent Agent 是否需要反问

    Args:
        state: 系统状态

    Returns:
        下一个节点名称：clarify 或 proceed
    """
    if state.clarification_needed:
        logger.info(
            "clarification_needed",
            question=state.clarification_question,
        )
        return "need_clarify"

    return "proceed"


def check_route_feasibility(state: SystemState) -> str:
    """
    检查路线规划是否成功

    Args:
        state: 系统状态

    Returns:
        下一个节点名称：success 或 fallback
    """
    routes = state.routes

    if routes and len(routes) > 0:
        # 检查是否有可行方案
        feasible_count = sum(1 for r in routes if r.get("is_feasible", True))
        if feasible_count > 0:
            return "success"

    logger.warning(
        "route_not_feasible",
        routes_count=len(routes) if routes else 0,
    )
    return "fallback"


def get_agents_for_request_type(request_type: RequestType) -> list[str]:
    """
    获取指定请求类型需要执行的 Agent 列表

    Args:
        request_type: 请求类型

    Returns:
        Agent 名称列表
    """
    agent_map = {
        "NEW": ["intent", "profile", "retrieval", "ugc", "route", "presentation"],
        "MODIFY_POI": ["retrieval", "ugc", "route", "presentation"],
        "MODIFY_TIME": ["route", "presentation"],
        "MODIFY_PREFER": ["profile", "retrieval", "route", "presentation"],
        "REDO": ["intent", "profile", "retrieval", "ugc", "route", "presentation"],
        "CLARIFY": ["intent", "profile", "retrieval", "ugc", "route", "presentation"],
    }

    return agent_map.get(request_type, ["intent", "profile", "retrieval", "ugc", "route", "presentation"])


def estimate_request_duration(request_type: RequestType) -> float:
    """
    估算请求处理时间（秒）

    Args:
        request_type: 请求类型

    Returns:
        估算时间（秒）
    """
    duration_map = {
        "NEW": 8.0,
        "MODIFY_POI": 3.0,
        "MODIFY_TIME": 2.0,
        "MODIFY_PREFER": 4.0,
        "REDO": 8.0,
        "CLARIFY": 8.0,
    }

    return duration_map.get(request_type, 8.0)