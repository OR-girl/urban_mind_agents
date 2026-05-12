"""
POI Services 模块

POI数据服务，包括：
- dianping: 大众点评API客户端
"""

from smartroute.services.poi.dianping import DianpingClient

__all__ = ["DianpingClient"]
