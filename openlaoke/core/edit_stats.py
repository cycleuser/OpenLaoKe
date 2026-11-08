"""Per-session edit accounting.

The model is told to make small edits, and the only honest way to check that is
to count what actually landed on disk: how many files were created versus
modified, and how many lines went in and came out.  A session that rewrote
three hundred lines to change one signature is visible here and nowhere else.

Counts are line-level, computed with a sequence matcher rather than by
subtracting line totals, because a one-line change and a full rewrite can have
the same net zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

MAX_TRACKED_FILES = 500


def count_line_changes(before: str, after: str) -> tuple[int, int]:
    """Return ``(lines_added, lines_removed)`` between two texts."""
    old_lines = before.splitlines()
    new_lines = after.splitlines()
    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added = removed = 0
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        removed += old_end - old_start
        added += new_end - new_start
    return added, removed


@dataclass
class EditStats:
    """Line and file counts for one session."""

    files_created: int = 0
    files_modified: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    per_file: dict[str, dict[str, int]] = field(default_factory=dict)

    def record(self, path: str, before: str, after: str, created: bool) -> tuple[int, int]:
        """Record one write. Returns the ``(added, removed)`` for that write."""
        added, removed = count_line_changes(before, after)
        self.lines_added += added
        self.lines_removed += removed
        if created:
            self.files_created += 1
        else:
            self.files_modified += 1

        entry = self.per_file.setdefault(
            path, {"added": 0, "removed": 0, "writes": 0, "created": 0}
        )
        entry["added"] += added
        entry["removed"] += removed
        entry["writes"] += 1
        entry["created"] = 1 if created else entry.get("created", 0)

        if len(self.per_file) > MAX_TRACKED_FILES:
            oldest = next(iter(self.per_file))
            del self.per_file[oldest]
        return added, removed

    @property
    def files_touched(self) -> int:
        return self.files_created + self.files_modified

    @property
    def net_lines(self) -> int:
        return self.lines_added - self.lines_removed

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "per_file": self.per_file,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> EditStats:
        if not data:
            return cls()
        return cls(
            files_created=int(data.get("files_created", 0) or 0),
            files_modified=int(data.get("files_modified", 0) or 0),
            lines_added=int(data.get("lines_added", 0) or 0),
            lines_removed=int(data.get("lines_removed", 0) or 0),
            per_file={
                str(path): {str(key): int(value) for key, value in counts.items()}
                for path, counts in (data.get("per_file") or {}).items()
            },
        )

    def render(self, top: int = 10) -> str:
        if not self.per_file:
            return "No edits recorded in this session."
        sign = "+" if self.net_lines >= 0 else ""
        lines = [
            f"Files: {self.files_created} created, {self.files_modified} modified",
            f"Lines: +{self.lines_added} / -{self.lines_removed} (net {sign}{self.net_lines})",
        ]
        ordered = sorted(
            self.per_file.items(),
            key=lambda item: item[1]["added"] + item[1]["removed"],
            reverse=True,
        )[:top]
        if ordered:
            lines.append("Largest changes:")
            for path, counts in ordered:
                lines.append(f"  +{counts['added']:<5} -{counts['removed']:<5} {path}")
        return "\n".join(lines)


def record_edit(app_state: Any, path: str, before: str, after: str, created: bool) -> None:
    """Update the session's counters from a tool that wrote to disk."""
    stats = EditStats.from_dict(getattr(app_state, "edit_stats", None))
    stats.record(path, before, after, created)
    app_state.edit_stats = stats.to_dict()

    # When workers run in lanes, the touch ledger is how the parent finds out
    # that two of them wrote the same file.
    board = getattr(app_state, "_swarm_board", None)
    if board is not None:
        from openlaoke.core.swarm import CURRENT_MEMBER

        board.touch(path, CURRENT_MEMBER.get())
