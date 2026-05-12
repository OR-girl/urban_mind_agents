"""
VRPTW Solver - OR-Tools求解器

使用Google OR-Tools求解带时间窗的车辆路径问题
"""

import asyncio
from typing import Any, Optional

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from smartroute.schemas.intent import IntentResult
from smartroute.schemas.profile import UserProfile


class VRPTWSolver:
    """
    VRPTW求解器
    
    支持时间窗约束、用餐约束等
    """

    def __init__(self, timeout_seconds: int = 2) -> None:
        self.timeout_seconds = timeout_seconds
        self._map_api_client = None

    async def solve(
        self,
        pois: list[Any],
        intent: IntentResult,
        profile: UserProfile | None,
        weights: dict[str, float],
    ) -> Optional[list[Any]]:
        """
        求解VRPTW
        
        Args:
            pois: POI列表
            intent: IntentResult
            profile: UserProfile
            weights: 权重配置
            
        Returns:
            POI访问序列或None
        """
        n = len(pois)
        if n == 0:
            return None

        # 构建距离矩阵
        distance_matrix = await self._build_distance_matrix(pois, intent)

        # 构建时间窗
        time_windows = self._build_time_windows(pois, intent)

        # 构建体验得分
        experience_scores = [self._get_experience_score(poi) for poi in pois]

        # 构建费用
        costs = [self._get_cost(poi) for poi in pois]

        # 创建OR-Tools数据模型
        data = {
            "time_matrix": distance_matrix,
            "time_windows": time_windows,
            "experience_scores": experience_scores,
            "costs": costs,
            "weights": weights,
            "total_duration": int(intent.temporal.duration_hours * 60),
            "depot": 0,
        }

        # 创建路由模型
        manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)  # +1 for depot
        routing = pywrapcp.RoutingModel(manager)

        # 时间维度
        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_node)
            if from_node == 0 or to_node == 0:
                return 0
            return data["time_matrix"][from_node - 1][to_node - 1]

        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # 添加时间窗约束
        time = "Time"
        routing.AddDimension(
            transit_callback_index,
            30,  # 允许等待时间
            data["total_duration"],
            False,
            time,
        )
        time_dimension = routing.GetDimensionOrDie(time)

        # 设置时间窗
        for location_idx in range(1, n + 1):
            index = manager.NodeToIndex(location_idx)
            time_dimension.CumulVar(index).SetRange(
                data["time_windows"][location_idx - 1][0],
                data["time_windows"][location_idx - 1][1],
            )

        # 求解参数
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.FromSeconds(self.timeout_seconds)

        # 求解
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            return self._extract_solution(manager, routing, solution, pois, data)

        return None

    async def _build_distance_matrix(
        self,
        pois: list[Any],
        intent: IntentResult,
    ) -> list[list[int]]:
        """
        构建距离矩阵（分钟）
        
        Args:
            pois: POI列表
            intent: IntentResult
            
        Returns:
            时间距离矩阵
        """
        n = len(pois)
        matrix = [[0] * n for _ in range(n)]

        # TODO: 实际实现需要调用地图API
        # 这里使用模拟数据
        for i in range(n):
            for j in range(n):
                if i != j:
                    # 简化计算：假设平均15分钟通勤
                    matrix[i][j] = 15

        return matrix

    def _build_time_windows(
        self,
        pois: list[Any],
        intent: IntentResult,
    ) -> list[tuple[int, int]]:
        """
        构建时间窗
        
        Args:
            pois: POI列表
            intent: IntentResult
            
        Returns:
            时间窗列表（分钟）
        """
        start_minutes = self._time_to_minutes(intent.temporal.start_time)
        end_minutes = self._time_to_minutes(intent.temporal.end_time)

        time_windows = []

        for poi in pois:
            poi_dict = poi if isinstance(poi, dict) else poi.model_dump()

            # 解析营业时间（简化）
            # TODO: 实际实现需要精确解析
            open_time = start_minutes
            close_time = end_minutes

            duration = poi_dict.get("estimated_duration_min", 60)

            window_start = max(open_time, start_minutes)
            window_end = min(close_time - duration, end_minutes)

            if window_start >= window_end:
                window_start = start_minutes
                window_end = end_minutes

            time_windows.append((window_start, window_end))

        return time_windows

    def _time_to_minutes(self, time_str: str) -> int:
        """
        时间转换为分钟
        
        Args:
            time_str: HH:MM格式
            
        Returns:
            分钟数
        """
        try:
            h, m = map(int, time_str.split(":"))
            return h * 60 + m
        except Exception:
            return 9 * 60  # 默认9点

    def _get_experience_score(self, poi: Any) -> float:
        """
        获取体验得分
        
        Args:
            poi: POI
            
        Returns:
            得分
        """
        poi_dict = poi if isinstance(poi, dict) else poi.model_dump()
        rating = poi_dict.get("rating", 3.0)
        sentiment = poi_dict.get("ugc_sentiment", {})
        avg_sentiment = sum(sentiment.values()) / len(sentiment) if sentiment else 0.0

        return (rating / 5.0) * 0.5 + (avg_sentiment / 5.0) * 0.5

    def _get_cost(self, poi: Any) -> float:
        """
        获取费用
        
        Args:
            poi: POI
            
        Returns:
            人均费用
        """
        poi_dict = poi if isinstance(poi, dict) else poi.model_dump()
        return poi_dict.get("avg_cost", 100)

    def _extract_solution(
        self,
        manager: Any,
        routing: Any,
        solution: Any,
        pois: list[Any],
        data: dict[str, Any],
    ) -> list[Any]:
        """
        提取求解结果
        
        Args:
            manager: RoutingIndexManager
            routing: RoutingModel
            solution: Solution
            pois: POI列表
            data: 数据字典
            
        Returns:
            POI访问序列
        """
        route = []
        index = routing.Start(0)

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node > 0:  # 跳过depot
                route.append(pois[node - 1])
            index = solution.Value(routing.NextVar(index))

        return route
