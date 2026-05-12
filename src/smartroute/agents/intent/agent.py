"""
Intent Agent - 意图识别Agent主类

将用户自由文本转化为结构化指令，包括：
- 意图大类分类
- 槽位抽取
- 隐式推理
- 歧义检测
"""

from datetime import datetime
from typing import Any

from smartroute.agents.base import LLMBasedAgent
from smartroute.agents.intent.extractor import SlotExtractor
from smartroute.agents.intent.rules import ImplicitRuleEngine
from smartroute.agents.intent.ambiguity import AmbiguityDetector
from smartroute.core.exceptions import IntentExtractionError
from smartroute.schemas import SystemState
from smartroute.schemas.intent import IntentResult


class IntentAgent(LLMBasedAgent):
    """
    意图识别Agent
    
    处理流程：
    1. 文本预处理
    2. 上下文融合（DialogStateTracker）
    3. 槽位抽取（LLM Function Calling）
    4. 隐式推理（规则引擎）
    5. 歧义检测
    """

    agent_name = "intent"

    def __init__(self) -> None:
        super().__init__()
        self.extractor = SlotExtractor()
        self.rule_engine = ImplicitRuleEngine(
            rules_path=self.get_config_value("implicit_rules_path", "config/implicit_rules.yaml")
        )
        self.ambiguity_detector = AmbiguityDetector(
            confidence_threshold=self.get_config_value("confidence_threshold", 0.7)
        )

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行意图识别
        
        Args:
            state: 系统状态
            
        Returns:
            包含 IntentResult 的字典
        """
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # 合并对话历史
        dialog_history = state.dialog_history[-self.get_config_value("max_dialog_history_rounds", 3):]
        
        # 槽位抽取
        try:
            intent = await self.extractor.extract(
                query=state.raw_query,
                dialog_history=dialog_history,
                current_date=current_date,
                request_type=state.request_type,
                existing_intent=state.intent,  # 多轮增量合并
            )
        except Exception as e:
            self.logger.error("slot_extraction_failed", error=str(e))
            raise IntentExtractionError(
                message=f"意图抽取失败: {e}",
                code="INTENT_EXTRACTION_ERROR",
            ) from e

        # 隐式推理
        intent = self.rule_engine.apply(intent)
        
        # 歧义检测
        need_clarify, question = self.ambiguity_detector.detect(intent)
        
        return {
            "intent": intent.model_dump(),
            "clarification_needed": need_clarify,
            "clarification_question": question,
        }

    async def extract_intent_incremental(
        self,
        base_intent: IntentResult,
        new_query: str,
        operation_type: str = "ADD",
    ) -> IntentResult:
        """
        多轮增量意图合并
        
        Args:
            base_intent: 基础意图
            new_query: 新输入
            operation_type: ADD/REPLACE/REMOVE
            
        Returns:
            合合后的 IntentResult
        """
        new_intent = await self.extractor.extract(
            query=new_query,
            dialog_history=[],
            current_date=datetime.now().strftime("%Y-%m-%d"),
            request_type="MODIFY",
        )
        
        return self.extractor.merge_incremental(base_intent, new_intent, operation_type)
