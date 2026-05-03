"""FileState — read-before-edit safety tracking.

Inspired by nanobot's FileState system. Tracks per-file read/write state
with mtime and content hash. Enforces that Write/Edit tools only modify
files that have been read first (stale content detection).

Key features:
- record_read(): mark file as read with mtime + SHA-256 hash
- record_write(): update state after write
- check_read(): validate file was recently read, detect stale content
- is_unchanged(): dedup reads, return stub if file hasn't changed
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FileReadState:
    path: str
    read_mtime: float = 0.0
    read_hash: str = ""
    last_write_mtime: float = 0.0
    write_hash: str = ""
    read_count: int = 0
    write_count: int = 0
    warnings: list[str] = field(default_factory=list)


class FileStateStore:
    def __init__(self) -> None:
        self._states: dict[str, FileReadState] = {}

    def record_read(self, path: str, content: str) -> FileReadState:
        abs_path = os.path.realpath(path)
        try:
            mtime = os.path.getmtime(abs_path)
        except OSError:
            mtime = time.time()
        content_hash = _hash_content(content)

        if abs_path in self._states:
            state = self._states[abs_path]
            state.read_mtime = mtime
            state.read_hash = content_hash
            state.read_count += 1
        else:
            state = FileReadState(
                path=abs_path,
                read_mtime=mtime,
                read_hash=content_hash,
                read_count=1,
            )
            self._states[abs_path] = state
        return state

    def record_write(self, path: str, content: str) -> None:
        abs_path = os.path.realpath(path)
        try:
            mtime = os.path.getmtime(abs_path)
        except OSError:
            mtime = time.time()
        content_hash = _hash_content(content)

        if abs_path in self._states:
            state = self._states[abs_path]
            state.last_write_mtime = mtime
            state.write_hash = content_hash
            state.write_count += 1
        else:
            self._states[abs_path] = FileReadState(
                path=abs_path,
                last_write_mtime=mtime,
                write_hash=content_hash,
                write_count=1,
            )

    def check_read(self, path: str) -> str | None:
        abs_path = os.path.realpath(path)
        state = self._states.get(abs_path)

        if state is None:
            return f"Warning: file '{path}' has not been read yet. Read it first to verify content before editing."

        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return f"Error: cannot access '{path}'"

        if abs(current_mtime - state.read_mtime) > 1.0:
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    current_content = f.read()
                current_hash = _hash_content(current_content)
                if current_hash != state.read_hash:
                    return (
                        f"Warning: file '{path}' was modified since last read. "
                        "Re-read the file to get the latest content before editing."
                    )
            except Exception:
                return f"Warning: file '{path}' state is stale. Re-read before editing."

        return None

    def is_unchanged(self, path: str, content: str) -> bool:
        abs_path = os.path.realpath(path)
        state = self._states.get(abs_path)
        if state is None:
            return False

        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return False

        content_hash = _hash_content(content)
        return (
            abs(current_mtime - state.read_mtime) < 1.0
            and content_hash == state.read_hash
        )

    def get_state(self, path: str) -> FileReadState | None:
        abs_path = os.path.realpath(path)
        return self._states.get(abs_path)

    def clear(self) -> None:
        self._states.clear()


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]
