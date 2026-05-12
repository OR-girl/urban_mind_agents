"""
Implicit Rule Engine - 隐式推理规则引擎

基于 YAML 配置文件的规则引擎，根据已抽取字段推断隐含约束
"""

import yaml
from typing import Any

from smartroute.schemas.intent import IntentResult


class ImplicitRuleEngine:
    """
    隐式推理规则引擎
    
    支持：
    - 嵌套字段路径访问（如 party.child_ages）
    - 条件匹配（contains/contains_any/equals/any_less_than）
    - 动作执行（append/set/default_if_empty/max）
    """

    def __init__(self, rules_path: str = "config/implicit_rules.yaml") -> None:
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, path: str) -> list[dict[str, Any]]:
        """
        加载规则文件
        
        Args:
            path: YAML文件路径
            
        Returns:
            规则列表
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("rules", [])
        except FileNotFoundError:
            # 如果文件不存在，返回默认规则
            return self._default_rules()

    def _default_rules(self) -> list[dict[str, Any]]:
        """
        默认规则（当配置文件不存在时使用）
        """
        return [
            {
                "id": "elder_walk_limit",
                "condition": {"field": "party.composition", "contains": "elder"},
                "actions": [
                    {"field": "preferences.avoid", "append": "长距离步行"},
                    {"field": "preferences.avoid", "append": "爬山"},
                    {"field": "temporal.duration_hours", "max": 7.0},
                ],
                "description": "有老人时限制步行强度",
            },
            {
                "id": "toddler_indoor",
                "condition": {"field": "party.child_ages", "any_less_than": 6},
                "actions": [
                    {"field": "preferences.nice_to_have", "append": "室内场所"},
                    {"field": "preferences.nice_to_have", "append": "母婴室"},
                    {"field": "preferences.avoid", "append": "长时间排队"},
                ],
                "description": "有幼儿时优先室内场所",
            },
            {
                "id": "business_strict_time",
                "condition": {"field": "raw_query", "contains_any": ["出差", "商务", "会议"]},
                "actions": [
                    {"field": "intent_type", "set": "business"},
                    {"field": "temporal.flexibility", "set": "strict"},
                ],
                "description": "商务场景时间严格",
            },
            {
                "id": "default_duration",
                "condition": {"field": "raw_query", "contains_any": ["一日游", "全天"]},
                "actions": [
                    {"field": "temporal.duration_hours", "set": 8.0},
                    {"field": "temporal.start_time", "default_if_empty": "09:00"},
                ],
                "description": "一日游默认8小时",
            },
        ]

    def apply(self, intent: IntentResult) -> IntentResult:
        """
        应用所有匹配的隐式推理规则
        
        Args:
            intent: IntentResult
            
        Returns:
            应用规则后的 IntentResult
        """
        intent_dict = intent.model_dump()
        triggered_rules = []

        for rule in self.rules:
            if self._check_condition(rule.get("condition", {}), intent_dict):
                self._apply_actions(rule.get("actions", []), intent_dict)
                triggered_rules.append(rule.get("id", "unknown"))

        # 记录被推断的字段
        if "inferred_fields" not in intent_dict:
            intent_dict["inferred_fields"] = []
        intent_dict["inferred_fields"].extend(triggered_rules)

        return IntentResult.model_validate(intent_dict)

    def _check_condition(self, condition: dict[str, Any], data: dict[str, Any]) -> bool:
        """
        检查规则条件是否满足
        
        Args:
            condition: 条件字典
            data: Intent数据
            
        Returns:
            是否满足条件
        """
        if not condition:
            return False

        field_value = self._get_nested(data, condition.get("field", ""))

        if "contains" in condition:
            target = condition["contains"]
            if isinstance(field_value, list):
                return target in field_value
            return target in str(field_value or "")

        if "contains_any" in condition:
            keywords = condition["contains_any"]
            return any(kw in str(field_value or "") for kw in keywords)

        if "equals" in condition:
            return field_value == condition["equals"]

        if "any_less_than" in condition:
            threshold = condition["any_less_than"]
            if isinstance(field_value, list):
                return any(v < threshold for v in field_value if isinstance(v, (int, float)))
            return False

        return False

    def _get_nested(self, data: dict[str, Any], path: str) -> Any:
        """
        支持点分隔的嵌套字段路径
        
        Args:
            data: 数据字典
            path: 字段路径（如 party.child_ages）
            
        Returns:
            字段值
        """
        if not path:
            return None

        keys = path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

        return value

    def _apply_actions(self, actions: list[dict[str, Any]], data: dict[str, Any]) -> None:
        """
        执行规则动作
        
        Args:
            actions: 动作列表
            data: Intent数据字典（会被修改）
        """
        for action in actions:
            field_path = action.get("field", "")
            if not field_path:
                continue

            # 导航到目标位置
            keys = field_path.split(".")
            target = data

            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]

            last_key = keys[-1]

            if "append" in action:
                # 添加到列表
                if last_key not in target:
                    target[last_key] = []
                if isinstance(target[last_key], list):
                    append_value = action["append"]
                    if append_value not in target[last_key]:
                        target[last_key].append(append_value)

            elif "set" in action:
                # 设置值
                target[last_key] = action["set"]

            elif "default_if_empty" in action:
                # 仅在字段为空时设置默认值
                if not target.get(last_key):
                    target[last_key] = action["default_if_empty"]

            elif "max" in action:
                # 设置最大值
                current = target.get(last_key)
                max_value = action["max"]
                if current is None or current > max_value:
                    target[last_key] = max_value

    def add_rule(self, rule: dict[str, Any]) -> None:
        """
        动态添加规则
        
        Args:
            rule: 规则字典
        """
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """
        移除规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否成功移除
        """
        for i, rule in enumerate(self.rules):
            if rule.get("id") == rule_id:
                self.rules.pop(i)
                return True
        return False
