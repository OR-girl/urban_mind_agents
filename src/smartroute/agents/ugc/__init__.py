"""
UGC Insight Agent 模块

评论洞察Agent，对候选POI的用户评论进行深度分析

核心组件：
- UGCInsightAgent: 主Agent类
- LLMAnalyzer: LLM通道分析器
- NLPAnalyzer: NLP通道分析器
- CacheManager: UGC缓存管理器
"""

__all__ = ["UGCInsightAgent", "NLPAnalyzer"]

def __getattr__(name: str):
    if name == "UGCInsightAgent":
        from smartroute.agents.ugc.agent import UGCInsightAgent
        return UGCInsightAgent
    if name == "NLPAnalyzer":
        from smartroute.agents.ugc.nlp_analyzer import NLPAnalyzer
        return NLPAnalyzer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
