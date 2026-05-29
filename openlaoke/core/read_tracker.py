"""Read-tracker and context-aware read guard.

Tracks read paths, enforces read-before-write, and provides smart truncation
when files exceed context budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field

READ_TOOLS = {"Read", "Edit", "ApplyPatch", "Glob", "Grep", "ListDirectory"}


@dataclass
class ReadTracker:
    """Tracks which paths have been read this session for write-guard enforcement."""

    _read_paths: set[str] = field(default_factory=set)
    _write_denied_paths: set[str] = field(default_factory=set)
    _context_usage: int = 0
    _context_max: int = 32000
    _head_lines: int = 30
    _enabled: bool = True

    def record_read(self, path: str) -> None:
        self._read_paths.add(path)

    def has_read(self, path: str) -> bool:
        return path in self._read_paths

    def check_before_write(self, path: str) -> str | None:
        """Check if write to existing file should be blocked. Returns deny message or None."""
        if not self._enabled:
            return None
        if path in self._read_paths:
            return None
        if path in self._write_denied_paths:
            self._write_denied_paths.discard(path)
            return None
        import os

        if os.path.exists(path):
            self._write_denied_paths.add(path)
            return (
                f"[WRITE-GUARD] You haven't read '{path}' yet. "
                "Read the file first to understand its contents before overwriting. "
                "Call read_file on this path, then try writing again."
            )
        return None

    def set_context_budget(self, usage: int, max_tokens: int) -> None:
        self._context_usage = usage
        self._context_max = max_tokens

    def should_guard_read(self, file_size: int) -> bool:
        """Determine if read should be smart-truncated."""
        if not self._enabled:
            return False
        if file_size > self._context_max * 0.5:
            return True
        return self._context_usage > self._context_max * 0.8

    def get_guard_message(self) -> str:
        return (
            "[READ-GUARD] File is large relative to context. "
            f"Showing first {self._head_lines} lines (imports + signatures). "
            "Use grep to search for specific content, or read a smaller line range."
        )

    def reset(self) -> None:
        self._read_paths.clear()
        self._write_denied_paths.clear()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
