"""
Retrieval Agent - POI召回Agent主类

多路召回候选POI，包括语义召回、地理召回、协同过滤、类目召回和热门兜底
"""

from typing import Any

from smartroute.agents.base import VectorBasedAgent, CacheableAgent
from smartroute.agents.retrieval.retriever import MultiPathRetriever
from smartroute.agents.retrieval.ranker import CoarseRanker, DiversityReranker
from smartroute.schemas import SystemState


class RetrievalAgent(VectorBasedAgent, CacheableAgent):
    """
    POI召回Agent
    
    处理流程：
    1. 多路并行召回（5路）
    2. 召回融合与去重
    3. 粗排（LightGBM打分）
    4. 硬过滤（营业时间/饮食禁忌）
    5. MMR多样性重排
    """

    agent_name = "retrieval"

    def __init__(self) -> None:
        # 需要先初始化父类
        VectorBasedAgent.__init__(self)
        CacheableAgent.__init__(self)

        self.retriever = MultiPathRetriever(
            semantic_top_k=self.get_config_value("semantic", {}).get("top_k", 50),
            geo_top_k=100,
            collab_top_k=self.get_config_value("collaborative", {}).get("top_k", 30),
            hot_top_k=self.get_config_value("hot_fallback", {}).get("top_k", 20),
        )
        self.ranker = CoarseRanker(
            model_path=self.get_config_value("coarse_rank", {}).get("model_path", ""),
        )
        self.diversity_reranker = DiversityReranker(
            lambda_param=self.get_config_value("mmr", {}).get("lambda_param", 0.6),
            top_k=self.get_config_value("mmr", {}).get("candidate_pool_size", 20),
        )

    async def execute(self, state: SystemState) -> dict[str, Any]:
        """
        执行POI召回
        
        Args:
            state: 系统状态
            
        Returns:
            包含候选POI列表的字典
        """
        intent = state.get_intent()
        profile = state.get_profile()

        if not intent:
            self.logger.warning("intent_missing_for_retrieval")
            return {"candidates": [], "retrieval_metadata": {"error": "no_intent"}}

        # 多路并行召回
        candidates, metadata = await self.retriever.retrieve_multi_path(
            intent=intent,
            profile=profile,
        )

        self.logger.info(
            "multi_path_retrieval_completed",
            total_candidates=len(candidates),
            paths=metadata.get("path_counts", {}),
        )

        if not candidates:
            self.logger.warning("no_candidates_retrieved")
            return {"candidates": [], "retrieval_metadata": metadata}

        # 粗排
        ranked_candidates = await self.ranker.rank(
            candidates=candidates,
            intent=intent,
            profile=profile,
        )

        # 硬过滤
        filtered_candidates = await self._apply_hard_filters(
            ranked_candidates,
            intent,
            profile,
        )

        # MMR多样性重排
        final_candidates = self.diversity_reranker.rerank(filtered_candidates)

        metadata["final_count"] = len(final_candidates)
        metadata["filtered_count"] = len(filtered_candidates)

        return {
            "candidates": [c.model_dump() if hasattr(c, "model_dump") else c for c in final_candidates],
            "retrieval_metadata": metadata,
        }

    async def _apply_hard_filters(
        self,
        candidates: list[Any],
        intent: Any,
        profile: Any,
    ) -> list[Any]:
        """
        应用硬过滤

        Args:
            candidates: 候选POI列表
            intent: IntentResult
            profile: UserProfile

        Returns:
            过滤后的候选列表
        """
        filtered = []

        for poi in candidates:
            poi_dict = poi.model_dump() if hasattr(poi, "model_dump") else poi

            # 营业时间过滤（简化版，实际需要更精确的校验）
            # TODO: 实际实现需要解析营业时间并与出行时段对比

            # 饮食禁忌过滤
            if profile and profile.dietary_restrictions:
                poi_tags = poi_dict.get("tags", [])
                for restriction in profile.dietary_restrictions:
                    if restriction in str(poi_tags):
                        continue  # 跳过不符合饮食禁忌的POI

            # 已去过的POI过滤（可选）
            if profile and profile.visited_poi_ids:
                poi_id = poi_dict.get("poi_id", "")
                if poi_id in profile.visited_poi_ids:
                    continue  # 跳过已去过的POI

            filtered.append(poi)

        return filtered


