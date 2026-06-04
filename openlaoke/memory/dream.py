"""Dream-style memory consolidation.

A :class:`DreamConsolidator` runs periodically (cron) or on-demand
(``/dream``). It:

1. Reads unprocessed history since the last dream cursor.
2. Builds a restricted prompt directing the agent to call
   ``remember`` / ``forget`` / ``SaveDoc`` to update memory.
3. Runs an ephemeral turn with a memory-scoped tool set.
4. Auto-commits changes via :class:`GitStore`.

The cursor advances only when the dream turn completes successfully.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DreamResult:
    """Result of a single dream consolidation cycle."""

    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    facts_added: int = 0
    facts_updated: int = 0
    facts_deleted: int = 0
    docs_written: int = 0
    notes: list[str] = field(default_factory=list)
    success: bool = False


class DreamConsolidator:
    """Coordinates the dream memory-consolidation cycle."""

    DEFAULT_INTERVAL_HOURS = 2.0

    def __init__(
        self,
        memory_root: str | None = None,
        interval_hours: float = DEFAULT_INTERVAL_HOURS,
    ) -> None:
        self.memory_root = Path(memory_root or "~/.openlaoke/memory").expanduser()
        self.memory_root.mkdir(parents=True, exist_ok=True)
        self.interval_hours = interval_hours
        self._cursor_path = self.memory_root / ".dream_cursor"
        self._log_path = self.memory_root / "dream.log"

    @property
    def cursor(self) -> int:
        if not self._cursor_path.exists():
            return 0
        try:
            return int(self._cursor_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            return 0

    def advance_cursor(self, value: int) -> None:
        self._cursor_path.write_text(str(value), encoding="utf-8")

    def build_prompt(
        self,
        history: list[dict[str, Any]],
        max_history_chars: int = 20000,
    ) -> str:
        """Build the restricted prompt directing the dream turn."""
        if not history:
            return ""
        body_chars = max_history_chars
        joined = ""
        for entry in history:
            line = f"- {entry.get('role', '?')}: {entry.get('content', '')}"
            if len(joined) + len(line) + 1 > body_chars:
                break
            joined += line + "\n"
        return (
            "You are running a memory-consolidation turn. Review the history "
            "below and call `remember` for each durable fact worth keeping, "
            "`forget` for facts that are now stale, and `SaveDoc` if a "
            "long-form document is warranted. Do not respond to the user. "
            "Do not call any tool outside `remember`, `forget`, and `SaveDoc`.\n\n"
            f"## History (since cursor {self.cursor})\n\n{joined}"
        )

    def restricted_tools(self) -> set[str]:
        """Tools available during a dream turn."""
        return {"remember", "forget", "SaveDoc", "read_file"}

    def log(self, message: str) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
