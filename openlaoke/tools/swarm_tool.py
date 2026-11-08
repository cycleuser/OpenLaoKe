"""Swarm tool - run workers on separate lanes and read the shared board."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.swarm import MAX_MEMBERS, get_swarm
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

ACTIONS = ("start", "status", "await", "messages", "note", "cancel")


class SwarmTask(BaseModel):
    name: str = Field(description="Lane name, short and unique")
    prompt: str = Field(description="What this worker should do; it gets its own context")


class SwarmInput(BaseModel):
    action: str = Field(
        default="status", description="start | status | await | messages | note | cancel"
    )
    tasks: list[SwarmTask] = Field(
        default_factory=list, description="start: 1-6 workers, each with a name and a prompt"
    )
    ids: list[str] = Field(
        default_factory=list, description="await/cancel: worker ids or names; empty means all"
    )
    text: str = Field(default="", description="note: message for the board")
    timeout: float = Field(default=120.0, description="await: seconds to wait")
    limit: int = Field(default=20, description="messages: how many to show")


class SwarmTool(Tool):
    """Coordinate several sub-agents."""

    name = "Swarm"
    description = (
        "Run up to 6 workers in parallel, each with its own context, then collect their "
        "results. 'start' returns immediately with worker ids; 'await' blocks until they "
        "finish; 'status' shows state, results and which files each lane touched; "
        "'note'/'messages' are a shared board; 'cancel' stops the rest. Workers share the "
        "filesystem, so two lanes editing one file is a coordination mistake - check "
        "'status' for the touch ledger before merging results."
    )
    input_schema = SwarmInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = str(kwargs.get("action") or "status").strip().lower()
        if action not in ACTIONS:
            return self._error(ctx, f"Error: action must be one of {', '.join(ACTIONS)}")

        swarm = get_swarm(ctx.app_state)

        if action == "start":
            raw = kwargs.get("tasks") or []
            tasks = [
                {
                    "name": str(
                        item.get("name") if isinstance(item, dict) else getattr(item, "name", "")
                    ),
                    "prompt": str(
                        item.get("prompt")
                        if isinstance(item, dict)
                        else getattr(item, "prompt", "")
                    ),
                }
                for item in raw
            ]
            try:
                members = swarm.start(tasks)
            except ValueError as exc:
                return self._error(ctx, f"Error: {exc}")
            id_list = ", ".join(member.id for member in members)
            return self._result(
                ctx,
                f"Started {len(members)} worker(s): {id_list}. "
                "Use action='await' to collect them, or action='status' to watch.",
            )

        if action == "status":
            return self._result(ctx, swarm.render())

        if action == "await":
            ids = [str(item) for item in (kwargs.get("ids") or [])]
            timeout = kwargs.get("timeout")
            members, finished = await swarm.await_members(
                ids or None, timeout=float(timeout) if timeout else None
            )
            if not members:
                return self._result(ctx, "No workers to wait for.")
            if finished:
                return self._result(ctx, "All workers finished.\n\n" + swarm.report())
            return self._result(
                ctx, "Still running when the wait ended; check action='status'.\n" + swarm.render()
            )

        if action == "messages":
            limit = max(1, min(200, int(kwargs.get("limit") or 20)))
            body = swarm.board.render_messages(limit)
            return self._result(ctx, body + "\n\nTouched files:\n" + swarm.board.render_touched())

        if action == "note":
            text = str(kwargs.get("text") or "").strip()
            if not text:
                return self._error(ctx, "Error: text is required for note")
            swarm.board.post(text)
            return self._result(ctx, "Posted to the board.")

        cancelled = await swarm.cancel([str(item) for item in (kwargs.get("ids") or [])] or None)
        return self._result(ctx, f"Cancelled {cancelled} worker(s).\n" + swarm.render())

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(SwarmTool())


__all__ = ["SwarmTool", "MAX_MEMBERS", "register"]
