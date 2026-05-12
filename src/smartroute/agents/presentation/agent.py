"""
Presentation Agent - 方案生成Agent主类

将路线规划结果转化为用户友好的展示内容，支持流式输出
"""

import asyncio
from typing import Any

from smartroute.agents.base import LLMBasedAgent
from smartroute.agents.presentation.reason_generator import PersonalizedReasonGenerator
from smartroute.agents.presentation.comparison import PlanComparisonGenerator
from smartroute.agents.presentation.hints import AdjustableHintsGenerator
from smartroute.schemas import SystemState
from smartroute.schemas.response import FinalResponse


class PresentationAgent(LLMBasedAgent):
    """
    方案生成Agent
    
    处理流程：
    1. 方案差异点提取
    2. 个性化话术生成
    3. 多模态渲染数据组装
    4. 可调整提示生成
    5. 流式输出
    """

    agent_name = "presentation"

    def __init__(self) -> None:
        super().__init__()
        self.reason_generator = PersonalizedReasonGenerator(
            max_reason_length=self.get_config_value("personalization", {}).get("max_reason_length", 60),
        )
        self.comparison_generator = PlanComparisonGenerator()
        self.hints_generator = AdjustableHintsGenerator()

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行方案生成
        
        Args:
            state: 系统状态
            
        Returns:
            包含最终响应的字典
        """
        routes = state.routes or []
        profile = state.get_profile()
        intent = state.get_intent()

        if not routes:
            self.logger.warning("no_routes_for_presentation")
            return {"final_response": self._empty_response(state)}

        # 生成个性化推荐理由
        enriched_pois_map = self._build_enriched_pois_map(state)
        
        for route in routes:
            timeline = route.get("timeline", [])
            for item in timeline:
                poi_id = item.get("poi_id", "")
                if poi_id in enriched_pois_map:
                    poi_data = enriched_pois_map[poi_id]
                    reason = await self.reason_generator.generate(
                        poi=poi_data,
                        profile=profile,
                        intent=intent,
                    )
                    item["why_for_you"] = reason

        # 方案对比矩阵
        plan_comparison = self.comparison_generator.generate(routes)

        # 可调整提示
        adjustable_hints = self.hints_generator.generate(routes, enriched_pois_map)

        # 生成方案概述
        summary = await self._generate_summary(routes, profile, intent)

        # 组装最终响应
        final_response = FinalResponse(
            session_id=state.session_id,
            summary=summary,
            plans=routes,
            plan_comparison=plan_comparison,
            adjustable_hints=adjustable_hints,
            metadata={
                "generated_at": state.trace_id,
                "total_cost": state.llm_cost_total,
                "timings": state.stage_timings,
            },
        )

        return {"final_response": final_response.model_dump()}

    def _build_enriched_pois_map(self, state: SystemState) -> dict[str, Any]:
        enriched_pois = state.enriched_pois or []
        return {poi.get("poi_id", ""): poi for poi in enriched_pois}

    async def _generate_summary(self, routes: list[Any], profile: Any, intent: Any) -> str:
        if not routes:
            return "抱歉，未能生成合适的路线方案。"

        summary_prompt = self._build_summary_prompt(routes, profile, intent)
        summary = await self.call_llm(
            messages=[{"role": "user", "content": summary_prompt}],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=300,
        )
        return summary

    def _build_summary_prompt(self, routes: list[Any], profile: Any, intent: Any) -> str:
        intent_desc = intent.intent_type.value if intent else "出行"
        profile_summary = ""
        if profile and profile.scene_preferences:
            top_scenes = sorted(profile.scene_preferences.items(), key=lambda x: x[1], reverse=True)[:2]
            profile_summary = f"，您偏好{', '.join([s[0] for s in top_scenes])}"

        return f"""
请为用户生成一个简洁的路线方案概述（不超过50字）。

用户需求：{intent_desc}{profile_summary}
方案数量：{len(routes)}个

要求：语气自然、友好，突出方案特色，简短（不超过50字）。
"""

    def _empty_response(self, state: SystemState) -> dict[str, Any]:
        return {
            "session_id": state.session_id,
            "summary": "抱歉，未能生成合适的路线方案。请尝试修改您的需求。",
            "plans": [],
            "plan_comparison": {},
            "adjustable_hints": ["请重新描述您的出行需求"],
            "metadata": {"error": "no_routes"},
        }

    async def stream_output(self, routes: list[Any], profile: Any) -> Any:
        import json
        from fastapi.responses import StreamingResponse

        async def generate():
            yield f"data: {json.dumps({'type': 'structured', 'plans': routes}, ensure_ascii=False)}\n\n"
            text = "为您定制了三套个性化路线方案..."
            for char in text:
                yield f"data: {json.dumps({'type': 'text', 'token': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
