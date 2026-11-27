"""Local project memory with BM25 retrieval.

The point of this store is to survive the thing that loses the most: context
compaction. A fact written here (the build command, the reason a migration was
reverted, the name the user wants used) can be retrieved by keyword later even
after the conversation that produced it is gone.

Retrieval is BM25 over a small tokeniser that handles Chinese by character
bigrams, because a whole-file `len() // 4` style heuristic would make recall
useless for the sessions this is meant for. No embeddings, no network: the store
is a JSON file next to the user's other OpenLaoKe state, keyed by project so two
repositories do not see each other's notes.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".openlaoke", "memory")
MAX_ENTRIES = 2000
DEFAULT_LIMIT = 8

# Who asserted a fact, strongest first. The model writes "agent" notes and
# cannot promote itself: only a human typing ``/memory remember`` produces
# "user", so a model that decides its own guess outranks the user's stated
# preference has no way to record that. Retrieval ranks by this rank before
# it ranks by BM25 score, because relevance is not authority.
AUTHORITY_RANK = {"user": 3, "project": 2, "agent": 1, "imported": 0}
DEFAULT_AUTHORITY = "agent"

_WORD = re.compile(r"[a-z0-9_]+")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "is",
    "it",
    "for",
    "on",
    "with",
    "this",
    "that",
    "be",
    "as",
    "at",
    "by",
    "from",
    "we",
    "you",
    "i",
    "的",
    "了",
    "是",
    "在",
    "和",
    "与",
    "也",
    "就",
    "都",
    "而",
    "及",
    "或",
}


def tokenize(text: str) -> list[str]:
    """Lowercase words plus CJK character bigrams."""
    lowered = text.lower()
    tokens = [word for word in _WORD.findall(lowered) if word not in _STOPWORDS]
    # Mixed alphanumeric runs ("3000ms", "sha256sum") also index their parts, so a
    # query for "3000" or "sha256" matches the way a reader expects.
    for word in list(tokens):
        if word.isalnum() and not word.isdigit() and not word.isalpha():
            tokens.extend(part for part in re.findall(r"[a-z]+|[0-9]+", word) if part)
    for run in _CJK.findall(lowered):
        if len(run) == 1:
            tokens.append(run)
            continue
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


@dataclass
class MemoryEntry:
    id: str
    text: str
    tags: list[str] = field(default_factory=list)
    kind: str = "note"
    links: list[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    uses: int = 0
    authority: str = DEFAULT_AUTHORITY
    # Notes this one replaces, and the note that replaced this one. A superseded
    # note stays on disk (evidence is not deleted) but drops out of retrieval so
    # an old decision cannot outvote the one that cancelled it.
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str = ""

    @property
    def rank(self) -> int:
        return AUTHORITY_RANK.get(self.authority, 0)

    @property
    def superseded(self) -> bool:
        return bool(self.superseded_by)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        known = set(cls.__dataclass_fields__)
        entry = cls(**{key: value for key, value in data.items() if key in known})
        if entry.authority not in AUTHORITY_RANK:
            entry.authority = DEFAULT_AUTHORITY
        return entry


def project_key(cwd: str) -> str:
    normalised = os.path.abspath(cwd)
    digest = hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:16]
    return digest


class MemoryStore:
    """JSON-backed note store with a BM25 index built on demand."""

    def __init__(self, cwd: str, path: str | None = None) -> None:
        self.cwd = os.path.abspath(cwd)
        self.path = path or os.path.join(MEMORY_DIR, f"{project_key(self.cwd)}.json")
        self.entries: list[MemoryEntry] = []
        self._dirty = False
        self._index: dict[str, tuple[dict[str, int], int]] | None = None
        self.load()

    # ── persistence ──────────────────────────────────────────────────────

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return
        raw = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            return
        self.entries = [MemoryEntry.from_dict(item) for item in raw if isinstance(item, dict)]

    def save(self) -> None:
        if not self._dirty:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "version": 1,
            "cwd": self.cwd,
            "saved_at": time.time(),
            "entries": [entry.to_dict() for entry in self.entries],
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self._dirty = False

    # ── writing ──────────────────────────────────────────────────────────

    def remember(
        self,
        text: str,
        tags: list[str] | None = None,
        kind: str = "note",
        authority: str = DEFAULT_AUTHORITY,
        supersedes: list[str] | None = None,
    ) -> MemoryEntry:
        """Store a fact, optionally replacing older notes.

        ``supersedes`` marks the listed notes as replaced instead of deleting
        them: the history of a decision is often worth more than the decision.
        Ids that do not exist are ignored, because a model recalling an id from
        a stale turn should not fail the whole write.
        """
        cleaned = " ".join(text.split())
        if not cleaned:
            raise ValueError("memory text is empty")
        if authority not in AUTHORITY_RANK:
            raise ValueError(f"authority must be one of {', '.join(sorted(AUTHORITY_RANK))}")
        replaced = [identifier for identifier in (supersedes or []) if self.get(identifier)]

        for existing in self.entries:
            if existing.text == cleaned:
                existing.updated_at = time.time()
                if tags:
                    existing.tags = sorted({*existing.tags, *tags})
                # Re-asserting a fact at a higher authority upgrades it; a later
                # "agent" restatement never demotes what the user said.
                if AUTHORITY_RANK[authority] > existing.rank:
                    existing.authority = authority
                self._apply_supersedes(existing, replaced)
                self._dirty = True
                self.save()
                return existing

        now = time.time()
        entry = MemoryEntry(
            id=f"m{int(now * 1000) % 10_000_000:07d}{len(self.entries):03d}",
            text=cleaned,
            tags=sorted(set(tags or [])),
            kind=kind or "note",
            created_at=now,
            updated_at=now,
            authority=authority,
        )
        self._apply_supersedes(entry, replaced)
        self.entries.append(entry)
        if len(self.entries) > MAX_ENTRIES:
            self.entries = self.entries[-MAX_ENTRIES:]
        self._index = None
        self._dirty = True
        self.save()
        return entry

    def _apply_supersedes(self, entry: MemoryEntry, replaced: list[str]) -> None:
        for identifier in replaced:
            if identifier == entry.id:
                continue
            old = self.get(identifier)
            if old is None:
                continue
            old.superseded_by = entry.id
            old.updated_at = time.time()
            if identifier not in entry.supersedes:
                entry.supersedes.append(identifier)

    def forget(self, identifier: str) -> MemoryEntry | None:
        for index, entry in enumerate(self.entries):
            if entry.id == identifier:
                self.entries.pop(index)
                self._index = None
                self._dirty = True
                self.save()
                return entry
        return None

    def tag(self, identifier: str, tags: list[str], remove: bool = False) -> MemoryEntry | None:
        entry = self.get(identifier)
        if entry is None:
            return None
        current = set(entry.tags)
        current = current - set(tags) if remove else current | set(tags)
        entry.tags = sorted(current)
        entry.updated_at = time.time()
        self._dirty = True
        self.save()
        return entry

    def link(self, first: str, second: str) -> tuple[MemoryEntry, MemoryEntry] | None:
        left, right = self.get(first), self.get(second)
        if left is None or right is None:
            return None
        if right.id not in left.links:
            left.links.append(right.id)
        if left.id not in right.links:
            right.links.append(left.id)
        self._dirty = True
        self.save()
        return left, right

    def clear(self) -> int:
        """Drop every note for this project; returns how many were removed."""
        count = len(self.entries)
        self.entries = []
        self._index = None
        self._dirty = True
        self.save()
        return count

    def get(self, identifier: str) -> MemoryEntry | None:
        for entry in self.entries:
            if entry.id == identifier:
                return entry
        return None

    # ── reading ──────────────────────────────────────────────────────────

    def _build_index(self) -> dict[str, tuple[dict[str, int], int]]:
        if self._index is not None:
            return self._index
        index: dict[str, tuple[dict[str, int], int]] = {}
        for entry in self.entries:
            tokens = tokenize(f"{entry.text} {' '.join(entry.tags)}")
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            index[entry.id] = (counts, len(tokens))
        self._index = index
        return index

    def search(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        include_superseded: bool = False,
    ) -> list[tuple[MemoryEntry, float]]:
        """BM25 ranking over the stored notes, grouped by authority first.

        Relevance is not authority: a note the user typed ("always use pytest,
        never unittest") must not be pushed out of the top of the list by an
        agent note that merely repeats the query's words more often. Within one
        authority level the order is still pure BM25.
        """
        query_tokens = tokenize(query)
        if not query_tokens or not self.entries:
            return []

        index = self._build_index()
        total = len(index)
        average_length = sum(length for _counts, length in index.values()) / max(1, total)
        document_frequency: dict[str, int] = {}
        for counts, _length in index.values():
            for token in set(counts):
                document_frequency[token] = document_frequency.get(token, 0) + 1

        k1, b = 1.5, 0.75
        scored: list[tuple[MemoryEntry, float]] = []
        for entry in self.entries:
            if entry.superseded and not include_superseded:
                continue
            counts, length = index[entry.id]
            score = 0.0
            for token in set(query_tokens):
                frequency = counts.get(token, 0)
                if not frequency:
                    continue
                idf = math.log(
                    1
                    + (total - document_frequency.get(token, 0) + 0.5)
                    / (document_frequency.get(token, 0) + 0.5)
                )
                denominator = frequency + k1 * (1 - b + b * length / max(average_length, 1e-9))
                score += idf * frequency * (k1 + 1) / denominator
            if score > 0:
                scored.append((entry, score))

        scored.sort(key=lambda item: (item[0].rank, item[1]), reverse=True)
        return scored[:limit]

    def recall(
        self, query: str, limit: int = DEFAULT_LIMIT, include_superseded: bool = False
    ) -> list[MemoryEntry]:
        results = self.search(query, limit, include_superseded=include_superseded)
        for entry, _score in results:
            entry.uses += 1
        if results:
            self._dirty = True
            self.save()
        return [entry for entry, _score in results]

    def recent(self, tag: str = "", limit: int = 50) -> list[MemoryEntry]:
        entries = self.entries
        if tag:
            entries = [entry for entry in entries if tag in entry.tags]
        return sorted(entries, key=lambda entry: (entry.updated_at, entry.rank), reverse=True)[
            :limit
        ]

    def related(self, identifier: str) -> list[MemoryEntry]:
        entry = self.get(identifier)
        if entry is None:
            return []
        linked = [self.get(link) for link in entry.links]
        found = [item for item in linked if item is not None]
        if found:
            return found
        # No explicit links: fall back to textual neighbours so a first query
        # still returns something useful.
        return [match for match in self.recall(entry.text, limit=4) if match.id != entry.id][:3]

    def render(self, entries: list[MemoryEntry]) -> str:
        if not entries:
            return "Nothing in memory matches."
        lines = []
        for entry in entries:
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            authority = "" if entry.authority == DEFAULT_AUTHORITY else f" <{entry.authority}>"
            replaced = f" superseded by {entry.superseded_by}" if entry.superseded else ""
            supersedes = f" replaces {', '.join(entry.supersedes)}" if entry.supersedes else ""
            lines.append(
                f"{entry.id} ({entry.kind}){tags}{authority}{replaced}{supersedes} {entry.text}"
            )
        return "\n".join(lines)

    def digest(self, query: str = "", limit: int = 12, max_chars: int = 1200) -> str:
        """A compact block for the system prompt, strongest authority first.

        Superseded notes are excluded: the prompt must carry the current fact,
        not the one it replaced. The block shrinks from the weakest end, so a
        tight budget can never crowd out what the user said.
        """
        entries = self.recall(query, limit=limit) if query else self.recent(limit=limit)
        entries = [entry for entry in entries if not entry.superseded]
        entries.sort(key=lambda entry: (entry.rank, entry.updated_at), reverse=True)
        lines: list[str] = []
        used = 0
        for entry in entries:
            marker = "" if entry.authority == DEFAULT_AUTHORITY else f"[{entry.authority}] "
            line = f"- {marker}{entry.text}"
            if used + len(line) + 1 > max_chars:
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)

    def stats(self) -> str:
        if not self.entries:
            return f"Memory is empty ({self.path})."
        tags: dict[str, int] = {}
        for entry in self.entries:
            for tag in entry.tags:
                tags[tag] = tags.get(tag, 0) + 1
        tag_note = ", ".join(f"{tag}×{count}" for tag, count in sorted(tags.items())[:12])
        authorities: dict[str, int] = {}
        for entry in self.entries:
            authorities[entry.authority] = authorities.get(entry.authority, 0) + 1
        superseded = sum(1 for entry in self.entries if entry.superseded)
        authority_note = ", ".join(
            f"{name}×{count}"
            for name, count in sorted(
                authorities.items(),
                key=lambda item: (-item[1], -AUTHORITY_RANK.get(item[0], 0)),
            )
        )
        return (
            f"{len(self.entries)} note(s) in {self.path}"
            + (f"\ntags: {tag_note}" if tag_note else "")
            + (f"\nauthority: {authority_note}" if authority_note else "")
            + (f"\nsuperseded: {superseded}" if superseded else "")
        )


def get_store(app_state: Any) -> MemoryStore:
    """One store per session, cached on the state."""
    existing = getattr(app_state, "_memory_store", None)
    if isinstance(existing, MemoryStore):
        return existing
    store = MemoryStore(app_state.get_cwd())
    app_state._memory_store = store
    return store
