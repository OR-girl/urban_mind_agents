"""
Multi-Plan Generator - 多方案生成器

生成3个差异化路线方案，支持多种交通方式
"""

import asyncio
from typing import Any

from smartroute.agents.route.solver import VRPTWSolver, TRANSPORT_SPEEDS, TRANSPORT_COSTS
from smartroute.schemas.intent import IntentResult, TransportMode
from smartroute.schemas.profile import UserProfile
from smartroute.schemas.route import RoutePlan, POITimelineItem


class MultiPlanGenerator:
    """
    多方案生成器
    
    生成3个差异化路线方案，保证POI重叠率不超过阈值
    """

    def __init__(
        self,
        plan_configs: list[dict[str, Any]],
        max_overlap_ratio: float = 0.5,
    ) -> None:
        self.plan_configs = plan_configs
        self.max_overlap_ratio = max_overlap_ratio

    async def generate(
        self,
        pois: list[Any],
        intent: IntentResult,
        profile: UserProfile | None,
        solver: VRPTWSolver,
    ) -> list[dict[str, Any]]:
        """
        生成多方案
        
        Args:
            pois: POI列表
            intent: IntentResult
            profile: UserProfile
            solver: VRPTWSolver
            
        Returns:
            路线方案列表
        """
        plans = []
        used_poi_ids = set()

        for i, config in enumerate(self.plan_configs):
            # 确保差异化
            candidate_pois = self._ensure_diversity(pois, used_poi_ids, i)

            # 求解
            route_sequence = await solver.solve(
                pois=candidate_pois,
                intent=intent,
                profile=profile,
                weights=config["weights"],
            )

            if route_sequence:
                # 构建时间轴
                timeline = self._build_timeline(route_sequence, intent)

                plan = {
                    "plan_id": f"plan_{chr(97 + i)}",  # plan_a, plan_b, plan_c
                    "name": config["name"],
                    "tagline": config["tagline"],
                    "timeline": timeline,
                    "highlights": self._extract_highlights(route_sequence),
                    "summary": self._compute_summary(timeline),
                    "weights": config["weights"],
                }

                plans.append(plan)

                # 记录已使用的POI
                for poi in route_sequence:
                    poi_dict = poi if isinstance(poi, dict) else poi.model_dump()
                    used_poi_ids.add(poi_dict.get("poi_id", ""))

        return plans

    def _ensure_diversity(
        self,
        pois: list[Any],
        used_poi_ids: set[str],
        plan_index: int,
    ) -> list[Any]:
        """
        确保差异化
        
        Args:
            pois: 原始POI列表
            used_poi_ids: 已使用的POI ID集合
            plan_index: 方案索引
            
        Returns:
            差异化后的候选列表
        """
        if plan_index == 0:
            # 第一个方案使用全部候选
            return pois[:15]

        # 后续方案替换部分重叠POI
        diverse_pois = []
        overlap_count = 0
        max_overlap = int(len(pois) * self.max_overlap_ratio)

        for poi in pois:
            poi_dict = poi if isinstance(poi, dict) else poi.model_dump()
            poi_id = poi_dict.get("poi_id", "")

            if poi_id in used_poi_ids:
                overlap_count += 1
                if overlap_count <= max_overlap:
                    diverse_pois.append(poi)
            else:
                diverse_pois.append(poi)

        return diverse_pois[:15]

    def _build_timeline(
        self,
        route_sequence: list[Any],
        intent: IntentResult,
    ) -> list[dict[str, Any]]:
        """
        构建时间轴

        Args:
            route_sequence: POI访问序列
            intent: IntentResult

        Returns:
            时间轴列表
        """
        timeline = []

        start_minutes = self._time_to_minutes(intent.temporal.start_time)
        current_time = start_minutes

        # 获取交通方式
        transport_mode = intent.transport.primary_mode
        speed_kmh = TRANSPORT_SPEEDS.get(transport_mode, 4.0)
        cost_per_km = TRANSPORT_COSTS.get(transport_mode, 0.0)

        for i, poi in enumerate(route_sequence):
            poi_dict = poi if isinstance(poi, dict) else poi.model_dump()

            # 建议游览时长
            duration = poi_dict.get("estimated_duration_min", 60)

            # 排队时间
            queue_time = poi_dict.get("estimated_queue_minutes", 0)

            arrive_time = self._minutes_to_time(current_time)
            leave_time = self._minutes_to_time(current_time + duration + queue_time)

            item = {
                "poi_id": poi_dict.get("poi_id", ""),
                "poi_name": poi_dict.get("name", ""),
                "category": poi_dict.get("category", ""),
                "arrive_time": arrive_time,
                "leave_time": leave_time,
                "duration_min": duration,
                "estimated_cost": poi_dict.get("avg_cost", 0),
                "highlights": poi_dict.get("highlights", [])[:2],
                "warnings": poi_dict.get("warnings", [])[:1],
                "queue_warning": poi_dict.get("queue_warning", ""),
            }

            if i < len(route_sequence) - 1:
                # 交通到下一个
                next_poi = route_sequence[i + 1]
                next_dict = next_poi if isinstance(next_poi, dict) else next_poi.model_dump()

                # 计算距离和通行时间
                distance_km = self._get_distance_between_pois(poi_dict, next_dict)
                travel_minutes = int(distance_km / speed_kmh * 60)

                # 交通方式额外开销
                if transport_mode == TransportMode.CAR:
                    travel_minutes += 5  # 找停车位
                elif transport_mode == TransportMode.PUBLIC:
                    travel_minutes += 10  # 换乘等待
                elif transport_mode == TransportMode.TAXI:
                    travel_minutes += 3  # 等待接单

                travel_minutes = max(travel_minutes, 5)

                # 计算交通费用
                transport_cost = round(distance_km * cost_per_km, 1)

                # 交通方式名称
                mode_name = self._get_transport_mode_name(transport_mode)

                item["transport_to_next"] = {
                    "mode": mode_name,
                    "duration_min": travel_minutes,
                    "distance_m": int(distance_km * 1000),
                    "cost": transport_cost,
                }

            timeline.append(item)

            # 更新时间
            current_time += duration + queue_time + travel_minutes

        return timeline

    def _get_distance_between_pois(self, poi_a_dict: dict, poi_b_dict: dict) -> float:
        """获取两个POI之间的距离（km）"""
        from smartroute.mock.data import DISTANCE_MATRIX

        poi_a_id = poi_a_dict.get("poi_id", "")
        poi_b_id = poi_b_dict.get("poi_id", "")

        if poi_a_id in DISTANCE_MATRIX and poi_b_id in DISTANCE_MATRIX[poi_a_id]:
            walk_minutes = DISTANCE_MATRIX[poi_a_id][poi_b_id]
            distance_km = walk_minutes / 12.0
            return distance_km

        return 3.0  # 默认3km

    def _get_transport_mode_name(self, mode: TransportMode) -> str:
        """获取交通方式显示名称"""
        names = {
            TransportMode.WALK: "步行",
            TransportMode.BIKE: "骑行",
            TransportMode.CAR: "驾车",
            TransportMode.TAXI: "打车",
            TransportMode.PUBLIC: "公共交通",
            TransportMode.MIXED: "混合交通",
        }
        return names.get(mode, "步行")

    def _time_to_minutes(self, time_str: str) -> int:
        """时间转分钟"""
        try:
            h, m = map(int, time_str.split(":"))
            return h * 60 + m
        except Exception:
            return 9 * 60

    def _minutes_to_time(self, minutes: int) -> str:
        """分钟转时间"""
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    def _extract_highlights(self, route_sequence: list[Any]) -> list[str]:
        """
        提取方案亮点
        
        Args:
            route_sequence: POI访问序列
            
        Returns:
            亮点列表
        """
        highlights = []

        # 高评分POI
        top_rating_poi = max(
            route_sequence,
            key=lambda x: (
                x if isinstance(x, dict) else x.model_dump()
            ).get("rating", 0),
        )
        top_dict = top_rating_poi if isinstance(top_rating_poi, dict) else top_rating_poi.model_dump()
        if top_dict.get("rating", 0) >= 4.5:
            highlights.append(f"包含高分景点「{top_dict.get('name', '')}」")

        # 特色体验
        for poi in route_sequence[:3]:
            poi_dict = poi if isinstance(poi, dict) else poi.model_dump()
            poi_highlights = poi_dict.get("highlights", [])
            if poi_highlights:
                highlights.append(f"{poi_dict.get('name', '')}: {poi_highlights[0]}")

        return highlights[:3]

    def _compute_summary(self, timeline: list[dict[str, Any]]) -> dict[str, Any]:
        """
        计算方案摘要
        
        Args:
            timeline: 时间轴
            
        Returns:
            摘要字典
        """
        if not timeline:
            return {"total_duration_h": 0, "total_cost": 0, "total_distance_km": 0}

        # 总时长
        start = self._time_to_minutes(timeline[0].get("arrive_time", "09:00"))
        end = self._time_to_minutes(timeline[-1].get("leave_time", "18:00"))
        duration_hours = (end - start) / 60.0

        # 总费用
        total_cost = sum(item.get("estimated_cost", 0) for item in timeline)

        # 总步行距离
        total_distance = sum(
            item.get("transport_to_next", {}).get("distance_m", 0)
            for item in timeline
        ) / 1000.0

        return {
            "total_duration_h": round(duration_hours, 1),
            "total_cost": round(total_cost, 0),
            "total_distance_km": round(total_distance, 1),
        }
