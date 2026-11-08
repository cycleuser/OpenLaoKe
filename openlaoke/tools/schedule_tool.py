"""Schedule tool - reminders and recurring local jobs.

Three forms only: ``every 30m``, ``daily 09:00``, and ``2026-11-09T08:30`` for a
single run. An entry either queues a prompt for the model (a reminder to check
something) or runs a shell command in the background.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.scheduler import ScheduleError, get_scheduler
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

ACTIONS = ("add", "list", "cancel", "pause", "resume", "run")


class ScheduleInput(BaseModel):
    action: str = Field(default="list", description="add | list | cancel | pause | resume | run")
    name: str = Field(
        default="", description="add: a short label; other actions: also accept the id"
    )
    when: str = Field(
        default="",
        description="add: 'every 30m', 'daily 09:00', or '2026-11-09T08:30' (one run)",
    )
    prompt: str = Field(default="", description="add: text to queue for the model when it fires")
    command: str = Field(
        default="", description="add: shell command to run in the background instead"
    )
    id: str = Field(default="", description="cancel/pause/resume/run: entry id or name")


class ScheduleTool(Tool):
    """Maintain the local schedule."""

    name = "Schedule"
    description = (
        "Schedule a recurring reminder or job. 'every 30m', 'daily 09:00' and one-shot "
        "'2026-11-09T08:30' are the only forms. An entry either queues a prompt for you "
        "(delivered at the next turn) or runs a shell command in the background. Nothing "
        "fires while the session is closed."
    )
    input_schema = ScheduleInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = str(kwargs.get("action") or "list").strip().lower()
        if action not in ACTIONS:
            return self._error(ctx, f"Error: action must be one of {', '.join(ACTIONS)}")

        scheduler = get_scheduler(ctx.app_state)

        if action == "list":
            return self._result(ctx, scheduler.render())

        if action == "add":
            try:
                entry = scheduler.add(
                    name=str(kwargs.get("name") or ""),
                    when=str(kwargs.get("when") or ""),
                    prompt=str(kwargs.get("prompt") or ""),
                    command=str(kwargs.get("command") or ""),
                )
            except ScheduleError as exc:
                return self._error(ctx, f"Error: {exc}")
            return self._result(ctx, f"Added {entry.id} ({entry.when}).\n{scheduler.render()}")

        identifier = str(kwargs.get("id") or kwargs.get("name") or "").strip()
        if not identifier:
            return self._error(ctx, f"Error: id is required for action={action}")

        if action == "cancel":
            if not scheduler.cancel(identifier):
                return self._error(ctx, f"Error: no schedule matching {identifier}")
            return self._result(ctx, f"Cancelled {identifier}.\n{scheduler.render()}")

        if action in ("pause", "resume"):
            toggled = scheduler.set_enabled(identifier, action == "resume")
            if toggled is None:
                return self._error(ctx, f"Error: no schedule matching {identifier}")
            return self._result(ctx, f"{toggled.id} is now {'on' if toggled.enabled else 'off'}.")

        # run it now, regardless of its next_run
        target = scheduler.get(identifier)
        if target is None:
            return self._error(ctx, f"Error: no schedule matching {identifier}")
        target.next_run = 0.0
        scheduler.save()
        return self._result(
            ctx,
            f"{target.id} marked due; it runs on the next scheduler tick "
            f"({'prompt' if target.prompt else 'command'}).",
        )

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(ScheduleTool())
