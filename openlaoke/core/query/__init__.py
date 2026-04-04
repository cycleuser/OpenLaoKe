"""AsyncGenerator Query Engine module.

This module provides a stream-based query execution engine that handles:
- Streaming API responses via AsyncGenerator
- Tool execution with progress tracking
- Context management and compaction
- Error recovery with retry mechanisms

Based on Claude Code's query.ts and QueryEngine.ts patterns.
"""

from __future__ import annotations

from openlaoke.core.query.context import (
    QueryContext,
    QueryTracking,
    TurnState,
    create_query_context,
)
from openlaoke.core.query.engine import (
    QueryEngine,
    run_query,
)
from openlaoke.core.query.events import (
    CompactBoundaryEvent,
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
    QueryResult,
    StopReason,
    StreamRequestStartEvent,
    ThinkingDeltaEvent,
    ToolProgressEvent,
    ToolResultEvent,
    ToolUseEvent,
    TurnEndEvent,
)
from openlaoke.core.query.recovery import (
    MaxOutputTokensError,
    ModelFallbackError,
    PromptTooLongError,
    RecoveryError,
    RecoveryHandler,
    TimeoutHandler,
    categorize_error,
    create_missing_tool_result_blocks,
)
from openlaoke.core.query.stream import (
    StreamingState,
    StreamProcessor,
    merge_streams,
    stream_with_retry,
    stream_with_timeout,
)

__all__ = [
    "QueryEngine",
    "run_query",
    "QueryContext",
    "QueryTracking",
    "TurnState",
    "create_query_context",
    "QueryEvent",
    "QueryEventType",
    "QueryResult",
    "StopReason",
    "MessageStartEvent",
    "ContentDeltaEvent",
    "ThinkingDeltaEvent",
    "ContentBlockStartEvent",
    "ContentBlockStopEvent",
    "ToolUseEvent",
    "ToolResultEvent",
    "ToolProgressEvent",
    "MessageDeltaEvent",
    "MessageStopEvent",
    "MessageEndEvent",
    "ErrorEvent",
    "TurnEndEvent",
    "CompactBoundaryEvent",
    "StreamRequestStartEvent",
    "StreamProcessor",
    "StreamingState",
    "merge_streams",
    "stream_with_timeout",
    "stream_with_retry",
    "RecoveryHandler",
    "TimeoutHandler",
    "RecoveryError",
    "PromptTooLongError",
    "MaxOutputTokensError",
    "ModelFallbackError",
    "categorize_error",
    "create_missing_tool_result_blocks",
]
