"""
SmartRoute Agent 基类模块

定义所有 Agent 的通用接口和行为
"""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from smartroute.core.config import get_settings
from smartroute.core.exceptions import AgentError
from smartroute.core.logging import AgentLogger
from smartroute.core.utils import Timer
from smartroute.schemas import SystemState

settings = get_settings()


class BaseAgent(ABC):
    """
    Agent 基类

    所有 Agent 必须继承此基类，实现 execute 方法
    """

    agent_name: str = "base"

    def __init__(self) -> None:
        self.logger = AgentLogger(self.agent_name)
        self.config = settings.get_agent_config(self.agent_name)

    @abstractmethod
    async def execute(self, state: SystemState) -> Any:
        """
        执行 Agent 的核心逻辑

        Args:
            state: 系统状态

        Returns:
            Agent 执行结果
        """
        pass

    def bind_context(self, state: SystemState) -> None:
        """
        绑定上下文信息到日志器

        Args:
            state: 系统状态
        """
        self.logger.bind_context(
            trace_id=state.trace_id,
            session_id=state.session_id,
            user_id=state.user_id,
        )

    async def run_with_timing(self, state: SystemState) -> Any:
        """
        带计时的执行方法

        Args:
            state: 系统状态

        Returns:
            Agent 执行结果
        """
        self.bind_context(state)

        timer = Timer()
        timer.start()

        try:
            self.logger.info(f"{self.agent_name}_started")
            result = await self.execute(state)
            duration = timer.stop()
            self.logger.timing(f"{self.agent_name}_completed", duration)
            return result

        except AgentError as e:
            duration = timer.stop()
            self.logger.error(
                f"{self.agent_name}_failed",
                error=e.message,
                code=e.code,
                duration_ms=duration,
            )
            raise

        except Exception as e:
            duration = timer.stop()
            self.logger.error(
                f"{self.agent_name}_unexpected_error",
                error=str(e),
                duration_ms=duration,
            )
            raise AgentError(
                message=str(e),
                code=f"{self.agent_name.upper()}_ERROR",
                agent_name=self.agent_name,
            ) from e

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取 Agent 配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self.config.get(key, default)


class LLMBasedAgent(BaseAgent):
    """
    基于 LLM 的 Agent 基类

    提供 LLM 调用的通用功能
    """

    def __init__(self) -> None:
        super().__init__()
        self._llm_router = None

    async def get_llm_client(self) -> Any:
        """
        获取 LLM 客户端（通过路由器）

        Returns:
            LLM 客户端
        """
        if self._llm_router is None:
            from smartroute.services.llm.router import LLMRouter
            self._llm_router = LLMRouter()

        return self._llm_router

    async def call_llm(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        调用 LLM

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 Token 数
            **kwargs: 其他参数

        Returns:
            LLM 响应文本
        """
        llm_router = await self.get_llm_client()

        self.logger.info(
            "llm_call_started",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        timer = Timer()
        timer.start()

        response = await llm_router.call(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        duration = timer.stop()

        self.logger.llm_call(
            model=model or "default",
            input_tokens=0,  # 实际值由 LLM Router 提供
            output_tokens=0,
            duration_ms=duration,
            cost_yuan=0.0,
        )

        return response

    async def call_llm_with_function(
        self,
        messages: list[dict[str, str]],
        function_schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """
        使用 Function Calling 调用 LLM

        Args:
            messages: 消息列表
            function_schema: Function Schema
            model: 模型名称
            temperature: 温度参数

        Returns:
            Function 返回的 JSON 数据
        """
        llm_router = await self.get_llm_client()

        self.logger.info(
            "llm_function_call_started",
            model=model,
            function=function_schema.get("name", "unknown"),
        )

        timer = Timer()
        timer.start()

        result = await llm_router.call_with_function(
            messages=messages,
            function_schema=function_schema,
            model=model,
            temperature=temperature,
        )

        duration = timer.stop()

        self.logger.llm_call(
            model=model or "default",
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration,
            cost_yuan=0.0,
        )

        return result


class CacheableAgent(BaseAgent):
    """
    支持缓存的 Agent 基类

    使用本地 JSON 文件作为缓存存储（替代 Redis）
    """

    # 缓存目录
    CACHE_DIR = Path(__file__).parent.parent.parent.parent / ".cache"

    def __init__(self) -> None:
        super().__init__()
        self._cache_ttl = 3600  # 默认 1 小时
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """确保缓存目录存在"""
        if not self.CACHE_DIR.exists():
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_file(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 使用 hash 作为文件名，避免特殊字符问题
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.CACHE_DIR / f"{safe_key}.json"

    async def get_cached(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在或过期返回 None
        """
        import json
        import time

        cache_file = self._get_cache_file(key)

        if not cache_file.exists():
            self.logger.debug("cache_miss", key=key)
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查 TTL 过期
            expire_at = data.get("expire_at", 0)
            if time.time() > expire_at:
                # 过期，删除文件
                cache_file.unlink()
                self.logger.debug("cache_expired", key=key)
                return None

            self.logger.debug("cache_hit", key=key)
            return data.get("value")

        except Exception as e:
            self.logger.warning("cache_read_failed", key=key, error=str(e))
            return None

    async def set_cached(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），默认使用 self._cache_ttl
        """
        import json
        import time

        cache_file = self._get_cache_file(key)
        ttl = ttl or self._cache_ttl

        try:
            data = {
                "value": value,
                "expire_at": time.time() + ttl,
                "created_at": time.time(),
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.debug("cache_set", key=key, ttl=ttl)

        except Exception as e:
            self.logger.warning("cache_write_failed", key=key, error=str(e))

    async def delete_cached(self, key: str) -> None:
        """
        删除缓存值

        Args:
            key: 缓存键
        """
        cache_file = self._get_cache_file(key)

        if cache_file.exists():
            try:
                cache_file.unlink()
                self.logger.debug("cache_deleted", key=key)
            except Exception as e:
                self.logger.warning("cache_delete_failed", key=key, error=str(e))


class VectorBasedAgent(BaseAgent):
    """
    基于向量检索的 Agent 基类

    提供 Milvus 向量检索的通用功能
    """

    def __init__(self) -> None:
        super().__init__()
        self._vector_client = None
        self._embedding_service = None

    async def get_vector_client(self) -> Any:
        """
        获取 Milvus 向量客户端

        Returns:
            Milvus 客户端
        """
        if self._vector_client is None:
            from smartroute.services.vector_store.milvus import MilvusClient
            self._vector_client = MilvusClient()

        return self._vector_client

    async def get_embedding_service(self) -> Any:
        """
        获取 Embedding 服务

        Returns:
            Embedding 服务实例
        """
        if self._embedding_service is None:
            from smartroute.services.llm.embedding import EmbeddingService
            self._embedding_service = EmbeddingService()

        return self._embedding_service

    async def encode_text(self, text: str) -> list[float]:
        """
        将文本编码为向量

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        embedding_service = await self.get_embedding_service()
        return await embedding_service.encode(text)

    async def vector_search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        执行向量检索

        Args:
            collection_name: 集合名称
            query_vector: 查询向量
            top_k: 返回数量
            filter_expr: 过滤表达式

        Returns:
            检索结果列表
        """
        vector_client = await self.get_vector_client()
        return await vector_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=top_k,
            filter_expr=filter_expr,
        )