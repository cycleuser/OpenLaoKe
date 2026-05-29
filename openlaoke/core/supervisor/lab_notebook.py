"""Lab notebook / CHANGELOG system.

Inspired by Feynman's CHANGELOG convention.
Records research progress, failures, and next steps chronologically.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class LabEntry:
    """A single entry in the lab notebook."""

    timestamp: str
    slug: str
    action: str
    details: str
    status: str = "in_progress"
    next_step: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"### [{self.timestamp}] {self.action}",
            f"- **Slug:** {self.slug}",
            f"- **Status:** {self.status}",
            f"- {self.details}",
        ]
        if self.next_step:
            lines.append(f"- **Next:** {self.next_step}")
        lines.append("")
        return "\n".join(lines)


class LabNotebook:
    """Lab notebook for tracking research progress."""

    def __init__(self, base_dir: str | None = None):
        if base_dir is None:
            base_dir = os.getcwd()
        self.base_dir = base_dir
        self.file_path = os.path.join(base_dir, "CHANGELOG.md")
        self._entries: list[LabEntry] = []

    def _ensure_file(self) -> None:
        if not os.path.exists(self.file_path):
            header = "# Lab Notebook\n\nChronological record of research progress, failures, and next steps.\n\n"
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(header)

    def add_entry(
        self,
        slug: str,
        action: str,
        details: str,
        status: str = "in_progress",
        next_step: str = "",
    ) -> LabEntry:
        timestamp = time.strftime("%Y-%m-%d %H:%M")

        entry = LabEntry(
            timestamp=timestamp,
            slug=slug,
            action=action,
            details=details,
            status=status,
            next_step=next_step,
        )

        self._entries.append(entry)
        self._append_to_file(entry)
        return entry

    def _append_to_file(self, entry: LabEntry) -> None:
        self._ensure_file()
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(entry.to_markdown())

    def get_entries(self, slug: str | None = None) -> list[LabEntry]:
        if slug is None:
            return self._entries
        return [e for e in self._entries if e.slug == slug]

    def get_last_entry(self, slug: str | None = None) -> LabEntry | None:
        entries = self.get_entries(slug)
        return entries[-1] if entries else None

    def load_from_file(self) -> list[LabEntry]:
        if not os.path.exists(self.file_path):
            return []

        entries = []
        with open(self.file_path, encoding="utf-8") as f:
            content = f.read()

        current_entry = None
        for line in content.split("\n"):
            if line.startswith("### ["):
                if current_entry:
                    entries.append(current_entry)
                timestamp = line.split("]")[0].replace("### [", "")
                action = line.split("] ")[1] if "] " in line else ""
                current_entry = LabEntry(
                    timestamp=timestamp,
                    slug="",
                    action=action,
                    details="",
                )
            elif line.startswith("- **Slug:**") and current_entry:
                current_entry.slug = line.split("**Slug:**")[1].strip()
            elif line.startswith("- **Status:**") and current_entry:
                current_entry.status = line.split("**Status:**")[1].strip()
            elif line.startswith("- **Next:**") and current_entry:
                current_entry.next_step = line.split("**Next:**")[1].strip()
            elif line.startswith("- ") and current_entry:
                detail = line[2:]
                if current_entry.details:
                    current_entry.details += "\n" + detail
                else:
                    current_entry.details = detail

        if current_entry:
            entries.append(current_entry)

        self._entries = entries
        return entries

    def get_summary(self) -> str:
        if not self._entries:
            return "No entries in lab notebook."

        lines = ["## Lab Notebook Summary\n"]
        for entry in self._entries[-5:]:
            lines.append(entry.to_markdown())
        return "\n".join(lines)
