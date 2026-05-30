"""
LLM Router - Anthropic-first multi-provider router with circuit breakers.
Primary: Anthropic SDK → DeepSeek proxy (supports native tool_use).
Fallback: OpenAI SDK → text completion + JSON extraction.
"""

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import openai

from smartroute.core.config import get_settings
from smartroute.core.exceptions import LLMError

settings = get_settings()


class LLMRouter:
    """Anthropic-first router. DeepSeek via Anthropic protocol → native tool_use."""

    def __init__(self) -> None:
        self.circuit_breakers: dict[str, dict[str, Any]] = {
            "anthropic": {"failures": 0, "open_until": 0, "failure_threshold": 5, "recovery_timeout": 60},
            "openai":    {"failures": 0, "open_until": 0, "failure_threshold": 5, "recovery_timeout": 60},
            "qwen":      {"failures": 0, "open_until": 0, "failure_threshold": 5, "recovery_timeout": 60},
        }
        self._openai_client = None
        self._anthropic_client = None

    # ══════════════════════════════════════════════════════════════
    #  Public API
    # ══════════════════════════════════════════════════════════════

    async def call(
        self, messages: list[dict[str, str]], model: str | None = None,
        temperature: float = 0.1, max_tokens: int = 1000, **kwargs: Any,
    ) -> str:
        """普通文本调用。OpenAI 用于文本（快），Anthropic 备用。"""
        # OpenAI first — 文本调用 DeepSeek 的 OpenAI 端点更快更稳定
        if not self._is_open("openai"):
            try:
                result = await self._openai_chat(messages, model, temperature, max_tokens)
                self._record_success("openai"); return result
            except Exception:
                self._record_failure("openai")
        if not self._is_open("anthropic"):
            try:
                result = await self._anthropic_chat(messages, model, temperature, max_tokens)
                self._record_success("anthropic"); return result
            except Exception:
                self._record_failure("anthropic")
        raise LLMError(message="所有LLM供应商均不可用", code="ALL_PROVIDERS_FAILED")

    async def call_with_function(
        self, messages: list[dict[str, str]], function_schema: dict[str, Any],
        model: str | None = None, temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Structured extraction via Anthropic native tool_use → text fallback."""
        fn_name = function_schema.get("name", "extract_data")
        fn_desc = function_schema.get("description", "")
        fn_params = function_schema.get("parameters", {})

        # Anthropic native tool_use (DeepSeek proxy now supports it)
        if not self._is_open("anthropic"):
            try:
                client = await self._get_anthropic_client()
                actual_model = model or settings.llm.anthropic_model_claude
                resp = await client.messages.create(
                    model=actual_model, messages=messages,
                    tools=[{"name": fn_name, "description": fn_desc, "input_schema": fn_params}],
                    temperature=temperature, max_tokens=2000,
                )
                self._record_success("anthropic")
                for block in resp.content:
                    if block.type == "tool_use":
                        return block.input if isinstance(block.input, dict) else json.loads(str(block.input))
                # No tool_use block → try text
                for block in resp.content:
                    if block.type == "text" and block.text:
                        parsed = self._parse_json_from_text(block.text)
                        if parsed and (parsed.get("intent_type") or parsed.get("confidence")):
                            return parsed
            except Exception:
                self._record_failure("anthropic")

        # Text fallback
        return await self._text_extraction_fallback(messages, function_schema)

    async def stream(
        self, messages: list[dict[str, str]], model: str | None = None,
        temperature: float = 0.1, max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """流式输出 (Anthropic → OpenAI)"""
        if not self._is_open("anthropic"):
            try:
                client = await self._get_anthropic_client()
                actual_model = model or settings.llm.anthropic_model_sonnet
                async with client.messages.stream(
                    model=actual_model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                ) as s:
                    async for text in s.text_stream:
                        if text: yield text
                self._record_success("anthropic"); return
            except Exception: self._record_failure("anthropic")
        if not self._is_open("openai"):
            try:
                client = await self._get_openai_client()
                actual_model = model or settings.llm.openai_model_default
                s = await client.chat.completions.create(
                    model=actual_model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens, stream=True,
                )
                async for chunk in s:
                    token = chunk.choices[0].delta.content or ""
                    if token: yield token
                self._record_success("openai"); return
            except Exception: self._record_failure("openai")
        raise LLMError(message="所有LLM供应商均不可用", code="STREAM_ALL_PROVIDERS_FAILED")

    # ══════════════════════════════════════════════════════════════
    #  Provider implementations
    # ══════════════════════════════════════════════════════════════

    async def _anthropic_chat(self, messages, model, temp, max_tok) -> str:
        client = await self._get_anthropic_client()
        actual = model or settings.llm.anthropic_model_claude
        resp = await client.messages.create(model=actual, messages=messages, temperature=temp, max_tokens=max_tok)
        return resp.content[0].text if resp.content else ""

    async def _openai_chat(self, messages, model, temp, max_tok) -> str:
        client = await self._get_openai_client()
        actual = model or settings.llm.openai_model_default
        resp = await client.chat.completions.create(model=actual, messages=messages, temperature=temp, max_tokens=max_tok)
        return resp.choices[0].message.content or ""

    # ══════════════════════════════════════════════════════════════
    #  Clients (lazy init)
    # ══════════════════════════════════════════════════════════════

    async def _get_anthropic_client(self):
        from anthropic import AsyncAnthropic
        if self._anthropic_client is None:
            base = settings.llm.anthropic_base_url
            if "api.anthropic.com" in base:
                base = "https://api.anthropic.com"
            self._anthropic_client = AsyncAnthropic(
                api_key=settings.llm.anthropic_api_key or "sk-placeholder",
                base_url=base,
            )
        return self._anthropic_client

    async def _get_openai_client(self) -> openai.AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = openai.AsyncOpenAI(
                api_key=settings.llm.openai_api_key or "sk-placeholder",
                base_url=settings.llm.openai_base_url or "https://api.openai.com/v1",
            )
        return self._openai_client

    # ══════════════════════════════════════════════════════════════
    #  Circuit breaker
    # ══════════════════════════════════════════════════════════════

    def _is_open(self, name: str) -> bool:
        return self.circuit_breakers.get(name, {}).get("open_until", 0) > time.time()

    def _record_success(self, name: str) -> None:
        self.circuit_breakers[name]["failures"] = 0
        self.circuit_breakers[name]["open_until"] = 0

    def _record_failure(self, name: str) -> None:
        s = self.circuit_breakers[name]; s["failures"] += 1
        if s["failures"] >= s["failure_threshold"]:
            s["open_until"] = time.time() + s["recovery_timeout"]

    # ══════════════════════════════════════════════════════════════
    #  Text extraction fallback
    # ══════════════════════════════════════════════════════════════

    def _parse_json_from_text(self, text: str) -> dict:
        t = (text or "").strip()
        for fence in ("```json", "```"):
            if fence in t:
                s = t.find(fence) + len(fence); e = t.find("```", s)
                if e > s: t = t[s:e].strip(); break
        bs = t.find("{"); be = t.rfind("}")
        if bs >= 0 and be > bs: t = t[bs:be + 1]
        try: return json.loads(t)
        except (json.JSONDecodeError, ValueError): return {}

    async def _text_extraction_fallback(self, messages, schema) -> dict:
        user_content = ""
        if messages:
            last = messages[-1]; user_content = (last.get("content", "") or "")[:500]
        prompt = f"""你是一个出行意图解析助手。请从用户输入中提取结构化出行信息，以 JSON 格式输出。

用户输入：「{user_content}」

请输出以下 JSON（严格按照此结构，不要输出任何解释文字）：
{{
  "intent_type": "tour|food_tour|city_walk|business|date|family|nature|culture",
  "confidence": 0.0-1.0,
  "spatial": {{"city": "城市名", "region": "区域或null", "anchor_poi": "锚点POI或null", "radius_km": null}},
  "temporal": {{"date": "YYYY-MM-DD", "start_time": "HH:MM", "end_time": "HH:MM", "duration_hours": 8.0, "flexibility": "flexible"}},
  "party": {{"size": 1, "composition": ["elder","child","adult"], "child_ages": [], "special_needs": []}},
  "preferences": {{"must_have": [], "nice_to_have": [], "avoid": [], "themes": [], "cuisine_types": [], "poi_style": null}},
  "budget": {{"per_person": 金额数字或null, "level": "budget|mid|premium|luxury或null"}},
  "ambiguity_flags": [],
  "inferred_fields": []
}}

重要规则：
1. spatial.city 必须从输入中提取（杭州、北京等）
2. temporal.date 必须是绝对日期（YYYY-MM-DD），start_time/end_time 不能为 null，默认填 "09:00"/"18:00"
3. 如果提到"父母"/"爸妈"/"老人"，party.composition 包含 "elder"，party.size 至少为2
4. 如果提到预算金额，填入 budget.per_person
5. 如果提到菜系，填入 preferences.cuisine_types
6. 意图类型根据输入合理推断（带父母→family，约会→date，商务→business）
7. 只输出 JSON，不要输出 markdown 代码块或其他文字"""
        result = await self.call(messages=[{"role": "user", "content": prompt}], temperature=0.1, max_tokens=2000)
        return self._parse_json_from_text(result)
