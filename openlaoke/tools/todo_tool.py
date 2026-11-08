"""Todo tool: the harness-side task list.

Keeping the plan as data rather than prose is what lets the loop wake the model
when it stops early, skip what is genuinely blocked, and refuse an unproven
"done".  Shape follows jcode's todo (docs/HARNESS.md:139, :191) minus the swarm
parts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

STATUS_DESCRIPTION = "'pending' | 'in_progress' | 'done' | 'cancelled'"


class TodoPatch(BaseModel):
    name: str = Field(description="Unique task name; this is the key used to patch it later")
    status: str | None = Field(default=None, description=f"New status. {STATUS_DESCRIPTION}")
    phase: str | None = Field(
        default=None, description="Phase label; phases run in the order given"
    )
    lane: str | None = Field(
        default=None, description="Lane label; lanes inside a phase can run in parallel"
    )
    after: list[str] | None = Field(
        default=None, description="Names of tasks that must be done before this one"
    )
    evidence: str | None = Field(
        default=None,
        description="Required with status='done': the command or check that proved it, with its result",
    )
    outcome: str | None = Field(default=None, description="What you actually found or produced")
    blocked_reason: str | None = Field(
        default=None,
        description="Set when nothing you can do will unblock this task; empty string clears it",
    )
    external_blocker: str | None = Field(
        default=None, description="Something outside this session must happen first"
    )
    rename_to: str | None = Field(default=None, description="Rename this task")
    delete: bool | None = Field(default=None, description="Remove this task")


class TodoInput(BaseModel):
    items: list[TodoPatch] | None = Field(
        default=None, description="Patches to apply, one per task, keyed by 'name'"
    )
    action: str = Field(
        default="merge",
        description="'merge' (default) applies items, 'list' shows the plan, 'clear' empties it",
    )
    detail: bool = Field(default=False, description="list: include counts and blocked reasons")


class TodoTool(Tool):
    """Maintain the session's task list."""

    name = "Todo"
    description = (
        "Track the work as named tasks instead of prose. Call it once at the start with every step "
        "you plan, then patch only the tasks that changed. A task cannot be 'done' without evidence: "
        "name the command or check you ran and what it printed. If a task cannot proceed for a "
        "reason you cannot fix, set blocked_reason so the loop stops nagging about it. While any "
        "task stays open the loop will keep prompting you to continue."
    )
    input_schema = TodoInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        from openlaoke.core.todo_engine import TodoStore

        store = TodoStore(ctx.app_state.todo_state)
        action = str(kwargs.get("action") or "merge")

        if action == "clear":
            store.clear()
            return self._result(ctx, "Task list cleared.")
        if action == "list":
            body = store.render(detail=bool(kwargs.get("detail", False)))
            return self._result(ctx, body)

        patches = kwargs.get("items") or []
        if not patches:
            return self._result(
                ctx,
                "Nothing to do: pass items=[...] or action='list'.\n" + store.render(detail=True),
            )

        normalised: list[dict[str, Any]] = []
        for patch in patches:
            if isinstance(patch, TodoPatch):
                normalised.append(patch.model_dump(exclude_none=True))
            elif isinstance(patch, dict):
                normalised.append({k: v for k, v in patch.items() if v is not None})

        removed = [str(p.get("name")) for p in normalised if p.get("delete")]
        for name in removed:
            store.items = [item for item in store.items if item.name != name]
        normalised = [p for p in normalised if not p.get("delete")]

        touched, warnings = store.apply(normalised) if normalised else ([], [])

        lines = [f"Recorded {len(touched)} task(s)." if touched else "No task changed."]
        if removed:
            lines.append(f"Removed: {', '.join(removed)}")
        lines.extend(f"warning: {warning}" for warning in warnings)
        lines.append(store.render(detail=True))
        return self._result(ctx, "\n".join(lines))

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)


def register(registry: ToolRegistry) -> None:
    registry.register(TodoTool())
