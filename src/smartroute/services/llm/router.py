"""
LLM Router - OpenAI-first multi-provider router with circuit breakers.
Primary: OpenAI SDK → text completion + function calling.
Fallback: Anthropic SDK → native tool_use.
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
    """OpenAI-first router with Anthropic fallback."""

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
        """普通文本调用。Anthropic 优先，OpenAI fallback。"""
        print(f"[Call] anthropic circuit breaker: {self._is_open('anthropic')}")

        if not self._is_open("anthropic"):
            try:
                print("[Call] 尝试Anthropic...")
                result = await self._anthropic_chat(messages, model, temperature, max_tokens, **kwargs)
                print(f"[Call] Anthropic返回: {result[:100] if result else 'EMPTY'}...")
                self._record_success("anthropic")
                return result
            except Exception as e:
                print(f"[Call] Anthropic失败: {e}")
                self._record_failure("anthropic")

        if not self._is_open("openai"):
            try:
                print("[Call] Fallback OpenAI...")
                result = await self._openai_chat(messages, model, temperature, max_tokens, **kwargs)
                print(f"[Call] OpenAI返回: {result[:100] if result else 'EMPTY'}...")
                self._record_success("openai")
                return result
            except Exception as e:
                print(f"[Call] OpenAI失败: {e}")
                self._record_failure("openai")

        raise LLMError(message="LLM调用失败", code="LLM_CALL_FAILED")

    async def call_with_function(
        self, messages: list[dict[str, str]], function_schema: dict[str, Any],
        model: str | None = None, temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Structured extraction: Anthropic tool_use → OpenAI function calling → text fallback."""
        fn_name = function_schema.get("name", "extract_data")

        # Anthropic tool_use first
        if not self._is_open("anthropic"):
            try:
                client = await self._get_anthropic_client()
                actual_model = model or settings.llm.anthropic_model_claude
                anthropic_tool = {
                    "name": fn_name,
                    "description": function_schema.get("description", ""),
                    "input_schema": function_schema.get("parameters", {})
                }
                resp = await client.messages.create(
                    model=actual_model, messages=messages,
                    tools=[anthropic_tool],
                    temperature=temperature, max_tokens=2000,
                    thinking={"type": "disabled"},
                )
                for block in resp.content:
                    if block.type == "tool_use":
                        self._record_success("anthropic")
                        return block.input
                return await self._fallback_function_call(messages, function_schema)
            except Exception as e:
                print(f"[call_with_function] Anthropic失败: {e}")
                self._record_failure("anthropic")

        # OpenAI function calling fallback
        if not self._is_open("openai"):
            try:
                client = await self._get_openai_client()
                actual_model = model or settings.llm.openai_model_default
                resp = await client.chat.completions.create(
                    model=actual_model, messages=messages,
                    tools=[{"type": "function", "function": function_schema}],
                    temperature=temperature, max_tokens=2000,
                )
                tool_calls = resp.choices[0].message.tool_calls
                if tool_calls:
                    self._record_success("openai")
                    args = tool_calls[0].function.arguments
                    return json.loads(args) if isinstance(args, str) else args
                return await self._fallback_function_call(messages, function_schema)
            except Exception as e:
                print(f"[call_with_function] OpenAI失败: {e}")
                self._record_failure("openai")

        return await self._fallback_function_call(messages, function_schema)

    async def stream(
        self, messages: list[dict[str, str]], model: str | None = None,
        temperature: float = 0.1, max_tokens: int = 1500,
    ) -> AsyncGenerator[str, None]:
        """流式输出 - Anthropic 优先，OpenAI fallback"""
        if not self._is_open("anthropic"):
            try:
                client = await self._get_anthropic_client()
                actual_model = model or settings.llm.anthropic_model_claude
                async with client.messages.stream(
                    model=actual_model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                    thinking={"type": "disabled"},
                ) as stream:
                    async for text in stream.text_stream:
                        yield text
                self._record_success("anthropic")
                return
            except Exception as e:
                print(f"[Stream] Anthropic失败: {e}")
                import traceback
                traceback.print_exc()
                self._record_failure("anthropic")

        if not self._is_open("openai"):
            try:
                client = await self._get_openai_client()
                actual_model = model or settings.llm.openai_model_default
                s = await client.chat.completions.create(
                    model=actual_model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens, stream=True,
                )
                async for chunk in s:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            yield delta.content
                self._record_success("openai")
                return
            except Exception as e:
                print(f"[Stream] OpenAI失败: {e}")
                import traceback
                traceback.print_exc()
                self._record_failure("openai")

        raise LLMError(message="LLM流式调用失败", code="STREAM_FAILED")

    # ══════════════════════════════════════════════════════════════
    #  Provider implementations
    # ══════════════════════════════════════════════════════════════

    async def _anthropic_chat(self, messages, model, temp, max_tok) -> str:
        client = await self._get_anthropic_client()
        actual = model or settings.llm.anthropic_model_claude
        resp = await client.messages.create(
            model=actual, messages=messages,
            temperature=temp, max_tokens=max_tok,
            thinking={"type": "disabled"},
        )
        for block in resp.content:
            if block.type == "text":
                return block.text
        return ""

    async def _openai_chat(self, messages, model, temp, max_tok, **kwargs) -> str:
        client = await self._get_openai_client()
        actual = model or settings.llm.openai_model_default
        print(f"[OpenAI] 调用模型: {actual}")
        resp = await client.chat.completions.create(
            model=actual, messages=messages,
            temperature=temp, max_tokens=max_tok, **kwargs,
        )
        print(f"[OpenAI] 响应: choices数量={len(resp.choices)}, finish_reason={resp.choices[0].finish_reason if resp.choices else 'N/A'}")
        if resp.choices:
            msg = resp.choices[0].message
            print(f"[OpenAI] message.content={repr(msg.content)[:100] if msg.content else 'None'}")
            print(f"[OpenAI] message.tool_calls={msg.tool_calls}")
        content = resp.choices[0].message.content or ""
        print(f"[OpenAI] 最终返回内容长度: {len(content)}")
        return content

    # ══════════════════════════════════════════════════════════════
    #  Clients (lazy init)
    # ══════════════════════════════════════════════════════════════

    async def _get_anthropic_client(self):
        from anthropic import AsyncAnthropic
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(
                api_key=settings.llm.anthropic_api_key or "sk-placeholder",
                base_url=settings.llm.anthropic_base_url,
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
    #  Text extraction fallback (原始实现)
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

    async def _fallback_function_call(
        self,
        messages: list[dict[str, str]],
        function_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """降级：使用文本解析代替Function Calling"""
        print("[Fallback] 进入fallback...")

        # 安全获取消息内容
        user_content = ""
        if messages and len(messages) > 0:
            last_msg = messages[-1]
            user_content = last_msg.get('content', '')
            user_content = user_content.encode('utf-8', errors='replace').decode('utf-8')

        # 简化prompt，只要求核心字段（glm-5对复杂prompt处理不好）
        fn_name = function_schema.get("name", "extract_data")
        if fn_name == "extract_intent":
            # 意图抽取的简化prompt
            prompt = f"""
请从以下用户输入中提取关键信息，以JSON格式返回：

用户输入：{user_content}

请返回JSON，包含以下字段：
- intent_type: 意图类型(tour/food_tour/city_walk/business/date/family/nature/culture)
- city: 城市
- anchor_poi: 锚点地点
- date: 日期(YYYY-MM-DD格式)
- start_time: 开始时间(HH:MM格式)
- end_time: 结束时间(HH:MM格式)
- party_size: 出行人数
- transport_mode: 交通方式(walk/bike/car/taxi/public)，注意识别"开车"、"自驾"等关键词
- budget_per_person: 人均预算
- confidence: 置信度(0-1)

示例返回格式：
{{"intent_type": "family", "city": "杭州", "anchor_poi": "西湖"}}
"""
        else:
            # 其他场景的通用prompt
            schema_str = json.dumps(function_schema.get('parameters', {}), ensure_ascii=False, indent=2)
            prompt = f"""
请以JSON格式输出：
{schema_str}

用户输入：{user_content}
"""

        # 调用LLM（增加max_tokens）
        result = await self._openai_chat(
            [{"role": "user", "content": prompt}],
            None, 0.1, 4000  # 增加max_tokens到4000
        )

        print(f"[Fallback] LLM返回: {result[:200] if result else 'EMPTY'}")

        # 解析JSON
        parsed = self._parse_json_from_text(result)

        # 如果解析成功但字段不完整，补充默认值
        if parsed and fn_name == "extract_intent":
            parsed = self._fill_intent_defaults(parsed)

        print(f"[Fallback] 解析结果: {parsed}")
        return parsed

    def _fill_intent_defaults(self, parsed: dict) -> dict:
        """补充Intent字段的默认结构"""
        # 处理 start_time 和 end_time 为 None 的情况
        start_time = parsed.get("start_time") or "09:00"
        end_time = parsed.get("end_time") or "18:00"

        # 构建完整的Intent结构
        result = {
            "intent_type": parsed.get("intent_type", "tour"),
            "confidence": parsed.get("confidence", 0.5),
            "spatial": {
                "city": parsed.get("city", "未知"),
                "anchor_poi": parsed.get("anchor_poi"),
                "radius_km": 5.0,
            },
            "temporal": {
                "date": parsed.get("date", "2026-06-06"),
                "start_time": start_time,
                "end_time": end_time,
                "duration_hours": 8.0,
            },
            "party": {
                "size": parsed.get("party_size", 1),
            },
            "budget": {
                "per_person": parsed.get("budget_per_person"),
            },
            "transport": {
                "primary_mode": parsed.get("transport_mode", "walk"),
            },
            "preferences": {},
            "poi_schedule": [],
        }
        return result