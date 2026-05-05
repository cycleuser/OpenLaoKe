"""Memory tools for AI agent: store and recall memories.

Provides MCP-style tools that the agent can use to persist and retrieve
cross-session memories. Similar to Rein's rein_store and rein_recall.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore
from openlaoke.types.core_types import ToolResultBlock

logger = logging.getLogger(__name__)


@dataclass
class MemoryToolResult:
    success: bool = True
    message: str = ""
    data: dict[str, Any] | None = None


class MemoryStoreTool:
    name = "mem_store"
    description = "Store a memory for cross-session recall. Use to save important findings, decisions, or context."

    async def call(
        self,
        content: str,
        memory_type: str = "fact",
        key: str = "",
        tags: list[str] | None = None,
        session_id: str = "",
        importance: float = 0.5,
        **kwargs: Any,
    ) -> ToolResultBlock:
        try:
            store = SQLiteMemoryStore()
            record = MemoryRecord(
                id=f"mem_{hashlib.md5(f'{content[:50]}{time.time()}'.encode()).hexdigest()[:12]}",
                content=content,
                memory_type=memory_type,
                key=key or f"{memory_type}_{content[:30]}",
                tags=tags or [],
                source_session=session_id,
                source_tool="mem_store",
                confidence=0.9,
                importance=importance,
            )
            mid = store.store(record)
            return ToolResultBlock(
                tool_use_id="",
                content=f"Memory stored: {mid}\nType: {memory_type}\nContent: {content[:100]}",
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id="",
                content=f"Failed to store memory: {e}",
                is_error=True,
            )


class MemoryRecallTool:
    name = "mem_recall"
    description = "Recall memories matching a query. Searches BM25 full-text, vector similarity, and knowledge graph."

    async def call(
        self,
        query: str,
        limit: int = 10,
        memory_type: str | None = None,
        query_type: str = "general",
        session_id: str = "",
        **kwargs: Any,
    ) -> ToolResultBlock:
        try:
            store = SQLiteMemoryStore()
            results = store.hybrid_search(
                query=query,
                limit=limit,
                memory_type=memory_type,
                query_type=query_type,
            )
            if not results:
                return ToolResultBlock(
                    tool_use_id="",
                    content=f"No memories found for: {query}",
                )
            lines = [f"Found {len(results)} memories for: {query}\n"]
            for i, record in enumerate(results, 1):
                lines.append(
                    f"{i}. [{record.memory_type}] (score: {record.importance:.2f}) {record.content[:150]}"
                )
                if record.tags:
                    lines.append(f"   Tags: {', '.join(record.tags[:5])}")
                if record.source_session:
                    lines.append(f"   Session: {record.source_session[:12]}")
                lines.append("")
            return ToolResultBlock(
                tool_use_id="",
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id="",
                content=f"Failed to recall memories: {e}",
                is_error=True,
            )


class MemoryTimelineTool:
    name = "mem_timeline"
    description = "Query the event timeline for a session. Shows what tools were run and when."

    async def call(
        self,
        session_id: str = "",
        event_type: str = "",
        limit: int = 20,
        **kwargs: Any,
    ) -> ToolResultBlock:
        try:
            store = SQLiteMemoryStore()
            events = store.query_timeline(
                session_id=session_id,
                event_type=event_type,
                limit=limit,
            )
            if not events:
                return ToolResultBlock(
                    tool_use_id="",
                    content="No timeline events found.",
                )
            lines = [f"Timeline ({len(events)} events):\n"]
            for event in events:
                ts = time.strftime("%H:%M:%S", time.localtime(event.created_at))
                lines.append(f"[{ts}] {event.event_type}: {event.summary}")
            return ToolResultBlock(
                tool_use_id="",
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id="",
                content=f"Failed to query timeline: {e}",
                is_error=True,
            )


class MemoryStatsTool:
    name = "mem_stats"
    description = "Show memory database statistics."

    async def call(self, **kwargs: Any) -> ToolResultBlock:
        try:
            store = SQLiteMemoryStore()
            stats = store.get_stats()
            lines = ["Memory Statistics:", ""]
            lines.append(f"Total memories: {stats['total_memories']}")
            lines.append(f"Total concepts: {stats['total_concepts']}")
            lines.append(f"Timeline events: {stats['total_timeline_events']}")
            lines.append(f"Database: {stats['db_path']}")
            if stats["memory_types"]:
                lines.append("\nBy type:")
                for mtype, count in stats["memory_types"].items():
                    lines.append(f"  {mtype}: {count}")
            return ToolResultBlock(
                tool_use_id="",
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id="",
                content=f"Failed to get stats: {e}",
                is_error=True,
            )


class MemorySearchTool:
    name = "mem_search"
    description = "Search memories by type with simple listing."

    async def call(
        self,
        memory_type: str = "fact",
        limit: int = 20,
        **kwargs: Any,
    ) -> ToolResultBlock:
        try:
            store = SQLiteMemoryStore()
            records = store.get_by_type(memory_type, limit=limit)
            if not records:
                return ToolResultBlock(
                    tool_use_id="",
                    content=f"No memories of type '{memory_type}'.",
                )
            lines = [f"Memories of type '{memory_type}' ({len(records)}):\n"]
            for i, record in enumerate(records, 1):
                lines.append(
                    f"{i}. (imp: {record.importance:.2f}, hits: {record.hit_count}) {record.content[:120]}"
                )
                if record.tags:
                    lines.append(f"   Tags: {', '.join(record.tags[:5])}")
                lines.append("")
            return ToolResultBlock(
                tool_use_id="",
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id="",
                content=f"Failed to search memories: {e}",
                is_error=True,
            )


def get_memory_tools() -> list:
    return [
        MemoryStoreTool(),
        MemoryRecallTool(),
        MemoryTimelineTool(),
        MemoryStatsTool(),
        MemorySearchTool(),
    ]
