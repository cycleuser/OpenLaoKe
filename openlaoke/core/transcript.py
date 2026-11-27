"""Append-only JSONL transcript: one line per committed message.

The session snapshot (``<id>.json``) is rewritten wholesale on every save. It is
atomic now, which covers the failure that loses a conversation, but it is still
the wrong shape for evidence: each save costs O(messages), and a snapshot that
is damaged takes the whole history with it.

This is the other half: an append-only journal that costs one line per message,
survives a half-written tail, and can be replayed to rebuild the conversation.
The snapshot stays authoritative for the runtime state (tasks, costs, todo);
the transcript is what recovers the messages when the snapshot is unreadable.

A torn final line is normal after a crash and is skipped. A torn line anywhere
else is a real corruption and is reported rather than silently accepted.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

TRANSCRIPT_SUFFIX = ".jsonl"
_HEADER_TYPE = "session.start"
_MESSAGE_TYPE = "message"


@dataclass
class TranscriptHealth:
    """What a replay found: usable records, and anything suspicious."""

    records: int = 0
    last_seq: int = 0
    torn_tail: bool = False
    corrupt_lines: list[int] = field(default_factory=list)
    duplicate_seqs: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.corrupt_lines and not self.duplicate_seqs

    def render(self) -> str:
        parts = [f"{self.records} record(s), last seq {self.last_seq}"]
        if self.torn_tail:
            parts.append("torn final line (normal after a crash; skipped)")
        if self.corrupt_lines:
            parts.append(f"corrupt lines: {', '.join(map(str, self.corrupt_lines))}")
        if self.duplicate_seqs:
            parts.append(f"duplicate seq: {', '.join(map(str, self.duplicate_seqs))}")
        return "; ".join(parts)


def transcript_path_for(snapshot_path: str) -> str:
    stem, _extension = os.path.splitext(snapshot_path)
    return stem + TRANSCRIPT_SUFFIX


class Transcript:
    """One append-only journal. Every write is ``O_APPEND`` + ``fsync``."""

    def __init__(self, path: str, *, session_id: str = "", cwd: str = "", model: str = "") -> None:
        self.path = path
        self.session_id = session_id
        self.cwd = cwd
        self.model = model
        self._seq = 0
        self._started = False

    # ── writing ─────────────────────────────────────────────────────────

    def append_message(self, message: Any) -> int:
        """Append one message; returns its sequence number."""
        self._ensure_header()
        payload = message.to_dict() if hasattr(message, "to_dict") else dict(message)
        self._seq += 1
        self._append(
            {
                "type": _MESSAGE_TYPE,
                "seq": self._seq,
                "at": float(getattr(message, "timestamp", 0.0) or 0.0),
                "message": payload,
            }
        )
        return self._seq

    def _ensure_header(self) -> None:
        if self._started:
            return
        self._started = True
        if os.path.exists(self.path) and os.path.getsize(self.path) > 0:
            # Continue an existing journal: pick up its sequence number so a new
            # process cannot restart at 1 and make the file look tampered with.
            health, records = self._parse()
            self._seq = max((record.get("seq", 0) for record in records), default=0)
            return
        self._append(
            {
                "type": _HEADER_TYPE,
                "session_id": self.session_id,
                "cwd": self.cwd,
                "model": self.model,
                "at": time.time(),
            }
        )

    def _append(self, record: dict[str, Any]) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        line = (json.dumps(record, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            view = memoryview(line)
            while view:
                written = os.write(fd, view)
                if written == 0:
                    raise OSError("short write while appending the transcript")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    # ── reading ─────────────────────────────────────────────────────────

    def replay(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Return ``(header, message records)``; the header may be empty."""
        _health, records = self._parse()
        header: dict[str, Any] = {}
        messages: list[dict[str, Any]] = []
        for record in records:
            if record.get("type") == _HEADER_TYPE:
                header = record
            elif record.get("type") == _MESSAGE_TYPE and isinstance(record.get("message"), dict):
                messages.append(record)
        return header, messages

    def health(self) -> TranscriptHealth:
        return self._parse()[0]

    def records(self) -> list[dict[str, Any]]:
        return self._parse()[1]

    def _parse(self) -> tuple[TranscriptHealth, list[dict[str, Any]]]:
        health = TranscriptHealth()
        if not os.path.exists(self.path):
            return health, []
        with open(self.path, "rb") as handle:
            raw = handle.read()
        if not raw:
            return health, []

        torn_tail = not raw.endswith(b"\n")
        lines = raw.split(b"\n")
        if torn_tail:
            lines = lines[:-1]  # the incomplete fragment is the expected casualty

        records: list[dict[str, Any]] = []
        seen: set[int] = set()
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # A damaged line in the middle is not a crash artefact: a crash
                # can only lose the tail. Report it instead of pretending the
                # journal is fine.
                health.corrupt_lines.append(index + 1)
                continue
            if not isinstance(record, dict):
                health.corrupt_lines.append(index + 1)
                continue
            seq = record.get("seq")
            if type(seq) is int:
                if seq in seen:
                    health.duplicate_seqs.append(seq)
                seen.add(seq)
                health.last_seq = max(health.last_seq, seq)
            records.append(record)

        health.records = len(records)
        health.torn_tail = torn_tail
        return health, records


def load_messages(path: str) -> list[dict[str, Any]]:
    """Replay a journal into raw message dicts (for recovery)."""
    _header, messages = Transcript(path).replay()
    return [record["message"] for record in messages]
