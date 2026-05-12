"""
API Routes 模块

FastAPI路由定义，包括：
- plan: 路线规划接口
- user: 用户偏好接口
"""

from smartroute.api.routes.plan import router as plan_router
from smartroute.api.routes.user import router as user_router

__all__ = ["plan_router", "user_router"]
