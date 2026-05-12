"""
Personalized Reason Generator - 个性化话术生成器

为每个POI生成个性化的推荐理由
"""

from typing import Any


PERSONALIZED_REASON_PROMPT = """
你是一个贴心的旅行顾问。请为用户生成一段个性化的POI推荐理由。

用户画像：
- 菜系偏好：{cuisine_preferences}
- 消费档位：{spending_level}
- 场景偏好：{scene_preferences}
- 出行人员：{party_composition}

POI 信息：
- 名称：{poi_name}
- 类型：{poi_category}
- 人均消费：{avg_cost} 元
- 亮点：{highlights}
- 场景标签：{scene_tags}

要求：
1. 1-2句话，不超过60字
2. 必须结合用户画像，体现个性化
3. 语气自然、亲切
4. 如果POI与用户偏好有差异，给出合理解释

示例："虽然你平时偏爱日料，但带父母游西湖，楼外楼是品尝正宗杭帮菜的首选，环境也适合长辈用餐。"
"""


class PersonalizedReasonGenerator:
    """
    个性化推荐理由生成器
    """

    def __init__(self, max_reason_length: int = 60) -> None:
        self.max_reason_length = max_reason_length
        self._llm_router = None

    async def generate(
        self,
        poi: dict[str, Any],
        profile: Any,
        intent: Any,
    ) -> str:
        """
        生成个性化推荐理由
        
        Args:
            poi: POI字典
            profile: UserProfile
            intent: IntentResult
            
        Returns:
            推荐理由文本
        """
        # 构建Prompt
        prompt = self._build_prompt(poi, profile, intent)

        # 调用LLM
        reason = await self._call_llm(prompt)

        # 截断处理
        if len(reason) > self.max_reason_length:
            reason = reason[:self.max_reason_length - 3] + "..."

        return reason

    def _build_prompt(self, poi: dict[str, Any], profile: Any, intent: Any) -> str:
        cuisine_prefs = ""
        if profile and profile.cuisine_preferences:
            cuisine_prefs = ", ".join([c.cuisine_type for c in profile.cuisine_preferences[:3]])

        spending_level = profile.spending_level if profile else "mid"

        scene_prefs = ""
        if profile and profile.scene_preferences:
            top_scenes = sorted(profile.scene_preferences.items(), key=lambda x: x[1], reverse=True)[:3]
            scene_prefs = ", ".join([s[0] for s in top_scenes])

        party_comp = ""
        if intent and intent.party.composition:
            comp_map = {"elder": "老人", "child": "儿童", "adult": "成人", "teen": "青少年"}
            party_comp = ", ".join([comp_map.get(c, c) for c in intent.party.composition])

        highlights = ", ".join(poi.get("highlights", [])[:2])
        scene_tags = ", ".join(poi.get("scene_tags", [])[:3])

        return PERSONALIZED_REASON_PROMPT.format(
            cuisine_preferences=cuisine_prefs,
            spending_level=spending_level,
            scene_preferences=scene_prefs,
            party_composition=party_comp,
            poi_name=poi.get("name", ""),
            poi_category=poi.get("category", ""),
            avg_cost=poi.get("avg_cost", 0),
            highlights=highlights,
            scene_tags=scene_tags,
        )

    async def _call_llm(self, prompt: str) -> str:
        from smartroute.services.llm.router import LLMRouter

        if self._llm_router is None:
            self._llm_router = LLMRouter()

        response = await self._llm_router.call(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.7,
            max_tokens=100,
        )

        return response.strip()
