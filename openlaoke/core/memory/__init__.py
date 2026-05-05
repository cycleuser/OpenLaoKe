"""MemoryManager - unified memory system for OpenLaoKe.

Integrates MemoryStore, MemoryNudger, MemorySearcher, and SQLite-based
long-term memory with FTS5, jieba tokenization, three-channel retrieval,
knowledge graph, and timeline events.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from openlaoke.core.memory.memory_entry import MemoryEntry, MemoryType
from openlaoke.core.memory.memory_nudger import MemoryNudger
from openlaoke.core.memory.memory_searcher import MemorySearcher
from openlaoke.core.memory.memory_store import MemoryStore
from openlaoke.core.memory.sqlite_store import (
    MemoryRecord,
    SQLiteMemoryStore,
    TimelineEvent,
)

__all__ = [
    "MemoryManager",
    "get_memory_manager",
    "MemoryRecord",
    "SQLiteMemoryStore",
    "TimelineEvent",
    "MemoryEntry",
    "MemoryType",
]

logger = logging.getLogger(__name__)


class MemoryManager:
    _instance: MemoryManager | None = None
    _store: MemoryStore
    _nudger: MemoryNudger
    _searcher: MemorySearcher
    _sqlite: SQLiteMemoryStore
    _loaded: bool
    _recent_failures: list[str]

    def __new__(cls) -> MemoryManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = MemoryStore()
            cls._instance._nudger = MemoryNudger()
            cls._instance._searcher = MemorySearcher()
            cls._instance._sqlite = SQLiteMemoryStore()
            cls._instance._loaded = False
            cls._instance._recent_failures = []
        return cls._instance

    def load(self) -> None:
        if self._loaded:
            return
        self._store.load()
        self._loaded = True

    def save(self) -> None:
        self._store.save()

    def on_user_message(
        self,
        content: str,
        session_id: str = "",
        tool_error: str | None = None,
    ) -> list[MemoryEntry]:
        self.load()
        entries = self._nudger.analyze(content, tool_error, session_id)
        for entry in entries:
            self._store.add(entry)
            self._store_sqlite_entry(entry, session_id)

        if tool_error:
            self._recent_failures.append(tool_error)
            if len(self._recent_failures) > 10:
                self._recent_failures = self._recent_failures[-10:]
            repeated = self._nudger.analyze_repeated_pattern(self._recent_failures, session_id)
            if repeated:
                self._store.add(repeated)
                self._store_sqlite_entry(repeated, session_id)
                entries.append(repeated)

        self.save()
        return entries

    def on_tool_error(self, tool_name: str, error: str, session_id: str = "") -> None:
        self.load()
        entry = MemoryEntry(
            memory_type=MemoryType.LESSON,
            key=f"tool_{tool_name}_error",
            content=f"{tool_name} failed: {error[:200]}",
            trigger="tool_execution_failed",
            source_session=session_id,
        )
        self._store.add(entry)
        self._store_sqlite_entry(entry, session_id)
        self._recent_failures.append(f"{tool_name}: {error}")
        self.save()

    def _store_sqlite_entry(self, entry: MemoryEntry, session_id: str = "") -> None:
        try:
            record = MemoryRecord(
                id=entry.id,
                content=entry.content,
                memory_type=str(entry.memory_type),
                key=entry.key,
                tags=entry.tags,
                source_session=entry.source_session or session_id,
                confidence=entry.confidence,
                importance=0.8
                if entry.memory_type in (MemoryType.CORRECTION, MemoryType.LESSON)
                else 0.5,
                metadata={
                    "trigger": entry.trigger,
                    "hit_count": entry.hit_count,
                },
            )
            self._sqlite.store(record)
        except Exception as e:
            logger.debug(f"Failed to store entry in SQLite: {e}")

    def inject_into_system_prompt(self, max_chars: int = 2000) -> str:
        self.load()
        legacy = self._store.format_for_system_prompt(max_chars // 2)
        try:
            recent = self._sqlite.get_recent(5)
            lines = ["## Recent Context"]
            remaining = max_chars - len(legacy) - 50
            for record in recent:
                line = f"- [{record.memory_type}] {record.content[:100]}"
                if len("\n".join(lines)) + len(line) > remaining:
                    break
                lines.append(line)
            sqlite_part = "\n".join(lines)
        except Exception:
            sqlite_part = ""
        return f"{legacy}\n\n{sqlite_part}".strip()

    def search(self, query: str) -> dict[str, Any]:
        self.load()
        memories = self._store.search(query)
        sessions = self._searcher.search_sessions(query)
        try:
            sqlite_results = self._sqlite.hybrid_search(query, limit=10)
            sqlite_memories = [
                {
                    "id": r.id,
                    "memory_type": r.memory_type,
                    "content": r.content,
                    "confidence": r.confidence,
                    "hit_count": r.hit_count,
                    "tags": r.tags,
                    "score": r.importance,
                }
                for r in sqlite_results
            ]
        except Exception:
            sqlite_memories = []
        return {
            "memories": [m.to_dict() for m in memories[:10]],
            "sqlite_memories": sqlite_memories,
            "sessions": sessions[:5],
        }

    def recall(
        self, query: str, limit: int = 10, memory_type: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            results = self._sqlite.hybrid_search(query, limit=limit, memory_type=memory_type)
            return [
                {
                    "id": r.id,
                    "memory_type": r.memory_type,
                    "content": r.content,
                    "tags": r.tags,
                    "score": r.importance,
                    "source_session": r.source_session,
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Recall failed: {e}")
            return []

    def store(
        self,
        content: str,
        memory_type: str = "fact",
        key: str = "",
        tags: list[str] | None = None,
        session_id: str = "",
    ) -> str:
        try:
            record = MemoryRecord(
                id=f"mem_{hashlib.md5(f'{content[:50]}{time.time()}'.encode()).hexdigest()[:12]}",
                content=content,
                memory_type=memory_type,
                key=key or f"{memory_type}_{content[:30]}",
                tags=tags or [],
                source_session=session_id,
                confidence=0.9,
                importance=0.7,
            )
            return self._sqlite.store(record)
        except Exception as e:
            logger.warning(f"Store failed: {e}")
            return ""

    def get_timeline(self, session_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        try:
            events = self._sqlite.query_timeline(session_id=session_id, limit=limit)
            return [e.to_dict() for e in events]
        except Exception:
            return []

    def get_stats(self) -> dict[str, Any]:
        try:
            return self._sqlite.get_stats()
        except Exception:
            return {"error": "Failed to get stats"}

    def get_corrections(self) -> list[MemoryEntry]:
        self.load()
        return self._store.get_by_type(MemoryType.CORRECTION)

    def get_preferences(self) -> list[MemoryEntry]:
        self.load()
        return self._store.get_by_type(MemoryType.PREFERENCE)

    def get_lessons(self) -> list[MemoryEntry]:
        self.load()
        return self._store.get_by_type(MemoryType.LESSON)

    def add_correction(self, content: str, session_id: str = "") -> MemoryEntry:
        self.load()
        entry = MemoryEntry(
            memory_type=MemoryType.CORRECTION,
            key=f"correction_{len(self.get_corrections())}",
            content=content,
            trigger="explicit_add",
            source_session=session_id,
        )
        self._store.add(entry)
        self._store_sqlite_entry(entry, session_id)
        self.save()
        return entry

    def clear(self) -> None:
        self._store = MemoryStore()
        self._store.save()
        self._recent_failures = []


def get_memory_manager() -> MemoryManager:
    return MemoryManager()
