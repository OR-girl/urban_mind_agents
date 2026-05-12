"""
Pytest 配置文件

定义通用的fixtures和测试配置
"""

import pytest
import asyncio
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    创建事件循环

    为异步测试提供事件循环
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def mock_redis():
    """
    自动Mock Redis连接

    所有测试自动使用Mock Redis，避免实际连接
    """
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.setex = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.exists = AsyncMock(return_value=False)

    # Mock pipeline operations
    mock_pipe = MagicMock()
    mock_pipe.get = MagicMock(return_value=None)
    mock_pipe.set = MagicMock(return_value=None)
    mock_pipe.execute = AsyncMock(return_value={})
    mock_client.pipeline = MagicMock(return_value=mock_pipe)

    with patch("redis.asyncio.Redis", return_value=mock_client):
        # Also patch the cache manager's _get_redis method
        with patch("smartroute.agents.ugc.cache.UGCCacheManager._get_redis", return_value=mock_client):
            yield mock_client


@pytest.fixture(autouse=True)
def mock_milvus():
    """
    自动Mock Milvus连接

    所有测试自动使用Mock Milvus，避免实际连接
    """
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=[])
    mock_client.insert = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.query = AsyncMock(return_value=[])

    with patch("smartroute.storage.vector.milvus.MilvusClient", return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def mock_llm_router():
    """
    自动Mock LLM Router

    所有测试自动使用Mock LLM Router，避免实际API调用
    """
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value="Mock LLM response")
    mock_router.call_with_function = AsyncMock(return_value={"result": "mock"})

    with patch("smartroute.services.llm.router.LLMRouter", return_value=mock_router):
        yield mock_router


@pytest.fixture(autouse=True)
def mock_embedding_service():
    """
    自动Mock Embedding Service

    所有测试自动使用Mock Embedding，避免实际API调用
    """
    mock_service = MagicMock()
    mock_service.encode = AsyncMock(return_value=[0.1] * 768)
    mock_service.encode_batch = AsyncMock(return_value=[[0.1] * 768])

    with patch("smartroute.services.llm.embedding.EmbeddingService", return_value=mock_service):
        yield mock_service


@pytest.fixture(autouse=True)
def mock_amap_client():
    """
    自动Mock Amap Client

    所有测试自动使用Mock Amap Client，避免实际API调用
    """
    mock_client = MagicMock()
    mock_client.distance_matrix = AsyncMock(return_value=[[0, 15, 20], [15, 0, 10], [20, 10, 0]])
    mock_client.poi_search = AsyncMock(return_value=[])
    mock_client.route_plan = AsyncMock(return_value={})

    with patch("smartroute.services.map.amap.AmapClient", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_redis_client():
    """
    Mock Redis 客户端

    用于测试中模拟Redis操作（显式使用）
    """
    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=True)

    return client


@pytest.fixture
def mock_milvus_client():
    """
    Mock Milvus 客户端

    用于测试中模拟向量检索操作（显式使用）
    """
    client = MagicMock()
    client.search = AsyncMock(return_value=[])
    client.insert = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=True)

    return client


@pytest.fixture
def mock_llm_client():
    """
    Mock LLM 客户端

    用于测试中模拟LLM调用
    """
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()

    return client


@pytest.fixture
def mock_settings():
    """
    Mock 配置

    用于测试中模拟配置
    """
    settings = MagicMock()
    settings.db.redis_host = "localhost"
    settings.db.redis_port = 6379
    settings.db.redis_password = None
    settings.db.redis_db = 0

    return settings


@pytest.fixture
def sample_intent_result():
    """
    示例 IntentResult

    用于测试中的意图结果
    """
    from smartroute.schemas.intent import (
        IntentResult,
        IntentType,
        SpatialConstraint,
        TemporalConstraint,
        PartyInfo,
        Preferences,
        BudgetInfo,
    )

    return IntentResult(
        intent_type=IntentType.TOUR,
        confidence=0.95,
        spatial=SpatialConstraint(
            city="杭州",
            region="西湖区",
            anchor_poi="西湖",
            radius_km=5.0,
        ),
        temporal=TemporalConstraint(
            date="2026-05-13",
            start_time="09:00",
            end_time="18:00",
            duration_hours=8.0,
        ),
        party=PartyInfo(
            size=3,
            composition=["adult", "elder"],
        ),
        preferences=Preferences(
            must_have=["西湖"],
            nice_to_have=["雷峰塔"],
            themes=["自然风光"],
        ),
        budget=BudgetInfo(
            per_person=500.0,
        ),
        raw_query="明天带父母去西湖玩一天，预算500元",
    )


@pytest.fixture
def sample_user_profile():
    """
    示例 UserProfile

    用于测试中的用户画像
    """
    from smartroute.schemas.profile import (
        UserProfile,
        CuisinePreference,
    )

    return UserProfile(
        user_id="test_user_001",
        is_cold_start=False,
        cuisine_preferences=[
            CuisinePreference(cuisine_type="杭帮菜", score=0.9, order_count=10),
            CuisinePreference(cuisine_type="日料", score=0.7, order_count=5),
        ],
        spending_level="mid",
        avg_spend_per_person=150.0,
        scene_preferences={"亲子": 0.8, "网红": 0.3},
        walk_tolerance_km=5.0,
    )


@pytest.fixture
def sample_poi_list():
    """
    示例 POI 列表

    用于测试中的POI召回结果
    """
    return [
        {
            "poi_id": "poi_001",
            "name": "西湖",
            "category": "景点/自然风光",
            "location": {"lat": 30.259, "lng": 120.130},
            "avg_cost": 0.0,
            "rating": 4.8,
            "review_count": 50000,
            "tags": ["自然风光", "免费", "世界遗产"],
        },
        {
            "poi_id": "poi_002",
            "name": "雷峰塔",
            "category": "景点/历史遗迹",
            "location": {"lat": 30.252, "lng": 120.148},
            "avg_cost": 40.0,
            "rating": 4.5,
            "review_count": 30000,
            "tags": ["历史遗迹", "文化", "登高望远"],
        },
        {
            "poi_id": "poi_003",
            "name": "楼外楼",
            "category": "餐厅/杭帮菜",
            "location": {"lat": 30.253, "lng": 120.137},
            "avg_cost": 150.0,
            "rating": 4.6,
            "review_count": 20000,
            "tags": ["杭帮菜", "老字号", "西湖醋鱼"],
        },
    ]