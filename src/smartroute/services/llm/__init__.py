"""
LLM Services 模块

大语言模型服务，包括：
- router: 多供应商路由器
- embedding: 向量化服务
"""

from smartroute.services.llm.router import LLMRouter

__all__ = ["LLMRouter"]
