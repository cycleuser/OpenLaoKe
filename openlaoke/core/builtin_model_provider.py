"""Built-in GGUF model provider for local inference using llama-cpp-python."""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openlaoke.core.local_model_manager import LocalModelManager
from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    MessageRole,
    TokenUsage,
    ToolUseBlock,
)
from openlaoke.utils.install_logger import get_install_logger


@dataclass
class BuiltinModelProvider:
    """Provider for local GGUF models using llama-cpp-python."""

    model_path: str = ""
    n_ctx: int = 262144
    n_threads: int = -1
    n_gpu_layers: int = 0
    temperature: float = 0.3
    max_tokens: int = 2048
    repetition_penalty: float = 1.1
    logger: Any = None
    _llm: Any = None
    _model_manager: LocalModelManager | None = None

    def __post_init__(self) -> None:
        if self.logger is None:
            self.logger = get_install_logger()
        if self._model_manager is None:
            self._model_manager = LocalModelManager()

    def _ensure_loaded(self) -> None:
        """Ensure the model is loaded."""
        if self._llm is None:
            if not self.model_path:
                raise ValueError("No model path specified")
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found: {self.model_path}")

            self.logger.info(f"Loading GGUF model: {self.model_path}")

            try:
                from llama_cpp import Llama

                self._llm = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_threads=self.n_threads if self.n_threads > 0 else None,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False,
                )
                self.logger.info("Model loaded successfully")
            except ImportError:
                self.logger.error("llama-cpp-python not installed")
                self.logger.error("Install with: pip install llama-cpp-python")
                raise
            except Exception as e:
                self.logger.error(f"Failed to load model: {e}")
                raise

    async def send_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        """Send a message to the local model."""
        self._ensure_loaded()

        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        formatted_messages = self._format_messages(system_prompt, messages)

        try:
            response = self._llm.create_chat_completion(
                messages=formatted_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                repeat_penalty=self.repetition_penalty,
            )

            return self._parse_response_with_thinking(response)

        except Exception as e:
            self.logger.error(f"Model inference failed: {e}")
            raise

    async def stream_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[tuple[str, TokenUsage | None, CostInfo | None]]:
        """Stream a response from the local model."""
        self._ensure_loaded()

        max_tokens = max_tokens or self.max_tokens
        temperature = temperature if temperature is not None else self.temperature

        formatted_messages = self._format_messages(system_prompt, messages)

        try:
            stream = self._llm.create_chat_completion(
                messages=formatted_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                stream=True,
                repeat_penalty=self.repetition_penalty,
            )

            final_usage = None
            final_cost = None

            for chunk in stream:
                text, usage, cost = self._parse_stream_chunk(chunk)
                if text:
                    yield text, None, None
                if usage:
                    final_usage = usage
                    final_cost = cost

            yield "", final_usage, final_cost

        except Exception as e:
            self.logger.error(f"Model streaming failed: {e}")
            raise

    def _format_messages(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format messages for llama-cpp-python, truncating if needed."""
        formatted = []

        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool_result":
                role = "tool"

            formatted.append({"role": role, "content": content})

        total_chars = sum(len(m.get("content", "")) for m in formatted)
        max_context_chars = (self.n_ctx - self.max_tokens) * 3

        if total_chars > max_context_chars and max_context_chars > 0:
            overhead_chars = total_chars - max_context_chars
            for _, m in enumerate(formatted):
                if m["role"] == "system" and len(m["content"]) > overhead_chars:
                    m["content"] = m["content"][: len(m["content"]) - overhead_chars]
                    self.logger.info(
                        f"System prompt truncated by {overhead_chars} chars to fit context window"
                    )
                    break

            total_chars = sum(len(m.get("content", "")) for m in formatted)
            if total_chars > max_context_chars:
                while len(formatted) > 2 and total_chars > max_context_chars:
                    removed = formatted.pop(1)
                    total_chars -= len(removed.get("content", ""))

        return formatted

    def _parse_response_with_thinking(
        self, response: dict[str, Any]
    ) -> tuple[AssistantMessage, TokenUsage, CostInfo]:
        content = ""
        tool_uses = []
        thinking = ""

        choices = response.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            raw_content = message.get("content", "") or ""

            thinking_content, parsed_content, parsed_tool_uses = self._parse_raw_tool_calls(
                raw_content
            )
            if parsed_tool_uses:
                tool_uses = parsed_tool_uses
                content = parsed_content
                thinking = thinking_content
            else:
                thinking_tag_open = "<" + "think" + "ing>"
                thinking_tag_close = "</" + "think" + "ing>"
                thinking_pattern = (
                    re.escape(thinking_tag_open) + r"(.*?)" + re.escape(thinking_tag_close)
                )
                thinking_match = re.search(thinking_pattern, raw_content, re.DOTALL)
                if thinking_match:
                    thinking = thinking_match.group(1).strip()
                    content = re.sub(thinking_pattern, "", raw_content, flags=re.DOTALL).strip()
                else:
                    content = raw_content

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

        usage_data = response.get("usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )
        cost = CostInfo(
            input_cost=0.0,
            output_cost=0.0,
        )

        return (
            AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_uses=tool_uses,
                stop_reason=choice.get("finish_reason") if choices else None,
                thinking=thinking,
            ),
            usage,
            cost,
        )

    def _parse_stream_chunk(
        self, chunk: dict[str, Any]
    ) -> tuple[str, TokenUsage | None, CostInfo | None]:
        """Parse a streaming chunk from llama-cpp-python."""
        text = ""
        usage = None
        cost = None

        choices = chunk.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            text = delta.get("content", "") or ""

        usage_data = chunk.get("usage", {})
        if usage_data:
            usage = TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )
            cost = CostInfo(
                input_cost=0.0,
                output_cost=0.0,
            )

        return text, usage, cost

    def _parse_raw_tool_calls(
        self, raw_content: str,
    ) -> tuple[str, str, list[ToolUseBlock]]:
        import uuid

        content = raw_content
        tool_uses: list[ToolUseBlock] = []

        tool_pattern = re.compile(
            r"<tool_call>\s*(.*?)\s*</tool_call>",
            re.DOTALL | re.IGNORECASE,
        )

        def _extract(match_text: str) -> list[ToolUseBlock]:
            results: list[ToolUseBlock] = []
            for block in tool_pattern.findall(match_text):
                fn_match = re.search(r"<function=(\w+)>", block)
                if not fn_match:
                    continue
                tool_name = fn_match.group(1)

                params: dict[str, Any] = {}
                param_parts = re.split(r"<parameter=(\w+)>", block)
                if len(param_parts) <= 1:
                    continue

                i = 1
                while i < len(param_parts) - 1:
                    key = param_parts[i]
                    val = param_parts[i + 1].strip()
                    if val:
                        params[key] = val
                    i += 2

                if tool_name and params:
                    results.append(
                        ToolUseBlock(
                            id=f"call_{uuid.uuid4().hex[:12]}",
                            name=tool_name,
                            input=params,
                        )
                    )
            return results

        tool_uses = _extract(raw_content)
        if tool_uses:
            content = tool_pattern.sub("", raw_content).strip()
            return "", content, tool_uses

        return "", raw_content, []

    def unload(self) -> None:
        """Unload the model to free memory."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            self.logger.info("Model unloaded")

    def __del__(self) -> None:
        self.unload()
