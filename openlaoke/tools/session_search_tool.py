"""SessionSearch and ConversationSearch tools.

Two scopes, one implementation: the saved sessions on disk, and the messages of
the running conversation. Both are BM25 over the same tokeniser, so the answer
does not depend on whether the text was compacted out of context or written in a
session from last week.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class SessionSearchInput(BaseModel):
    query: str = Field(description="What to look for; keywords are enough")
    limit: int = Field(default=8, description="Maximum hits")
    days: float = Field(default=0, description="Only sessions touched in the last N days; 0 means all")
    cwd: str = Field(default="", description="Only sessions started in this directory; empty means all")
    role: str = Field(default="", description="Only messages from this role ('user' or 'assistant')")


class SessionSearchTool(Tool):
    """Search every saved session."""

    name = "SessionSearch"
    description = (
        "Search the saved sessions on this machine for something that was discussed before, "
        "including sessions from other days. Returns the session id, message index, role, time "
        "and a snippet. Use it when the user refers to earlier work you cannot see."
    )
    input_schema = SessionSearchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        from openlaoke.core.session_index import SESSIONS_DIR, search_sessions

        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content="Error: query is required", is_error=True
            )
        limit = max(1, min(50, int(kwargs.get("limit") or 8)))
        hits = search_sessions(
            query,
            sessions_dir=SESSIONS_DIR,
            limit=limit,
            days=float(kwargs.get("days") or 0),
            cwd=str(kwargs.get("cwd") or ""),
            role=str(kwargs.get("role") or ""),
        )
        if not hits:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No session messages match '{query}'.",
            )
        body = "\n\n".join(hit.line() for hit in hits)
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id, content=f"{len(hits)} hit(s):\n\n{body}"
        )


class ConversationSearchInput(BaseModel):
    query: str = Field(description="What to look for in this conversation")
    limit: int = Field(default=8, description="Maximum hits")


class ConversationSearchTool(Tool):
    """Search the running conversation."""

    name = "ConversationSearch"
    description = (
        "Search this conversation, including messages that context compaction removed from "
        "what you can currently see. Use it before asking the user to repeat something they "
        "already said."
    )
    input_schema = ConversationSearchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        from openlaoke.core.session_index import search_conversation

        query = str(kwargs.get("query") or "").strip()
        if not query:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content="Error: query is required", is_error=True
            )
        limit = max(1, min(50, int(kwargs.get("limit") or 8)))
        hits = search_conversation(query, ctx.app_state.messages, limit=limit)
        if not hits:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No message in this conversation matches '{query}'.",
            )
        body = "\n\n".join(hit.line().replace("current #", "#") for hit in hits)
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id, content=f"{len(hits)} hit(s) in this conversation:\n\n{body}"
        )


def register(registry: ToolRegistry) -> None:
    registry.register(SessionSearchTool())
    registry.register(ConversationSearchTool())
