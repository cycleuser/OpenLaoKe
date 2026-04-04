"""API client for Anthropic-compatible LLM providers."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    MessageRole,
    SystemMessage,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
)


@dataclass
class ModelPricing:
    """Pricing information for a model (per million tokens)."""
    input_price: float = 3.0
    output_price: float = 15.0
    cache_read_price: float = 0.30
    cache_creation_price: float = 3.75


MODEL_PRICES: dict[str, ModelPricing] = {
    "claude-sonnet-4-20250514": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-opus-4-20250514": ModelPricing(15.0, 75.0, 1.50, 18.75),
    "claude-3-5-sonnet-20241022": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-3-5-haiku-20241022": ModelPricing(0.80, 4.0, 0.08, 1.0),
    "claude-3-haiku-20240307": ModelPricing(0.25, 1.25, 0.025, 0.30),
}


@dataclass
class APIConfig:
    """Configuration for the API client."""
    api_key: str = ""
    base_url: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    temperature: float = 1.0
    top_p: float = 1.0
    thinking_budget: int = 0
    timeout: float = 300.0
    max_retries: int = 3
    proxy_url: str | None = None

    @classmethod
    def from_env(cls) -> APIConfig:
        return cls(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            model=os.environ.get("OPENLAOKE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=int(os.environ.get("OPENLAOKE_MAX_TOKENS", "8192")),
            thinking_budget=int(os.environ.get("OPENLAOKE_THINKING_BUDGET", "0")),
            timeout=float(os.environ.get("OPENLAOKE_TIMEOUT", "300")),
            proxy_url=os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"),
        )


class APIClient:
    """HTTP client for Anthropic-compatible API."""

    def __init__(self, config: APIConfig | None = None) -> None:
        self.config = config or APIConfig.from_env()
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout, connect=30.0),
                limits=limits,
                proxy=self.config.proxy_url,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_messages(self, system_prompt: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                continue

            if role == "tool_result":
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_use_id", ""),
                            "content": content,
                        }
                    ],
                })
            elif role == "tool_use":
                result.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": msg.get("id", ""),
                            "name": msg.get("name", ""),
                            "input": msg.get("input", {}),
                        }
                    ],
                })
            else:
                result.append({"role": role, "content": content})

        return result

    def _calculate_cost(self, usage: dict[str, int]) -> CostInfo:
        pricing = MODEL_PRICES.get(self.config.model, ModelPricing())
        return CostInfo(
            input_cost=usage.get("input_tokens", 0) / 1_000_000 * pricing.input_price,
            output_cost=usage.get("output_tokens", 0) / 1_000_000 * pricing.output_price,
            cache_read_cost=usage.get("cache_read_input_tokens", 0) / 1_000_000 * pricing.cache_read_price,
            cache_creation_cost=usage.get("cache_creation_input_tokens", 0) / 1_000_000 * pricing.cache_creation_price,
        )

    def _parse_token_usage(self, usage: dict[str, int]) -> TokenUsage:
        return TokenUsage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
        )

    async def send_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AssistantMessage:
        """Send a single message request and get the response."""
        client = self._get_client()
        body: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "system": system_prompt,
            "messages": self._build_messages(system_prompt, messages),
        }

        if tools:
            body["tools"] = tools

        if self.config.thinking_budget > 0:
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget,
            }

        response = await client.post(
            "/v1/messages",
            headers=self._build_headers(),
            json=body,
        )
        response.raise_for_status()
        data = response.json()

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
        cost = self._calculate_cost(data.get("usage", {}))

        return AssistantMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_uses=tool_uses,
            stop_reason=data.get("stop_reason"),
        ), usage, cost

    async def stream_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[tuple[str, TokenUsage | None, CostInfo | None]]:
        """Stream a message response, yielding text chunks."""
        client = self._get_client()
        body: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "system": system_prompt,
            "messages": self._build_messages(system_prompt, messages),
            "stream": True,
        }

        if tools:
            body["tools"] = tools

        if self.config.thinking_budget > 0:
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget,
            }

        async with client.stream(
            "POST",
            "/v1/messages",
            headers=self._build_headers(),
            json=body,
        ) as response:
            response.raise_for_status()
            content = ""
            tool_uses = []
            final_usage = None
            final_cost = None

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")

                if event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        tool_uses.append(ToolUseBlock(
                            id=block["id"],
                            name=block["name"],
                            input={},
                        ))

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        content += text
                        yield text, None, None
                    elif delta.get("type") == "input_json_delta":
                        partial_json = delta.get("partial_json", "")
                        if tool_uses:
                            try:
                                tool_uses[-1].input = json.loads(
                                    json.dumps(tool_uses[-1].input)[:-1] + partial_json + "}"
                                )
                            except json.JSONDecodeError:
                                pass

                elif event_type == "message_delta":
                    usage_data = event.get("usage", {})
                    if usage_data:
                        final_usage = self._parse_token_usage(usage_data)
                        final_cost = self._calculate_cost(usage_data)

                elif event_type == "message_stop":
                    pass

            yield "", final_usage, final_cost
