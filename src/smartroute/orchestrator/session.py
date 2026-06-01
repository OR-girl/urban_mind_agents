"""
SmartRoute Agent Orchestrator Session 管理模块

基于 Redis 的 Session 状态持久化
"""

import json
from datetime import datetime
from typing import Any

from smartroute.core.config import get_settings
from smartroute.core.logging import get_logger
from smartroute.schemas import SystemState

logger = get_logger("orchestrator.session")
settings = get_settings()


class SessionManager:
    """
    Session 状态管理器

    使用 Redis 存储和管理 Session 状态
    """

    def __init__(self, redis_client=None) -> None:
        self.redis = redis_client
        self._prefix = settings.app.session_redis_prefix
        self._ttl = settings.app.session_ttl_seconds

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

    def _get_key(self, session_id: str) -> str:
        """生成 Redis key"""
        return f"{self._prefix}{session_id}"

    async def save_state(self, session_id: str, state: SystemState) -> None:
        """
        保存 Session 状态到 Redis

        Args:
            session_id: 会话 ID
            state: 系统状态
        """
        client = await self._get_redis()
        key = self._get_key(session_id)

        # 只保存需要跨轮次复用的字段
        persist_data = state.to_persist_dict()
        persist_data["updated_at"] = datetime.now().isoformat()

        await client.setex(
            key,
            self._ttl,
            json.dumps(persist_data, ensure_ascii=False),
        )

        logger.debug(
            "session_saved",
            session_id=session_id,
            ttl=self._ttl,
        )

    async def load_state(self, session_id: str) -> dict[str, Any] | None:
        """
        从 Redis 加载 Session 状态

        Args:
            session_id: 会话 ID

        Returns:
            Session 数据字典，不存在返回 None
        """
        client = await self._get_redis()
        key = self._get_key(session_id)

        data = await client.get(key)
        if data:
            logger.debug("session_loaded", session_id=session_id)
            return json.loads(data)

        logger.debug("session_not_found", session_id=session_id)
        return None

    async def update_state(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> None:
        """
        更新 Session 状态的部分字段

        Args:
            session_id: 会话 ID
            updates: 要更新的字段
        """
        existing_data = await self.load_state(session_id)
        if existing_data is None:
            logger.warning("session_update_failed_not_found", session_id=session_id)
            return

        # 合并更新
        for key, value in updates.items():
            if value is not None:
                existing_data[key] = value

        existing_data["updated_at"] = datetime.now().isoformat()

        client = await self._get_redis()
        key = self._get_key(session_id)
        await client.setex(
            key,
            self._ttl,
            json.dumps(existing_data, ensure_ascii=False),
        )

        logger.debug("session_updated", session_id=session_id)

    async def clear_session(self, session_id: str) -> None:
        """
        清除 Session

        Args:
            session_id: 会话 ID
        """
        client = await self._get_redis()
        key = self._get_key(session_id)
        await client.delete(key)

        logger.info("session_cleared", session_id=session_id)

    async def extend_ttl(self, session_id: str) -> None:
        """
        延长 Session TTL

        Args:
            session_id: 会话 ID
        """
        client = await self._get_redis()
        key = self._get_key(session_id)
        await client.expire(key, self._ttl)

        logger.debug("session_ttl_extended", session_id=session_id)

    async def exists(self, session_id: str) -> bool:
        """
        检查 Session 是否存在

        Args:
            session_id: 会话 ID

        Returns:
            是否存在
        """
        client = await self._get_redis()
        key = self._get_key(session_id)
        return await client.exists(key) > 0

    async def get_session_age(self, session_id: str) -> int:
        """
        获取 Session 剩余有效时间

        Args:
            session_id: 会话 ID

        Returns:
            剩余秒数
        """
        client = await self._get_redis()
        key = self._get_key(session_id)
        ttl = await client.ttl(key)
        return max(0, ttl)

    async def add_dialog_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        添加对话消息到 Session

        Args:
            session_id: 会话 ID
            role: 角色（user/system）
            content: 消息内容
        """
        existing_data = await self.load_state(session_id)
        if existing_data is None:
            existing_data = {
                "session_id": session_id,
                "dialog_history": [],
            }

        dialog_history = existing_data.get("dialog_history", [])
        dialog_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

        # 保留最近 10 轮对话
        if len(dialog_history) > 20:
            dialog_history = dialog_history[-20:]

        existing_data["dialog_history"] = dialog_history

        client = await self._get_redis()
        key = self._get_key(session_id)
        await client.setex(
            key,
            self._ttl,
            json.dumps(existing_data, ensure_ascii=False),
        )

    async def get_dialog_history(
        self,
        session_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        获取对话历史

        Args:
            session_id: 会话 ID
            limit: 最大返回数量

        Returns:
            对话历史列表
        """
        existing_data = await self.load_state(session_id)
        if existing_data is None:
            return []

        dialog_history = existing_data.get("dialog_history", [])
        return dialog_history[-limit:]

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self.redis:
            await self.redis.close()

    async def mark_clarify_pending(self, session_id: str, question: str) -> None:
        """标记 Session 为反问挂起状态"""
        client = await self._get_redis(); key = self._get_key(session_id)
        data = await client.get(key); state_data = json.loads(data) if data else {}
        state_data["status"] = "clarify_pending"
        if "dialog_history" not in state_data: state_data["dialog_history"] = []
        state_data["dialog_history"].append({"role":"system","content":question,"timestamp":datetime.now().isoformat()})
        await client.setex(key, self._ttl, json.dumps(state_data, ensure_ascii=False))
        logger.info("clarify_pending_marked", session_id=session_id)

    async def is_clarify_pending(self, session_id: str) -> bool:
        """检查 Session 是否处于反问挂起状态"""
        data = await self.load_state(session_id)
        return data.get("status") == "clarify_pending" if data else False


# 全局 Session Manager 实例
session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取全局 Session Manager 实例"""
    global session_manager
    if session_manager is None:
        session_manager = SessionManager()
    return session_manager