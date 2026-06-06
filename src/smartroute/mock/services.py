"""
Mock Service Layer - replaces Redis/Amap/Dianping/Milvus with in-memory implementations.
"""

from __future__ import annotations
import json, math, time as _time
from typing import Any
from smartroute.mock.data import DISTANCE_MATRIX, HANGZHOU_POIS, get_reviews_for_poi


class MockRedis:
    """In-memory Redis replacement."""
    def __init__(self): self._store: dict[str, str] = {}; self._ttl: dict[str, float] = {}
    async def get(self, key: str) -> str | None: self._expire_check(key); return self._store.get(key)
    async def setex(self, key: str, ttl: int, value: str) -> None: self._store[key] = value; self._ttl[key] = _time.time() + ttl
    async def set(self, key: str, value: str) -> None: self._store[key] = value
    async def delete(self, key: str) -> None: self._store.pop(key, None); self._ttl.pop(key, None)
    async def exists(self, key: str) -> int: self._expire_check(key); return 1 if key in self._store else 0
    async def keys(self, pattern: str = "*") -> list[str]: prefix = pattern.replace("*", ""); return [k for k in self._store if k.startswith(prefix)]
    def pipeline(self): return MockRedisPipeline(self)
    def _expire_check(self, key: str) -> None:
        if key in self._ttl and self._ttl[key] < _time.time(): self._store.pop(key, None); self._ttl.pop(key, None)
    async def close(self) -> None: self._store.clear(); self._ttl.clear()


class MockRedisPipeline:
    def __init__(self, redis): self._redis = redis; self._commands: list = []
    def get(self, key: str): self._commands.append(("get", (key,))); return self
    def setex(self, key: str, ttl: int, value: str): self._commands.append(("setex", (key, ttl, value))); return self
    async def execute(self) -> list:
        results = []
        for cmd, args in self._commands:
            if cmd == "get": results.append(await self._redis.get(args[0]))
            elif cmd == "setex": await self._redis.setex(*args); results.append(True)
        self._commands.clear(); return results


class MockServiceLayer:
    """Provides mock data for the full SmartRoute pipeline."""

    def __init__(self): self.redis = MockRedis()

    async def save_session(self, session_id: str, data: dict) -> None:
        await self.redis.setex(f"session:{session_id}", 86400, json.dumps(data, ensure_ascii=False))

    async def load_session(self, session_id: str) -> dict | None:
        raw = await self.redis.get(f"session:{session_id}")
        return json.loads(raw) if raw else None

    def retrieve_candidates(self, intent: Any, top_k: int = 20) -> list[dict[str, Any]]:
        candidates = []
        intent_dict = intent.model_dump() if hasattr(intent, "model_dump") else intent
        if isinstance(intent_dict, dict):
            needs = intent_dict.get("preferences", {}).get("must_have", [])
            themes = intent_dict.get("preferences", {}).get("themes", [])
            cuisine = intent_dict.get("preferences", {}).get("cuisine_types", [])
            budget = intent_dict.get("budget", {}).get("per_person") or 0
            intent_type = intent_dict.get("intent_type", "tour")
        else:
            needs = getattr(getattr(intent, "preferences", None), "must_have", [])
            themes = getattr(getattr(intent, "preferences", None), "themes", [])
            cuisine = getattr(getattr(intent, "preferences", None), "cuisine_types", [])
            budget = getattr(getattr(intent, "budget", None), "per_person", 0) or 0
            intent_type = getattr(intent, "intent_type", None)
            intent_type = intent_type.value if hasattr(intent_type, "value") else str(intent_type or "tour")

        for poi in HANGZHOU_POIS:
            score = 5.0
            tags = poi.get("tags", []); category = poi.get("category", "")
            if "餐" in category or "茶" in category: score += 1.0
            elif "景点" in category: score += 0.5
            elif "购物" in category: score += 0.5
            if themes:
                for theme in themes:
                    if theme in tags or theme in category: score += 1.5
            if cuisine:
                for c in cuisine:
                    if c in category or c in str(tags): score += 2.0
            # Category keyword matching from must_have/nice_to_have
            all_needs = (needs if isinstance(needs, list) else []) + (
                intent_dict.get("preferences", {}).get("nice_to_have", []) if isinstance(intent_dict, dict) else [])
            for need in all_needs:
                need_lower = (need or "").lower()
                if any(kw in need_lower for kw in ("购物", "商场", "逛街", "逛")) and "购物" in category: score += 3.0
                if any(kw in need_lower for kw in ("下午茶", "喝茶", "茶")) and "茶" in category: score += 3.0
                if "博物馆" in need_lower and "博物馆" in category: score += 3.0
            cost = poi.get("avg_cost", 0) or 0
            if "餐" in category and budget > 0:
                if cost > budget * 1.5: score -= 3.0
                elif cost <= budget: score += 1.0
            if intent_type in ("food_tour", "美食探索") and "餐" in category: score += 1.0
            elif intent_type in ("culture", "文化历史") and ("博物馆" in category or "寺庙" in category or "古迹" in category): score += 1.5
            elif intent_type in ("nature", "自然探索") and ("自然" in category or "茶" in category): score += 1.5
            if score > 1.0: candidates.append({**poi, "retrieval_score": round(score, 2)})
        candidates.sort(key=lambda x: x.get("retrieval_score", 0), reverse=True)
        return candidates[:top_k]

    def get_reviews_for_poi(self, poi_id: str) -> list[dict[str, Any]]: return get_reviews_for_poi(poi_id)
    def get_reviews_batch(self, poi_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return {pid: get_reviews_for_poi(pid) for pid in poi_ids}

    def get_distance_matrix(self, poi_ids: list[str], mode: str = "walking") -> list[list[int]]:
        n = len(poi_ids); matrix = [[0]*n for _ in range(n)]
        for i, si in enumerate(poi_ids):
            for j, sj in enumerate(poi_ids):
                if i == j: matrix[i][j] = 0
                elif si in DISTANCE_MATRIX and sj in DISTANCE_MATRIX[si]: matrix[i][j] = DISTANCE_MATRIX[si][sj]
                else: matrix[i][j] = 15
        return matrix

    @staticmethod
    def _haversine(lat1, lng1, lat2, lng2):
        R = 6371; dlat=math.radians(lat2-lat1); dlng=math.radians(lng2-lng1)
        a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
        return R*2*math.atan2(math.sqrt(a),math.sqrt(1-a))
