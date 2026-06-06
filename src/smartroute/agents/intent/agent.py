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
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# 设置 .env 文件的绝对路径
import os
os.chdir(project_root)
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
        from smartroute.core.config import get_settings
        settings = get_settings()
        print(settings.llm)
        # 合并对话历史
        dialog_history = state.dialog_history[-self.get_config_value("max_dialog_history_rounds", 3):]

        # 构建 Prompt 和 Function Schema
        prompt = self.extractor.build_prompt(
            query=state.raw_query,
            dialog_history=dialog_history,
            current_date=current_date,
            request_type=state.request_type,
        )
        function_schema = self.extractor.get_function_schema()

        # 调用 LLM Function Calling（统一由 Agent 管理）
        try:
            result = await self.call_llm_with_function(
                messages=[{"role": "user", "content": prompt}],
                function_schema=function_schema,
                temperature=0.1,
            )

        except Exception as e:
            self.logger.error("slot_extraction_failed", error=str(e))
            raise IntentExtractionError(
                message=f"意图抽取失败: {e}",
                raw_query=state.raw_query,
            ) from e

        print("LLM Response:\n", result)

        # 解析结果
        intent = self.extractor.parse_result(
            result=result,
            query=state.raw_query,
            request_type=state.request_type,
            existing_intent=state.intent,
        )
        print("槽位抽取Intent:\n", intent.model_dump())

        # 隐式推理
        intent = self.rule_engine.apply(intent)
        print("隐式推理Intent:\n", intent.model_dump())

        # 歧义检测
        need_clarify, question = self.ambiguity_detector.detect(intent)
        print("歧义检测Intent:\n", intent.model_dump())

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
            合并后的 IntentResult
        """
        from smartroute.core.config import get_settings
        settings = get_settings()

        current_date = datetime.now().strftime("%Y-%m-%d")

        prompt = self.extractor.build_prompt(
            query=new_query,
            dialog_history=[],
            current_date=current_date,
            request_type="MODIFY",
        )
        function_schema = self.extractor.get_function_schema()

        result = await self.call_llm_with_function(
            messages=[{"role": "user", "content": prompt}],
            function_schema=function_schema,
            temperature=0.1,
        )
        print( result)
        new_intent = self.extractor.parse_result(
            result=result,
            query=new_query,
            request_type="MODIFY",
        )

        return self.extractor.merge_incremental(base_intent, new_intent, operation_type)

if __name__ == "__main__":
    import asyncio
    query1 = "我们一家三口这周六想去杭州西湖玩一天，孩子6岁，体力一般，所以不想安排得太赶，也不想走太多路。希望上午能看看西湖经典风景，中午找一家适合带孩子吃饭的本地餐厅，下午可以安排一些轻松的亲子活动，比如坐船、喂鱼、拍照之类的。 我们比较怕人挤人，希望尽量避开特别热门、排队很久的地方。预算大概 600 元以内，不算来回交通。最好路线能顺一点，不要来回绕路。如果下午孩子累了，也希望有可以提前结束或者找地方休息的备选方案。另外如果当天西湖边人太多，能不能推荐一个相对安静一点、但也适合家庭散步和拍照的替代路线?"
    query2="明天上午一个人去西湖，下午去灵隐寺"
    intent_agent = IntentAgent()

    state = SystemState(raw_query=query1)
    result = asyncio.run(intent_agent.execute(state))
    for k, v in result.items():
        print(f"{k}: {v}")


