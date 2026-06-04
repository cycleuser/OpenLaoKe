"""Pending-memory turn-tail queue.

In-session memory writes (e.g. quick-add, complete_step) do not mutate
the cache-stable prefix. Instead, the note is queued here and appended
to the *next* outgoing user content, folding into the prefix on the
next session.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class PendingMemoryQueue:
    """Per-session queue of memory notes to apply on the next turn."""

    _notes: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, session_id: str, note: str) -> None:
        note = note.strip()
        if note:
            self._notes[session_id].append(note)

    def drain(self, session_id: str) -> list[str]:
        notes = self._notes.pop(session_id, [])
        return list(notes)

    def peek(self, session_id: str) -> list[str]:
        return list(self._notes.get(session_id, []))

    def clear(self, session_id: str) -> None:
        self._notes.pop(session_id, None)


def render_runtime_block(notes: list[str]) -> str:
    """Render a turn-tail runtime block for pending memory notes."""
    if not notes:
        return ""
    body = "\n".join(f"- {n}" for n in notes)
    return f"\n[Runtime Context]\nPending memory notes (will fold in next session):\n{body}\n"


_GLOBAL_QUEUE = PendingMemoryQueue()


def global_queue() -> PendingMemoryQueue:
    return _GLOBAL_QUEUE
