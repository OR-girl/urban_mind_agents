"""
Slot Extractor - 槽位抽取器

使用 LLM Function Calling 从用户输入中抽取结构化槽位
"""

import json
from datetime import datetime, timedelta
from typing import Any

from smartroute.schemas.intent import (
    IntentResult,
    IntentType,
    SpatialConstraint,
    TemporalConstraint,
    PartyInfo,
    Preferences,
    BudgetInfo,
)


INTENT_EXTRACTION_PROMPT = """
你是一个专业的出行意图解析助手。请从用户的输入中提取结构化的出行意图信息。

规则：
1. 仅提取用户明确表达或可以合理推断的信息，不要凭空捏造
2. 对于不确定的字段，留空而不是猜测
3. 注意识别隐式约束（如"带老人"暗示步行限制）
4. 日期如果是相对表达（"明天"、"这周六"），请转换为绝对日期

当前日期：{current_date}
请求类型：{request_type}
对话历史（最近轮次）：
{dialog_history}

用户输入：{user_query}
"""

INTENT_FUNCTION_SCHEMA = {
    "name": "extract_intent",
    "description": "提取用户出行意图的结构化信息",
    "parameters": {
        "type": "object",
        "properties": {
            "intent_type": {
                "type": "string",
                "enum": ["tour", "food_tour", "city_walk", "business", "date", "family", "nature", "culture"],
                "description": "意图类型",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "置信度",
            },
            "spatial": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市"},
                    "region": {"type": "string", "description": "区域/商圈"},
                    "anchor_poi": {"type": "string", "description": "锚点POI"},
                    "radius_km": {"type": "number", "description": "搜索半径(km)"},
                    "exclude_areas": {"type": "array", "items": {"type": "string"}, "description": "排除区域"},
                },
                "required": ["city"],
            },
            "temporal": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期(YYYY-MM-DD)"},
                    "start_time": {"type": "string", "default": "09:00", "description": "出发时间"},
                    "end_time": {"type": "string", "default": "18:00", "description": "结束时间"},
                    "duration_hours": {"type": "number", "default": 8.0, "description": "总时长(小时)"},
                    "flexibility": {"type": "string", "enum": ["strict", "flexible"], "default": "flexible"},
                    "meal_preferences": {"type": "array", "items": {"type": "string"}, "description": "用餐时段偏好"},
                },
                "required": ["date"],
            },
            "party": {
                "type": "object",
                "properties": {
                    "size": {"type": "integer", "default": 1, "description": "人数"},
                    "composition": {"type": "array", "items": {"type": "string"}, "description": "构成: elder/child/adult/teen"},
                    "child_ages": {"type": "array", "items": {"type": "integer"}, "description": "儿童年龄列表"},
                    "special_needs": {"type": "array", "items": {"type": "string"}, "description": "特殊需求: wheelchair/stroller"},
                },
            },
            "preferences": {
                "type": "object",
                "properties": {
                    "must_have": {"type": "array", "items": {"type": "string"}, "description": "必须包含的类型/主题"},
                    "nice_to_have": {"type": "array", "items": {"type": "string"}, "description": "希望包含"},
                    "avoid": {"type": "array", "items": {"type": "string"}, "description": "明确排除"},
                    "themes": {"type": "array", "items": {"type": "string"}, "description": "主题标签"},
                    "cuisine_types": {"type": "array", "items": {"type": "string"}, "description": "菜系偏好"},
                    "poi_style": {"type": "string", "enum": ["popular", "niche", "balanced"], "description": "POI风格偏好"},
                },
            },
            "budget": {
                "type": "object",
                "properties": {
                    "per_person": {"type": "number", "description": "人均预算(元)"},
                    "level": {"type": "string", "enum": ["budget", "mid", "premium", "luxury"], "description": "消费档位"},
                },
            },
            "ambiguity_flags": {"type": "array", "items": {"type": "string"}, "description": "需要反问的字段"},
            "inferred_fields": {"type": "array", "items": {"type": "string"}, "description": "系统自动推断的字段"},
        },
        "required": ["intent_type", "confidence", "spatial", "temporal"],
    },
}


