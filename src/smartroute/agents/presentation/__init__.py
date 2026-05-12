"""
Presentation Agent 模块

方案生成Agent，将路线规划结果转化为用户友好的展示内容

核心组件：
- PresentationAgent: 主Agent类
- PersonalizedReasonGenerator: 个性化话术生成器
- StreamOutputHandler: 流式输出处理器
- PlanComparisonGenerator: 方案对比矩阵生成器
"""

from smartroute.agents.presentation.agent import PresentationAgent

__all__ = ["PresentationAgent"]
