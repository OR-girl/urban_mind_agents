"""
Profile Service - 用户画像服务模块
"""

from smartroute.services.profile.mock_service import (
    MockProfileService,
    get_mock_profile_service,
    mock_profile_service,
)
from smartroute.services.profile.templates import (
    TEMPLATES,
    TEMPLATE_KEYS,
    HOT_POIS_HANGZHOU,
    get_template_by_id,
    get_template_list,
)

__all__ = [
    "MockProfileService",
    "get_mock_profile_service",
    "mock_profile_service",
    "TEMPLATES",
    "TEMPLATE_KEYS",
    "HOT_POIS_HANGZHOU",
    "get_template_by_id",
    "get_template_list",
]