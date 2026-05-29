"""Tool-call deduplication with sliding window.

Short-circuits identical consecutive read-only tool calls with cached results.
Separate per-turn guard for idempotent-write tools (memory_remember/forget).
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field

READ_ONLY_TOOLS = {
    "Read",
    "ListDirectory",
    "Glob",
    "Grep",
    "ToolSearch",
    "WebSearch",
    "WebFetch",
    "MemoryRecall",
    "MemorySearch",
    "MemoryTimeline",
    "MemoryStats",
}

IDEMPOTENT_WRITE_TOOLS = {
    "MemoryStore",
    "MemoryForget",
}


@dataclass
class ToolCallCache:
    window_size: int = 5
    _window: deque[tuple[str, str, str]] = field(default_factory=deque)
    _results: dict[str, str] = field(default_factory=dict)
    _idempotent_this_turn: set[str] = field(default_factory=set)

    def check(self, tool_name: str, args: dict[str, object]) -> str | None:
        """Check if tool call should be deduplicated. Returns cached result or None."""
        if tool_name in READ_ONLY_TOOLS:
            call_key = _make_key(tool_name, args)
            for cached_name, _cached_args, cached_key in self._window:
                if cached_name == tool_name and cached_key == call_key:
                    return self._results.get(call_key)
        return None

    def record(self, tool_name: str, args: dict[str, object], result: str) -> None:
        """Record a tool call result (only for read-only tools)."""
        if tool_name not in READ_ONLY_TOOLS:
            return
        call_key = _make_key(tool_name, args)
        self._window.append((tool_name, json.dumps(args, sort_keys=True), call_key))
        self._results[call_key] = result
        while len(self._window) > self.window_size:
            _, _, old_key = self._window.popleft()
            if old_key in self._results:
                del self._results[old_key]

    def check_idempotent_write(self, tool_name: str, args: dict[str, object]) -> str | None:
        """Check idempotent-write dedup (per-turn)."""
        if tool_name in IDEMPOTENT_WRITE_TOOLS:
            call_key = _make_key(tool_name, args)
            if call_key in self._idempotent_this_turn:
                return f"[already stored this turn - deduplicated '{tool_name}' call]"
            self._idempotent_this_turn.add(call_key)
        return None

    def reset_turn(self) -> None:
        self._idempotent_this_turn.clear()

    def clear(self) -> None:
        self._window.clear()
        self._results.clear()
        self._idempotent_this_turn.clear()


def _make_key(tool_name: str, args: dict[str, object]) -> str:
    raw = json.dumps({"name": tool_name, "args": args}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()
