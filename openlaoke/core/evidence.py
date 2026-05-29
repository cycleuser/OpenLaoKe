"""Evidence store - automated capture of what was tried, what worked, what failed.

Stored as searchable memory objects. The model learns from past sessions.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class EvidenceEntry:
    task_id: str = ""
    commands_tried: list[str] = field(default_factory=list)
    commands_failed: list[str] = field(default_factory=list)
    commands_succeeded: list[str] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    validation_results: list[str] = field(default_factory=list)
    summary: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "commands_tried": self.commands_tried,
            "commands_failed": self.commands_failed,
            "commands_succeeded": self.commands_succeeded,
            "files_created": self.files_created,
            "files_edited": self.files_edited,
            "validation_results": self.validation_results,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> EvidenceEntry:
        return cls(
            task_id=d.get("task_id", ""),
            commands_tried=d.get("commands_tried", []),
            commands_failed=d.get("commands_failed", []),
            commands_succeeded=d.get("commands_succeeded", []),
            files_created=d.get("files_created", []),
            files_edited=d.get("files_edited", []),
            validation_results=d.get("validation_results", []),
            summary=d.get("summary", ""),
            timestamp=d.get("timestamp", time.time()),
        )

    def to_context_string(self) -> str:
        parts = []
        if self.commands_failed:
            parts.append(f"Failed commands: {', '.join(self.commands_failed[-3:])}")
        if self.commands_succeeded:
            parts.append(f"Successful commands: {', '.join(self.commands_succeeded[-3:])}")
        if self.files_created:
            parts.append(f"Created: {', '.join(self.files_created)}")
        if self.files_edited:
            parts.append(f"Edited: {', '.join(self.files_edited)}")
        if self.summary:
            parts.append(f"Summary: {self.summary}")
        return " | ".join(parts)


@dataclass
class EvidenceStore:
    store_dir: str = ""
    max_entries: int = 50
    _enabled: bool = True
    _current_task_id: str = ""
    _current_entry: EvidenceEntry | None = None

    def get_dir(self) -> str:
        if self.store_dir:
            return self.store_dir
        return os.path.join(os.getcwd(), ".smallcode", "evidence")

    def start_task(self, task_id: str) -> None:
        self._current_task_id = task_id
        self._current_entry = EvidenceEntry(task_id=task_id)

    def record_command(self, command: str, success: bool, error_tail: str = "") -> None:
        if not self._current_entry:
            return
        self._current_entry.commands_tried.append(command)
        if success:
            self._current_entry.commands_succeeded.append(command)
        else:
            self._current_entry.commands_failed.append(f"{command} -- {error_tail[:200]}")

    def record_file(self, path: str, created: bool = True) -> None:
        if not self._current_entry:
            return
        if created:
            if path not in self._current_entry.files_created:
                self._current_entry.files_created.append(path)
        else:
            if path not in self._current_entry.files_edited:
                self._current_entry.files_edited.append(path)

    def record_validation(self, result: str) -> None:
        if not self._current_entry:
            return
        self._current_entry.validation_results.append(result)

    def finish_task(self, summary: str = "") -> EvidenceEntry | None:
        if not self._current_entry:
            return None
        self._current_entry.summary = summary
        self._persist()
        entry = self._current_entry
        self._current_entry = None
        return entry

    def _persist(self) -> None:
        if not self._enabled or not self._current_entry:
            return
        d = self.get_dir()
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, f"{self._current_task_id}.json")
        with open(fp, "w") as f:
            json.dump(self._current_entry.to_dict(), f, indent=2)

    def load_recent(self, limit: int = 5) -> list[EvidenceEntry]:
        d = self.get_dir()
        if not os.path.isdir(d):
            return []
        entries = []
        files = sorted(os.listdir(d), reverse=True)
        for fn in files[:limit]:
            fp = os.path.join(d, fn)
            try:
                with open(fp) as f:
                    entries.append(EvidenceEntry.from_dict(json.load(f)))
            except Exception:
                pass
        return entries

    def search(self, query: str, limit: int = 3) -> list[EvidenceEntry]:
        all_entries = self.load_recent(self.max_entries)
        if not query:
            return all_entries[:limit]
        query_lower = query.lower()
        scored = []
        for entry in all_entries:
            text = entry.to_context_string().lower()
            score = sum(1 for w in query_lower.split() if w in text)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
