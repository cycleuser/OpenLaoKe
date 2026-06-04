"""Per-tool-call progress bus.

Long-running tools (bash, code-graph, sandbox install) publish chunks of
output as they run so the UI can show live progress.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ProgressChunk:
    tool_call_id: str
    session_id: str
    chunk: str
    kind: str = "stdout"
    timestamp: float = field(default_factory=time.time)


class ProgressBus:
    """Per-tool-call streaming progress buffer."""

    def __init__(self) -> None:
        self._buffers: dict[str, list[ProgressChunk]] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._closed: set[str] = set()

    def open(self, tool_call_id: str, session_id: str = "") -> None:
        self._buffers[tool_call_id] = []
        self._events[tool_call_id] = asyncio.Event()
        self._closed.discard(tool_call_id)

    def publish(self, chunk: ProgressChunk) -> None:
        buf = self._buffers.setdefault(chunk.tool_call_id, [])
        buf.append(chunk)
        ev = self._events.get(chunk.tool_call_id)
        if ev is not None:
            ev.set()
            ev.clear()

    def close(self, tool_call_id: str) -> None:
        self._closed.add(tool_call_id)
        ev = self._events.get(tool_call_id)
        if ev is not None:
            ev.set()

    def chunks(self, tool_call_id: str) -> list[ProgressChunk]:
        return list(self._buffers.get(tool_call_id, []))

    def text(self, tool_call_id: str) -> str:
        return "".join(c.chunk for c in self._buffers.get(tool_call_id, []) if c.kind == "stdout")

    def is_closed(self, tool_call_id: str) -> bool:
        return tool_call_id in self._closed

    async def wait(self, tool_call_id: str, timeout: float = 0.05) -> bool:
        ev = self._events.get(tool_call_id)
        if ev is None:
            return True
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    def clear(self, tool_call_id: str) -> None:
        self._buffers.pop(tool_call_id, None)
        self._events.pop(tool_call_id, None)
        self._closed.discard(tool_call_id)


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:10]}"
