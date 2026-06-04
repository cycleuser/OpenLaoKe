"""Knowledge-injection system.

Short Markdown notes in ``knowledge/`` are auto-injected into the
system prompt, scoped by keyword overlap. The total budget is enforced
*both* per-entry and per-turn so that the prompt prefix never blows up.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """A single knowledge note."""

    name: str
    path: str
    body: str
    keywords: list[str] = field(default_factory=list)
    scope: str = "general"


@dataclass
class KnowledgeLoader:
    """Loads and scores knowledge notes for prompt injection."""

    base_dirs: list[str] = field(default_factory=list)
    entries: dict[str, KnowledgeEntry] = field(default_factory=dict)
    max_tokens: int = 1500
    per_entry_cap: int = 500
    token_estimator: Callable[[str], int] = field(default=lambda s: len(s) // 4)

    def __post_init__(self) -> None:
        if not self.base_dirs:
            self.base_dirs = [
                os.path.expanduser("~/.openlaoke/knowledge"),
                "knowledge",
            ]
        for d in self.base_dirs:
            self._scan(Path(d).expanduser())

    def _scan(self, root: Path) -> None:
        if not root.is_dir():
            return
        for path in root.rglob("*.md"):
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            scope = path.parent.name if path.parent else "general"
            keywords = self._extract_keywords(body)
            name = path.stem
            self.entries[name] = KnowledgeEntry(
                name=name,
                path=str(path),
                body=body,
                keywords=keywords,
                scope=scope,
            )

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        seen: set[str] = set()
        keywords: list[str] = []
        for w in words:
            if w in seen:
                continue
            seen.add(w)
            keywords.append(w)
            if len(keywords) >= 50:
                break
        return keywords

    def search(self, query: str, top_k: int = 5) -> list[KnowledgeEntry]:
        query_words = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", query.lower()))
        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in self.entries.values():
            kw_set = set(entry.keywords)
            if not kw_set:
                continue
            overlap = len(kw_set & query_words)
            if overlap <= 0:
                continue
            scored.append((overlap, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def format_for_prompt(self, query: str, top_k: int = 5) -> str:
        entries = self.search(query, top_k=top_k)
        if not entries:
            return ""
        total = 0
        parts: list[str] = ["<knowledge>"]
        for entry in entries:
            body = entry.body.strip()
            if len(body) > self.per_entry_cap * 4:
                body = body[: self.per_entry_cap * 4] + "..."
            cost = self.token_estimator(body)
            if total + cost > self.max_tokens:
                break
            parts.append(f"### {entry.name}\n\n{body}")
            total += cost
        parts.append("</knowledge>")
        return "\n".join(parts)