if __name__ == "__main__":
    import asyncio
    from smartroute.schemas.intent import IntentResult, IntentType, SpatialConstraint, TemporalConstraint, PartyInfo, Preferences, BudgetInfo
    from smartroute.schemas.profile import UserProfile, CuisinePreference
    from smartroute.schemas.state import SystemState

    # 模拟 IntentResult（意图识别的结果）
    mock_intent = IntentResult(
        intent_type=IntentType.FAMILY,
        confidence=0.95,
        spatial=SpatialConstraint(
            city="杭州",
            region="西湖",
            anchor_poi="西湖",
            radius_km=5.0,
            exclude_areas=[],
        ),
        temporal=TemporalConstraint(
            date="2026-06-05",
            start_time="09:00",
            end_time="18:00",
            duration_hours=8.0,
            flexibility="flexible",
            meal_preferences=["lunch"],
        ),
        party=PartyInfo(
            size=3,
            composition=["adult", "adult", "child"],
            child_ages=[6],
            special_needs=[],
        ),
        preferences=Preferences(
            must_have=["餐厅"],  # 必须有餐厅
            nice_to_have=["亲子", "轻松"],
            avoid=["排队很久"],
            themes=["家庭出游"],
            cuisine_types=["杭帮菜"],
            poi_style=None,
        ),
        budget=BudgetInfo(
            per_person=200,
            level="mid",
        ),
        ambiguity_flags=[],
        inferred_fields=[],
        raw_query="我们一家三口这周六想去杭州西湖玩一天",
    )

    # 模拟 UserProfile（用户画像）
    mock_profile = UserProfile(
        user_id="test_user_001",
        is_cold_start=False,
        cuisine_preferences=[
            CuisinePreference(cuisine_type="杭帮菜", score=0.8, order_count=5),
            CuisinePreference(cuisine_type="日料", score=0.6, order_count=3),
        ],
        spending_level="mid",
        avg_spend_per_person=150.0,
        scene_preferences={"亲子": 0.7, "自然风光": 0.5, "文化历史": 0.3},
        walk_tolerance_km=3.0,
        dietary_restrictions=[],
        visited_poi_ids=["poi_xihu_001"],  # 已去过西湖
        niche_preference_score=0.3,
    )

    # 模拟 SystemState
    mock_state = SystemState(
        session_id="test_session_001",
        trace_id="test_trace_001",
        request_type="NEW",
        user_id="test_user_001",
        raw_query="我们一家三口这周六想去杭州西湖玩一天",
        dialog_history=[],
        intent=mock_intent.model_dump(),
        profile=mock_profile.model_dump(),
    )

    print("=" * 60)
    print("测试 Retrieval Agent 召回效果")
    print("=" * 60)
    print(f"\n用户意图: {mock_intent.intent_type.value}")
    print(f"城市: {mock_intent.spatial.city}")
    print(f"锚点: {mock_intent.spatial.anchor_poi}")
    print(f"半径: {mock_intent.spatial.radius_km} km")
    print(f"必须包含: {mock_intent.preferences.must_have}")
    print(f"预算: {mock_intent.budget.per_person} 元/人")
    print(f"用户画像消费档位: {mock_profile.spending_level}")
    print(f"已去过: {mock_profile.visited_poi_ids}")

    # 运行 Retrieval Agent
    agent = RetrievalAgent()
    result = asyncio.run(agent.execute(mock_state))

    candidates = result.get("candidates", [])
    metadata = result.get("retrieval_metadata", {})

    print("\n" + "=" * 60)
    print("召回结果")
    print("=" * 60)
    print(f"\n召回路径统计: {metadata.get('path_counts', {})}")
    print(f"最终候选数量: {metadata.get('final_count', 0)}")
    print(f"过滤后数量: {metadata.get('filtered_count', 0)}")

    print("\n候选 POI 列表:")
    print("-" * 60)
    for i, poi in enumerate(candidates[:10], 1):
        name = poi.get("name", "未知")
        category = poi.get("category", "未知")
        rating = poi.get("rating", 0)
        avg_cost = poi.get("avg_cost", 0)
        distance_km = poi.get("distance_km", 0)
        if isinstance(distance_km, str):
            distance_km = 0.0
        retrieval_path = poi.get("retrieval_path", "未知")
        score = poi.get("coarse_rank_score", 0) or 0

        print(f"{i}. {name}")
        print(f"   类目: {category} | 评分: {rating} | 人均: ¥{avg_cost}")
        print(f"   距离: {distance_km:.1f}km (预估) | 召回来源: {retrieval_path} | 排序分: {score:.3f}")
        print(f"   标签: {poi.get('tags', [])[:3]}")
        print()

    print("\n" + "=" * 60)
    print("召回 Agent 与意图 Agent 的串联关系")
    print("=" * 60)
    print("""
串联流程:
┌─────────────┐
│ 用户输入    │ "我们一家三口想去杭州西湖玩一天"
└──────┬──────┘
       ↓
┌─────────────┐
│ Intent Agent│ 解析意图 → IntentResult
│             │ - 城市: 杭州
│             │ - 锚点: 西湖
│             │ - 必须有: 餐厅
│             │ - 预算: 200元/人
│             │ - 人员: 一家三口+6岁孩子
└──────┬──────┘
       ↓ IntentResult 写入 SystemState.intent
       ↓
┌─────────────┐
│ Profile Agent│ 获取用户画像 → UserProfile
│             │ - 消费档位: mid
│             │ - 已去过: 西湖
│             │ - 偏好: 亲子、自然风光
└──────┬──────┘
       ↓ UserProfile 写入 SystemState.profile
       ↓
       ↓ Intent + Profile 作为输入
       ↓
┌─────────────┐
│Retrieval Agent│ 5路并行召回
│             │ 1. 语义召回: 匹配"亲子"、"家庭"标签
│             │ 2. 地理召回: 西湖5km内
│             │ 3. 协同过滤: mid消费档位用户喜欢
│             │ 4. 类目召回: 必须有餐厅
│             │ 5. 热门兜底: 高评分POI
└──────┬──────┘
       ↓ 去重 + 粗排 + 过滤 + MMR重排
       ↓
       ↓ 候选POI列表写入 SystemState.candidates
       ↓
┌─────────────┐
│ UGC Agent   │ 分析评论 → EnrichedPOI
└──────┬──────┘
       ↓
┌─────────────┐
│ Route Agent │ 路线规划 → 3个方案
└──────┬──────┘
       ↓
┌─────────────┐
│Presentation │ 生成最终输出
└─────────────┘

关键点:
- Intent Agent 输出 IntentResult → Retrieval 输入
- Profile Agent 输出 UserProfile → Retrieval 输入
- Retrieval 输出 candidates → 后续 Agent 输入
- 所有数据通过 SystemState 流转
    """)
