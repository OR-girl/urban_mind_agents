"""
SmartRoute Agent - 主应用入口

FastAPI应用初始化和启动
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smartroute.api.routes import plan_router, user_router
from smartroute.core.config import get_settings
from smartroute.core.logging import setup_logging


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时初始化
    setup_logging()

    # 初始化外部服务连接
    # TODO: 初始化Redis、Milvus等连接

    yield

    # 关闭时清理
    # TODO: 关闭连接池


app = FastAPI(
    title="SmartRoute Agent",
    description="AI驱动的智能路线规划系统",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册路由
app.include_router(plan_router)
app.include_router(user_router)


@app.get("/health")
async def health_check():
    """
    健康检查
    """
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """
    根路径
    """
    return {
        "name": "SmartRoute Agent",
        "description": "AI驱动的智能路线规划系统",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "smartroute.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
