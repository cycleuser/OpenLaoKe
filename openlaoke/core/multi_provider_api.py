"""Multi-provider API client supporting Anthropic, OpenAI, and local models."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from openlaoke.core.builtin_model_provider import BuiltinModelProvider
from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    MessageRole,
    StreamChunk,
    StreamEventType,
    TokenUsage,
    ToolUseBlock,
)
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)


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
    "gemini-2.0-flash": ModelPricing(0.1, 0.4, 0.0, 0.0),
    "gemini-2.0-pro": ModelPricing(1.25, 5.0, 0.0, 0.0),
    "gemini-1.5-flash": ModelPricing(0.075, 0.3, 0.0, 0.0),
    "gemini-1.5-pro": ModelPricing(1.25, 5.0, 0.0, 0.0),
    "grok-2-latest": ModelPricing(2.0, 10.0, 0.0, 0.0),
    "grok-2-1212": ModelPricing(2.0, 10.0, 0.0, 0.0),
    "grok-beta": ModelPricing(5.0, 15.0, 0.0, 0.0),
    "mistral-large-latest": ModelPricing(2.0, 6.0, 0.0, 0.0),
    "mistral-small-latest": ModelPricing(0.2, 0.6, 0.0, 0.0),
    "codestral-latest": ModelPricing(0.2, 0.6, 0.0, 0.0),
    "open-mistral-nemo": ModelPricing(0.03, 0.06, 0.0, 0.0),
    "llama-3.3-70b-versatile": ModelPricing(0.59, 0.79, 0.0, 0.0),
    "llama-3.1-8b-instant": ModelPricing(0.05, 0.08, 0.0, 0.0),
    "mixtral-8x7b-32768": ModelPricing(0.27, 0.27, 0.0, 0.0),
    "gemma2-9b-it": ModelPricing(0.2, 0.2, 0.0, 0.0),
    "command-r-plus": ModelPricing(3.0, 15.0, 0.0, 0.0),
    "command-r": ModelPricing(0.5, 1.5, 0.0, 0.0),
    "command": ModelPricing(1.0, 2.0, 0.0, 0.0),
    "command-light": ModelPricing(0.3, 0.6, 0.0, 0.0),
    "big-pickle": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "mimo-v2-flash-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "minimax-m2.1-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "mimo-v2-omni-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "qwen3.6-plus-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "grok-code": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "kimi-k2.5-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "glm-5-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "gpt-5-nano": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "nemotron-3-super-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "minimax-m2.5-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "trinity-large-preview-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "glm-4.7-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
    "mimo-v2-pro-free": ModelPricing(0.0, 0.0, 0.0, 0.0),
}


class MultiProviderClient:
    """HTTP client supporting multiple LLM providers."""

    def __init__(self, config: MultiProviderConfig, proxy: str | None = None) -> None:
        self.config = config
        self._proxy = proxy
        self._client: httpx.AsyncClient | None = None
        self._timeout = 300.0
        self._builtin_client: BuiltinModelProvider | None = None

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
        if self._builtin_client:
            self._builtin_client.unload()
            self._builtin_client = None

    async def _send_builtin_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        """Send message to built-in GGUF model."""
        if self._builtin_client is None:
            from openlaoke.core.local_model_manager import LocalModelManager

            manager = LocalModelManager()
            model_id = model or self.config.get_active_model()
            model_path = manager.get_model_path(model_id)

            if not model_path:
                raise ValueError(
                    f"Built-in model '{model_id}' not downloaded. "
                    f"Run: openlaoke model download {model_id}"
                )

            self._builtin_client = BuiltinModelProvider(
                model_path=model_path,
                n_ctx=self.config.local_n_ctx,
                max_tokens=min(max_tokens, 1024),
                temperature=self.config.local_temperature,
                repetition_penalty=self.config.local_repetition_penalty,
            )

        return await self._builtin_client.send_message(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=min(max_tokens, 1024),
            temperature=temperature,
        )

    async def _stream_builtin_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[tuple[str, TokenUsage | None, CostInfo | None]]:
        """Stream message from built-in GGUF model."""
        if self._builtin_client is None:
            from openlaoke.core.local_model_manager import LocalModelManager

            manager = LocalModelManager()
            model_id = model or self.config.get_active_model()
            model_path = manager.get_model_path(model_id)

            if not model_path:
                raise ValueError(
                    f"Built-in model '{model_id}' not downloaded. "
                    f"Run: openlaoke model download {model_id}"
                )

            self._builtin_client = BuiltinModelProvider(
                model_path=model_path,
                n_ctx=self.config.local_n_ctx,
                max_tokens=min(max_tokens, 1024),
                temperature=self.config.local_temperature,
                repetition_penalty=self.config.local_repetition_penalty,
            )

        async for chunk in self._builtin_client.stream_message(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=min(max_tokens, 1024),
            temperature=temperature,
        ):
            yield chunk

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
        elif provider.provider_type == ProviderType.AZURE_OPENAI:
            env_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        elif provider.provider_type == ProviderType.GOOGLE:
            env_key = os.environ.get("GOOGLE_API_KEY", "")
        elif provider.provider_type == ProviderType.GOOGLE_VERTEX:
            env_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        elif provider.provider_type == ProviderType.AWS_BEDROCK:
            env_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        elif provider.provider_type == ProviderType.XAI:
            env_key = os.environ.get("XAI_API_KEY", "")
        elif provider.provider_type == ProviderType.MISTRAL:
            env_key = os.environ.get("MISTRAL_API_KEY", "")
        elif provider.provider_type == ProviderType.GROQ:
            env_key = os.environ.get("GROQ_API_KEY", "")
        elif provider.provider_type == ProviderType.CEREBRAS:
            env_key = os.environ.get("CEREBRAS_API_KEY", "")
        elif provider.provider_type == ProviderType.COHERE:
            env_key = os.environ.get("COHERE_API_KEY", "")
        elif provider.provider_type == ProviderType.DEEPINFRA:
            env_key = os.environ.get("DEEPINFRA_API_KEY", "")
        elif provider.provider_type == ProviderType.TOGETHERAI:
            env_key = os.environ.get("TOGETHERAI_API_KEY", "")
        elif provider.provider_type == ProviderType.PERPLEXITY:
            env_key = os.environ.get("PERPLEXITY_API_KEY", "")
        elif provider.provider_type == ProviderType.OPENROUTER:
            env_key = os.environ.get("OPENROUTER_API_KEY", "")
        elif provider.provider_type == ProviderType.GITHUB_COPILOT:
            env_key = os.environ.get("GITHUB_TOKEN", "")
        elif provider.provider_type == ProviderType.OPENCODE:
            env_key = os.environ.get("OPENCODE_API_KEY", "")
        elif provider.provider_type == ProviderType.OPENAI_COMPATIBLE:
            env_key = os.environ.get("OPENAI_API_KEY", "")

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
        elif provider.provider_type == ProviderType.AZURE_OPENAI:
            env_url = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        elif provider.provider_type == ProviderType.GOOGLE:
            env_url = os.environ.get(
                "GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
            )
        elif provider.provider_type == ProviderType.GOOGLE_VERTEX:
            env_url = os.environ.get("GOOGLE_VERTEX_BASE_URL", "")
        elif provider.provider_type == ProviderType.AWS_BEDROCK:
            env_url = os.environ.get("AWS_BEDROCK_REGION", "")
        elif provider.provider_type == ProviderType.XAI:
            env_url = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
        elif provider.provider_type == ProviderType.MISTRAL:
            env_url = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        elif provider.provider_type == ProviderType.GROQ:
            env_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        elif provider.provider_type == ProviderType.CEREBRAS:
            env_url = os.environ.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
        elif provider.provider_type == ProviderType.COHERE:
            env_url = os.environ.get("COHERE_BASE_URL", "https://api.cohere.ai/v2")
        elif provider.provider_type == ProviderType.DEEPINFRA:
            env_url = os.environ.get("DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai")
        elif provider.provider_type == ProviderType.TOGETHERAI:
            env_url = os.environ.get("TOGETHERAI_BASE_URL", "https://api.together.xyz/v1")
        elif provider.provider_type == ProviderType.PERPLEXITY:
            env_url = os.environ.get("PERPLEXITY_BASE_URL", "https://api.perplexity.ai")
        elif provider.provider_type == ProviderType.OPENROUTER:
            env_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        elif provider.provider_type == ProviderType.GITHUB_COPILOT:
            env_url = os.environ.get("GITHUB_COPILOT_BASE_URL", "https://api.githubcopilot.com")
        elif provider.provider_type == ProviderType.OPENCODE:
            env_url = os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1")
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
        elif provider.provider_type == ProviderType.AZURE_OPENAI:
            return {
                "api-key": api_key,
                "Content-Type": "application/json",
            }
        elif provider.provider_type == ProviderType.GOOGLE:
            return {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            }
        elif (
            provider.provider_type == ProviderType.GOOGLE_VERTEX
            or provider.provider_type == ProviderType.COHERE
        ):
            return {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
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
                result.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("input_schema", {}),
                        },
                    }
                )
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
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": content,
                            }
                        ],
                    }
                )
            # Handle our internal tool_result format
            elif role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_use_id", ""),
                                "content": content,
                            }
                        ],
                    }
                )
            # Handle tool_use (legacy)
            elif role == "tool_use":
                result.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": msg.get("id", ""),
                                "name": msg.get("name", ""),
                                "input": msg.get("input", {}),
                            }
                        ],
                    }
                )
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
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args,
                        }
                    )
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
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "content": content,
                    }
                )
            # Handle our internal tool_result format
            elif role == "tool_result":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_use_id", ""),
                        "content": content,
                    }
                )
            # Handle tool_use (legacy)
            elif role == "tool_use":
                if not result or result[-1].get("role") != "assistant":
                    result.append({"role": "assistant", "content": "", "tool_calls": []})
                result[-1].setdefault("tool_calls", []).append(
                    {
                        "id": msg.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": msg.get("name", ""),
                            "arguments": json.dumps(msg.get("input", {})),
                        },
                    }
                )
            # Handle assistant with tool_calls (OpenAI native)
            elif role == "assistant" and "tool_calls" in msg:
                result.append(msg)
            else:
                result.append({"role": role, "content": content})

        return result

    def _parse_anthropic_response(
        self, data: dict[str, Any]
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_uses.append(
                    ToolUseBlock(
                        id=block["id"],
                        name=block["name"],
                        input=block["input"],
                    )
                )

        usage = self._parse_token_usage(data.get("usage", {}))
        cost = self._calculate_cost(data.get("usage", {}), data.get("model", ""))

        return (
            AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_uses=tool_uses,
                stop_reason=data.get("stop_reason"),
            ),
            usage,
            cost,
        )

    def _parse_openai_response(
        self, data: dict[str, Any]
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
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
                tool_uses.append(
                    ToolUseBlock(
                        id=tool_call.get("id", ""),
                        name=func.get("name", ""),
                        input=args,
                    )
                )

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )
        cost = self._calculate_cost(usage_data, data.get("model", ""))

        return (
            AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_uses=tool_uses,
                stop_reason=choices[0].get("finish_reason") if choices else None,
            ),
            usage,
            cost,
        )

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

        if provider.provider_type == ProviderType.LOCAL_BUILTIN:
            return await self._send_builtin_message(
                system_prompt, messages, tools, model, max_tokens, temperature
            )

        model = model or self.config.get_active_model()
        base_url = self._get_base_url(provider)
        client = self._get_client()
        headers = self._build_headers(provider)

        converted_messages = self._convert_messages_for_provider(messages, provider.provider_type)

        if provider.provider_type == ProviderType.ANTHROPIC:
            endpoint = f"{base_url}/v1/messages"
            body = self._build_anthropic_body(
                model, converted_messages, tools, max_tokens, temperature, thinking_budget
            )
            body["system"] = system_prompt
        elif provider.provider_type == ProviderType.AZURE_OPENAI:
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            endpoint = (
                f"{base_url}/openai/deployments/{model}/chat/completions?api-version={api_version}"
            )
            body = self._build_openai_body(
                model, converted_messages, tools, max_tokens, temperature
            )
            body["messages"] = [
                {"role": "system", "content": system_prompt},
                *body["messages"],
            ]
        elif provider.provider_type == ProviderType.GOOGLE:
            endpoint = f"{base_url}/models/{model}:generateContent"
            body = self._build_google_body(
                system_prompt, converted_messages, tools, max_tokens, temperature
            )
        elif provider.provider_type == ProviderType.GOOGLE_VERTEX:
            project_id = os.environ.get("GOOGLE_VERTEX_PROJECT", "")
            location = os.environ.get("GOOGLE_VERTEX_LOCATION", "us-central1")
            endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
            body = self._build_google_body(
                system_prompt, converted_messages, tools, max_tokens, temperature
            )
        elif provider.provider_type == ProviderType.AWS_BEDROCK:
            region = os.environ.get("AWS_REGION", "us-east-1")
            endpoint = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke"
            body = self._build_bedrock_body(
                system_prompt, converted_messages, tools, max_tokens, temperature
            )
        elif provider.provider_type == ProviderType.COHERE:
            endpoint = f"{base_url}/chat"
            body = self._build_cohere_body(
                model, system_prompt, converted_messages, tools, max_tokens, temperature
            )
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

        if response.status_code >= 400:
            error_detail = ""
            try:
                error_data = response.json()
                error_detail = f"\nError details: {error_data}"
            except Exception:
                error_detail = f"\nResponse text: {response.text[:500]}"

            logger.warning(
                "API Error: %s %s | Endpoint: %s | Model: %s | Messages: %d%s",
                response.status_code,
                response.reason_phrase,
                endpoint,
                body.get("model", "N/A"),
                len(body.get("messages", [])),
                error_detail,
            )

        response.raise_for_status()
        data = response.json()

        if provider.provider_type == ProviderType.ANTHROPIC:
            return self._parse_anthropic_response(data)
        elif provider.provider_type in (ProviderType.GOOGLE, ProviderType.GOOGLE_VERTEX):
            return self._parse_google_response(data, model)
        elif provider.provider_type == ProviderType.AWS_BEDROCK:
            return self._parse_bedrock_response(data, model)
        elif provider.provider_type == ProviderType.COHERE:
            return self._parse_cohere_response(data, model)
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
    ) -> AsyncIterator[StreamChunk]:
        provider = self.config.get_active_provider()
        if not provider:
            raise ValueError("No active provider configured")

        if provider.provider_type == ProviderType.LOCAL_BUILTIN:
            async for chunk in self._stream_builtin_message(
                system_prompt, messages, tools, model, max_tokens, temperature
            ):
                text, usage, cost = chunk
                yield StreamChunk(
                    event_type=StreamEventType.TEXT if text else StreamEventType.USAGE,
                    text=text,
                    usage=usage,
                    cost=cost,
                )
            return

        model = model or self.config.get_active_model()
        base_url = self._get_base_url(provider)
        client = self._get_client()
        headers = self._build_headers(provider)

        converted_messages = self._convert_messages_for_provider(messages, provider.provider_type)

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

        pending_tool_calls: dict[int, dict[str, Any]] = {}
        final_usage: TokenUsage | None = None
        final_cost: CostInfo | None = None

        async with client.stream("POST", endpoint, headers=headers, json=body) as response:
            response.raise_for_status()

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
                        for chunk in self._parse_anthropic_stream_events(
                            event, pending_tool_calls, model
                        ):
                            yield chunk
                    else:
                        for chunk in self._parse_openai_stream_events(
                            event, pending_tool_calls, model
                        ):
                            yield chunk

                    if chunk.event_type == StreamEventType.USAGE:
                        if chunk.usage:
                            final_usage = chunk.usage
                        if chunk.cost:
                            final_cost = chunk.cost

        for tc_idx, tc_data in pending_tool_calls.items():
            args_str = tc_data.get("arguments", "")
            try:
                json.loads(args_str)
            except json.JSONDecodeError:
                args_str = "{}"
            yield StreamChunk(
                event_type=StreamEventType.TOOL_CALL_START,
                tool_call_id=tc_data.get("id", f"call_{tc_idx}"),
                tool_call_name=tc_data.get("name", ""),
                tool_call_arguments=args_str,
            )

        if final_usage or final_cost:
            yield StreamChunk(event_type=StreamEventType.USAGE, usage=final_usage, cost=final_cost)
        else:
            yield StreamChunk(event_type=StreamEventType.USAGE)

    def _parse_anthropic_stream_events(
        self,
        event: dict[str, Any],
        pending_tool_calls: dict[int, dict[str, Any]],
        model: str,
    ) -> list[StreamChunk]:
        event_type = event.get("type", "")
        chunks: list[StreamChunk] = []

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    chunks.append(StreamChunk(event_type=StreamEventType.TEXT, text=text))
            elif delta.get("type") == "input_json_delta":
                partial = delta.get("partial_json", "")
                idx = event.get("index", 0)
                if idx in pending_tool_calls:
                    pending_tool_calls[idx]["arguments"] = (
                        pending_tool_calls[idx].get("arguments", "") + partial
                    )

        elif event_type == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                idx = event.get("index", 0)
                pending_tool_calls[idx] = {
                    "id": block.get("id", f"call_{idx}"),
                    "name": block.get("name", ""),
                    "arguments": "",
                }

        elif event_type == "message_delta":
            usage_data = event.get("usage", {})
            if usage_data:
                usage = TokenUsage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                )
                cost = self._calculate_cost(
                    {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
                    model,
                )
                chunks.append(StreamChunk(event_type=StreamEventType.USAGE, usage=usage, cost=cost))

        elif event_type == "message_stop":
            pending_tool_calls.clear()

        return chunks

    def _parse_openai_stream_events(
        self,
        event: dict[str, Any],
        pending_tool_calls: dict[int, dict[str, Any]],
        model: str,
    ) -> list[StreamChunk]:
        chunks: list[StreamChunk] = []
        text = ""
        usage = None
        cost = None

        choices = event.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            content = delta.get("content")
            if content:
                text = content

            tool_calls = delta.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    idx = tc.get("index", 0)
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            "id": tc.get("id", ""),
                            "name": "",
                            "arguments": "",
                        }
                    if tc.get("id"):
                        pending_tool_calls[idx]["id"] = tc["id"]
                    func = tc.get("function", {})
                    if func.get("name"):
                        pending_tool_calls[idx]["name"] = func["name"]
                    if func.get("arguments"):
                        pending_tool_calls[idx]["arguments"] = (
                            pending_tool_calls[idx].get("arguments", "") + func["arguments"]
                        )

            finish_reason = choices[0].get("finish_reason")
            if finish_reason == "tool_calls" or finish_reason == "stop":
                pending_tool_calls.clear()

        usage_data = event.get("usage", {})
        if usage_data:
            usage = TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )
            cost = self._calculate_cost(
                {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
                model,
            )

        if text:
            chunks.append(StreamChunk(event_type=StreamEventType.TEXT, text=text))
        if usage:
            chunks.append(StreamChunk(event_type=StreamEventType.USAGE, usage=usage, cost=cost))

        return chunks

    def _build_google_body(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                continue
            gemini_role = "user" if role in ["user", "tool", "tool_result"] else "model"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if tools:
            body["tools"] = self._convert_tools_to_google_format(tools)
        return body

    def _convert_tools_to_google_format(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
            else:
                func = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            result.append(
                {
                    "functionDeclarations": [
                        {
                            "name": func.get("name", ""),
                            "description": func.get("description", ""),
                            "parameters": func.get("parameters", {}),
                        }
                    ]
                }
            )
        return result

    def _parse_google_response(
        self, data: dict[str, Any], model: str = ""
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []
        candidates = data.get("candidates", [])
        if candidates:
            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])
            for part in content_parts:
                if "text" in part:
                    content += part["text"]
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    tool_uses.append(
                        ToolUseBlock(
                            id=fc.get("name", ""), name=fc.get("name", ""), input=fc.get("args", {})
                        )
                    )
        usage_data = data.get("usageMetadata", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("promptTokenCount", 0),
            output_tokens=usage_data.get("candidatesTokenCount", 0),
        )
        cost = self._calculate_cost(
            {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
            model or self.config.get_active_model(),
        )
        return (
            AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_uses=tool_uses,
                stop_reason=candidates[0].get("finishReason") if candidates else None,
            ),
            usage,
            cost,
        )

    def _build_bedrock_body(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        bedrock_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                continue
            bedrock_role = "user" if role in ["user", "tool", "tool_result"] else "assistant"
            bedrock_messages.append({"role": bedrock_role, "content": [{"text": content}]})
        body: dict[str, Any] = {
            "messages": bedrock_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = self._convert_tools_to_openai_format(tools)
        return body

    def _parse_bedrock_response(
        self, data: dict[str, Any], model: str
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []
        output = data.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])
        for block in content_blocks:
            if "text" in block:
                content += block["text"]
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_uses.append(
                    ToolUseBlock(
                        id=tu.get("toolUseId", ""),
                        name=tu.get("name", ""),
                        input=tu.get("input", {}),
                    )
                )
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("inputTokens", 0),
            output_tokens=usage_data.get("outputTokens", 0),
        )
        cost = self._calculate_cost(
            {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}, model
        )
        return (
            AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_uses=tool_uses,
                stop_reason=data.get("stopReason"),
            ),
            usage,
            cost,
        )

    def _build_cohere_body(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        chat_history = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                continue
            cohere_role = "USER" if role in ["user", "tool", "tool_result"] else "CHATBOT"
            chat_history.append({"role": cohere_role, "message": content})
        body: dict[str, Any] = {
            "model": model,
            "message": messages[-1].get("content", "") if messages else "",
            "chat_history": chat_history[:-1] if chat_history else [],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            body["preamble"] = system_prompt
        if tools:
            body["tools"] = self._convert_tools_to_cohere_format(tools)
        return body

    def _convert_tools_to_cohere_format(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
            else:
                func = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                    },
                }
            )
        return result

    def _parse_cohere_response(
        self, data: dict[str, Any], model: str = ""
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []
        text = data.get("text", "")
        content = text
        tool_calls = data.get("tool_calls", [])
        for tc in tool_calls:
            tool_uses.append(
                ToolUseBlock(
                    id=tc.get("name", ""), name=tc.get("name", ""), input=tc.get("parameters", {})
                )
            )
        usage_data = data.get("meta", {}).get("tokens", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        )
        cost = self._calculate_cost(
            {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
            model or self.config.get_active_model(),
        )
        return (
            AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_uses=tool_uses,
                stop_reason=data.get("finish_reason"),
            ),
            usage,
            cost,
        )
