"""Memory searcher for searching across past sessions and memory entries."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openlaoke.core.memory.memory_entry import MemoryEntry


class MemorySearcher:
    def __init__(self) -> None:
        self._session_dir = Path.home() / ".openlaoke" / "sessions"

    def search_sessions(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self._session_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        query_lower = query.lower()
        for session_file in sorted(
            self._session_dir.glob("*.json"), key=os.path.getmtime, reverse=True
        ):
            if len(results) >= limit:
                break
            try:
                with open(session_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            messages = data.get("messages", [])
            matching: list[str] = []
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str) and query_lower in content.lower():
                    matching.append(content[:200])

            if matching:
                results.append(
                    {
                        "session_id": session_file.stem,
                        "model": data.get("session_config", {}).get("model", ""),
                        "matches": matching[:3],
                        "match_count": len(matching),
                    }
                )
        return results

    def search_memories(self, query: str, memories: list[MemoryEntry]) -> list[MemoryEntry]:
        query_lower = query.lower()
        results: list[MemoryEntry] = []
        for entry in memories:
            if query_lower in entry.key.lower() or query_lower in entry.content.lower():
                results.append(entry)
                entry.access()
        return sorted(results, key=lambda e: e.confidence * e.hit_count, reverse=True)