class SlotExtractor:
    """
    槽位抽取器
    
    使用 LLM Function Calling 抽取结构化意图
    """

    def __init__(self) -> None:
        self._llm_router = None

    async def extract(
        self,
        query: str,
        dialog_history: list[dict[str, Any]],
        current_date: str,
        request_type: str = "NEW",
        existing_intent: dict[str, Any] | None = None,
    ) -> IntentResult:
        """
        抽取意图槽位
        
        Args:
            query: 用户输入
            dialog_history: 对话历史
            current_date: 当前日期
            request_type: 请求类型
            existing_intent: 已有意图（多轮增量）
            
        Returns:
            IntentResult
        """
        # 构建Prompt
        history_text = "\n".join([
            f"[{h.get('role', 'user')}]: {h.get('content', '')}"
            for h in dialog_history
        ]) if dialog_history else "无对话历史"

        prompt = INTENT_EXTRACTION_PROMPT.format(
            current_date=current_date,
            request_type=request_type,
            dialog_history=history_text,
            user_query=query,
        )

        # 调用LLM Function Calling
        result = await self._call_llm_function(prompt, INTENT_FUNCTION_SCHEMA)

        # 解析结果
        intent = self._parse_result(result)

        # 多轮增量合并
        if existing_intent and request_type in ("MODIFY", "CLARIFY"):
            intent = self.merge_incremental(
                IntentResult.model_validate(existing_intent),
                intent,
                self._detect_operation_type(query),
            )

        return intent

    async def _call_llm_function(
        self,
        prompt: str,
        function_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        调用LLM Function Calling
        
        Args:
            prompt: 输入提示
            function_schema: Function Schema
            
        Returns:
            Function返回的JSON数据
        """
        # 延迟导入避免循环依赖
        from smartroute.services.llm.router import LLMRouter
        
        if self._llm_router is None:
            self._llm_router = LLMRouter()

        result = await self._llm_router.call_with_function(
            messages=[{"role": "user", "content": prompt}],
            function_schema=function_schema,
            model="gpt-4o",  # 意图抽取使用高精度模型
            temperature=0.1,
        )

        return result

    def _parse_result(self, result: dict[str, Any]) -> IntentResult:
        """
        解析LLM返回结果
        
        Args:
            result: Function返回的JSON
            
        Returns:
            IntentResult
        """
        # 处理相对日期转换
        if result.get("spatial"):
            spatial = SpatialConstraint(**result["spatial"])
        else:
            spatial = SpatialConstraint(city="未知")

        if result.get("temporal"):
            temporal_data = result["temporal"]
            temporal_data["date"] = self._resolve_relative_date(
                temporal_data.get("date", "")
            )
            temporal = TemporalConstraint(**temporal_data)
        else:
            temporal = TemporalConstraint(date=datetime.now().strftime("%Y-%m-%d"))

        if result.get("party"):
            party = PartyInfo(**result["party"])
        else:
            party = PartyInfo()

        if result.get("preferences"):
            preferences = Preferences(**result["preferences"])
        else:
            preferences = Preferences()

        if result.get("budget"):
            budget = BudgetInfo(**result["budget"])
        else:
            budget = BudgetInfo()

        intent_type = IntentType(result.get("intent_type", "tour"))
        confidence = result.get("confidence", 0.5)

        return IntentResult(
            intent_type=intent_type,
            confidence=confidence,
            spatial=spatial,
            temporal=temporal,
            party=party,
            preferences=preferences,
            budget=budget,
            ambiguity_flags=result.get("ambiguity_flags", []),
            inferred_fields=result.get("inferred_fields", []),
            raw_query=result.get("raw_query", ""),
        )

    def _resolve_relative_date(self, date_str: str) -> str:
        """
        解析相对日期
        
        Args:
            date_str: 日期字符串
            
        Returns:
            绝对日期 YYYY-MM-DD
        """
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")

        today = datetime.now()

        relative_dates = {
            "今天": today,
            "明天": today + timedelta(days=1),
            "后天": today + timedelta(days=2),
            "后天": today + timedelta(days=2),
        }

        if date_str in relative_dates:
            return relative_dates[date_str].strftime("%Y-%m-%d")

        # 处理"这周六"等表达式
        if "周" in date_str or "星期" in date_str:
            weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
            for key, value in weekday_map.items():
                if key in date_str:
                    target_weekday = value
                    days_ahead = target_weekday - today.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        return date_str

    def _detect_operation_type(self, query: str) -> str:
        """
        检测操作类型
        
        Args:
            query: 用户输入
            
        Returns:
            ADD/REPLACE/REMOVE
        """
        remove_keywords = ["去掉", "删除", "不要", "取消"]
        replace_keywords = ["换成", "改为", "替换", "换成"]

        for kw in remove_keywords:
            if kw in query:
                return "REMOVE"

        for kw in replace_keywords:
            if kw in query:
                return "REPLACE"

        return "ADD"

    def merge_incremental(
        self,
        base_intent: IntentResult,
        new_intent: IntentResult,
        operation_type: str = "ADD",
    ) -> IntentResult:
        """
        多轮增量意图合并
        
        Args:
            base_intent: 基础意图
            new_intent: 新意图
            operation_type: ADD/REPLACE/REMOVE
            
        Returns:
            合合后的 IntentResult
        """
        base_dict = base_intent.model_dump()
        new_dict = new_intent.model_dump()

        if operation_type == "ADD":
            # 追加模式：新字段补充到已有字段
            for key in ["must_have", "nice_to_have", "avoid", "themes"]:
                existing = base_dict["preferences"].get(key, [])
                new_items = new_dict["preferences"].get(key, [])
                base_dict["preferences"][key] = list(set(existing + new_items))

        elif operation_type == "REPLACE":
            # 替换模式：新字段覆盖已有字段
            for key, value in new_dict.items():
                if value and value != base_dict.get(key):
                    if key == "preferences":
                        # 特殊处理：只替换非空字段
                        for pref_key, pref_value in value.items():
                            if pref_value:
                                base_dict["preferences"][pref_key] = pref_value
                    else:
                        base_dict[key] = value

        elif operation_type == "REMOVE":
            # 删除模式：从 must_have 中移除
            for item in new_dict["preferences"].get("avoid", []):
                if item in base_dict["preferences"].get("must_have", []):
                    base_dict["preferences"]["must_have"].remove(item)

        return IntentResult.model_validate(base_dict)
