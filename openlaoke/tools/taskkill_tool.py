"""Taskkill tool - kill running tasks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class TaskKillInput(BaseModel):
    task_id: str = Field(description="ID of the task to kill")


class TaskKillTool(Tool):
    """Kill a running task."""

    name = "Taskkill"
    description = "Kill a running task by its ID."
    input_schema = TaskKillInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        task_id = kwargs.get("task_id", "")

        if not task_id:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: task_id is required",
                is_error=True,
            )

        state = ctx.app_state.get_task(task_id)
        if not state:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Task not found: {task_id}",
                is_error=True,
            )

        if state.status in ("completed", "failed", "killed"):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Task {task_id} is already in terminal state: {state.status}",
                is_error=False,
            )

        from openlaoke.core.task import TaskManager
        task_mgr = TaskManager(ctx.app_state)
        task_mgr.kill_task(task_id)

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Task {task_id} ({state.type.value}) has been killed.",
            is_error=False,
        )


def register(registry: ToolRegistry) -> None:
    registry.register(TaskKillTool())
