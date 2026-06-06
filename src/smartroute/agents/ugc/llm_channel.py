"""
SmartRoute Agent UGC Insight Agent LLM 通道模块

使用 LLM 进行高精度的评论分析
"""

import json
from typing import Any

from smartroute.agents.base import LLMBasedAgent
from smartroute.core.config import get_settings
from smartroute.core.logging import get_logger
from smartroute.schemas import UGCSentiment

settings = get_settings()
logger = get_logger("agent.ugc.llm_channel")


UGC_ANALYSIS_PROMPT = """
你是一个专业的餐厅/景点评论分析师。请分析以下 POI 的用户评论，提取结构化洞察。

POI 信息：
- 名称：{poi_name}
- 类型：{poi_category}
- 综合评分：{rating}

近期评论（{review_count} 条，近 3 个月）：
{reviews_text}

只返回一个JSON对象，不要任何解释、不要markdown代码块。格式如下：
{{"highlights":["亮点1","亮点2","亮点3"],"warnings":["避雷1","避雷2","避雷3"],"best_time":"最佳游览时段","ugc_sentiment":{{"food":0,"service":0,"environment":0,"wait_time":0,"value_for_money":0}},"scene_tags":["标签1","标签2"],"queue_warning":"排队预警","peak_hours":["高峰1","高峰2"],"estimated_duration_min":60}}

规则：
- highlights: 最多3条，每条15字以内，基于评论中的正面体验
- warnings: 最多3条，每条15字以内，基于评论中的问题
- ugc_sentiment: food/service/environment/wait_time/value_for_money 各0-5分，基于评论客观评分
- scene_tags: 从[亲子友好,商务宴请,约会浪漫,独自用餐,聚会聚餐,夜宵,下午茶,快餐便餐]中选择
- queue_warning: 如有排队问题请描述，无则空字符串
- peak_hours: 高峰时段列表，无则空数组
- estimated_duration_min: 建议游览时长(分钟)，默认60
"""


