"""
LLM Router - 多供应商LLM路由器

支持OpenAI、Anthropic、Qwen多供应商切换和熔断
"""

import json
import time
from typing import Any

import openai
from anthropic import AsyncAnthropic

from smartroute.core.config import get_settings
from smartroute.core.exceptions import LLMError


settings = get_settings()


PROVIDER_CONFIGS = [
    {"name": "openai", "priority": 1, "models": {"default": settings.llm.openai_model_default}},
    {"name": "anthropic", "priority": 2, "models": {"default": settings.llm.anthropic_model_claude}},
    {"name": "qwen", "priority": 3, "models": {"default": settings.llm.qwen_model}},
]


class LLMRouter:
    """
    LLM供应商路由器
    
    支持：
    - 多供应商按优先级切换
    - 熔断器保护
    - Function Calling
    """

    def __init__(self) -> None:
        self.providers = PROVIDER_CONFIGS
        self.circuit_breakers: dict[str, dict[str, Any]] = {}
        self._openai_client = None
        self._anthropic_client = None

        for provider in self.providers:
            self.circuit_breakers[provider["name"]] = {
                "failures": 0,
                "open_until": 0,
                "failure_threshold": 5,
                "recovery_timeout": 60,
            }

    async def call(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        调用LLM
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度
            max_tokens: 最大Token
            **kwargs: 其他参数
            
        Returns:
            响应文本
        """
        for provider in sorted(self.providers, key=lambda x: x["priority"]):
            if self._is_circuit_open(provider["name"]):
                continue

            try:
                result = await self._call_provider(
                    provider=provider,
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                self._record_success(provider["name"])
                return result

            except Exception as e:
                self._record_failure(provider["name"])
                continue

        raise LLMError(
            message="所有LLM供应商均不可用",
            code="ALL_PROVIDERS_FAILED",
        )

    async def call_with_function(
        self,
        messages: list[dict[str, str]],
        function_schema: dict[str, Any],
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """
        Function Calling
        
        Args:
            messages: 消息列表
            function_schema: Function Schema
            model: 模型名称
            temperature: 温度
            
        Returns:
            Function返回的JSON
        """
        # OpenAI支持Function Calling
        if self._is_circuit_open("openai"):
            # 降级使用文本解析
            return await self._fallback_function_call(messages, function_schema)

        try:
            client = await self._get_openai_client()

            response = await client.chat.completions.create(
                model=model or settings.llm.openai_model_default,
                messages=messages,
                tools=[{
                    "type": "function",
                    "function": function_schema,
                }],
                tool_choice={"type": "function", "function": {"name": function_schema["name"]}},
                temperature=temperature,
                max_tokens=1000,
            )

            tool_call = response.choices[0].message.tool_calls[0]
            raw_json = tool_call.function.arguments

            self._record_success("openai")
            return json.loads(raw_json)

        except Exception as e:
            self._record_failure("openai")
            return await self._fallback_function_call(messages, function_schema)

    async def _call_provider(
        self,
        provider: dict[str, Any],
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> str:
        """
        调用特定供应商
        """
        provider_name = provider["name"]
        actual_model = model or provider["models"].get("default", "gpt-4o")

        if provider_name == "openai":
            client = await self._get_openai_client()
            response = await client.chat.completions.create(
                model=actual_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        elif provider_name == "anthropic":
            client = await self._get_anthropic_client()
            response = await client.messages.create(
                model=actual_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.content[0].text if response.content else ""

        elif provider_name == "qwen":
            # TODO: 实现Qwen调用
            raise NotImplementedError("Qwen provider not implemented")

        raise ValueError(f"Unknown provider: {provider_name}")

    async def _get_openai_client(self) -> openai.AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = openai.AsyncOpenAI(
                api_key=settings.llm.openai_api_key,
                base_url=settings.llm.openai_base_url,
            )
        return self._openai_client

    async def _get_anthropic_client(self) -> AsyncAnthropic:
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(
                api_key=settings.llm.anthropic_api_key,
            )
        return self._anthropic_client

    def _is_circuit_open(self, provider_name: str) -> bool:
        state = self.circuit_breakers.get(provider_name, {})
        return state.get("open_until", 0) > time.time()

    def _record_success(self, provider_name: str) -> None:
        state = self.circuit_breakers.get(provider_name, {})
        state["failures"] = 0
        state["open_until"] = 0

    def _record_failure(self, provider_name: str) -> None:
        state = self.circuit_breakers.get(provider_name, {})
        state["failures"] = state.get("failures", 0) + 1

        if state["failures"] >= state.get("failure_threshold", 5):
            state["open_until"] = time.time() + state.get("recovery_timeout", 60)

    async def _fallback_function_call(
        self,
        messages: list[dict[str, str]],
        function_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        降级：使用文本解析代替Function Calling
        """
        # 安全地序列化 schema，避免 surrogate 字符问题
        try:
            schema_str = json.dumps(
                function_schema['parameters'],
                ensure_ascii=False,
                indent=2
            )
        except UnicodeEncodeError:
            # 如果出现编码问题，使用 ensure_ascii=True
            schema_str = json.dumps(
                function_schema['parameters'],
                ensure_ascii=True,
                indent=2
            )

        # 安全获取消息内容
        user_content = ""
        if messages and len(messages) > 0:
            last_msg = messages[-1]
            user_content = last_msg.get('content', '')
            # 清理可能的 surrogate 字符
            user_content = user_content.encode('utf-8', errors='replace').decode('utf-8')

        prompt = f"""
请以JSON格式输出以下信息，严格按照给定的Schema：
{schema_str}

用户输入：{user_content}
"""
        result = await self.call(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {}
