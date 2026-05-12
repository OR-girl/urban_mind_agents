"""
Adjustable Hints Generator - 可调整提示生成器

生成用户可调整的提示内容
"""

from typing import Any


class AdjustableHintsGenerator:
    """
    可调整提示生成器
    """

    def generate(
        self,
        routes: list[Any],
        enriched_pois_map: dict[str, Any],
    ) -> list[str]:
        """
        生成可调整提示
        
        Args:
            routes: 路线方案列表
            enriched_pois_map: POI数据映射
            
        Returns:
            提示列表
        """
        hints = []

        if not routes:
            return ["请描述您的出行需求，我将为您生成路线方案"]

        # 检查高排队POI
        for route in routes[:1]:  # 基于第一个方案
            timeline = route.get("timeline", [])
            for item in timeline:
                if item.get("queue_warning"):
                    poi_name = item.get("poi_name", "")
                    hints.append(f"可将「{poi_name}」换成排队较少的替代选项")
                    break  # 只提示一个

        # 检查可添加的类型
        categories = set()
        for route in routes[:1]:
            for item in route.get("timeline", []):
                categories.add(item.get("category", ""))

        if not any("下午茶" in cat or "茶" in cat for cat in categories):
            hints.append("可以加入一个下午茶环节（约 14:00-15:30）")

        if not any("购物" in cat for cat in categories):
            hints.append("如需购物，可在路线末尾加入附近商场")

        # 时间调整提示
        hints.append("告诉我您想提前结束或延后出发，我会调整时间安排")

        # POI替换提示
        hints.append("告诉我您想替换哪个地点，我可以为您推荐类似选项")

        return hints[:4]  # 最多4条提示
