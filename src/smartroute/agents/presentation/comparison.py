"""
Plan Comparison Generator - 方案对比矩阵生成器

生成方案对比矩阵，突出差异点
"""

from typing import Any


class PlanComparisonGenerator:
    """
    方案对比矩阵生成器
    """

    def generate(self, routes: list[Any]) -> dict[str, Any]:
        """
        生成对比矩阵
        
        Args:
            routes: 路线方案列表
            
        Returns:
            对比矩阵字典
        """
        if len(routes) < 2:
            return {}

        comparison = {
            "dimensions": ["餐厅选择", "路线风格", "总费用", "总步行", "预计排队"],
            "plans": {},
        }

        for route in routes:
            plan_id = route.get("plan_id", "")
            timeline = route.get("timeline", [])
            summary = route.get("summary", {})

            # 提取餐厅
            restaurants = [
                item for item in timeline
                if "餐" in item.get("category", "") or "餐厅" in item.get("category", "")
            ]

            # 计算总排队
            queue_count = sum(
                1 for item in timeline
                if item.get("queue_warning", "")
            )

            comparison["plans"][plan_id] = {
                "餐厅选择": restaurants[0].get("poi_name", "待定") if restaurants else "待定",
                "路线风格": route.get("tagline", ""),
                "总费用": f"¥{summary.get('total_cost', 0)}/人",
                "总步行": f"{summary.get('total_distance_km', 0):.1f}km",
                "预计排队": f"约 {queue_count * 30} 分钟" if queue_count > 0 else "较少",
            }

        return comparison

    def generate_text_comparison(self, routes: list[Any]) -> str:
        """
        生成文本对比说明
        
        Args:
            routes: 路线方案列表
            
        Returns:
            对比文本
        """
        if len(routes) < 2:
            return ""

        comparisons = []

        # 费用对比
        costs = [
            (r.get("plan_id", ""), r.get("summary", {}).get("total_cost", 0))
            for r in routes
        ]
        sorted_by_cost = sorted(costs, key=lambda x: x[1])
        if sorted_by_cost[0][1] < sorted_by_cost[-1][1] - 20:
            comparisons.append(
                f"「{sorted_by_cost[0][0]}」费用最低，适合预算敏感用户"
            )

        # 步行对比
        walks = [
            (r.get("plan_id", ""), r.get("summary", {}).get("total_distance_km", 0))
            for r in routes
        ]
        sorted_by_walk = sorted(walks, key=lambda x: x[1])
        if sorted_by_walk[0][1] < sorted_by_walk[-1][1] - 1:
            comparisons.append(
                f"「{sorted_by_walk[0][0]}」步行最少，适合体力有限用户"
            )

        return " | ".join(comparisons) if comparisons else "三个方案各有特色，请根据偏好选择"
