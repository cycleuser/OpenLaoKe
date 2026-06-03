"""Snapshot and auto-rollback system integrated with supervisor.

Opens file checkpoints before each agent turn. On validation hard-fail,
reverts all edits back to checkpoint state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class SnapshotEntry:
    path: str
    before_content: str | None = None
    is_new_file: bool = False


@dataclass
class SnapshotCheckpoint:
    label: str = ""
    entries: dict[str, SnapshotEntry] = field(default_factory=dict)
    work_dir: str = ""

    def note(self, path: str, before_content: str) -> None:
        if path in self.entries:
            return
        exists = os.path.exists(path)
        self.entries[path] = SnapshotEntry(
            path=path,
            before_content=before_content if exists else None,
            is_new_file=not exists,
        )

    def rollback(self) -> list[str]:
        restored = []
        for entry in self.entries.values():
            abs_path = (
                os.path.join(self.work_dir, entry.path)
                if self.work_dir and not os.path.isabs(entry.path)
                else entry.path
            )
            if entry.is_new_file or entry.before_content is None:
                try:
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        restored.append(entry.path)
                except FileNotFoundError:
                    pass
            else:
                parent = os.path.dirname(abs_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(abs_path, "w") as f:
                    f.write(entry.before_content)
                restored.append(entry.path)
        return restored

    def commit(self) -> None:
        self.entries.clear()


@dataclass
class SnapshotManager:
    _current_checkpoint: SnapshotCheckpoint | None = None
    _snapshot_dir: str = ""
    auto_rollback: bool = False
    _enabled: bool = True

    def begin(self, label: str = "") -> SnapshotCheckpoint:
        self._current_checkpoint = SnapshotCheckpoint(label=label)
        return self._current_checkpoint

    def note(self, path: str, before_content: str) -> None:
        if self._current_checkpoint:
            self._current_checkpoint.note(path, before_content)

    def rollback(self) -> list[str]:
        if self._current_checkpoint:
            result = self._current_checkpoint.rollback()
            self._current_checkpoint = None
            return result
        return []

    def commit(self) -> None:
        if self._current_checkpoint:
            self._current_checkpoint.commit()
            self._current_checkpoint = None

    @property
    def has_checkpoint(self) -> bool:
        return self._current_checkpoint is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
