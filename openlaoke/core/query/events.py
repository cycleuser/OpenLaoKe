"""QueryEvent types and event system for AsyncGenerator query engine."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openlaoke.types.core_types import (
    CostInfo,
    Message,
    TokenUsage,
    ToolProgress,
    ToolResultBlock,
    ToolUseBlock,
)


class QueryEventType(Enum):
    """Types of events yielded during query execution."""

    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_delta"
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_BLOCK_STOP = "content_block_stop"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    TOOL_PROGRESS = "tool_progress"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"
    MESSAGE_END = "message_end"
    ERROR = "error"
    TURN_END = "turn_end"
    COMPACT_BOUNDARY = "compact_boundary"
    STREAM_REQUEST_START = "stream_request_start"
    THINKING_DELTA = "thinking_delta"


class StopReason(Enum):
    """Reasons for stopping a query loop."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    ERROR = "error"
    ABORTED = "aborted"
    BLOCKING_LIMIT = "blocking_limit"
    PROMPT_TOO_LONG = "prompt_too_long"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    MAX_TURNS = "max_turns"
    MAX_BUDGET = "max_budget"


@dataclass
class QueryEvent:
    """Base event yielded during query execution."""

    type: QueryEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class MessageStartEvent(QueryEvent):
    """Event when a new message starts."""

    message_id: str = ""
    role: str = "assistant"
    model: str = ""
    type: QueryEventType = field(default=QueryEventType.MESSAGE_START, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "role": self.role,
            "model": self.model,
        }


@dataclass
class ContentDeltaEvent(QueryEvent):
    """Event for text content streaming."""

    message_id: str = ""
    content: str = ""
    index: int = 0
    type: QueryEventType = field(default=QueryEventType.CONTENT_DELTA, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "content": self.content,
            "index": self.index,
        }


@dataclass
class ThinkingDeltaEvent(QueryEvent):
    """Event for thinking content streaming."""

    message_id: str = ""
    content: str = ""
    index: int = 0
    type: QueryEventType = field(default=QueryEventType.THINKING_DELTA, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "content": self.content,
            "index": self.index,
        }


@dataclass
class ContentBlockStartEvent(QueryEvent):
    """Event when a content block starts."""

    message_id: str = ""
    index: int = 0
    block_type: str = "text"
    type: QueryEventType = field(default=QueryEventType.CONTENT_BLOCK_START, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "index": self.index,
            "block_type": self.block_type,
        }


@dataclass
class ContentBlockStopEvent(QueryEvent):
    """Event when a content block stops."""

    message_id: str = ""
    index: int = 0
    type: QueryEventType = field(default=QueryEventType.CONTENT_BLOCK_STOP, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "index": self.index,
        }


@dataclass
class ToolUseEvent(QueryEvent):
    """Event when a tool use block is detected."""

    tool_use_id: str = ""
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    message_id: str = ""
    index: int = 0
    type: QueryEventType = field(default=QueryEventType.TOOL_USE, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "tool_use_id": self.tool_use_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "message_id": self.message_id,
            "index": self.index,
        }

    @classmethod
    def from_block(cls, block: ToolUseBlock, message_id: str, index: int) -> ToolUseEvent:
        return cls(
            tool_use_id=block.id,
            tool_name=block.name,
            tool_input=block.input,
            message_id=message_id,
            index=index,
        )


@dataclass
class ToolResultEvent(QueryEvent):
    """Event when a tool execution result is ready."""

    tool_use_id: str = ""
    tool_name: str = ""
    result: ToolResultBlock | None = None
    message_id: str = ""
    type: QueryEventType = field(default=QueryEventType.TOOL_RESULT, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "tool_use_id": self.tool_use_id,
            "tool_name": self.tool_name,
            "result": self.result.to_dict() if self.result else None,
            "message_id": self.message_id,
        }


