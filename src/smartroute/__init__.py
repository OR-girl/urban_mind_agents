"""
SmartRoute Agent - AI 驱动的智能路线规划系统

基于多 Agent 协同架构，将用户自然语言意图转化为可执行的个性化路线方案。

核心模块：
- core: 基础配置、日志、异常、工具
- schemas: 数据模型和 Schema 定义
- orchestrator: 主控调度器
- agents: 各专职 Agent 实现
- services: 外部服务客户端
- storage: 数据存储
- api: FastAPI 接口
"""

__version__ = "1.0.0"
__author__ = "SmartRoute Team"

from smartroute.core import get_settings, settings
from smartroute.schemas import SystemState

__all__ = [
    "__version__",
    "__author__",
    "settings",
    "get_settings",
    "SystemState",
]