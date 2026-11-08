"""Memory tool - remember and recall across compaction.

Everything here is local: a JSON file per project, retrieved with BM25 so a
keyword is enough. This is the tool for facts that must outlive the transcript:
"the release gate is pytest + ruff + mypy", "do not use 硅片, write 芯片".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.memory_store import get_store
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

ACTIONS = (
    "remember",
    "recall",
    "search",
    "list",
    "forget",
    "tag",
    "link",
    "related",
    "stats",
)


class MemoryInput(BaseModel):
    action: str = Field(
        default="recall",
        description=("remember | recall | search | list | forget | tag | link | related | stats"),
    )
    text: str = Field(
        default="", description="remember: the fact to store; recall/search: the query"
    )
    id: str = Field(default="", description="Target note id for forget/tag/link/related")
    other_id: str = Field(default="", description="link: the second note id")
    tags: list[str] = Field(
        default_factory=list, description="remember/tag: tags to attach or remove"
    )
    kind: str = Field(default="note", description="remember: 'note', 'decision', 'convention'")
    remove: bool = Field(default=False, description="tag: remove the listed tags instead of adding")
    limit: int = Field(default=8, description="Maximum notes to return")


class MemoryTool(Tool):
    """Store and retrieve durable project facts."""

    name = "Memory"
    description = (
        "Long-term notes for this project, stored locally and retrieved by keyword. Use "
        "'remember' for facts that must survive context compaction (commands that work, "
        "decisions and why, naming conventions the user insists on), and 'recall' before "
        "asking the user something they may already have told you. Notes are per project "
        "and persist across sessions."
    )
    input_schema = MemoryInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = str(kwargs.get("action") or "recall").strip().lower()
        if action not in ACTIONS:
            return self._error(ctx, f"Error: action must be one of {', '.join(ACTIONS)}")

        store = get_store(ctx.app_state)
        limit = max(1, min(50, int(kwargs.get("limit") or 8)))

        if action == "stats":
            return self._result(ctx, store.stats())

        if action == "remember":
            text = str(kwargs.get("text") or "")
            tags = [str(tag) for tag in (kwargs.get("tags") or [])]
            try:
                entry = store.remember(text, tags=tags, kind=str(kwargs.get("kind") or "note"))
            except ValueError as exc:
                return self._error(ctx, f"Error: {exc}")
            return self._result(ctx, f"Remembered as {entry.id}: {entry.text}")

        if action in ("recall", "search"):
            query = str(kwargs.get("text") or "").strip()
            if not query:
                return self._error(ctx, "Error: text is required as the query")
            scored = store.search(query, limit=limit)
            if action == "search":
                if not scored:
                    return self._result(ctx, "No matching notes.")
                body = "\n".join(f"{entry.id} {score:.2f} {entry.text}" for entry, score in scored)
                return self._result(ctx, body)
            entries = [entry for entry, _score in scored]
            if not entries:
                return self._result(
                    ctx,
                    f"No memory matches '{query}'. If this is a fact worth keeping, "
                    "store it with action='remember'.",
                )
            return self._result(ctx, store.render(entries))

        if action == "list":
            tag = str(kwargs.get("kind") or "")
            # `kind` doubles as the tag filter here to keep the schema small; a
            # tag that matches a kind name is far more useful than the reverse.
            entries = store.recent(tag=tag, limit=limit)
            if not entries:
                return self._result(ctx, store.stats())
            return self._result(ctx, store.render(entries))

        identifier = str(kwargs.get("id") or "").strip()
        if not identifier:
            return self._error(ctx, f"Error: id is required for action={action}")

        if action == "forget":
            removed = store.forget(identifier)
            if removed is None:
                return self._error(ctx, f"Error: no note with id {identifier}")
            return self._result(ctx, f"Forgot {identifier}.")

        if action == "tag":
            tagged = store.tag(
                identifier,
                [str(tag) for tag in (kwargs.get("tags") or [])],
                remove=bool(kwargs.get("remove")),
            )
            if tagged is None:
                return self._error(ctx, f"Error: no note with id {identifier}")
            return self._result(ctx, f"{tagged.id} tags: {', '.join(tagged.tags) or '(none)'}")

        if action == "link":
            other = str(kwargs.get("other_id") or "").strip()
            if not other:
                return self._error(ctx, "Error: other_id is required for link")
            linked = store.link(identifier, other)
            if linked is None:
                return self._error(ctx, "Error: one of the two ids does not exist")
            return self._result(ctx, f"Linked {identifier} <-> {other}.")

        # related
        neighbours = store.related(identifier)
        if not neighbours:
            return self._result(ctx, f"No notes related to {identifier}.")
        return self._result(ctx, store.render(neighbours))

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(MemoryTool())
