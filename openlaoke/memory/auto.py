"""Per-project auto-memory store.

One fact per file, with a YAML frontmatter header. ``MEMORY.md`` is the
index file that loads into the cache-stable prefix. Facts reference
each other via ``[[name]]`` wikilinks.

Types:
* ``user`` — about the user
* ``feedback`` — explicit feedback
* ``project`` — about the project
* ``reference`` — external references
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FactType(StrEnum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Fact:
    """A single auto-memory fact stored as its own Markdown file."""

    fact_id: str
    name: str
    type: FactType
    body: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    references: list[str] = field(default_factory=list)
    path: str = ""

    def one_line(self) -> str:
        first = (self.body or "").splitlines()
        first = first[0] if first else ""
        if len(first) > 120:
            first = first[:117] + "..."
        return f"- **{self.name}**: {first}"


def _new_id() -> str:
    return f"fact_{uuid.uuid4().hex[:8]}"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "untitled"


def _serialize(fact: Fact) -> str:
    refs = "\n".join(f"- [[{r}]]" for r in fact.references)
    body = fact.body.rstrip()
    if refs:
        body = f"{body}\n\n## References\n\n{refs}"
    front = (
        f"---\n"
        f"id: {fact.fact_id}\n"
        f"name: {fact.name}\n"
        f"type: {fact.type.value}\n"
        f"created_at: {fact.created_at}\n"
        f"updated_at: {fact.updated_at}\n"
        f"---\n\n"
    )
    return front + body


def _deserialize(text: str, path: str = "") -> Fact | None:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        import yaml

        meta = yaml.safe_load(match.group(1)) or {}
        body = match.group(2)
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    try:
        ftype = FactType(meta.get("type", "project"))
    except ValueError:
        ftype = FactType.PROJECT
    refs = re.findall(r"\[\[([^\]]+)\]\]", body)
    return Fact(
        fact_id=str(meta.get("id") or _new_id()),
        name=str(meta.get("name") or Path(path).stem if path else "untitled"),
        type=ftype,
        body=body,
        created_at=float(meta.get("created_at", 0.0) or 0.0),
        updated_at=float(meta.get("updated_at", 0.0) or 0.0),
        references=refs,
        path=path,
    )


class AutoMemoryStore:
    """Disk-backed auto-memory store."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root) if root else Path(os.path.expanduser("~/.openlaoke/memory"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "MEMORY.md"

    def _fact_path(self, fact_id: str) -> Path:
        return self.root / f"{fact_id}.md"

    def add(
        self,
        name: str,
        body: str,
        type: FactType = FactType.PROJECT,
        references: list[str] | None = None,
    ) -> Fact:
        fact = Fact(
            fact_id=_new_id(),
            name=name,
            type=type,
            body=body,
            references=references or [],
        )
        self._write(fact)
        self._reindex()
        return fact

    def update(self, fact_id: str, **changes: Any) -> Fact | None:
        path = self._fact_path(fact_id)
        if not path.exists():
            return None
        fact = _deserialize(path.read_text(encoding="utf-8"), str(path))
        if fact is None:
            return None
        for key, value in changes.items():
            if hasattr(fact, key):
                setattr(fact, key, value)
        fact.updated_at = time.time()
        self._write(fact)
        self._reindex()
        return fact

    def get(self, fact_id: str) -> Fact | None:
        path = self._fact_path(fact_id)
        if not path.exists():
            return None
        return _deserialize(path.read_text(encoding="utf-8"), str(path))

    def list_facts(self) -> list[Fact]:
        facts: list[Fact] = []
        for path in sorted(self.root.glob("fact_*.md")):
            fact = _deserialize(path.read_text(encoding="utf-8"), str(path))
            if fact is not None:
                facts.append(fact)
        return facts

    def delete(self, fact_id: str) -> bool:
        path = self._fact_path(fact_id)
        if not path.exists():
            return False
        path.unlink()
        self._reindex()
        return True

    def index_text(self) -> str:
        """Return the cache-stable index content (one line per fact)."""
        if not self._index_path.exists():
            self._reindex()
        if not self._index_path.exists():
            return ""
        return self._index_path.read_text(encoding="utf-8")

    def _write(self, fact: Fact) -> None:
        path = self._fact_path(fact.fact_id)
        path.write_text(_serialize(fact), encoding="utf-8")
        fact.path = str(path)

    def _reindex(self) -> None:
        facts = self.list_facts()
        if not facts:
            if self._index_path.exists():
                self._index_path.unlink()
            return
        lines = ["# Memory Index", ""]
        for fact in facts:
            lines.append(fact.one_line())
        self._index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def search(self, query: str, limit: int = 5) -> list[Fact]:
        """Full-text keyword search across all facts.

        Scores each fact by how many query words appear in its name + body.
        Returns top matches sorted by score descending.
        """
        if not query.strip():
            return []
        terms = query.lower().split()
        scored: list[tuple[float, Fact]] = []
        for fact in self.list_facts():
            text = (fact.name + " " + fact.body).lower()
            score = sum(1.0 for t in terms if t in text)
            if score > 0:
                bonus = 2.0 if any(t in fact.name.lower() for t in terms) else 0
                scored.append((score + bonus, fact))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored[:limit]]


def quick_add(
    store: AutoMemoryStore,
    text: str,
    type: FactType = FactType.PROJECT,
) -> Fact:
    """Parse ``text`` of the form ``name: body`` and add it as a fact."""
    if ":" in text:
        name, _, body = text.partition(":")
        name = name.strip()
        body = body.strip()
    else:
        name = _slugify(text[:32])
        body = text.strip()
    return store.add(name=name or "untitled", body=body, type=type)
