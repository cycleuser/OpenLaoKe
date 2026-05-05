"""Persistent memory store with JSON backend and MEMORY.md export."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from openlaoke.core.memory.memory_entry import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)

MEMORY_DIR = Path.home() / ".openlaoke" / "memory"
MEMORY_JSON = MEMORY_DIR / "memory.json"
MEMORY_MD = MEMORY_DIR / "MEMORY.md"
MAX_MEMORIES = 200


class MemoryStore:
    def __init__(self) -> None:
        self._memories: dict[str, MemoryEntry] = {}
        self._dirty = False

    def load(self) -> None:
        if not MEMORY_JSON.exists():
            return
        try:
            with open(MEMORY_JSON, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    entry = MemoryEntry.from_dict(item)
                    entry.decay()
                    self._memories[entry.id] = entry
            self._cleanup_low_confidence()
        except Exception:
            logger.warning("Failed to load memories", exc_info=True)

    def save(self) -> None:
        if not self._dirty:
            return
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = [m.to_dict() for m in self._memories.values()]
        with open(MEMORY_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._export_markdown()
        self._dirty = False

    def add(self, entry: MemoryEntry) -> None:
        existing = self._find_similar(entry.key, entry.content)
        if existing:
            existing.content = entry.content
            existing.confidence = min(1.0, existing.confidence + 0.2)
            existing.hit_count += 1
            existing.last_accessed = time.time()
        elif len(self._memories) < MAX_MEMORIES:
            self._memories[entry.id] = entry
        else:
            self._evict_lowest()
            self._memories[entry.id] = entry
        self._dirty = True

    def get(self, entry_id: str) -> MemoryEntry | None:
        entry = self._memories.get(entry_id)
        if entry:
            entry.access()
            self._dirty = True
        return entry

    def search(self, query: str, memory_type: MemoryType | None = None) -> list[MemoryEntry]:
        results: list[MemoryEntry] = []
        query_lower = query.lower()
        for entry in self._memories.values():
            if memory_type and entry.memory_type != memory_type:
                continue
            if query_lower in entry.key.lower() or query_lower in entry.content.lower():
                results.append(entry)
                entry.access()
        results.sort(key=lambda e: e.confidence * e.hit_count, reverse=True)
        self._dirty = bool(results)
        return results

    def get_by_type(self, memory_type: MemoryType) -> list[MemoryEntry]:
        results = [e for e in self._memories.values() if e.memory_type == memory_type]
        return sorted(results, key=lambda e: e.confidence, reverse=True)

    def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        sorted_entries = sorted(
            self._memories.values(), key=lambda e: e.last_accessed, reverse=True
        )
        return sorted_entries[:limit]

    def remove(self, entry_id: str) -> bool:
        if entry_id in self._memories:
            del self._memories[entry_id]
            self._dirty = True
            return True
        return False

    def format_for_system_prompt(self, max_chars: int = 2000) -> str:
        relevant = sorted(
            self._memories.values(),
            key=lambda e: e.confidence * (e.hit_count + 1),
            reverse=True,
        )
        lines: list[str] = ["## User Memory"]
        char_count = 0
        for entry in relevant:
            line = f"- [{entry.memory_type.upper()}] {entry.content}"
            if char_count + len(line) > max_chars:
                break
            lines.append(line)
            char_count += len(line)
        return "\n".join(lines)

    def _find_similar(self, key: str, content: str) -> MemoryEntry | None:
        for entry in self._memories.values():
            if entry.key.lower() == key.lower():
                return entry
            if content[:50].lower() == entry.content[:50].lower():
                return entry
        return None

    def _cleanup_low_confidence(self) -> None:
        to_remove = [mid for mid, entry in self._memories.items() if entry.confidence < 0.15]
        for mid in to_remove:
            del self._memories[mid]

    def _evict_lowest(self) -> None:
        if not self._memories:
            return
        lowest = min(self._memories.values(), key=lambda e: e.confidence * (e.hit_count + 1))
        del self._memories[lowest.id]

    def _export_markdown(self) -> None:
        lines = [
            "# OpenLaoKe Memory",
            f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        for mtype in MemoryType:
            entries = self.get_by_type(mtype)
            if not entries:
                continue
            lines.append(f"## {mtype.title()}")
            for entry in entries:
                conf = f" [{entry.confidence:.0%}]" if entry.confidence < 1.0 else ""
                hits = f" (×{entry.hit_count})" if entry.hit_count > 1 else ""
                lines.append(f"- {entry.content}{conf}{hits}")
            lines.append("")
        with open(MEMORY_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
