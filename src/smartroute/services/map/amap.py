"""
Amap Client - 高德地图API客户端

提供距离矩阵、POI搜索、路线规划等功能
"""

import aiohttp
from typing import Any

from smartroute.core.config import get_settings
from smartroute.core.exceptions import MapAPIError


settings = get_settings()


class AmapClient:
    """
    高德地图API客户端
    """

    def __init__(self) -> None:
        self.base_url = settings.external.amap_base_url or "https://restapi.amap.com/v3"
        self.api_key = settings.external.amap_api_key
        self._session = None

    async def distance_matrix(
        self,
        origins: list[tuple[float, float]],
        destinations: list[tuple[float, float]],
        mode: str = "walking",
        departure_time: str | None = None,
    ) -> list[list[int]]:
        """
        获取距离矩阵
        
        Args:
            origins: 起点列表 [(lat, lng), ...]
            destinations: 终点列表
            mode: 交通方式 (walking/driving/transit)
            departure_time: 出发时间
            
        Returns:
            时间矩阵（分钟）
        """
        # 构建请求
        origins_str = "|".join([f"{lng},{lat}" for lat, lng in origins])
        destinations_str = "|".join([f"{lng},{lat}" for lat, lng in destinations])

        url = f"{self.base_url}/distance"
        params = {
            "key": self.api_key,
            "origins": origins_str,
            "destination": destinations_str,
            "type": self._get_distance_type(mode),
            "output": "json",
        }

        try:
            response = await self._request(url, params)
            results = response.get("results", [])

            # 解析结果
            n_origins = len(origins)
            n_dest = len(destinations)
            matrix = [[0] * n_dest for _ in range(n_origins)]

            for i, result in enumerate(results):
                row = i // n_dest
                col = i % n_dest
                duration = result.get("duration", 0)
                matrix[row][col] = int(duration) // 60  # 转换为分钟

            return matrix

        except Exception as e:
            raise MapAPIError(
                message=f"距离矩阵请求失败: {e}",
                code="AMAP_DISTANCE_ERROR",
            ) from e

    async def poi_search(
        self,
        keywords: str,
        city: str,
        location: tuple[float, float] | None = None,
        radius: int = 5000,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        POI搜索
        
        Args:
            keywords: 搜索关键词
            city: 城市
            location: 中心点 (lat, lng)
            radius: 搜索半径（米）
            limit: 返回数量
            
        Returns:
            POI列表
        """
        url = f"{self.base_url}/place/around"
        params = {
            "key": self.api_key,
            "keywords": keywords,
            "city": city,
            "offset": limit,
            "output": "json",
        }

        if location:
            params["location"] = f"{location[1]}, {location[0]}"
            params["radius"] = radius

        try:
            response = await self._request(url, params)
            pois = response.get("pois", [])

            return [
                {
                    "poi_id": poi.get("id", ""),
                    "name": poi.get("name", ""),
                    "category": poi.get("type", ""),
                    "location": self._parse_location(poi.get("location", "")),
                    "address": poi.get("address", ""),
                    "distance": int(poi.get("distance", 0)),
                }
                for poi in pois
            ]

        except Exception as e:
            raise MapAPIError(
                message=f"POI搜索失败: {e}",
                code="AMAP_POI_ERROR",
            ) from e

    async def route_plan(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        mode: str = "walking",
    ) -> dict[str, Any]:
        """
        路线规划
        
        Args:
            origin: 起点
            destination: 终点
            mode: 交通方式
            
        Returns:
            路线信息
        """
        url = f"{self.base_url}/direction/{mode}"
        params = {
            "key": self.api_key,
            "origin": f"{origin[1]}, {origin[0]}",
            "destination": f"{destination[1]}, {destination[0]}",
            "output": "json",
        }

        try:
            response = await self._request(url, params)
            route = response.get("route", {})

            return {
                "distance": int(route.get("distance", 0)),
                "duration": int(route.get("duration", 0)) // 60,
                "steps": route.get("paths", [{}])[0].get("steps", []),
            }

        except Exception as e:
            raise MapAPIError(
                message=f"路线规划失败: {e}",
                code="AMAP_ROUTE_ERROR",
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
                raise MapAPIError(
                    message=f"HTTP错误: {response.status}",
                    code="AMAP_HTTP_ERROR",
                )
            return await response.json()

    def _get_distance_type(self, mode: str) -> int:
        """
        获取距离计算类型
        """
        type_map = {
            "walking": 3,
            "driving": 1,
            "transit": 2,
        }
        return type_map.get(mode, 3)

    def _parse_location(self, location_str: str) -> dict[str, float]:
        """
        解析位置字符串
        """
        if not location_str:
            return {"lat": 0.0, "lng": 0.0}

        try:
            lng, lat = map(float, location_str.split(","))
            return {"lat": lat, "lng": lng}
        except Exception:
            return {"lat": 0.0, "lng": 0.0}

    async def close(self) -> None:
        """
        关闭Session
        """
        if self._session:
            await self._session.close()
            self._session = None