class LLMChannel(LLMBasedAgent):
    """
    LLM 通道

    使用大语言模型进行高精度评论分析
    """

    agent_name = "ugc_llm_channel"

    def __init__(self) -> None:
        super().__init__()
        self.max_reviews_per_poi = 50

    async def execute(self, state: Any) -> dict[str, Any]:
        """
        执行入口（LLMChannel 作为辅助组件，不直接作为 Agent 运行）

        Args:
            state: 系统状态（不直接使用）

        Returns:
            状态信息
        """
        return {"status": "llm_channel_ready"}

    async def analyze(
        self,
        poi: dict[str, Any],
        reviews: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        使用 LLM 分析 POI 评论

        Args:
            poi: POI 信息
            reviews: 评论列表

        Returns:
            结构化分析结果
        """
        # 选取评论（优先低分评论用于避雷提取）
        selected_reviews = self._select_reviews(reviews)

        # 格式化评论文本
        reviews_text = self._format_reviews_text(selected_reviews)

        # 构建 Prompt
        prompt = UGC_ANALYSIS_PROMPT.format(
            poi_name=poi.get("name", ""),
            poi_category=poi.get("category", ""),
            rating=poi.get("rating", "N/A"),
            review_count=len(selected_reviews),
            reviews_text=reviews_text,
        )

        try:
            # 直接调用 Anthropic API（绕过 router 避免 fallback 链路复杂性）
            from anthropic import AsyncAnthropic
            import os
            client = AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"),
            )
            resp = await client.messages.create(
                model=self._get_model_name(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000,
                thinking={"type": "disabled"},
            )
            response = ""
            for block in resp.content:
                if block.type == "text":
                    response = block.text
                    break

            # 检查响应是否为空
            if not response or not response.strip():
                logger.warning("llm_empty_response", poi_id=poi.get("poi_id"))
                return self._get_empty_result(poi, "empty_response")

            # 解析结果
            result = self._parse_response(response, poi)

            result["analysis_channel"] = "llm"
            result["review_count_analyzed"] = len(selected_reviews)

            return result

        except Exception as e:
            logger.error("llm_analysis_failed", poi_id=poi.get("poi_id"), error=str(e))
            # 返回空结果
            return self._get_empty_result(poi, "llm_error")

    def _get_model_name(self) -> str:
        """获取模型名称 - 直接调用 Anthropic API"""
        llm_config = settings.get_llm_config()
        providers = llm_config.get("providers", [])
        for provider in providers:
            if provider.get("name") == "anthropic":
                return provider.get("models", {}).get("ugc_analysis", "deepseek-v4-pro")
        return "deepseek-v4-pro"

    def _select_reviews(
        self,
        reviews: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        选择要分析的评论

        优先低分评论（避雷更有价值），并控制数量
        """
        if not reviews:
            return []

        # 按评分排序，低分优先
        sorted_reviews = sorted(
            reviews,
            key=lambda r: (
                r.get("rating", 3),
                -r.get("timestamp", 0),
            ),
        )

        return sorted_reviews[:self.max_reviews_per_poi]

    def _format_reviews_text(
        self,
        reviews: list[dict[str, Any]],
    ) -> str:
        """格式化评论文本"""
        lines: list[str] = []

        for review in reviews:
            rating = review.get("rating", "?")
            content = review.get("content", "")[:200]
            lines.append(f"[{rating}星] {content}")

        return "\n".join(lines)

    def _parse_response(
        self,
        response: str,
        poi: dict[str, Any],
    ) -> dict[str, Any]:
        """
        解析 LLM 响应

        Args:
            response: LLM 返回的文本
            poi: POI 信息

        Returns:
            结构化结果
        """
        try:
            # 尝试解析 JSON
            # 如果响应包含 markdown 代码块，提取其中的 JSON
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()

            result = json.loads(response)

            # 确保必要字段存在
            result.setdefault("highlights", [])
            result.setdefault("warnings", [])
            result.setdefault("best_time", "")
            result.setdefault("ugc_sentiment", {})
            result.setdefault("scene_tags", [])
            result.setdefault("queue_warning", "")
            result.setdefault("peak_hours", [])
            result.setdefault("estimated_duration_min", 60)
            result.setdefault("confidence", 0.8)  # JSON 解析成功即认为置信度为 0.8

            # 截断过长的内容
            result["highlights"] = result["highlights"][:3]
            result["warnings"] = result["warnings"][:3]
            result["scene_tags"] = result["scene_tags"][:5]

            return result

        except json.JSONDecodeError as e:
            logger.warning("llm_response_parse_failed", error=str(e))
            return self._get_empty_result(poi, "parse_error")

    def _get_empty_result(
        self,
        poi: dict[str, Any],
        error_reason: str = "",
    ) -> dict[str, Any]:
        """获取空结果（失败时使用）"""
        return {
            "poi_id": poi.get("poi_id", ""),
            "highlights": [],
            "warnings": [],
            "best_time": "",
            "ugc_sentiment": {
                "food": 0.0,
                "service": 0.0,
                "environment": 0.0,
                "wait_time": 0.0,
                "value_for_money": 0.0,
            },
            "scene_tags": [],
            "queue_warning": "",
            "peak_hours": [],
            "estimated_duration_min": 60,
            "confidence": 0.0,
            "analysis_channel": "llm",
            "error_reason": error_reason,
        }

    async def batch_analyze(
        self,
        pois: list[dict[str, Any]],
        reviews_map: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        """
        批量分析多个 POI

        Args:
            pois: POI 列表
            reviews_map: POI ID -> 评论列表的映射

        Returns:
            POI ID -> 分析结果的映射
        """
        results: dict[str, dict[str, Any]] = {}

        for poi in pois:
            poi_id = poi.get("poi_id", "")
            reviews = reviews_map.get(poi_id, [])

            if reviews:
                result = await self.analyze(poi, reviews)
                results[poi_id] = result

        return results


# 全局 LLM 通道实例
_llm_channel: LLMChannel | None = None


def get_llm_channel() -> LLMChannel:
    """获取 LLM 通道实例"""
    global _llm_channel
    if _llm_channel is None:
        _llm_channel = LLMChannel()
    return _llm_channel