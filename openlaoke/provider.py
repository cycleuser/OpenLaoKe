"""Provider base: streaming, retry, role-alternation, prompt-cache markers.

The :class:`LLMProvider` ABC is the single layer that all
provider-specific adapters (Anthropic, OpenAI, DeepSeek, etc.) build
on. It enforces:

* Streaming-first API with a small set of typed chunks.
* Retry with exponential backoff.
* Role alternation — consecutive same-role messages are merged.
* Prompt-cache marker indices (``last_builtin_idx``, ``tail_idx``).
* Reasoning extraction (Kimi, DeepSeek-R1, MiMo ``reasoning_content``,
  Anthropic ``thinking_blocks``).
"""

from __future__ import annotations

import abc
import asyncio
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ChunkKind(StrEnum):
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL = "tool_call"
    USAGE = "usage"
    ERROR = "error"
    DONE = "done"


@dataclass
class Chunk:
    """A single streaming chunk from a provider."""

    kind: ChunkKind
    text: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    partial: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    error: str = ""


@dataclass
class CacheMarkers:
    """Prompt-cache boundary indices into the message list.

    * ``last_builtin_idx`` — index of the last message that was part of
      the cacheable prefix (system prompt + tool schema). The provider
      should not re-include anything from index 0 to this point on
      subsequent turns.
    * ``tail_idx`` — index where the user-tunable tail begins.
    """

    last_builtin_idx: int = 0
    tail_idx: int = 0


@dataclass
class ProviderRequest:
    """A request to a provider."""

    system: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 1.0
    reasoning_effort: str = ""
    cache_markers: CacheMarkers = field(default_factory=CacheMarkers)


@dataclass
class ProviderError:
    """Classified provider error."""

    code: str
    message: str
    retry_after: float = 0.0
    arrearage: bool = False


_RETRY_DELAYS = (1.0, 2.0, 4.0)
_PERSISTENT_MAX_DELAY = 60.0
_PERSISTENT_IDENTICAL_ERROR_LIMIT = 10


class LLMProvider(abc.ABC):
    """Base class for LLM providers."""

    def __init__(self, name: str, **config: Any) -> None:
        self.name = name
        self.config = config
        self._last_error: str = ""
        self._identical_error_count = 0

    @abc.abstractmethod
    async def stream(self, request: ProviderRequest) -> AsyncIterator[Chunk]:
        """Stream a response as a sequence of typed chunks."""
        raise NotImplementedError

    async def chat(self, request: ProviderRequest) -> dict[str, Any]:
        """Aggregate-stream a response and return the full message."""
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        async for chunk in self.stream(request):
            if chunk.kind == ChunkKind.TEXT:
                text_parts.append(chunk.text)
            elif chunk.kind == ChunkKind.REASONING:
                reasoning_parts.append(chunk.text)
            elif chunk.kind == ChunkKind.TOOL_CALL:
                tool_calls.append(
                    {
                        "id": chunk.tool_call_id,
                        "name": chunk.tool_name,
                        "input": chunk.tool_args,
                    }
                )
            elif chunk.kind == ChunkKind.USAGE:
                usage = {
                    "input_tokens": chunk.input_tokens,
                    "output_tokens": chunk.output_tokens,
                    "cache_hit_tokens": chunk.cache_hit_tokens,
                    "cache_miss_tokens": chunk.cache_miss_tokens,
                }
            elif chunk.kind == ChunkKind.ERROR:
                raise RuntimeError(chunk.error or "provider error")
        return {
            "text": "".join(text_parts),
            "reasoning": "".join(reasoning_parts),
            "tool_calls": tool_calls,
            "usage": usage,
        }

    async def chat_with_retry(self, request: ProviderRequest) -> dict[str, Any]:
        """Standard retry mode: a few attempts, exponential backoff."""
        last_exc: Exception | None = None
        for attempt, delay in enumerate((*_RETRY_DELAYS, _RETRY_DELAYS[-1])):
            try:
                return await self.chat(request)
            except Exception as exc:
                last_exc = exc
                provider_error = self._classify_error(exc)
                if provider_error.arrearage:
                    raise
                logger.debug("Provider %s attempt %d failed: %s", self.name, attempt + 1, exc)
                await asyncio.sleep(delay)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("provider chat failed with no error")

    async def chat_stream_with_retry(self, request: ProviderRequest) -> AsyncIterator[Chunk]:
        """Persistent retry mode for long-running streams."""
        delay_index = 0
        delay = _RETRY_DELAYS[0]
        while True:
            try:
                async for chunk in self.stream(request):
                    yield chunk
                return
            except Exception as exc:
                err = self._classify_error(exc)
                if err.arrearage:
                    raise
                if err.message == self._last_error:
                    self._identical_error_count += 1
                    if self._identical_error_count >= _PERSISTENT_IDENTICAL_ERROR_LIMIT:
                        raise
                else:
                    self._identical_error_count = 0
                    self._last_error = err.message
                sleep_for = err.retry_after or delay
                sleep_for = min(sleep_for, _PERSISTENT_MAX_DELAY)
                logger.debug("Provider %s stream retry in %.1fs: %s", self.name, sleep_for, exc)
                await asyncio.sleep(sleep_for)
                delay_index = min(delay_index + 1, len(_RETRY_DELAYS) - 1)
                delay = _RETRY_DELAYS[delay_index]

    def _classify_error(self, exc: Exception) -> ProviderError:
        """Classify an exception into a typed :class:`ProviderError`."""
        text = str(exc)
        lowered = text.lower()
        if any(
            token in lowered
            for token in (
                "insufficient_quota",
                "payment_required",
                "billing",
                "arrearage",
                "402",
            )
        ):
            return ProviderError("arrearage", text, arrearage=True)
        retry_match = re.search(r"retry[ _-]?after[: ]+(\d+(?:\.\d+)?)", lowered)
        if retry_match:
            return ProviderError("rate_limit", text, retry_after=float(retry_match.group(1)))
        if any(token in lowered for token in ("429", "rate limit", "too many requests")):
            return ProviderError("rate_limit", text)
        return ProviderError("transient", text)


def enforce_role_alternation(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive same-role messages and ensure user-first."""
    if not messages:
        return messages
    fixed: list[dict[str, Any]] = []
    for msg in messages:
        if fixed and fixed[-1].get("role") == msg.get("role"):
            prev = fixed[-1]
            content = prev.get("content", "")
            new_content = msg.get("content", "")
            if isinstance(content, str) and isinstance(new_content, str):
                prev["content"] = content + "\n" + new_content
            else:
                prev["content"] = (
                    content
                    if isinstance(content, list)
                    else [{"type": "text", "text": str(content)}]
                )
                prev["content"] += (
                    new_content
                    if isinstance(new_content, list)
                    else [{"type": "text", "text": str(new_content)}]
                )
        else:
            fixed.append(dict(msg))
    while fixed and fixed[0].get("role") not in ("user", "system"):
        fixed.pop(0)
    if not fixed:
        return fixed
    if fixed[-1].get("role") == "user" and len(fixed) >= 2:
        second_last = fixed[-2]
        if second_last.get("role") == "user":
            merged_content = (
                (second_last.get("content", "") or "") + "\n" + (fixed[-1].get("content", "") or "")
            )
            fixed[-2] = {"role": "assistant", "content": "ok"}
            fixed[-1] = {"role": "user", "content": merged_content}
    return fixed


def detect_arrearage_response(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in ("insufficient_quota", "payment_required", "billing", "arrearage", "402")
    )