@dataclass
class ToolProgressEvent(QueryEvent):
    """Event for tool execution progress updates."""

    progress: ToolProgress | None = None
    type: QueryEventType = field(default=QueryEventType.TOOL_PROGRESS, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.progress:
            self.data = {
                "tool_use_id": self.progress.tool_use_id,
                "tool_name": self.progress.tool_name,
                "message": self.progress.message,
                "percentage": self.progress.percentage,
            }


@dataclass
class MessageDeltaEvent(QueryEvent):
    """Event for message-level updates (stop_reason, usage)."""

    message_id: str = ""
    stop_reason: str | None = None
    usage: TokenUsage | None = None
    type: QueryEventType = field(default=QueryEventType.MESSAGE_DELTA, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "stop_reason": self.stop_reason,
            "usage": self.usage.to_dict() if self.usage else None,
        }


@dataclass
class MessageStopEvent(QueryEvent):
    """Event when a message stops streaming."""

    message_id: str = ""
    stop_reason: str | None = None
    type: QueryEventType = field(default=QueryEventType.MESSAGE_STOP, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "message_id": self.message_id,
            "stop_reason": self.stop_reason,
        }


@dataclass
class MessageEndEvent(QueryEvent):
    """Event when a complete message is ready."""

    message: Message | None = None
    type: QueryEventType = field(default=QueryEventType.MESSAGE_END, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.message:
            self.data = self.message.to_dict()


@dataclass
class ErrorEvent(QueryEvent):
    """Event for errors during query execution."""

    error_message: str = ""
    error_type: str = ""
    is_retryable: bool = False
    retry_count: int = 0
    type: QueryEventType = field(default=QueryEventType.ERROR, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "error_message": self.error_message,
            "error_type": self.error_type,
            "is_retryable": self.is_retryable,
            "retry_count": self.retry_count,
        }


@dataclass
class TurnEndEvent(QueryEvent):
    """Event marking the end of a turn in the agentic loop."""

    turn_count: int = 0
    total_usage: TokenUsage | None = None
    total_cost: CostInfo | None = None
    stop_reason: StopReason = StopReason.END_TURN
    type: QueryEventType = field(default=QueryEventType.TURN_END, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "turn_count": self.turn_count,
            "total_usage": self.total_usage.to_dict() if self.total_usage else None,
            "total_cost": self.total_cost.total_cost if self.total_cost else 0.0,
            "stop_reason": self.stop_reason.value,
        }


@dataclass
class CompactBoundaryEvent(QueryEvent):
    """Event marking a context compact boundary."""

    pre_compact_tokens: int = 0
    post_compact_tokens: int = 0
    compacted_message_count: int = 0
    type: QueryEventType = field(default=QueryEventType.COMPACT_BOUNDARY, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.data = {
            "pre_compact_tokens": self.pre_compact_tokens,
            "post_compact_tokens": self.post_compact_tokens,
            "compacted_message_count": self.compacted_message_count,
        }


@dataclass
class StreamRequestStartEvent(QueryEvent):
    """Event when a stream request starts."""

    type: QueryEventType = field(default=QueryEventType.STREAM_REQUEST_START, init=False)
    data: dict[str, Any] = field(default_factory=dict, init=False)


class QueryResult:
    """Final result of a query execution."""

    def __init__(
        self,
        reason: StopReason,
        messages: list[Message] | None = None,
        total_usage: TokenUsage | None = None,
        total_cost: CostInfo | None = None,
        turn_count: int = 0,
        error: Exception | None = None,
    ) -> None:
        self.reason = reason
        self.messages = messages or []
        self.total_usage = total_usage or TokenUsage()
        self.total_cost = total_cost or CostInfo()
        self.turn_count = turn_count
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason.value,
            "messages": [m.to_dict() for m in self.messages],
            "total_usage": self.total_usage.to_dict(),
            "total_cost": self.total_cost.total_cost,
            "turn_count": self.turn_count,
            "error": str(self.error) if self.error else None,
        }
