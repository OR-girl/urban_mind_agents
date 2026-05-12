"""
SmartRoute Agent Orchestrator LangGraph 执行图模块

定义 Agent 执行 DAG 和调度逻辑
"""

import asyncio
from typing import Any

from langgraph.graph import END, StateGraph

from smartroute.core.exceptions import FallbackTriggeredError
from smartroute.core.logging import AgentLogger, get_logger
from smartroute.core.utils import Timer
from smartroute.orchestrator.fallback import FallbackLevel, get_fallback_handler
from smartroute.orchestrator.router import (
    check_clarification_needed,
    check_route_feasibility,
    route_decision,
)
from smartroute.orchestrator.session import get_session_manager
from smartroute.schemas import SystemState

logger = get_logger("orchestrator.graph")


class OrchestratorGraph:
    """
    Orchestrator 执行图

    使用 LangGraph 构建和管理 Agent 执行 DAG
    """

    def __init__(self) -> None:
        self.graph: StateGraph | None = None
        self.session_manager = get_session_manager()
        self.fallback_handler = get_fallback_handler()
        self._agent_loggers: dict[str, AgentLogger] = {}

    def _get_agent_logger(self, agent_name: str) -> AgentLogger:
        """获取 Agent 日志器"""
        if agent_name not in self._agent_loggers:
            self._agent_loggers[agent_name] = AgentLogger(agent_name)
        return self._agent_loggers[agent_name]

    def build_graph(self) -> StateGraph:
        """
        构建 LangGraph 执行图

        Returns:
            StateGraph 实例
        """
        # 创建状态图
        graph = StateGraph(SystemState)

        # 注册所有节点
        graph.add_node("router", self._router_node)
        graph.add_node("intent", self._intent_node)
        graph.add_node("clarify", self._clarify_node)
        graph.add_node("profile_retrieval_parallel", self._parallel_profile_retrieval_node)
        graph.add_node("ugc", self._ugc_node)
        graph.add_node("route", self._route_node)
        graph.add_node("presentation", self._presentation_node)
        graph.add_node("fallback", self._fallback_node)

        # 设置入口点
        graph.set_entry_point("router")

        # 条件路由：根据 request_type 决定执行路径
        graph.add_conditional_edges(
            "router",
            route_decision,
            {
                "NEW": "intent",
                "MODIFY_POI": "profile_retrieval_parallel",
                "MODIFY_TIME": "route",
                "MODIFY_PREFER": "profile_retrieval_parallel",
                "REDO": "intent",
                "CLARIFY": "intent",
            },
        )

        # Intent 完成后：检查是否需要反问
        graph.add_conditional_edges(
            "intent",
            check_clarification_needed,
            {
                "need_clarify": "clarify",
                "proceed": "profile_retrieval_parallel",
            },
        )

        # 反问后结束（等待用户回复）
        graph.add_edge("clarify", END)

        # 并行执行后继续
        graph.add_edge("profile_retrieval_parallel", "ugc")

        # UGC 完成后进入路线规划
        graph.add_edge("ugc", "route")

        # Route 完成后：检查可行性
        graph.add_conditional_edges(
            "route",
            check_route_feasibility,
            {
                "success": "presentation",
                "fallback": "fallback",
            },
        )

        # 降级后仍然输出
        graph.add_edge("fallback", "presentation")

        # Presentation 后结束
        graph.add_edge("presentation", END)

        self.graph = graph
        return graph

    def compile_graph(self) -> Any:
        """
        编译执行图

        Returns:
            可执行的 CompiledGraph
        """
        if self.graph is None:
            self.build_graph()

        # 编译图（不使用 checkpointer，使用自定义 Session 管理）
        return self.graph.compile()

    async def execute(self, initial_state: SystemState) -> SystemState:
        """
        执行完整的 Agent 流程

        Args:
            initial_state: 初始系统状态

        Returns:
            最终系统状态
        """
        compiled_graph = self.compile_graph()

        # 记录开始时间
        total_timer = Timer()
        total_timer.start()

        try:
            # 执行图
            result = await compiled_graph.invoke(initial_state)

            # 记录总耗时
            total_duration = total_timer.stop()
            result.update_timing("total", total_duration)

            # 保存 Session
            await self.session_manager.save_state(result.session_id, result)

            return result

        except FallbackTriggeredError as e:
            # 捕获降级触发，应用降级策略
            logger.warning(
                "fallback_triggered",
                session_id=initial_state.session_id,
                level=e.level,
                reason=e.reason,
            )

            fallback_state = self.fallback_handler.apply_fallback(
                initial_state,
                e.original_error,
            )

            total_duration = total_timer.stop()
            fallback_state.update_timing("total", total_duration)

            return fallback_state

        except Exception as e:
            # 捕获其他异常，尝试最大程度降级
            logger.error(
                "execution_failed",
                session_id=initial_state.session_id,
                error=str(e),
            )

            # L3 降级
            fallback_state = self.fallback_handler.handle_l3_fallback(initial_state)

            total_duration = total_timer.stop()
            fallback_state.update_timing("total", total_duration)

            fallback_state.error_info = {
                "code": "EXECUTION_ERROR",
                "message": str(e),
            }

            return fallback_state

    async def run(
        self,
        session_id: str,
        user_id: str | None = None,
        query: str = "",
        request_type: str = "NEW",
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        简化的执行入口（供API调用）

        Args:
            session_id: 会话ID
            user_id: 用户ID
            query: 用户查询
            request_type: 请求类型
            stream: 是否流式输出

        Returns:
            执行结果字典
        """
        # 创建初始状态
        initial_state = SystemState(
            session_id=session_id,
            trace_id=f"trace_{session_id}",
            request_type=request_type,
            user_id=user_id,
            raw_query=query,
            dialog_history=[],
        )

        # 执行图
        result_state = await self.execute(initial_state)

        # 返回字典格式结果
        return {
            "session_id": result_state.session_id,
            "final_response": result_state.final_response,
            "routes": result_state.routes,
            "clarification_needed": result_state.clarification_needed,
            "clarification_question": result_state.clarification_question,
            "error_info": result_state.error_info,
        }

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        """
        获取Session状态

        Args:
            session_id: 会话ID

        Returns:
            状态信息
        """
        state = await self.session_manager.load_state(session_id)
        if state:
            return {
                "session_id": session_id,
                "status": "active",
                "intent": state.intent,
                "profile": state.profile,
                "routes": state.routes,
            }
        return {"session_id": session_id, "status": "not_found"}

    async def clear_session(self, session_id: str) -> None:
        """
        清除Session

        Args:
            session_id: 会话ID
        """
        await self.session_manager.delete_state(session_id)

    # ============================================
    # 节点实现
    # ============================================

    async def _router_node(self, state: SystemState) -> SystemState:
        """路由节点：根据请求类型决定执行路径"""
        timer = Timer()
        timer.start()

        # 如果没有 session_id，生成新的
        if not state.session_id:
            from smartroute.core.utils import generate_session_id
            state.session_id = generate_session_id()

        # 分类请求类型
        from smartroute.orchestrator.router import classify_request
        state.request_type = classify_request(state)

        # 加载已有 Session 状态（如果有）
        if state.request_type != "NEW":
            existing_state = await self.session_manager.load_state(state.session_id)
            if existing_state:
                # 合并已有状态
                for key, value in existing_state.items():
                    if key not in ["raw_query", "request_type"]:
                        setattr(state, key, value)

        state.update_timing("router", timer.stop())
        return state

    async def _intent_node(self, state: SystemState) -> SystemState:
        """Intent Agent 节点"""
        timer = Timer()
        timer.start()

        agent_logger = self._get_agent_logger("intent")
        agent_logger.bind_context(state.trace_id, state.session_id)

        try:
            # 调用 Intent Agent
            from smartroute.agents.intent import IntentAgent
            agent = IntentAgent()
            intent_result, clarification = await agent.execute(state)

            state.intent = intent_result.model_dump() if intent_result else None
            state.clarification_needed = clarification is not None
            state.clarification_question = clarification

            agent_logger.timing("intent_extraction", timer.stop())

        except Exception as e:
            agent_logger.error("intent_failed", error=str(e))
            state.error_info = {
                "agent": "intent",
                "error": str(e),
            }

        state.update_timing("intent", timer.stop())
        return state

    async def _clarify_node(self, state: SystemState) -> SystemState:
        """反问节点：输出反问，等待用户回复"""
        # 反问节点不执行任何 Agent，只是标记需要反问
        # 实际的反问内容由 Presentation Agent 处理
        return state

    async def _parallel_profile_retrieval_node(
        self,
        state: SystemState,
    ) -> SystemState:
        """
        并行执行 Profile 和 Retrieval Agent
        """
        timer = Timer()
        timer.start()

        # 并行执行两个 Agent
        profile_task = self._execute_profile_agent(state)
        retrieval_task = self._execute_retrieval_agent(state)

        try:
            profile_result, retrieval_result = await asyncio.gather(
                profile_task,
                retrieval_task,
                return_exceptions=True,
            )

            # 处理 Profile 结果
            if isinstance(profile_result, Exception):
                logger.warning(
                    "profile_agent_failed",
                    error=str(profile_result),
                )
                state.profile = self.fallback_handler._get_default_profile(state.user_id)
            else:
                state.profile = profile_result

            # 处理 Retrieval 结果
            if isinstance(retrieval_result, Exception):
                logger.warning(
                    "retrieval_agent_failed",
                    error=str(retrieval_result),
                )
                state.candidates = []
            else:
                state.candidates = retrieval_result

        except asyncio.TimeoutError:
            logger.warning(
                "parallel_execution_timeout",
                session_id=state.session_id,
            )
            # 超时降级
            state = self.fallback_handler.handle_l1_fallback(state)

        state.update_timing("profile_retrieval_parallel", timer.stop())
        return state

    async def _execute_profile_agent(
        self,
        state: SystemState,
    ) -> dict[str, Any] | None:
        """执行 Profile Agent"""
        agent_logger = self._get_agent_logger("profile")
        agent_logger.bind_context(state.trace_id, state.session_id)

        try:
            from smartroute.agents.profile import ProfileAgent
            agent = ProfileAgent()
            profile_result = await agent.execute(state)
            return profile_result.model_dump() if profile_result else None

        except Exception as e:
            agent_logger.error("profile_failed", error=str(e))
            raise

    async def _execute_retrieval_agent(
        self,
        state: SystemState,
    ) -> list[dict[str, Any]] | None:
        """执行 Retrieval Agent"""
        agent_logger = self._get_agent_logger("retrieval")
        agent_logger.bind_context(state.trace_id, state.session_id)

        try:
            from smartroute.agents.retrieval import RetrievalAgent
            agent = RetrievalAgent()
            candidates, metadata = await agent.execute(state)
            state.retrieval_metadata = metadata
            return candidates

        except Exception as e:
            agent_logger.error("retrieval_failed", error=str(e))
            raise

    async def _ugc_node(self, state: SystemState) -> SystemState:
        """UGC Insight Agent 节点"""
        timer = Timer()
        timer.start()

        agent_logger = self._get_agent_logger("ugc")
        agent_logger.bind_context(state.trace_id, state.session_id)

        try:
            from smartroute.agents.ugc import UGCInsightAgent
            agent = UGCInsightAgent()
            enriched_pois = await agent.execute(state)
            state.enriched_pois = enriched_pois

            agent_logger.timing("ugc_analysis", timer.stop())

        except Exception as e:
            agent_logger.error("ugc_failed", error=str(e))
            # 使用基础 POI 数据
            if state.candidates:
                state.enriched_pois = self.fallback_handler._convert_to_enriched_pois(
                    state.candidates,
                )

        state.update_timing("ugc", timer.stop())
        return state

    async def _route_node(self, state: SystemState) -> SystemState:
        """Route Planning Agent 节点"""
        timer = Timer()
        timer.start()

        agent_logger = self._get_agent_logger("route")
        agent_logger.bind_context(state.trace_id, state.session_id)

        try:
            from smartroute.agents.route import RoutePlanningAgent
            agent = RoutePlanningAgent()
            routes = await agent.execute(state)
            state.routes = routes

            agent_logger.timing("route_planning", timer.stop())

        except Exception as e:
            agent_logger.error("route_failed", error=str(e))
            state.routes = []
            state.error_info = {
                "agent": "route",
                "error": str(e),
            }

        state.update_timing("route", timer.stop())
        return state

    async def _presentation_node(self, state: SystemState) -> SystemState:
        """Presentation Agent 节点"""
        timer = Timer()
        timer.start()

        agent_logger = self._get_agent_logger("presentation")
        agent_logger.bind_context(state.trace_id, state.session_id)

        try:
            from smartroute.agents.presentation import PresentationAgent
            agent = PresentationAgent()
            final_response = await agent.execute(state)
            state.final_response = final_response

            agent_logger.timing("presentation", timer.stop())

        except Exception as e:
            agent_logger.error("presentation_failed", error=str(e))
            # 最小化输出
            state.final_response = {
                "session_id": state.session_id,
                "summary": "方案生成遇到问题",
                "plans": state.routes or [],
                "success": False,
                "error_message": str(e),
            }

        state.update_timing("presentation", timer.stop())
        return state

    async def _fallback_node(self, state: SystemState) -> SystemState:
        """降级处理节点"""
        logger.warning(
            "fallback_node_triggered",
            session_id=state.session_id,
        )

        # 应用 L2 降级
        state = self.fallback_handler.handle_l2_fallback(state)

        return state


# 全局 Orchestrator 实例
orchestrator_graph: OrchestratorGraph | None = None


def get_orchestrator() -> OrchestratorGraph:
    """获取全局 Orchestrator 实例"""
    global orchestrator_graph
    if orchestrator_graph is None:
        orchestrator_graph = OrchestratorGraph()
        orchestrator_graph.build_graph()
    return orchestrator_graph