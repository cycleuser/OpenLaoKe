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
