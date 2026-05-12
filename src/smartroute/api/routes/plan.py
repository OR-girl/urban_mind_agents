"""
Plan Router - 路线规划接口

提供路线规划、调整等API
"""

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from smartroute.schemas import PlanRequest, AdjustRequest, FinalResponse
from smartroute.orchestrator.graph import OrchestratorGraph


router = APIRouter(prefix="/api/v1", tags=["plan"])


orchestrator = OrchestratorGraph()


@router.post("/route/plan", response_model=dict[str, Any])
async def plan_route(request: PlanRequest) -> dict[str, Any]:
    """
    路线规划接口
    
    Args:
        request: PlanRequest
        
    Returns:
        规划结果
    """
    result = await orchestrator.run(
        session_id=request.session_id,
        user_id=request.user_id,
        query=request.query,
        request_type="NEW",
    )

    return result


@router.post("/route/plan/stream")
async def plan_route_stream(request: Request) -> StreamingResponse:
    """
    流式路线规划接口
    
    Args:
        request: Request
        
    Returns:
        SSE流式响应
    """
    body = await request.json()

    async def generate():
        # 发送状态更新
        yield f"data: {json.dumps({'type': 'status', 'stage': 'intent', 'message': '正在理解您的需求...'}, ensure_ascii=False)}\n\n"

        # 执行规划
        result = await orchestrator.run(
            session_id=body.get("session_id", ""),
            user_id=body.get("user_id", ""),
            query=body.get("query", ""),
            request_type="NEW",
            stream=True,
        )

        # 发送结构化数据
        yield f"data: {json.dumps({'type': 'structured', 'data': result}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/route/adjust", response_model=dict[str, Any])
async def adjust_route(request: AdjustRequest) -> dict[str, Any]:
    """
    路线调整接口
    
    Args:
        request: AdjustRequest
        
    Returns:
        调整结果
    """
    result = await orchestrator.run(
        session_id=request.session_id,
        query=request.query,
        request_type="MODIFY",
    )

    return result


@router.post("/route/redo", response_model=dict[str, Any])
async def redo_route(request: PlanRequest) -> dict[str, Any]:
    """
    重新规划接口
    
    Args:
        request: PlanRequest
        
    Returns:
        新规划结果
    """
    result = await orchestrator.run(
        session_id=request.session_id,
        user_id=request.user_id,
        query=request.query,
        request_type="REDO",
    )

    return result


@router.get("/route/status/{session_id}")
async def get_route_status(session_id: str) -> dict[str, Any]:
    """
    获取规划状态
    
    Args:
        session_id: Session ID
        
    Returns:
        状态信息
    """
    status = await orchestrator.get_session_status(session_id)
    return status


@router.delete("/route/session/{session_id}")
async def clear_session(session_id: str) -> dict[str, Any]:
    """
    清除Session
    
    Args:
        session_id: Session ID
        
    Returns:
        操作结果
    """
    await orchestrator.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
