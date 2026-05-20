"""
用户画像预设模板

定义典型用户群体的画像模板，用于 Mock 数据生成
"""

from typing import Any


class UserProfileTemplate:
    """用户画像模板"""

    template_id: str
    template_name: str
    spending_level: str
    avg_spend_base: float
    walk_tolerance_base: float
    niche_preference_base: float
    scene_preferences: dict[str, float]
    cuisine_pool: list[str]
    is_night_owl: bool
    preferred_start_hour: int
    dietary_restrictions_pool: list[str]
    description: str


TEMPLATES: dict[str, dict[str, Any]] = {
    "youth_budget": {
        "template_id": "youth_budget",
        "template_name": "年轻学生",
        "spending_level": "budget",
        "avg_spend_base": 80.0,
        "walk_tolerance_base": 8.0,
        "niche_preference_base": 0.7,
        "scene_preferences": {
            "网红打卡": 0.7,
            "文艺": 0.6,
            "美食": 0.5,
            "户外": 0.4,
        },
        "cuisine_pool": ["奶茶咖啡", "快餐", "小吃", "火锅", "烧烤"],
        "is_night_owl": True,
        "preferred_start_hour": 10,
        "dietary_restrictions_pool": [],
        "description": "年轻学生群体，预算敏感，喜欢网红打卡和小众文艺场所，步行能力强，偏好夜间活动",
    },
    "family_parent": {
        "template_id": "family_parent",
        "template_name": "家庭用户",
        "spending_level": "mid",
        "avg_spend_base": 150.0,
        "walk_tolerance_base": 4.0,
        "niche_preference_base": 0.4,
        "scene_preferences": {
            "亲子": 0.8,
            "自然风光": 0.6,
            "美食": 0.5,
            "历史文化": 0.4,
        },
        "cuisine_pool": ["杭帮菜", "家常菜", "西餐", "日料", "自助餐"],
        "is_night_owl": False,
        "preferred_start_hour": 9,
        "dietary_restrictions_pool": [],
        "description": "有孩子的家庭用户，关注亲子友好场所，步行适中，偏好白天活动",
    },
    "business_mid": {
        "template_id": "business_mid",
        "template_name": "商务人士",
        "spending_level": "premium",
        "avg_spend_base": 300.0,
        "walk_tolerance_base": 3.0,
        "niche_preference_base": 0.3,
        "scene_preferences": {
            "商务宴请": 0.7,
            "安静私密": 0.6,
            "美食": 0.5,
            "环境优美": 0.4,
        },
        "cuisine_pool": ["粤菜", "日料", "西餐", "杭帮菜", "海鲜"],
        "is_night_owl": False,
        "preferred_start_hour": 8,
        "dietary_restrictions_pool": [],
        "description": "商务人士，消费较高，时间敏感，偏好知名场所和安静环境",
    },
    "elder_relaxed": {
        "template_id": "elder_relaxed",
        "template_name": "银发族",
        "spending_level": "mid",
        "avg_spend_base": 120.0,
        "walk_tolerance_base": 2.0,
        "niche_preference_base": 0.2,
        "scene_preferences": {
            "历史文化": 0.7,
            "自然风光": 0.5,
            "安静": 0.6,
            "公园": 0.5,
        },
        "cuisine_pool": ["杭帮菜", "家常菜", "点心", "茶餐厅"],
        "is_night_owl": False,
        "preferred_start_hour": 8,
        "dietary_restrictions_pool": ["辣", "油腻"],
        "description": "老年用户，步行受限，偏好历史文化景点和安静场所，饮食清淡",
    },
    "foodie": {
        "template_id": "foodie",
        "template_name": "美食探索者",
        "spending_level": "mid",
        "avg_spend_base": 200.0,
        "walk_tolerance_base": 5.0,
        "niche_preference_base": 0.5,
        "scene_preferences": {
            "美食探索": 0.9,
            "文艺": 0.4,
            "网红": 0.5,
            "小众": 0.3,
        },
        "cuisine_pool": ["杭帮菜", "川菜", "粤菜", "日料", "韩料", "火锅", "烧烤", "西餐"],
        "is_night_owl": True,
        "preferred_start_hour": 11,
        "dietary_restrictions_pool": [],
        "description": "美食爱好者，以吃为主，菜系偏好丰富，愿意为美食探索走更多路",
    },
    "culture_lover": {
        "template_id": "culture_lover",
        "template_name": "文化爱好者",
        "spending_level": "mid",
        "avg_spend_base": 150.0,
        "walk_tolerance_base": 4.0,
        "niche_preference_base": 0.6,
        "scene_preferences": {
            "历史文化": 0.8,
            "博物馆": 0.7,
            "文艺": 0.5,
            "小众": 0.4,
        },
        "cuisine_pool": ["杭帮菜", "茶餐厅", "点心", "素食"],
        "is_night_owl": False,
        "preferred_start_hour": 9,
        "dietary_restrictions_pool": [],
        "description": "文化爱好者，偏好博物馆、古迹、文艺场所，喜欢小众有深度的地方",
    },
}

TEMPLATE_KEYS = list(TEMPLATES.keys())


"""
杭州热门 POI 列表（用于生成 visited_poi_ids）
"""
HOT_POIS_HANGZHOU = [
    "西湖",
    "灵隐寺",
    "雷峰塔",
    "断桥残雪",
    "三潭印月",
    "苏堤春晓",
    "白堤",
    "岳王庙",
    "曲院风荷",
    "花港观鱼",
    "柳浪闻莺",
    "杭州动物园",
    "杭州植物园",
    "中国丝绸博物馆",
    "浙江省博物馆",
    "河坊街",
    "南宋御街",
    "武林广场",
    "钱塘江大桥",
    "九溪烟树",
    "龙井村",
    "梅家坞",
    "宋城",
    "西溪湿地",
    "千岛湖",
]


def get_template_by_id(template_id: str) -> dict[str, Any] | None:
    """根据 ID 获取模板"""
    return TEMPLATES.get(template_id)


def get_template_list() -> list[dict[str, Any]]:
    """获取所有模板列表"""
    return list(TEMPLATES.values())