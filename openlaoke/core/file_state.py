"""Per-session record of which files the model has actually looked at.

The Write tool refuses to clobber a file the model has not read, and Read
records what it handed over. Both sides look for this object on
``ToolContext.file_state``; without it the guard is silently skipped and a
small model can overwrite a file it never opened.

Paths are compared after ``os.path.realpath`` so ``./a.py``, ``a.py`` and a
symlink to it count as the same file.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field


@dataclass
class ReadRecord:
    """What a read returned, so a later edit can be checked against it."""

    path: str
    size: int
    truncated: bool = False


@dataclass
class FileState:
    """Tracks files read in the current session."""

    _reads: dict[str, ReadRecord] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @staticmethod
    def _key(path: str) -> str:
        try:
            return os.path.realpath(os.path.abspath(os.path.expanduser(path)))
        except OSError:
            return os.path.abspath(os.path.expanduser(path))

    def record_read(self, path: str, content: str = "", *, truncated: bool = False) -> None:
        """Note that *path* was shown to the model."""
        with self._lock:
            self._reads[self._key(path)] = ReadRecord(
                path=self._key(path), size=len(content), truncated=truncated
            )

    def was_read(self, path: str) -> bool:
        """True when *path* has been read in this session."""
        with self._lock:
            return self._key(path) in self._reads

    def forget(self, path: str) -> None:
        """Drop the record for *path* (e.g. after it was deleted)."""
        with self._lock:
            self._reads.pop(self._key(path), None)

    def reset(self) -> None:
        with self._lock:
            self._reads.clear()

    def read_paths(self) -> list[str]:
        with self._lock:
            return sorted(self._reads)
