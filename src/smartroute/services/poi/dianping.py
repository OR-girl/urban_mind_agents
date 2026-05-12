"""
Dianping Client - 大众点评API客户端

提供POI详情、评论获取等功能
"""

import aiohttp
from typing import Any

from smartroute.core.config import get_settings
from smartroute.core.exceptions import POIError


settings = get_settings()


class DianpingClient:
    """
    大众点评API客户端
    
    提供POI详情、评论等数据
    """

    def __init__(self) -> None:
        self.base_url = settings.external.dianping_base_url or "https://api.dianping.com/v1"
        self.api_key = settings.external.dianping_api_key
        self._session = None

    async def get_poi_detail(
        self,
        poi_id: str,
    ) -> dict[str, Any]:
        """
        获取POI详情
        
        Args:
            poi_id: POI ID
            
        Returns:
            POI详情
        """
        url = f"{self.base_url}/poi/{poi_id}"
        params = {
            "key": self.api_key,
        }

        try:
            response = await self._request(url, params)
            poi_data = response.get("data", {})

            return {
                "poi_id": poi_id,
                "name": poi_data.get("name", ""),
                "category": poi_data.get("category", ""),
                "location": poi_data.get("location", {}),
                "address": poi_data.get("address", ""),
                "avg_cost": float(poi_data.get("avgPrice", 0)),
                "rating": float(poi_data.get("score", 0)),
                "review_count": int(poi_data.get("reviewNum", 0)),
                "business_hours": poi_data.get("openTime", []),
                "tags": poi_data.get("tags", []),
            }

        except Exception as e:
            raise POIError(
                message=f"POI详情获取失败: {e}",
                code="DIANPING_POI_ERROR",
            ) from e

    async def get_poi_reviews(
        self,
        poi_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        获取POI评论
        
        Args:
            poi_id: POI ID
            limit: 返回数量
            offset: 偏移量
            
        Returns:
            评论列表
        """
        url = f"{self.base_url}/poi/{poi_id}/reviews"
        params = {
            "key": self.api_key,
            "limit": limit,
            "offset": offset,
        }

        try:
            response = await self._request(url, params)
            reviews = response.get("data", {}).get("reviews", [])

            return [
                {
                    "review_id": r.get("id", ""),
                    "rating": int(r.get("score", 0)),
                    "content": r.get("content", ""),
                    "timestamp": r.get("createTime", 0),
                    "user_id": r.get("userId", ""),
                    "images": r.get("images", []),
                }
                for r in reviews
            ]

        except Exception as e:
            raise POIError(
                message=f"评论获取失败: {e}",
                code="DIANPING_REVIEW_ERROR",
            ) from e

    async def search_pois(
        self,
        city: str,
        category: str | None = None,
        keywords: str | None = None,
        location: tuple[float, float] | None = None,
        radius: int = 5000,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        搜索POI
        
        Args:
            city: 城市
            category: 类目
            keywords: 关键词
            location: 中心点
            radius: 搜索半径
            limit: 返回数量
            
        Returns:
            POI列表
        """
        url = f"{self.base_url}/pois/search"
        params = {
            "key": self.api_key,
            "city": city,
            "limit": limit,
        }

        if category:
            params["category"] = category
        if keywords:
            params["keywords"] = keywords
        if location:
            params["location"] = f"{location[0]}, {location[1]}"
            params["radius"] = radius

        try:
            response = await self._request(url, params)
            pois = response.get("data", {}).get("pois", [])

            return [
                {
                    "poi_id": p.get("id", ""),
                    "name": p.get("name", ""),
                    "category": p.get("category", ""),
                    "location": p.get("location", {}),
                    "avg_cost": float(p.get("avgPrice", 0)),
                    "rating": float(p.get("score", 0)),
                    "review_count": int(p.get("reviewNum", 0)),
                    "distance": int(p.get("distance", 0)),
                }
                for p in pois
            ]

        except Exception as e:
            raise POIError(
                message=f"POI搜索失败: {e}",
                code="DIANPING_SEARCH_ERROR",
            ) from e

    async def _request(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        发送HTTP请求
        """
        if self._session is None:
            self._session = aiohttp.ClientSession()

        async with self._session.get(url, params=params) as response:
            if response.status != 200:
                raise POIError(
                    message=f"HTTP错误: {response.status}",
                    code="DIANPING_HTTP_ERROR",
                )
            return await response.json()

    async def close(self) -> None:
        """
        关闭Session
        """
        if self._session:
            await self._session.close()
            self._session = None
