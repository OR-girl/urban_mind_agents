"""
Slot Extractor - 槽位抽取器

负责构建意图抽取的 Prompt 和解析 LLM 返回结果
LLM 调用由上层 Agent 统一管理
"""

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
    POIScheduleItem,
    TimeSlot,
)


INTENT_EXTRACTION_PROMPT = """
你是一个专业的出行意图解析助手。请从用户的输入中提取结构化的出行意图信息。

规则：
1. 仅提取用户明确表达或可以合理推断的信息，不要凭空捏造
2. 对于不确定的字段，留空而不是猜测
3. 注意识别隐式约束（如"带老人"暗示步行限制）
4. 日期如果是相对表达（"明天"、"这周六"），请转换为绝对日期
5. 时间段关键词与时间推断（重要）：
   - "上午" → time_slot=morning, start_time="08:00",end_time = "12:00"
   - "中午" → time_slot=noon, start_time="11:00",end_time = "14:00"
   - "下午" → time_slot=afternoon, start_time="14:00",end_time = "18:00"
   - "傍晚/晚上" → time_slot=evening, start_time="18:00",end_time = "20:00"
   - 如果用户说"上午去西湖"，poi_schedule中西湖的time_slot=morning, start_time="08:00",end_time = "12:00"
   - 同时temporal.start_time也应该设置为08:00（根据最早的时间段推断）
6. 如果用户明确指定了某个POI的时间段（如"上午去西湖，下午去灵隐寺"），必须记录在poi_schedule中，并推断对应的start_time
7. POI先后顺序识别（重要）：
   - 如果用户使用了顺序关键词（"先...然后..."、"先...再..."、"第一站...第二站..."等），必须记录sequence字段
   - 例如："先去西湖，再去灵隐寺" → 西湖sequence=1，灵隐寺sequence=2
   - 例如："第一站西湖，第二站灵隐寺，最后去浙大" → sequence分别为1、2、3
   - 如果用户只是并列列举（如"去西湖和灵隐寺"），没有明确顺序词，则sequence留空（不填写）
   - 不要根据时间段推断顺序（上午vs下午不代表用户有顺序偏好）

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
                    "anchor_poi": {"type": "string", "description": "锚点POI（第一个目的地）"},
                    "radius_km": {"type": "number", "description": "搜索半径(km)"},
                    "exclude_areas": {"type": "array", "items": {"type": "string"}, "description": "排除区域"},
                },
                "required": ["city"],
            },
            "temporal": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期(YYYY-MM-DD)"},
                    "start_time": {"type": "string", "default": "09:00", "description": "出发时间（根据时间段推断，如'上午'则08:00）"},
                    "end_time": {"type": "string", "default": "18:00", "description": "结束时间"},
                    "duration_hours": {"type": "number", "default": 8.0, "description": "总时长(小时)，应当根据end_time和start_time计算得到"},
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
                    "must_have": {"type": "array", "items": {"type": "string"}, "description": "必须包含的POI名称"},
                    "nice_to_have": {"type": "array", "items": {"type": "string"}, "description": "希望包含"},
                    "avoid": {"type": "array", "items": {"type": "string"}, "description": "明确排除"},
                    "themes": {"type": "array", "items": {"type": "string"}, "description": "主题标签"},
                    "cuisine_types": {"type": "array", "items": {"type": "string"}, "description": "菜系偏好"},
                    "poi_style": {"type": "string", "enum": ["popular", "niche", "balanced"], "description": "POI风格偏好"},
                },
            },
            "poi_schedule": {
                "type": "array",
                "description": "用户明确指定时间段或顺序的POI安排",
                "items": {
                    "type": "object",
                    "properties": {
                        "poi_name": {"type": "string", "description": "POI名称"},
                        "time_slot": {"type": "string", "enum": ["morning", "noon", "afternoon", "evening", "night", "all_day"], "description": "时间段"},
                        "start_time": {"type": "string", "description": "期望开始时间(HH:MM)。根据时间段推断：morning→08:00, noon→11:00, afternoon→14:00, evening→18:00, night→20:00"},
                        "duration_minutes": {"type": "integer", "description": "期望停留时长(分钟)"},
                        "sequence": {"type": "integer", "minimum": 1, "description": "访问顺序（仅当用户明确说'先去A再去B'时填写，如A的sequence=1，B的sequence=2。如果用户没有明确顺序，则不填写此字段）"},
                        "priority": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1, "description": "优先级：1=必须去，2=想去，3=可选"},
                        "note": {"type": "string", "description": "备注"},
                    },
                    "required": ["poi_name"],
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

    负责构建 Prompt 和解析结果，不直接调用 LLM
    """

    def build_prompt(
        self,
        query: str,
        dialog_history: list[dict[str, Any]],
        current_date: str,
        request_type: str = "NEW",
    ) -> str:
        """
        构建意图抽取的 Prompt

        Args:
            query: 用户输入
            dialog_history: 对话历史
            current_date: 当前日期
            request_type: 请求类型

        Returns:
            构建好的 Prompt
        """
        history_text = "\n".join([
            f"[{h.get('role', 'user')}]: {h.get('content', '')}"
            for h in dialog_history
        ]) if dialog_history else "无对话历史"

        return INTENT_EXTRACTION_PROMPT.format(
            current_date=current_date,
            request_type=request_type,
            dialog_history=history_text,
            user_query=query,
        )

    def get_function_schema(self) -> dict[str, Any]:
        """
        获取 Function Calling Schema

        Returns:
            INTENT_FUNCTION_SCHEMA
        """
        return INTENT_FUNCTION_SCHEMA

    def parse_result(
        self,
        result: dict[str, Any],
        query: str,
        request_type: str = "NEW",
        existing_intent: dict[str, Any] | None = None,
    ) -> IntentResult:
        """
        解析 LLM 返回结果

        Args:
            result: LLM Function Calling 返回的 JSON
            query: 用户输入（用于检测操作类型）
            request_type: 请求类型
            existing_intent: 已有意图（多轮增量）

        Returns:
            IntentResult
        """
        intent = self._parse_to_intent(result, query)

        # 多轮增量合并
        if existing_intent and request_type in ("MODIFY", "CLARIFY"):
            intent = self.merge_incremental(
                IntentResult.model_validate(existing_intent),
                intent,
                self._detect_operation_type(query),
            )

        return intent

    def _parse_to_intent(self, result: dict[str, Any], query: str) -> IntentResult:
        """
        将 LLM 返回的 JSON 解析为 IntentResult

        Args:
            result: Function 返回的 JSON
            query: 用户原始输入

        Returns:
            IntentResult
        """
        # 处理相对日期转换
        if result.get("spatial"):
            spatial_data = result["spatial"]
            # city 为 None 时使用默认值
            if spatial_data.get("city") is None:
                spatial_data["city"] = "未知"
            spatial = SpatialConstraint(**spatial_data)
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

        # 解析 POI 时间安排
        poi_schedule = []
        if result.get("poi_schedule"):
            for item in result["poi_schedule"]:
                try:
                    time_slot = None
                    if item.get("time_slot"):
                        time_slot = TimeSlot(item["time_slot"])

                    # sequence 仅在用户明确指定顺序时才有值
                    sequence = item.get("sequence") if "sequence" in item else None

                    poi_schedule.append(
                        POIScheduleItem(
                            poi_name=item.get("poi_name", ""),
                            time_slot=time_slot,
                            start_time=item.get("start_time"),
                            duration_minutes=item.get("duration_minutes"),
                            sequence=sequence,
                            priority=item.get("priority", 1),
                            note=item.get("note"),
                        )
                    )
                except Exception:
                    # 忽略解析错误的项
                    pass

        # 如果 spatial.anchor_poi 为空，从 poi_schedule 推断（取第一个POI）
        if spatial.anchor_poi is None and poi_schedule:
            # 按sequence排序，取第一个；若无sequence则取列表第一个
            sorted_schedule = sorted(
                poi_schedule,
                key=lambda x: x.sequence if x.sequence is not None else 999
            )
            spatial.anchor_poi = sorted_schedule[0].poi_name

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
            poi_schedule=poi_schedule,
            ambiguity_flags=result.get("ambiguity_flags", []),
            inferred_fields=result.get("inferred_fields", []),
            raw_query=query,
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
            合并后的 IntentResult
        """
        base_dict = base_intent.model_dump()
        new_dict = new_intent.model_dump()

        if operation_type == "ADD":
            # 追加模式：新字段补充到已有字段
            for key in ["must_have", "nice_to_have", "avoid", "themes"]:
                existing = base_dict["preferences"].get(key, [])
                new_items = new_dict["preferences"].get(key, [])
                base_dict["preferences"][key] = list(set(existing + new_items))

            # 合并 poi_schedule：追加新的 POI 时间安排
            existing_poi_names = {item.get("poi_name") for item in base_dict.get("poi_schedule", [])}
            for new_item in new_dict.get("poi_schedule", []):
                if new_item.get("poi_name") not in existing_poi_names:
                    base_dict.setdefault("poi_schedule", []).append(new_item)

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
