"""
SmartRoute Agent UGC Insight Agent 缓存管理模块

POI 评论分析结果的缓存管理
"""

import json
from typing import Any

from smartroute.core.config import get_settings
from smartroute.core.logging import get_logger

logger = get_logger("agent.ugc.cache")
settings = get_settings()


class UGCCacheManager:
    """
    UGC 缓存管理器

    管理 POI 评论分析结果的 Redis 缓存
    """

    def __init__(self, redis_client=None) -> None:
        self.redis = redis_client
        self._prefix = settings.app.ugc_cache_ttl_seconds
        self._ttl = settings.app.ugc_cache_ttl_seconds or 604800  # 默认 7 天

    async def _get_redis(self):
        """获取 Redis 客户端（延迟导入）"""
        import redis.asyncio as redis
        if self.redis is None:
            self.redis = redis.Redis(
                host=settings.db.redis_host,
                port=settings.db.redis_port,
                password=settings.db.redis_password or None,
                db=settings.db.redis_db,
                decode_responses=True,
            )
        return self.redis

    def _get_key(self, poi_id: str) -> str:
        """生成缓存 key"""
        return f"ugc:poi:{poi_id}"

    async def get_cached(self, poi_id: str) -> Optional[dict[str, Any]]:
        """
        获取单个 POI 的缓存分析结果

        Args:
            poi_id: POI ID

        Returns:
            缓存的分析结果，不存在返回 None
        """
        client = await self._get_redis()
        key = self._get_key(poi_id)

        data = await client.get(key)
        if data:
            logger.debug("ugc_cache_hit", poi_id=poi_id)
            return json.loads(data)

        logger.debug("ugc_cache_miss", poi_id=poi_id)
        return None

    async def set_cache(
        self,
        poi_id: str,
        analysis: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """
        设置 POI 分析结果缓存

        Args:
            poi_id: POI ID
            analysis: 分析结果
            ttl: TTL（秒），默认使用配置值
        """
        client = await self._get_redis()
        key = self._get_key(poi_id)
        ttl = ttl or self._ttl

        await client.setex(
            key,
            ttl,
            json.dumps(analysis, ensure_ascii=False),
        )

        logger.debug("ugc_cache_set", poi_id=poi_id, ttl=ttl)

    async def batch_get(
        self,
        poi_ids: list[str],
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """
        批量获取缓存

        Args:
            poi_ids: POI ID 列表

        Returns:
            (命中结果字典, 未命中 POI ID 列表)
        """
        client = await self._get_redis()

        # 使用 pipeline 批量查询
        pipe = client.pipeline()
        for poi_id in poi_ids:
            pipe.get(self._get_key(poi_id))
        results = await pipe.execute()

        cached: dict[str, dict[str, Any]] = {}
        missed: list[str] = []

        for poi_id, result in zip(poi_ids, results):
            if result:
                cached[poi_id] = json.loads(result)
            else:
                missed.append(poi_id)

        logger.info(
            "ugc_batch_cache_query",
            total=len(poi_ids),
            cached=len(cached),
            missed=len(missed),
        )

        return cached, missed

    async def batch_set(
        self,
        analyses: dict[str, dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> None:
        """
        批量设置缓存

        Args:
            analyses: POI ID -> 分析结果的字典
            ttl: TTL（秒）
        """
        client = await self._get_redis()
        ttl = ttl or self._ttl

        pipe = client.pipeline()
        for poi_id, analysis in analyses.items():
            key = self._get_key(poi_id)
            pipe.setex(key, ttl, json.dumps(analysis, ensure_ascii=False))
        await pipe.execute()

        logger.info("ugc_batch_cache_set", count=len(analyses), ttl=ttl)

    async def delete_cached(self, poi_id: str) -> None:
        """
        删除缓存

        Args:
            poi_id: POI ID
        """
        client = await self._get_redis()
        key = self._get_key(poi_id)
        await client.delete(key)

        logger.debug("ugc_cache_deleted", poi_id=poi_id)

    async def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        client = await self._get_redis()

        # 统计 UGC 缓存 key 数量
        keys = await client.keys("ugc:poi:*")

        return {
            "total_cached_pois": len(keys),
            "ttl_seconds": self._ttl,
        }

    async def refresh_cache(
        self,
        poi_id: str,
        new_analysis: dict[str, Any],
    ) -> None:
        """
        刷新缓存（用于节假日前后主动更新）

        Args:
            poi_id: POI ID
            new_analysis: 新的分析结果
        """
        await self.set_cache(poi_id, new_analysis)
        logger.info("ugc_cache_refreshed", poi_id=poi_id)

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.close()


# 全局缓存管理器实例
_ugc_cache_manager: UGCCacheManager | None = None


def get_ugc_cache_manager() -> UGCCacheManager:
    """获取全局 UGC 缓存管理器实例"""
    global _ugc_cache_manager
    if _ugc_cache_manager is None:
        _ugc_cache_manager = UGCCacheManager()
    return _ugc_cache_manager