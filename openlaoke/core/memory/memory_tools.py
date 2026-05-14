"""Memory tools for AI agent: store and recall memories."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore
from openlaoke.core.tool import Tool, ToolContext
from openlaoke.types.core_types import ToolResultBlock

logger = logging.getLogger(__name__)


@dataclass
class MemoryToolResult:
    success: bool = True
    message: str = ""
    data: dict[str, Any] | None = None


class MemoryStoreInput(BaseModel):
    content: str = Field(description="The content to store")
    memory_type: str = Field(default="fact", description="Type of memory")
    key: str = Field(default="", description="Optional key for retrieval")
    tags: list[str] | None = Field(default=None, description="Optional tags")
    session_id: str = Field(default="", description="Optional session ID")
    importance: float = Field(default=0.5, description="Importance weight (0.0-1.0)")


class MemoryStoreTool(Tool):
    name = "mem_store"
    description = "Store a memory for cross-session recall. Use to save important findings, decisions, or context."
    input_schema = MemoryStoreInput

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        try:
            content = kwargs.get("content", "")
            memory_type = kwargs.get("memory_type", "fact")
            key = kwargs.get("key", "")
            tags = kwargs.get("tags") or []
            session_id = kwargs.get("session_id", "")
            importance = kwargs.get("importance", 0.5)

            store = SQLiteMemoryStore()
            record = MemoryRecord(
                id=f"mem_{hashlib.md5(f'{content[:50]}{time.time()}'.encode()).hexdigest()[:12]}",
                content=content,
                memory_type=memory_type,
                key=key or f"{memory_type}_{content[:30]}",
                tags=tags,
                source_session=session_id,
                source_tool="mem_store",
                confidence=0.9,
                importance=importance,
            )
            mid = store.store(record)
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Memory stored: {mid}\nType: {memory_type}\nContent: {content[:100]}",
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Failed to store memory: {e}",
                is_error=True,
            )


class MemoryRecallInput(BaseModel):
    query: str = Field(description="Search query for recall")
    limit: int = Field(default=10, description="Max results to return")
    memory_type: str | None = Field(default=None, description="Filter by memory type")
    query_type: str = Field(default="general", description="Query type: general/semantic/timeline")


class MemoryRecallTool(Tool):
    name = "mem_recall"
    description = "Recall memories matching a query. Searches BM25 full-text, vector similarity, and knowledge graph."
    input_schema = MemoryRecallInput

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        try:
            query = kwargs.get("query", "")
            limit = kwargs.get("limit", 10)
            memory_type = kwargs.get("memory_type")
            query_type = kwargs.get("query_type", "general")

            store = SQLiteMemoryStore()
            results = store.hybrid_search(
                query=query,
                limit=limit,
                memory_type=memory_type,
                query_type=query_type,
            )
            if not results:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
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
                tool_use_id=ctx.tool_use_id,
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Failed to recall memories: {e}",
                is_error=True,
            )


class MemoryTimelineInput(BaseModel):
    session_id: str = Field(default="", description="Session ID to filter by")
    event_type: str = Field(default="", description="Filter by event type")
    limit: int = Field(default=20, description="Max events to return")


class MemoryTimelineTool(Tool):
    name = "mem_timeline"
    description = "Query the event timeline for a session. Shows what tools were run and when."
    input_schema = MemoryTimelineInput

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        try:
            session_id = kwargs.get("session_id", "")
            event_type = kwargs.get("event_type", "")
            limit = kwargs.get("limit", 20)

            store = SQLiteMemoryStore()
            events = store.query_timeline(
                session_id=session_id,
                event_type=event_type,
                limit=limit,
            )
            if not events:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content="No timeline events found.",
                )
            lines = [f"Timeline ({len(events)} events):\n"]
            for event in events:
                ts = time.strftime("%H:%M:%S", time.localtime(event.created_at))
                lines.append(f"[{ts}] {event.event_type}: {event.summary}")
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Failed to query timeline: {e}",
                is_error=True,
            )


class MemoryStatsTool(Tool):
    name = "mem_stats"
    description = "Show memory database statistics."

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
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
                tool_use_id=ctx.tool_use_id,
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Failed to get stats: {e}",
                is_error=True,
            )


class MemorySearchInput(BaseModel):
    memory_type: str = Field(default="fact", description="Type of memory to list")
    limit: int = Field(default=20, description="Max results to return")


class MemorySearchTool(Tool):
    name = "mem_search"
    description = "Search memories by type with simple listing."
    input_schema = MemorySearchInput

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        try:
            memory_type = kwargs.get("memory_type", "fact")
            limit = kwargs.get("limit", 20)

            store = SQLiteMemoryStore()
            records = store.get_by_type(memory_type, limit=limit)
            if not records:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
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
                tool_use_id=ctx.tool_use_id,
                content="\n".join(lines),
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
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
