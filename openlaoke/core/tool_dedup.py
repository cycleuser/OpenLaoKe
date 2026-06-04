"""Tool call deduplication.

Detects repeated identical tool calls across iterations and blocks them
when the model is stuck in a loop. Caps at 3 identical calls to the same
tool with the same arguments.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_MAX_REPEATS = 3


class ToolDedup:
    """Tracks tool call history and flags repeated calls."""

    def __init__(self) -> None:
        self._history: list[str] = []
        self._blocked: set[str] = set()

    def _fingerprint(self, name: str, args: dict[str, Any]) -> str:
        canonical = json.dumps(args, sort_keys=True, ensure_ascii=False)
        return f"{name}:{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"

    def check(self, name: str, args: dict[str, Any]) -> str | None:
        """Return a block reason if this call should be deduped, else None.

        Tracks the last 20 calls. After ``_MAX_REPEATS`` identical calls,
        the fingerprint is blocked for the rest of the session.
        """
        fp = self._fingerprint(name, args)
        if fp in self._blocked:
            return (
                f"Dedup blocked: '{name}' with these args has been called "
                f"{_MAX_REPEATS}+ times. Try a different approach."
            )

        self._history.append(fp)
        if len(self._history) > 20:
            self._history.pop(0)

        count = sum(1 for h in self._history if h == fp)
        if count >= _MAX_REPEATS:
            self._blocked.add(fp)
            return (
                f"Dedup blocked: '{name}' with these args has been called "
                f"{count} times. Try a different approach."
            )
        return None

    def reset(self) -> None:
        self._history.clear()
        self._blocked.clear()


# Backward-compat: old ToolCallCache with record/check semantics
class _ToolCallCacheEntry:
    __slots__ = ("tool_name", "args_key", "result_preview")

    def __init__(self, tool_name: str, args_key: str, result_preview: str) -> None:
        self.tool_name = tool_name
        self.args_key = args_key
        self.result_preview = result_preview


_WRITE_TOOL_NAMES = frozenset({
    "Write", "Edit", "Bash", "ApplyPatch", "MultiEdit",
    "NotebookWrite", "Git", "write_file", "edit_file", "bash",
    "multi_edit", "apply_patch",
})


class ToolCallCache:
    """Result cache for read-only tool calls. Write tools never cached."""

    def __init__(self, window_size: int = 50) -> None:
        self._window: list[_ToolCallCacheEntry] = []
        self._max = window_size

    @staticmethod
    def _key(tool_name: str, args: dict[str, object]) -> str:
        canonical = json.dumps(args, sort_keys=True, ensure_ascii=False)
        return f"{tool_name}:{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"

    def record(self, tool_name: str, args: dict[str, object], result_preview: str) -> None:
        if tool_name in _WRITE_TOOL_NAMES:
            return
        key = self._key(tool_name, args)
        entry = _ToolCallCacheEntry(tool_name, key, result_preview[:500])
        self._window.append(entry)
        if len(self._window) > self._max:
            self._window.pop(0)

    def check(self, tool_name: str, args: dict[str, object]) -> str | None:
        if tool_name in _WRITE_TOOL_NAMES:
            return None
        key = self._key(tool_name, args)
        for entry in reversed(self._window):
            if entry.tool_name == tool_name and entry.args_key == key:
                return entry.result_preview
        return None

    def reset_turn(self) -> None:
        """Reset per-turn state (keeps window)."""
        pass

    def clear(self) -> None:
        """Clear entire cache."""
        self._window.clear()
