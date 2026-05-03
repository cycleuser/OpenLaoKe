"""MemoryManager - unified memory system for OpenLaoKe.

Integrates MemoryStore, MemoryNudger, and MemorySearcher into a single API.
Similar to Hermes agent's MEMORY.md approach.
"""

from __future__ import annotations

import logging
from typing import Any

from openlaoke.core.memory.memory_entry import MemoryEntry, MemoryType
from openlaoke.core.memory.memory_nudger import MemoryNudger
from openlaoke.core.memory.memory_searcher import MemorySearcher
from openlaoke.core.memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryManager:
    _instance: MemoryManager | None = None

    def __new__(cls) -> MemoryManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = MemoryStore()
            cls._instance._nudger = MemoryNudger()
            cls._instance._searcher = MemorySearcher()
            cls._instance._loaded = False
            cls._instance._recent_failures: list[str] = []
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

        if tool_error:
            self._recent_failures.append(tool_error)
            if len(self._recent_failures) > 10:
                self._recent_failures = self._recent_failures[-10:]
            repeated = self._nudger.analyze_repeated_pattern(
                self._recent_failures, session_id
            )
            if repeated:
                self._store.add(repeated)
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
        self._recent_failures.append(f"{tool_name}: {error}")
        self.save()

    def inject_into_system_prompt(self, max_chars: int = 2000) -> str:
        self.load()
        return self._store.format_for_system_prompt(max_chars)

    def search(self, query: str) -> dict[str, Any]:
        self.load()
        memories = self._store.search(query)
        sessions = self._searcher.search_sessions(query)
        return {
            "memories": [m.to_dict() for m in memories[:10]],
            "sessions": sessions[:5],
        }

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
        self.save()
        return entry

    def clear(self) -> None:
        self._store = MemoryStore()
        self._store.save()
        self._recent_failures = []


def get_memory_manager() -> MemoryManager:
    return MemoryManager()
