"""Stream processing utilities for AsyncGenerator query engine."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from openlaoke.core.query.events import (
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    ContentDeltaEvent,
    ErrorEvent,
    MessageDeltaEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageStopEvent,
    QueryEvent,
    QueryEventType,
    ThinkingDeltaEvent,
    ToolUseEvent,
)
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    TokenUsage,
    ToolUseBlock,
)


@dataclass
class StreamingState:
    """State tracking for streaming response."""

    message_id: str = field(default_factory=lambda: uuid4().hex)
    current_content: str = ""
    current_thinking: str = ""
    content_blocks: list[dict[str, Any]] = field(default_factory=list)
    tool_uses: list[ToolUseBlock] = field(default_factory=list)
    current_block_index: int = 0
    current_block_type: str = ""
    stop_reason: str | None = None
    usage: TokenUsage | None = None
    is_thinking_enabled: bool = False


class StreamProcessor:
    """Process streaming events from API into QueryEvents."""

    def __init__(self, message_id: str | None = None) -> None:
        self.state = StreamingState(message_id=message_id or uuid4().hex)
        self._block_start_time: float = 0.0

    def reset(self) -> None:
        self.state = StreamingState()

    async def process_anthropic_event(
        self, event: dict[str, Any]
    ) -> AsyncGenerator[QueryEvent, None]:
        """Process Anthropic-style streaming event."""
        event_type = event.get("type", "")

        if event_type == "message_start":
            message_data = event.get("message", {})
            self.state.message_id = message_data.get("id", uuid4().hex)
            self.state.usage = TokenUsage(
                input_tokens=message_data.get("usage", {}).get("input_tokens", 0),
                output_tokens=0,
            )
            yield MessageStartEvent(
                message_id=self.state.message_id,
                role="assistant",
                model=message_data.get("model", ""),
            )

        elif event_type == "content_block_start":
            index = event.get("index", 0)
            block = event.get("content_block", {})
            block_type = block.get("type", "text")
            self.state.current_block_index = index
            self.state.current_block_type = block_type
            self._block_start_time = time.time()

            yield ContentBlockStartEvent(
                message_id=self.state.message_id,
                index=index,
                block_type=block_type,
            )

            if block_type == "tool_use":
                tool_block = ToolUseBlock(
                    id=block.get("id", uuid4().hex),
                    name=block.get("name", ""),
                    input={},
                )
                self.state.tool_uses.append(tool_block)
                yield ToolUseEvent(
                    tool_use_id=tool_block.id,
                    tool_name=tool_block.name,
                    tool_input={},
                    message_id=self.state.message_id,
                    index=index,
                )

        elif event_type == "content_block_delta":
            index = event.get("index", 0)
            delta = event.get("delta", {})
            delta_type = delta.get("type", "text_delta")

            if delta_type == "text_delta":
                text = delta.get("text", "")
                self.state.current_content += text
                yield ContentDeltaEvent(
                    message_id=self.state.message_id,
                    content=text,
                    index=index,
                )

            elif delta_type == "thinking_delta" or delta_type == "input_json_delta":
                text = delta.get("thinking", delta.get("partial_json", ""))
                if delta_type == "thinking_delta":
                    self.state.current_thinking += text
                    yield ThinkingDeltaEvent(
                        message_id=self.state.message_id,
                        content=text,
                        index=index,
                    )
                else:
                    if self.state.tool_uses and index < len(self.state.tool_uses):
                        try:
                            partial = json.loads(text)
                            self.state.tool_uses[index].input.update(partial)
                        except json.JSONDecodeError:
                            pass

        elif event_type == "content_block_stop":
            index = event.get("index", 0)
            yield ContentBlockStopEvent(
                message_id=self.state.message_id,
                index=index,
            )

            if self.state.current_block_type == "text":
                self.state.content_blocks.append(
                    {
                        "type": "text",
                        "text": self.state.current_content,
                    }
                )
                self.state.current_content = ""
            elif self.state.current_block_type == "thinking":
                self.state.content_blocks.append(
                    {
                        "type": "thinking",
                        "thinking": self.state.current_thinking,
                    }
                )
                self.state.current_thinking = ""

        elif event_type == "message_delta":
            delta = event.get("delta", {})
            usage_data = event.get("usage", {})

            self.state.stop_reason = delta.get("stop_reason")

            if usage_data:
                output_tokens = usage_data.get("output_tokens", 0)
                if self.state.usage:
                    self.state.usage.output_tokens = output_tokens
                    self.state.usage.cache_read_tokens = usage_data.get(
                        "cache_read_input_tokens", 0
                    )
                    self.state.usage.cache_creation_tokens = usage_data.get(
                        "cache_creation_input_tokens", 0
                    )

            yield MessageDeltaEvent(
                message_id=self.state.message_id,
                stop_reason=self.state.stop_reason,
                usage=self.state.usage,
            )

        elif event_type == "message_stop":
            yield MessageStopEvent(
                message_id=self.state.message_id,
                stop_reason=self.state.stop_reason,
            )

            message = self._build_assistant_message()
            yield MessageEndEvent(message=message)

    async def process_openai_event(self, event: dict[str, Any]) -> AsyncGenerator[QueryEvent, None]:
        """Process OpenAI-style streaming event."""
        choices = event.get("choices", [])

        if not choices:
            usage_data = event.get("usage", {})
            if usage_data:
                self.state.usage = TokenUsage(
                    input_tokens=usage_data.get("prompt_tokens", 0),
                    output_tokens=usage_data.get("completion_tokens", 0),
                )
                yield MessageDeltaEvent(
                    message_id=self.state.message_id,
                    usage=self.state.usage,
                )
            return

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        if finish_reason:
            self.state.stop_reason = finish_reason
            yield MessageDeltaEvent(
                message_id=self.state.message_id,
                stop_reason=self.state.stop_reason,
            )

        content = delta.get("content")
        if content:
            self.state.current_content += content
            yield ContentDeltaEvent(
                message_id=self.state.message_id,
                content=content,
                index=0,
            )

        tool_calls = delta.get("tool_calls", [])
        for i, tc in enumerate(tool_calls):
            func = tc.get("function", {})
            tool_id = tc.get("id", uuid4().hex)
            tool_name = func.get("name", "")
            args_str = func.get("arguments", "{}")

            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            existing = None
            for tu in self.state.tool_uses:
                if tu.id == tool_id:
                    existing = tu
                    break

            if existing:
                existing.input.update(args)
            else:
                new_block = ToolUseBlock(id=tool_id, name=tool_name, input=args)
                self.state.tool_uses.append(new_block)
                yield ToolUseEvent(
                    tool_use_id=tool_id,
                    tool_name=tool_name,
                    tool_input=args,
                    message_id=self.state.message_id,
                    index=i,
                )

        if finish_reason == "stop":
            yield MessageStopEvent(
                message_id=self.state.message_id,
                stop_reason=self.state.stop_reason,
            )
            message = self._build_assistant_message()
            yield MessageEndEvent(message=message)

    def _build_assistant_message(self) -> AssistantMessage:
        """Build final assistant message from streaming state."""
        content_parts = []

        for block in self.state.content_blocks:
            content_parts.append(block)

        for tu in self.state.tool_uses:
            content_parts.append(tu.to_dict())

        if not content_parts and self.state.current_content:
            content_parts.append({"type": "text", "text": self.state.current_content})

        return AssistantMessage(
            role=MessageRole.ASSISTANT,
            content=self.state.current_content,
            tool_uses=self.state.tool_uses,
            stop_reason=self.state.stop_reason,
        )

    def get_usage(self) -> TokenUsage:
        return self.state.usage or TokenUsage()

    def get_tool_uses(self) -> list[ToolUseBlock]:
        return self.state.tool_uses

    def has_tool_uses(self) -> bool:
        return len(self.state.tool_uses) > 0


async def merge_streams(
    *generators: AsyncGenerator[QueryEvent, None],
) -> AsyncGenerator[QueryEvent, None]:
    """Merge multiple async generators into one."""
    for gen in generators:
        async for event in gen:
            yield event


async def stream_with_timeout(
    generator: AsyncGenerator[QueryEvent, None],
    timeout_seconds: float = 300.0,
) -> AsyncGenerator[QueryEvent, None]:
    """Wrap stream with timeout."""
    try:
        async with asyncio.timeout(timeout_seconds):
            async for event in generator:
                yield event
    except TimeoutError:
        yield ErrorEvent(
            error_message=f"Stream timed out after {timeout_seconds}s",
            error_type="timeout",
            is_retryable=True,
        )


async def stream_with_retry(
    generator_factory: Callable[[], AsyncGenerator[QueryEvent, None]],
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> AsyncGenerator[QueryEvent, None]:
    """Wrap stream with retry logic."""
    retry_count = 0
    while retry_count < max_retries:
        try:
            async for event in generator_factory():
                if event.type == QueryEventType.ERROR and event.data.get("is_retryable"):
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(retry_delay * retry_count)
                        continue
                yield event
                if event.type == QueryEventType.MESSAGE_END:
                    return
            return
        except Exception as e:
            retry_count += 1
            yield ErrorEvent(
                error_message=str(e),
                error_type="exception",
                is_retryable=True,
                retry_count=retry_count,
            )
            if retry_count < max_retries:
                await asyncio.sleep(retry_delay * retry_count)
