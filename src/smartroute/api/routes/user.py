"""
User Router - 用户偏好接口

提供用户画像管理API
"""

from typing import Any

from fastapi import APIRouter, Depends

from smartroute.schemas import UserPreferencesRequest
from smartroute.schemas.profile import UserProfile
from smartroute.agents.profile.agent import ProfileAgent


router = APIRouter(prefix="/api/v1/user", tags=["user"])


profile_agent = ProfileAgent()


@router.get("/profile/{user_id}", response_model=dict[str, Any])
async def get_user_profile(user_id: str) -> dict[str, Any]:
    """
    获取用户画像
    
    Args:
        user_id: User ID
        
    Returns:
        用户画像
    """
    from smartroute.storage.cache.redis import RedisCache

    cache = RedisCache()
    cached = await cache.get(f"profile:user:{user_id}")

    if cached:
        return cached

    # 默认画像
    return {
        "user_id": user_id,
        "is_cold_start": True,
        "confidence": 0.3,
    }


@router.put("/preferences", response_model=dict[str, Any])
async def update_user_preferences(
    request: UserPreferencesRequest,
) -> dict[str, Any]:
    """
    更新用户偏好
    
    Args:
        request: UserPreferencesRequest
        
    Returns:
        更新后的画像
    """
    updated_profile = await profile_agent.update_profile(
        user_id=request.user_id,
        updates={
            "dietary_restrictions": request.dietary_restrictions,
            "spending_level": request.spending_level,
        },
    )

    return updated_profile.model_dump()


@router.post("/preferences/tags", response_model=dict[str, Any])
async def set_preference_tags(
    user_id: str,
    tags: list[str],
) -> dict[str, Any]:
    """
    设置偏好标签（冷启动引导）
    
    Args:
        user_id: User ID
        tags: 标签列表
        
    Returns:
        构建的画像
    """
    from smartroute.agents.profile.cold_start import ColdStartHandler

    handler = ColdStartHandler()
    profile = handler.build_profile_from_selected_tags(user_id, tags)

    # 缓存画像
    from smartroute.storage.cache.redis import RedisCache

    cache = RedisCache()
    await cache.set(f"profile:user:{user_id}", profile.model_dump(), ttl=3600)

    return profile.model_dump()


@router.delete("/profile/{user_id}")
async def delete_user_profile(user_id: str) -> dict[str, Any]:
    """
    删除用户画像
    
    Args:
        user_id: User ID
        
    Returns:
        操作结果
    """
    from smartroute.storage.cache.redis import RedisCache

    cache = RedisCache()
    await cache.delete(f"profile:user:{user_id}")

    return {"status": "deleted", "user_id": user_id}


@router.get("/preferences/tags")
async def get_available_tags() -> list[str]:
    """
    获取可选偏好标签
    
    Returns:
        标签列表
    """
    from smartroute.agents.profile.cold_start import ColdStartHandler

    handler = ColdStartHandler()
    return handler.get_preference_tags_for_collection()
