"""Knowledge injection from local knowledge/ directory.

Loads short reference notes (100-500 words) from knowledge/ and injects the
most relevant ones into system prompt based on keyword overlap with user message.
No embeddings -- fully local, dependency-free.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
    "shall",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "and",
    "but",
    "or",
    "nor",
    "not",
    "so",
    "yet",
    "both",
    "either",
    "neither",
    "each",
    "every",
    "all",
    "any",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "only",
    "own",
    "same",
    "than",
    "too",
    "very",
    "just",
    "because",
    "about",
    "over",
    "under",
    "this",
    "that",
    "these",
    "those",
    "what",
    "which",
    "who",
    "whom",
    "where",
    "when",
    "how",
    "it",
    "its",
    "here",
    "there",
}

TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
FRONTMATTER_KEYWORDS_PATTERN = re.compile(r"keywords:\s*(.+)", re.IGNORECASE)


@dataclass
class KnowledgeEntry:
    path: str
    title: str = ""
    content: str = ""
    keywords: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.title or self.path


@dataclass
class KnowledgeLoader:
    max_tokens: int = 1500
    per_entry_cap: int = 1500
    _enabled: bool = True
    _entries: dict[str, KnowledgeEntry] = field(default_factory=dict)

    def load_directory(self, base_dir: str) -> None:
        if not os.path.isdir(base_dir):
            return
        self._entries.clear()
        self._scan_dir(base_dir, base_dir)

    def _scan_dir(self, top: str, root: str) -> None:
        try:
            entries = os.listdir(root)
        except PermissionError:
            return
        for name in sorted(entries):
            full = os.path.join(root, name)
            if os.path.isdir(full):
                self._scan_dir(top, full)
            elif name.endswith(".md"):
                try:
                    with open(full, encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue
                rel = os.path.relpath(full, top)
                entry = self._parse_entry(rel, content)
                self._entries[rel] = entry

    @staticmethod
    def _parse_entry(path: str, content: str) -> KnowledgeEntry:
        title = ""
        keywords: list[str] = []
        title_match = TITLE_PATTERN.search(content)
        if title_match:
            title = title_match.group(1).strip()
        kw_match = FRONTMATTER_KEYWORDS_PATTERN.search(content[:500])
        if kw_match:
            keywords = [k.strip().lower() for k in kw_match.group(1).split(",")]
        return KnowledgeEntry(path=path, title=title, content=content, keywords=keywords)

    def search(self, query: str, max_results: int = 3) -> list[KnowledgeEntry]:
        query_words = self._tokenize(query)
        if not query_words:
            return []
        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in self._entries.values():
            score = 0
            search_text = entry.title.lower() + " " + " ".join(entry.keywords)
            search_words = self._tokenize(search_text)
            for qw in query_words:
                if qw in search_words:
                    score += 1
            name_words = self._tokenize(os.path.basename(entry.path).replace(".md", ""))
            for qw in query_words:
                if qw in name_words:
                    score += 1
            for qw in query_words:
                if qw in entry.title.lower():
                    score += 2
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        total_chars = 0
        for _, entry in scored:
            snippet = entry.content[: self.per_entry_cap]
            results.append(entry)
            total_chars += len(snippet)
            if len(results) >= max_results or total_chars >= self.max_tokens * 4:
                break
        return results

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower())
        return {w for w in words if len(w) >= 3 and w not in STOP_WORDS}

    def format_for_prompt(self, entries: list[KnowledgeEntry]) -> str:
        if not entries:
            return ""
        parts = ["<knowledge>"]
        for entry in entries:
            snippet = entry.content[: self.per_entry_cap]
            parts.append(f"<!-- {entry.display_name} -->\n{snippet}")
        parts.append("</knowledge>")
        return "\n\n".join(parts)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def has_entries(self) -> bool:
        return len(self._entries) > 0
