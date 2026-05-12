"""
Intent Agent 模块

意图识别Agent，将用户自由文本转化为结构化指令

核心组件：
- IntentAgent: 主Agent类
- SlotExtractor: 槽位抽取器
- ImplicitRuleEngine: 隐式推理规则引擎
- AmbiguityDetector: 歧义检测与反问生成
"""

from smartroute.agents.intent.agent import IntentAgent

__all__ = ["IntentAgent"]
