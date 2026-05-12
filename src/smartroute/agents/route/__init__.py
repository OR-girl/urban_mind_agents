"""
Route Planning Agent 模块

路径规划Agent，在多重约束下求解最优POI访问序列

核心组件：
- RoutePlanningAgent: 主Agent类
- VRPTWSolver: OR-Tools求解器
- MultiPlanGenerator: 多方案生成器
- QueueTimePredictor: 排队时间预测
"""

from smartroute.agents.route.agent import RoutePlanningAgent

__all__ = ["RoutePlanningAgent"]
