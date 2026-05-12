"""
Redis Cache - Redis缓存客户端

提供键值存储功能
"""

import json
from typing import Any

import redis.asyncio as redis

from smartroute.core.config import get_settings


settings = get_settings()


class RedisCache:
    """
    Redis缓存客户端
    """

    def __init__(self) -> None:
        self._client = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=settings.db.redis_host,
                port=settings.db.redis_port,
                password=settings.db.redis_password or None,
                db=settings.db.redis_db,
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Any | None:
        """
        获取值
        
        Args:
            key: 键
            
        Returns:
            值或None
        """
        client = await self._get_client()
        data = await client.get(key)

        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        设置值
        
        Args:
            key: 键
            value: 值
            ttl: TTL（秒）
        """
        client = await self._get_client()

        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)

        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        """
        删除键
        
        Args:
            key: 键
        """
        client = await self._get_client()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 键
            
        Returns:
            是否存在
        """
        client = await self._get_client()
        return await client.exists(key) > 0

    async def expire(self, key: str, ttl: int) -> None:
        """
        设置过期时间
        
        Args:
            key: 键
            ttl: TTL（秒）
        """
        client = await self._get_client()
        await client.expire(key, ttl)

    async def ttl(self, key: str) -> int:
        """
        获取剩余过期时间
        
        Args:
            key: 键
            
        Returns:
            剩余秒数
        """
        client = await self._get_client()
        return await client.ttl(key)

    async def close(self) -> None:
        """
        关闭连接
        """
        if self._client:
            await self._client.close()
            self._client = None
