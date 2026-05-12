"""
Retrieval Agent 模块

POI召回Agent，从海量POI库中召回候选集

核心组件：
- RetrievalAgent: 主Agent类
- MultiPathRetriever: 多路召回器
- CoarseRanker: 粗排模型
- DiversityReranker: 多样性重排器
"""

from smartroute.agents.retrieval.agent import RetrievalAgent

__all__ = ["RetrievalAgent"]
