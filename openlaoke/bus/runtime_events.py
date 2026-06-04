"""Typed event stream emitted by the controller.

20 kinds of structured events so any frontend (TUI, WebUI, trace recorder)
can render the agent state without re-implementing turn lifecycle.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventKind(StrEnum):
    TURN_STARTED = "turn_started"
    REASONING = "reasoning"
    TEXT = "text"
    MESSAGE = "message"
    TOOL_DISPATCH = "tool_dispatch"
    TOOL_RESULT = "tool_result"
    USAGE = "usage"
    NOTICE = "notice"
    PHASE = "phase"
    APPROVAL_REQUEST = "approval_request"
    ASK_REQUEST = "ask_request"
    TURN_DONE = "turn_done"
    COMPACTION_STARTED = "compaction_started"
    COMPACTION_DONE = "compaction_done"
    TOOL_PROGRESS = "tool_progress"
    MCP_SURFACE_READY = "mcp_surface_ready"
    RETRYING = "retrying"
    GOAL_CHANGED = "goal_changed"
    LOOP_GUARD = "loop_guard"
    SKILL_INVOKED = "skill_invoked"


@dataclass
class AgentEvent:
    """Typed event observed by a :class:`EventSink`."""

    kind: EventKind
    session_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            self.kind = EventKind(self.kind)


class EventSink:
    """Fan-out sink. Each :meth:`emit` is delivered to every subscriber.

    Subscribers are coroutine callbacks. Errors are isolated — one bad
    subscriber cannot break the others or the agent.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callable[[AgentEvent], Awaitable[None] | None]] = []
        self._buffer: list[AgentEvent] = []
        self._max_buffer = 500

    def subscribe(self, callback: Callable[[AgentEvent], Awaitable[None] | None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AgentEvent], Awaitable[None] | None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def emit(self, event: AgentEvent) -> None:
        if not isinstance(event, AgentEvent):
            return
        self._buffer.append(event)
        if len(self._buffer) > self._max_buffer:
            self._buffer = self._buffer[-self._max_buffer :]
        for sub in list(self._subscribers):
            try:
                result = sub(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                continue

    def emit_sync(self, event: AgentEvent) -> None:
        """Fire-and-forget emit; for use from sync contexts."""
        if not isinstance(event, AgentEvent):
            return
        self._buffer.append(event)
        if len(self._buffer) > self._max_buffer:
            self._buffer = self._buffer[-self._max_buffer :]
        for sub in list(self._subscribers):
            try:
                result = sub(event)
                if hasattr(result, "__await__"):
                    import asyncio

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass
            except Exception:
                continue

    def recent(self, n: int = 50) -> list[AgentEvent]:
        return self._buffer[-n:]

    def clear(self) -> None:
        self._buffer.clear()


def make_event(
    kind: EventKind | str,
    session_id: str = "",
    **data: Any,
) -> AgentEvent:
    """Convenience factory for events."""
    return AgentEvent(kind=kind, session_id=session_id, data=data)
