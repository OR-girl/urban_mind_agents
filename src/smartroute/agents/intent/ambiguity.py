"""
SmartRoute Agent Intent Agent 歧义检测模块

检测用户输入中的歧义，生成反问
"""

from typing import Optional

from smartroute.core.logging import get_logger
from smartroute.schemas import IntentResult

logger = get_logger("agent.intent.ambiguity")


# 歧义检测规则配置
AMBIGUITY_RULES = [
    {
        "id": "city_missing",
        "condition": lambda intent: not intent.spatial.city,
        "question": "请问您计划在哪个城市游玩？",
        "priority": 1,
    },
    {
        "id": "date_missing",
        "condition": lambda intent: not intent.temporal.date,
        "question": "请问是哪天出行？",
        "priority": 2,
    },
    {
        "id": "low_confidence",
        "condition": lambda intent, threshold: intent.confidence < threshold,
        "question_template": "我理解您想{intent_type}，请问还有其他具体要求吗？",
        "priority": 3,
    },
    {
        "id": "time_poi_conflict",
        "condition": lambda intent: (
            intent.temporal.duration_hours < 2
            and len(intent.preferences.must_have) > 3
        ),
        "question": "您的时间较短但必去地点较多，是否可以减少必去景点，或延长游玩时间？",
        "priority": 1,
    },
    {
        "id": "budget_poi_conflict",
        "condition": lambda intent: (
            intent.budget.per_person
            and intent.budget.per_person < 100
            and intent.budget.level == "premium"
        ),
        "question": "您的人均预算较低但选择了高档消费档位，是否需要调整预算或档位？",
        "priority": 2,
    },
    {
        "id": "region_without_city",
        "condition": lambda intent: (
            intent.spatial.region
            and not intent.spatial.city
        ),
        "question": "请问您说的{region}是在哪个城市？",
        "priority": 1,
    },
]


def detect_ambiguity(
    intent: IntentResult,
    confidence_threshold: float = 0.7,
) -> tuple[bool, Optional[str]]:
    """
    检测意图中的歧义

    Args:
        intent: 意图结果
        confidence_threshold: 置信度阈值

    Returns:
        (是否需要反问, 反问内容) 元组
    """
    triggered_questions: list[tuple[int, str]] = []

    for rule in AMBIGUITY_RULES:
        # 检查条件
        condition = rule["condition"]

        # 处理不同参数数量的条件函数
        try:
            if rule["id"] == "low_confidence":
                is_triggered = condition(intent, confidence_threshold)
            else:
                is_triggered = condition(intent)
        except Exception:
            is_triggered = False

        if is_triggered:
            # 生成问题
            if "question" in rule:
                question = rule["question"]
            elif "question_template" in rule:
                # 使用模板生成问题
                template = rule["question_template"]
                intent_type_desc = _get_intent_type_description(intent.intent_type)
                question = template.format(intent_type=intent_type_desc)
            else:
                question = ""

            # 处理动态字段
            if "{region}" in question:
                question = question.replace("{region}", intent.spatial.region or "该区域")

            triggered_questions.append((rule["priority"], question))

            logger.debug(
                "ambiguity_rule_triggered",
                rule_id=rule["id"],
            )

    if not triggered_questions:
        return False, None

    # 按优先级排序，取前 2 个问题
    triggered_questions.sort(key=lambda x: x[0])
    questions = [q for _, q in triggered_questions[:2]]

    # 合并问题
    combined_question = " ".join(questions)

    return True, combined_question


def _get_intent_type_description(intent_type: str) -> str:
    """
    获取意图类型的描述文本

    Args:
        intent_type: 意图类型

    Returns:
        描述文本
    """
    descriptions = {
        "tour": "游览景点",
        "food_tour": "探索美食",
        "city_walk": "城市漫步",
        "business": "商务出行",
        "date": "约会",
        "family": "家庭出游",
        "nature": "自然探索",
        "culture": "文化历史游览",
    }

    return descriptions.get(intent_type, "出行游玩")


def validate_intent_completeness(intent: IntentResult) -> list[str]:
    """
    验证意图的完整性

    Args:
        intent: 意图结果

    Returns:
        缺失字段列表
    """
    missing_fields: list[str] = []

    # 必填字段检查
    if not intent.spatial.city:
        missing_fields.append("city")

    if not intent.temporal.date:
        missing_fields.append("date")

    if intent.party.size < 1:
        missing_fields.append("party_size")

    return missing_fields


def generate_clarification_questions(
    missing_fields: list[str],
) -> list[str]:
    """
    根据缺失字段生成反问问题

    Args:
        missing_fields: 缺失字段列表

    Returns:
        问题列表
    """
    field_questions = {
        "city": "请问您计划在哪个城市游玩？",
        "date": "请问是哪天出行？",
        "party_size": "请问有多少人一起出行？",
        "region": "请问您想去哪个区域或商圈？",
        "duration": "请问您计划游玩多长时间？",
    }

    questions: list[str] = []
    for field in missing_fields:
        if field in field_questions:
            questions.append(field_questions[field])

    return questions[:2]  # 最多问 2 个问题


class AmbiguityDetector:
    """
    歧义检测器

    提供更灵活的歧义检测能力
    """

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold

    def detect(self, intent: IntentResult) -> tuple[bool, Optional[str]]:
        """
        执行歧义检测

        Args:
            intent: 意图结果

        Returns:
            (是否需要反问, 反问内容)
        """
        return detect_ambiguity(intent, self.confidence_threshold)

    def validate(self, intent: IntentResult) -> list[str]:
        """
        验证意图完整性

        Args:
            intent: 意图结果

        Returns:
            缺失字段列表
        """
        return validate_intent_completeness(intent)