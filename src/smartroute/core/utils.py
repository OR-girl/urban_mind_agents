"""
SmartRoute Agent 通用工具模块

提供系统内使用的通用工具函数
"""

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any


def generate_trace_id() -> str:
    """生成唯一追踪 ID"""
    return f"trace_{uuid.uuid4().hex[:16]}"


def generate_session_id() -> str:
    """生成唯一会话 ID"""
    return f"sess_{uuid.uuid4().hex[:16]}"


def generate_plan_id(index: int) -> str:
    """生成方案 ID (plan_a, plan_b, plan_c)"""
    return f"plan_{chr(97 + index)}"


def time_to_minutes(time_str: str) -> int:
    """
    将时间字符串转换为分钟数

    Args:
        time_str: 时间字符串，格式为 HH:MM

    Returns:
        分钟数（从 0 点开始）
    """
    try:
        h, m = map(int, time_str.split(":"))
        return h * 60 + m
    except ValueError:
        return 0


def minutes_to_time(minutes: int) -> str:
    """
    将分钟数转换为时间字符串

    Args:
        minutes: 分钟数（从 0 点开始）

    Returns:
        时间字符串，格式为 HH:MM
    """
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def parse_relative_date(date_str: str, current_date: datetime | None = None) -> str:
    """
    解析相对日期表达式

    Args:
        date_str: 日期字符串（如 "明天"、"后天"、"这周六"）
        current_date: 当前日期，默认为今天

    Returns:
        绝对日期字符串（YYYY-MM-DD）
    """
    if current_date is None:
        current_date = datetime.now()

    # 已经是绝对日期格式
    if date_str.count("-") == 2 and len(date_str.split("-")[0]) == 4:
        return date_str

    relative_map = {
        "今天": 0,
        "明天": 1,
        "后天": 2,
        "后天": 3,
    }

    if date_str in relative_map:
        target_date = current_date + timedelta(days=relative_map[date_str])
        return target_date.strftime("%Y-%m-%d")

    # 处理"这周六"等格式
    if date_str.startswith("这"):
        weekday_name = date_str[1:]
        weekday_map = {
            "周一": 0,
            "周一": 1,
            "周二": 2,
            "周三": 3,
            "周四": 4,
            "周五": 5,
            "周六": 6,
            "周日": 6,
        }
        if weekday_name in weekday_map:
            target_weekday = weekday_map[weekday_name]
            current_weekday = current_date.weekday()
            days_diff = target_weekday - current_weekday
            if days_diff <= 0:
                days_diff += 7  # 下周
            target_date = current_date + timedelta(days=days_diff)
            return target_date.strftime("%Y-%m-%d")

    # 无法解析，返回原字符串
    return date_str


def compute_hash(data: dict[str, Any]) -> str:
    """
    计算字典数据的哈希值

    Args:
        data: 字典数据

    Returns:
        SHA256 哈希值（前16位）
    """
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def merge_dicts(base: dict, update: dict, exclude_none: bool = True) -> dict:
    """
    合并两个字典

    Args:
        base: 基础字典
        update: 更新字典
        exclude_none: 是否排除 None 值

    Returns:
        合合后的字典
    """
    result = base.copy()
    for key, value in update.items():
        if exclude_none and value is None:
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, exclude_none)
        else:
            result[key] = value
    return result


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    截断文本

    Args:
        text: 原文本
        max_length: 最大长度

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_cost_yuan(amount: float) -> str:
    """
    格式化费用显示

    Args:
        amount: 金额（元）

    Returns:
        格式化的金额字符串
    """
    if amount >= 1000:
        return f"¥{amount / 100:.0f}00"
    return f"¥{amount:.0f}"


def format_duration_minutes(minutes: int) -> str:
    """
    格式化时长显示

    Args:
        minutes: 分钟数

    Returns:
        格式化的时长字符串
    """
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        if mins == 0:
            return f"{hours}小时"
        return f"{hours}小时{mins}分钟"
    return f"{minutes}分钟"


def format_distance_km(distance_km: float) -> str:
    """
    格式化距离显示

    Args:
        distance_km: 距离（公里）

    Returns:
        格式化的距离字符串
    """
    if distance_km < 1:
        return f"{distance_km * 1000:.0f}米"
    return f"{distance_km:.1f}公里"


class Timer:
    """
    计时器工具类

    用于测量代码执行耗时
    """

    def __init__(self) -> None:
        self._start_time: float | None = None
        self._end_time: float | None = None

    def start(self) -> None:
        """开始计时"""
        self._start_time = time.time()
        self._end_time = None

    def stop(self) -> float:
        """
        停止计时

        Returns:
            耗时（毫秒）
        """
        self._end_time = time.time()
        return self.elapsed_ms

    @property
    def elapsed_ms(self) -> float:
        """
        获取已耗时（毫秒）

        Returns:
            耗时（毫秒）
        """
        if self._start_time is None:
            return 0.0
        end_time = self._end_time or time.time()
        return (end_time - self._start_time) * 1000

    @property
    def elapsed_seconds(self) -> float:
        """
        获取已耗时（秒）

        Returns:
            耗时（秒）
        """
        return self.elapsed_ms / 1000


def compute_category_similarity(category_a: str, category_b: str) -> float:
    """
    计算两个类目的相似度

    Args:
        category_a: 类目 A
        category_b: 类目 B

    Returns:
        相似度（0-1）
    """
    # 提取大类
    major_cat_a = category_a.split("/")[0] if "/" in category_a else category_a
    major_cat_b = category_b.split("/")[0] if "/" in category_b else category_b

    # 同一大类相似度高
    if major_cat_a == major_cat_b:
        return 0.8

    # 定义大类之间的相似度
    category_groups = {
        "餐厅": {"餐厅", "美食", "餐饮"},
        "景点": {"景点", "景区", "公园", "博物馆"},
        "购物": {"购物", "商场", "商店"},
        "娱乐": {"娱乐", "游乐园", "电影"},
    }

    for group in category_groups.values():
        if major_cat_a in group and major_cat_b in group:
            return 0.6

    return 0.1


def is_business_hours_covered(
    business_hours: list[dict[str, str]],
    visit_time: str,
    duration_minutes: int = 60,
) -> bool:
    """
    检查访问时间是否在营业时间内

    Args:
        business_hours: 营业时间列表 [{"open": "09:00", "close": "21:00"}]
        visit_time: 访问时间（HH:MM）
        duration_minutes: 停留时长（分钟）

    Returns:
        是否在营业时间内
    """
    if not business_hours:
        return True  # 无营业时间信息，默认允许

    visit_minutes = time_to_minutes(visit_time)
    leave_minutes = visit_minutes + duration_minutes

    for hours in business_hours:
        open_minutes = time_to_minutes(hours.get("open", "00:00"))
        close_minutes = time_to_minutes(hours.get("close", "24:00"))

        if open_minutes <= visit_minutes and leave_minutes <= close_minutes:
            return True

    return False