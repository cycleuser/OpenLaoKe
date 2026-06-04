"""Hierarchical bootstrap-doc loader.

The loader looks in order, returning the first that exists:

1. ``REASONIX.md``
2. ``REASONIX.local.md`` (machine-local, git-ignored)
3. ``AGENTS.md``
4. ``CLAUDE.md``
5. ``OPENLAOKE.md``

In addition, ``USER.md`` and ``SOUL.md`` are loaded if present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BOOTSTRAP_FILENAMES: tuple[str, ...] = (
    "REASONIX.md",
    "REASONIX.local.md",
    "AGENTS.md",
    "CLAUDE.md",
    "OPENLAOKE.md",
)

USER_FILENAMES: tuple[str, ...] = ("USER.md", "SOUL.md", "PROFILE.md")


@dataclass
class DocMemory:
    """A bootstrap document loaded from the workspace."""

    name: str
    path: str
    body: str
    priority: int


@dataclass
class DocMemoryBundle:
    """The hierarchy of bootstrap documents for a workspace."""

    primary: DocMemory | None = None
    locals_: list[DocMemory] = field(default_factory=list)
    user: list[DocMemory] = field(default_factory=list)
    supplementary: list[DocMemory] = field(default_factory=list)

    def combined_body(self, max_chars: int = 12000) -> str:
        parts: list[str] = []
        if self.primary:
            parts.append(f"# {self.primary.name}\n\n{self.primary.body}")
        for doc in self.supplementary:
            parts.append(f"# {doc.name}\n\n{doc.body}")
        for doc in self.locals_:
            parts.append(f"# {doc.name} (local)\n\n{doc.body}")
        for doc in self.user:
            parts.append(f"# {doc.name}\n\n{doc.body}")
        text = "\n\n---\n\n".join(parts)
        if len(text) > max_chars:
            text = text[: max_chars - 30] + "\n\n... (truncated)"
        return text

    def has_any(self) -> bool:
        return any([self.primary, self.locals_, self.user, self.supplementary])


def _read_first(work_dir: str, names: tuple[str, ...]) -> DocMemory | None:
    for priority, name in enumerate(names):
        path = Path(work_dir) / name
        if path.is_file():
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
                return DocMemory(
                    name=name,
                    path=str(path),
                    body=body,
                    priority=priority,
                )
            except OSError:
                continue
    return None


def _read_all(work_dir: str, names: tuple[str, ...]) -> list[DocMemory]:
    found: list[DocMemory] = []
    for priority, name in enumerate(names):
        path = Path(work_dir) / name
        if path.is_file():
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
                found.append(
                    DocMemory(
                        name=name,
                        path=str(path),
                        body=body,
                        priority=priority,
                    )
                )
            except OSError:
                continue
    return found


def load_bundle(work_dir: str) -> DocMemoryBundle:
    """Load the bootstrap doc hierarchy from ``work_dir``."""
    if not work_dir or not os.path.isdir(work_dir):
        return DocMemoryBundle()
    bundle = DocMemoryBundle()
    bundle.primary = _read_first(work_dir, BOOTSTRAP_FILENAMES)
    bundle.locals_ = [
        d for d in _read_all(work_dir, BOOTSTRAP_FILENAMES) if d.name.endswith(".local.md")
    ]
    bundle.user = _read_all(work_dir, USER_FILENAMES)
    bundle.supplementary = [
        d
        for d in _read_all(work_dir, BOOTSTRAP_FILENAMES)
        if d is not bundle.primary and d not in bundle.locals_
    ]
    return bundle
