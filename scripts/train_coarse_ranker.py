"""
训练 LightGBM 粗排模型

使用 Mock 数据生成训练样本，训练简单的排序模型
"""

import numpy as np
import lightgbm as lgb
import os

from smartroute.mock.data import HANGZHOU_POIS
from smartroute.schemas.intent import IntentResult, IntentType, SpatialConstraint, TemporalConstraint, Preferences, BudgetInfo, PartyInfo
from smartroute.schemas.profile import UserProfile, CuisinePreference


def generate_training_data(n_samples: int = 1000) -> tuple[np.ndarray, np.ndarray]:
    """
    生成模拟训练数据

    标签定义：用户对POI的匹配得分（0-1）

    Args:
        n_samples: 样本数量

    Returns:
        (特征矩阵, 标签向量)
    """
    np.random.seed(42)

    # 模拟不同的意图类型
    intent_types = ["tour", "food_tour", "family", "date", "city_walk"]
    spending_levels = ["budget", "mid", "premium"]

    features = []
    labels = []

    for _ in range(n_samples):
        # 随机选择一个POI
        poi = np.random.choice(HANGZHOU_POIS)

        # 随机生成意图和画像
        intent_type = np.random.choice(intent_types)
        spending_level = np.random.choice(spending_levels)
        budget = np.random.choice([50, 100, 150, 200, 300, 500])

        # 构建模拟意图
        intent = IntentResult(
            intent_type=IntentType(intent_type),
            confidence=0.8,
            spatial=SpatialConstraint(city="杭州", anchor_poi="西湖", radius_km=5.0),
            temporal=TemporalConstraint(date="2026-06-05"),
            preferences=Preferences(),
            budget=BudgetInfo(per_person=budget, level=spending_level),
            party=PartyInfo(size=np.random.randint(1, 5)),
            raw_query="模拟训练数据",
        )

        # 构建模拟画像
        profile = UserProfile(
            user_id="train_user",
            spending_level=spending_level,
            avg_spend_per_person=budget * 0.8,
            scene_preferences={"亲子": np.random.uniform(0, 1), "自然风光": np.random.uniform(0, 1)},
            dietary_restrictions=[],
            visited_poi_ids=[],
        )

        # 提取特征（与 ranker.py 中 _extract_features 一致）
        poi_dict = poi.copy()

        # 1. 语义相似度（模拟）
        semantic_sim = np.random.uniform(0.3, 0.9)

        # 2. 距离
        distance_km = poi_dict.get("distance_km", np.random.uniform(0.5, 10.0))

        # 3. 评分
        rating = poi_dict.get("rating", 4.0)

        # 4. 评论数（log）
        review_count = poi_dict.get("review_count", 100)
        log_review = np.log1p(review_count)

        # 5. 画像匹配度
        profile_match = compute_profile_match(poi_dict, profile)

        # 6. 预算匹配度
        budget_match = compute_budget_match(poi_dict, intent)

        # 7. 是否去过
        visited = 0.0

        feature_vec = [
            semantic_sim,
            distance_km,
            rating,
            log_review,
            profile_match,
            budget_match,
            visited,
        ]
        features.append(feature_vec)

        # 生成标签（模拟用户偏好）
        # 高评分 + 预算匹配 + 距离近 + 场景匹配 = 高得分
        label = (
            0.3 * (rating / 5.0) +
            0.25 * budget_match +
            0.2 * (1.0 / (1.0 + distance_km)) +
            0.15 * profile_match +
            0.1 * semantic_sim
        )
        # 加一些噪声
        label += np.random.uniform(-0.05, 0.05)
        label = np.clip(label, 0.0, 1.0)

        labels.append(label)

    return np.array(features), np.array(labels)


def compute_profile_match(poi: dict, profile: UserProfile) -> float:
    """计算画像匹配度"""
    score = 0.0
    poi_tags = set(poi.get("tags", []))

    # 场景偏好匹配
    for scene, weight in profile.scene_preferences.items():
        if scene in poi_tags:
            score += weight * 0.5

    # 消费档位匹配
    avg_cost = poi.get("avg_cost", 100)
    if profile.spending_level == "budget" and avg_cost < 50:
        score += 0.3
    elif profile.spending_level == "mid" and 50 <= avg_cost <= 200:
        score += 0.3
    elif profile.spending_level == "premium" and avg_cost > 200:
        score += 0.3

    return min(1.0, score)


def compute_budget_match(poi: dict, intent: IntentResult) -> float:
    """计算预算匹配度"""
    if not intent.budget.per_person:
        return 1.0

    avg_cost = poi.get("avg_cost", 0)
    ratio = avg_cost / intent.budget.per_person

    if ratio <= 1.0:
        return 1.0
    elif ratio <= 1.2:
        return 0.5
    else:
        return 0.0


def train_model(features: np.ndarray, labels: np.ndarray) -> lgb.Booster:
    """
    训练 LightGBM 模型

    Args:
        features: 特征矩阵
        labels: 标签向量

    Returns:
        训练好的模型
    """
    # 创建数据集
    train_data = lgb.Dataset(features, label=labels)

    # 模型参数（简单的回归任务）
    params = {
        "objective": "regression",
        "metric": "mse",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "num_threads": 1,
    }

    # 训练
    model = lgb.train(
        params,
        train_data,
        num_boost_round=100,
    )

    return model


def main():
    """训练并保存模型"""
    print("=" * 60)
    print("训练 LightGBM 粗排模型")
    print("=" * 60)

    # 生成训练数据
    print("\n生成训练数据...")
    features, labels = generate_training_data(n_samples=2000)
    print(f"样本数: {len(features)}")
    print(f"特征维度: {features.shape[1]}")

    # 特征名称
    feature_names = [
        "semantic_similarity",
        "distance_km",
        "rating",
        "log_review_count",
        "profile_match",
        "budget_match",
        "visited",
    ]

    # 训练模型
    print("\n训练模型...")
    model = train_model(features, labels)

    # 特征重要性
    print("\n特征重要性:")
    importance = model.feature_importance()
    for name, imp in zip(feature_names, importance):
        print(f"  {name}: {imp}")

    # 创建模型目录
    model_dir = "models"
    os.makedirs(model_dir, exist_ok=True)

    # 保存模型
    model_path = os.path.join(model_dir, "coarse_ranker.txt")
    model.save_model(model_path)
    print(f"\n模型已保存到: {model_path}")

    # 测试预测
    print("\n测试预测:")
    test_features = features[:5]
    predictions = model.predict(test_features)
    for i, (feat, pred, label) in enumerate(zip(test_features, predictions, labels[:5])):
        print(f"  样本{i+1}: 预测={pred:.3f}, 真实={label:.3f}")

    print("\n训练完成!")


if __name__ == "__main__":
    main()