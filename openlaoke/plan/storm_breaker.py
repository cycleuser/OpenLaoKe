"""Storm-breaker loop guard.

A loop-guard detects when the same tool, with the same error class, has
been called too many times in a row. The signature is
``(tool_name, error_class)`` *not* the tool arguments, because a stuck
model rewords arguments cosmetically while failing identically.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class StormBreaker:
    """Per-session storm breaker.

    Tracks a sliding window of the last N (tool, error) pairs. If the
    same pair appears ``threshold`` times in a row, the breaker fires.
    """

    threshold: int = 3
    window_size: int = 12
    _history: dict[str, deque[str]] = field(default_factory=dict)
    _fired_for: dict[str, set[str]] = field(default_factory=dict)

    def signature(self, tool_name: str, error: str) -> str:
        return f"{tool_name}::{error[:80]}"

    def classify_error(self, error: str) -> str:
        if not error:
            return "unknown"
        first = error.split("\n", 1)[0].split(":", 1)[0].strip()
        return first[:80] or "unknown"

    def record(self, session_id: str, tool_name: str, error: str) -> bool:
        """Record a failed tool call. Returns True if the breaker fires."""
        cls = self.classify_error(error)
        key = f"{session_id}::{tool_name}"
        history = self._history.setdefault(key, deque(maxlen=self.window_size))
        history.append(cls)
        fired = self._fired_for.setdefault(key, set())

        if len(history) < self.threshold:
            return False
        if all(c == cls for c in list(history)[-self.threshold :]) and cls not in fired:
            fired.add(cls)
            return True
        return False

    def reset(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._history.clear()
            self._fired_for.clear()
            return
        prefix = f"{session_id}::"
        for key in list(self._history.keys()):
            if key.startswith(prefix):
                self._history.pop(key, None)
                self._fired_for.pop(key, None)

    def message(self, tool_name: str, error: str, fired: int) -> str:
        return (
            f"[loop guard] {tool_name} has failed {fired} times in a row with the "
            f"same error ({self.classify_error(error)}). Re-sending it — even "
            "with the wording changed — will not help. Try a different tool, "
            "or state that you cannot complete the task."
        )
