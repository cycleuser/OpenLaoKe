"""Multi-provider API client supporting Anthropic, OpenAI, and local models."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    MessageRole,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
)
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType


@dataclass
class ModelPricing:
    """Pricing information for a model (per million tokens)."""
    input_price: float = 3.0
    output_price: float = 15.0
    cache_read_price: float = 0.30
    cache_creation_price: float = 3.75


DEFAULT_PRICING = ModelPricing(3.0, 15.0, 0.30, 3.75)

MODEL_PRICES: dict[str, ModelPricing] = {
    "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-opus-4-20250514": ModelPricing(15.0, 75.0, 1.50, 18.75),
    "claude-3-5-sonnet-20241022": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-3-5-haiku-20241022": ModelPricing(0.80, 4.0, 0.08, 1.0),
    "gpt-4o": ModelPricing(2.5, 10.0, 0.0, 0.0),
    "gpt-4o-mini": ModelPricing(0.15, 0.60, 0.0, 0.0),
    "gpt-4-turbo": ModelPricing(10.0, 30.0, 0.0, 0.0),
    "o1-preview": ModelPricing(15.0, 60.0, 0.0, 0.0),
    "o1-mini": ModelPricing(3.0, 12.0, 0.0, 0.0),
    "MiniMax-M2.7-highspeed": ModelPricing(0.2, 0.6, 0.0, 0.0),
    "MiniMax-M2.7": ModelPricing(0.5, 1.5, 0.0, 0.0),
    "MiniMax-M2.5-highspeed": ModelPricing(0.1, 0.3, 0.0, 0.0),
    "MiniMax-M2.5": ModelPricing(0.3, 0.9, 0.0, 0.0),
    "qwen3.5-plus": ModelPricing(0.4, 1.2, 0.0, 0.0),
    "qwen3-max-2026-01-23": ModelPricing(2.0, 6.0, 0.0, 0.0),
    "glm-5": ModelPricing(0.1, 0.3, 0.0, 0.0),
    "glm-4.7": ModelPricing(0.2, 0.6, 0.0, 0.0),
}


class MultiProviderClient:
    """HTTP client supporting multiple LLM providers."""

    def __init__(self, config: MultiProviderConfig, proxy: str | None = None) -> None:
        self.config = config
        self._proxy = proxy
        self._client: httpx.AsyncClient | None = None
        self._timeout = 300.0

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            proxy = self._proxy
            if proxy is None or proxy == "":
                proxy = None
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=30.0),
                limits=limits,
                proxy=proxy,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_api_key(self, provider: ProviderConfig) -> str:
        env_key = ""
        if provider.provider_type == ProviderType.ANTHROPIC:
            env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        elif provider.provider_type == ProviderType.OPENAI:
            env_key = os.environ.get("OPENAI_API_KEY", "")
        elif provider.provider_type == ProviderType.MINIMAX:
            env_key = os.environ.get("MINIMAX_API_KEY", "")
        elif provider.provider_type == ProviderType.ALIYUN_CODING_PLAN:
            env_key = os.environ.get("ALIYUN_API_KEY", "")
        elif provider.provider_type == ProviderType.OPENAI_COMPATIBLE:
            env_key = os.environ.get("OPENAI_API_KEY", "none")

        return provider.api_key or env_key

    def _get_base_url(self, provider: ProviderConfig) -> str:
        env_url = ""
        if provider.provider_type == ProviderType.ANTHROPIC:
            env_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        elif provider.provider_type == ProviderType.OPENAI:
            env_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        elif provider.provider_type == ProviderType.MINIMAX:
            env_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
        elif provider.provider_type == ProviderType.ALIYUN_CODING_PLAN:
            env_url = os.environ.get("ALIYUN_BASE_URL", "https://coding.dashscope.aliyuncs.com/v1")
        elif provider.provider_type == ProviderType.OPENAI_COMPATIBLE:
            env_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        return provider.base_url or env_url

    def _build_headers(self, provider: ProviderConfig) -> dict[str, str]:
        api_key = self._get_api_key(provider)

        if provider.provider_type == ProviderType.ANTHROPIC:
            return {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        elif provider.is_local:
            return {
                "Content-Type": "application/json",
            }
        else:
            return {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

    def _build_anthropic_body(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
        thinking_budget: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if temperature != 1.0:
            body["temperature"] = temperature
        if tools:
            body["tools"] = tools
        if thinking_budget > 0:
            body["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        return body

    def _build_openai_body(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if temperature != 1.0:
            body["temperature"] = temperature
        if tools:
            body["tools"] = self._convert_tools_to_openai_format(tools)
        return body

    def _convert_tools_to_openai_format(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert internal tool format to OpenAI API format."""
        result = []
        for tool in tools:
            # Check if already in OpenAI format
            if tool.get("type") == "function" and "function" in tool:
                result.append(tool)
            else:
                # Convert from internal format
                result.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                })
        return result

    def _convert_messages_for_provider(
        self,
        messages: list[dict[str, Any]],
        provider_type: ProviderType,
    ) -> list[dict[str, Any]]:
        if provider_type == ProviderType.ANTHROPIC:
            return self._convert_to_anthropic_format(messages)
        else:
            return self._convert_to_openai_format(messages)

    def _convert_to_anthropic_format(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                continue

            # Handle OpenAI native tool format
            if role == "tool":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content,
                    }],
                })
            # Handle our internal tool_result format
            elif role == "tool_result":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_use_id", ""),
                        "content": content,
                    }],
                })
            # Handle tool_use (legacy)
            elif role == "tool_use":
                result.append({
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "id": msg.get("id", ""),
                        "name": msg.get("name", ""),
                        "input": msg.get("input", {}),
                    }],
                })
            # Handle assistant with tool_calls (OpenAI native)
            elif role == "assistant" and "tool_calls" in msg:
                content_blocks = []
                if msg.get("content"):
                    content_blocks.append({"type": "text", "text": msg["content"]})
                for tc in msg.get("tool_calls", []):
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": args,
                    })
                result.append({"role": "assistant", "content": content_blocks})
            else:
                result.append({"role": role, "content": content})

        return result

    def _convert_to_openai_format(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle OpenAI native tool format
            if role == "tool":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": content,
                })
            # Handle our internal tool_result format
            elif role == "tool_result":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_use_id", ""),
                    "content": content,
                })
            # Handle tool_use (legacy)
            elif role == "tool_use":
                if not result or result[-1].get("role") != "assistant":
                    result.append({"role": "assistant", "content": "", "tool_calls": []})
                result[-1].setdefault("tool_calls", []).append({
                    "id": msg.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": msg.get("name", ""),
                        "arguments": json.dumps(msg.get("input", {})),
                    },
                })
            # Handle assistant with tool_calls (OpenAI native)
            elif role == "assistant" and "tool_calls" in msg:
                result.append(msg)
            else:
                result.append({"role": role, "content": content})

        return result

    def _parse_anthropic_response(self, data: dict[str, Any]) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_uses.append(ToolUseBlock(
                    id=block["id"],
                    name=block["name"],
                    input=block["input"],
                ))

        usage = self._parse_token_usage(data.get("usage", {}))
        cost = self._calculate_cost(data.get("usage", {}), data.get("model", ""))

        return AssistantMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_uses=tool_uses,
            stop_reason=data.get("stop_reason"),
        ), usage, cost

    def _parse_openai_response(self, data: dict[str, Any]) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []

        choices = data.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "") or ""

            for tool_call in message.get("tool_calls", []):
                func = tool_call.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_uses.append(ToolUseBlock(
                    id=tool_call.get("id", ""),
                    name=func.get("name", ""),
                    input=args,
                ))

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )
        cost = self._calculate_cost(usage_data, data.get("model", ""))

        return AssistantMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_uses=tool_uses,
            stop_reason=choices[0].get("finish_reason") if choices else None,
        ), usage, cost

    def _parse_token_usage(self, usage: dict[str, int]) -> TokenUsage:
        return TokenUsage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
        )

    def _calculate_cost(self, usage: dict[str, int], model: str) -> CostInfo:
        pricing = MODEL_PRICES.get(model, DEFAULT_PRICING)
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))

        return CostInfo(
            input_cost=input_tokens / 1_000_000 * pricing.input_price,
            output_cost=output_tokens / 1_000_000 * pricing.output_price,
        )

    async def send_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 1.0,
        thinking_budget: int = 0,
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        provider = self.config.get_active_provider()
        if not provider:
            raise ValueError("No active provider configured")

        model = model or self.config.get_active_model()
        base_url = self._get_base_url(provider)
        client = self._get_client()
        headers = self._build_headers(provider)

        converted_messages = self._convert_messages_for_provider(
            messages, provider.provider_type
        )

        if provider.provider_type == ProviderType.ANTHROPIC:
            endpoint = f"{base_url}/v1/messages"
            body = self._build_anthropic_body(
                model, converted_messages, tools, max_tokens, temperature, thinking_budget
            )
            body["system"] = system_prompt
        else:
            endpoint = f"{base_url}/chat/completions"
            body = self._build_openai_body(
                model, converted_messages, tools, max_tokens, temperature
            )
            body["messages"] = [
                {"role": "system", "content": system_prompt},
                *body["messages"],
            ]

        response = await client.post(endpoint, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

        if provider.provider_type == ProviderType.ANTHROPIC:
            return self._parse_anthropic_response(data)
        else:
            return self._parse_openai_response(data)

    async def stream_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 1.0,
        thinking_budget: int = 0,
    ) -> AsyncIterator[tuple[str, TokenUsage | None, CostInfo | None]]:
        provider = self.config.get_active_provider()
        if not provider:
            raise ValueError("No active provider configured")

        model = model or self.config.get_active_model()
        base_url = self._get_base_url(provider)
        client = self._get_client()
        headers = self._build_headers(provider)

        converted_messages = self._convert_messages_for_provider(
            messages, provider.provider_type
        )

        if provider.provider_type == ProviderType.ANTHROPIC:
            endpoint = f"{base_url}/v1/messages"
            body = self._build_anthropic_body(
                model, converted_messages, tools, max_tokens, temperature, thinking_budget
            )
            body["system"] = system_prompt
            body["stream"] = True
        else:
            endpoint = f"{base_url}/chat/completions"
            body = self._build_openai_body(
                model, converted_messages, tools, max_tokens, temperature
            )
            body["messages"] = [
                {"role": "system", "content": system_prompt},
                *body["messages"],
            ]
            body["stream"] = True

        async with client.stream("POST", endpoint, headers=headers, json=body) as response:
            response.raise_for_status()
            content = ""
            final_usage = None
            final_cost = None

            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if provider.provider_type == ProviderType.ANTHROPIC:
                        text, usage, cost = self._parse_anthropic_stream_event(event)
                    else:
                        text, usage, cost = self._parse_openai_stream_event(event)

                    if text:
                        content += text
                        yield text, None, None
                    if usage:
                        final_usage = usage
                        final_cost = cost

            yield "", final_usage, final_cost

    def _parse_anthropic_stream_event(self, event: dict[str, Any]) -> tuple[str, TokenUsage | None, CostInfo | None]:
        event_type = event.get("type", "")
        text = ""
        usage = None
        cost = None

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
        elif event_type == "message_delta":
            usage_data = event.get("usage", {})
            if usage_data:
                usage = TokenUsage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                )
                cost = CostInfo(
                    input_cost=usage.input_tokens / 1_000_000 * 3.0,
                    output_cost=usage.output_tokens / 1_000_000 * 15.0,
                )

        return text, usage, cost

    def _parse_openai_stream_event(self, event: dict[str, Any]) -> tuple[str, TokenUsage | None, CostInfo | None]:
        text = ""
        usage = None
        cost = None

        choices = event.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            text = delta.get("content", "") or ""

        usage_data = event.get("usage", {})
        if usage_data:
            usage = TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )
            cost = CostInfo(
                input_cost=usage.input_tokens / 1_000_000 * 2.5,
                output_cost=usage.output_tokens / 1_000_000 * 10.0,
            )

        return text, usage, cost