"""
UGC Insight Agent 模块

评论洞察Agent，对候选POI的用户评论进行深度分析

核心组件：
- UGCInsightAgent: 主Agent类
- LLMAnalyzer: LLM通道分析器
- NLPAnalyzer: NLP通道分析器
- CacheManager: UGC缓存管理器
"""

from smartroute.agents.ugc.agent import UGCInsightAgent

__all__ = ["UGCInsightAgent"]
