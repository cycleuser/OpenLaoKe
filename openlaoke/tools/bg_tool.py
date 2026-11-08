"""Bg tool - drive tasks the harness started.

`Bash` hands a slow command to the background after a few seconds, and this is
how that command is read or stopped afterwards.  The log lives in a file, so
`tail` is cheap regardless of how much the job has printed, and `output` can
resume from a character offset the model already saw instead of re-reading the
whole thing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.task import get_task_manager
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock, is_terminal_task_status

ACTIONS = ("list", "status", "output", "tail", "wait", "watch", "cancel")


class BgInput(BaseModel):
    action: str = Field(
        default="list",
        description=(
            "'list' (default) shows tasks; 'status' one task; 'output' reads from an offset; "
            "'tail' reads the last lines; 'wait' blocks until it ends; 'watch' waits a while "
            "and returns what was printed since; 'cancel' stops it"
        ),
    )
    task_id: str = Field(default="", description="Task id from Bash or a previous Bg call")
    lines: int = Field(default=40, description="tail: number of trailing lines")
    offset: int = Field(default=0, description="output: character offset to resume from")
    limit: int = Field(default=20000, description="output: maximum characters to return")
    timeout: float = Field(
        default=60.0, description="wait: seconds to wait; watch: seconds before returning"
    )


class BgTool(Tool):
    """Read, wait on, or cancel a background task."""

    name = "Bg"
    description = (
        "Manage tasks that are running in the background - usually a Bash command that "
        "overran and was moved back there. action='list' shows them, 'tail' shows recent "
        "output, 'wait' blocks until the task ends, 'watch' returns after a while with what "
        "was printed since, 'cancel' stops it. Prefer 'wait' or 'watch' over polling 'tail' "
        "in a loop."
    )
    input_schema = BgInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = str(kwargs.get("action") or "list").strip().lower()
        if action not in ACTIONS:
            return self._error(ctx, f"Error: action must be one of {', '.join(ACTIONS)}")

        manager = get_task_manager(ctx.app_state)

        if action == "list":
            return self._list(ctx)

        task_id = str(kwargs.get("task_id") or "").strip()
        if not task_id:
            return self._error(ctx, "Error: task_id is required for this action")

        state = ctx.app_state.get_task(task_id)
        if state is None:
            return self._error(ctx, f"Error: no task {task_id}. Use action='list' to see ids.")

        if action == "status":
            return self._result(ctx, self._describe(state))

        if action == "tail":
            lines = max(1, int(kwargs.get("lines") or 40))
            tail = manager.tail_output(state, lines)
            body = tail if tail.strip() else "(no output yet)"
            return self._result(ctx, f"{self._describe(state)}\n\n{body}")

        if action == "output":
            offset = max(0, int(kwargs.get("offset") or 0))
            limit = max(1, int(kwargs.get("limit") or 20000))
            chunk = manager.read_output(state, offset=offset, limit=limit)
            end = offset + len(chunk)
            header = f"{self._describe(state)}\n\n[chars {offset}-{end} of {state.output_offset}]"
            return self._result(ctx, f"{header}\n{chunk or '(no output yet)'}")

        if action == "wait":
            timeout = kwargs.get("timeout")
            await manager.wait_for(task_id, timeout=float(timeout) if timeout is not None else None)
            state = ctx.app_state.get_task(task_id) or state
            tail = manager.tail_output(state, 40)
            return self._result(ctx, f"{self._describe(state)}\n\n{tail or '(no output)'}")

        if action == "watch":
            seconds = float(kwargs.get("timeout") or 60.0)
            offset = max(0, int(kwargs.get("offset") or 0))
            await manager.wait_for(task_id, timeout=seconds)
            state = ctx.app_state.get_task(task_id) or state
            chunk = manager.read_output(state, offset=offset)
            end = offset + len(chunk)
            fresh = chunk if chunk.strip() else "(nothing new)"
            return self._result(
                ctx,
                f"{self._describe(state)}\n\n[new output, chars {offset}-{end}]\n{fresh}",
            )

        cancelled = await manager.cancel(task_id)
        state = ctx.app_state.get_task(task_id) or state
        prefix = "Cancelled" if cancelled else "Already finished; nothing to cancel:"
        return self._result(ctx, f"{prefix} {task_id}\n{self._describe(state)}")

    def _list(self, ctx: ToolContext) -> ToolResultBlock:
        tasks = [task for task in ctx.app_state.get_all_tasks() if task.id]
        if not tasks:
            return self._result(ctx, "No tasks in this session.")
        tasks.sort(key=lambda task: task.start_time, reverse=True)
        rows = ["id              type   status      age     description"]
        for task in tasks[:30]:
            rows.append(
                f"{task.id:<15} {task.type.value:<6} {task.status.value:<11} "
                f"{self._age(task):>6}  {task.description[:60]}"
            )
        active = sum(1 for task in tasks if not is_terminal_task_status(task.status))
        rows.append(f"({len(tasks)} task(s), {active} running)")
        return self._result(ctx, "\n".join(rows))

    @staticmethod
    def _age(task: Any) -> str:
        import time

        start = task.start_time or time.time()
        end = task.end_time or time.time()
        seconds = max(0.0, end - start)
        if seconds < 60:
            return f"{seconds:.0f}s"
        if seconds < 3600:
            return f"{seconds / 60:.0f}m"
        return f"{seconds / 3600:.1f}h"

    def _describe(self, state: Any) -> str:
        lines = [
            f"task {state.id}: {state.type.value} {state.status.value}",
            f"  {state.description[:120]}",
            f"  elapsed {self._age(state)}, output {state.output_offset:,} chars",
        ]
        if state.exit_code is not None:
            lines.append(f"  exit code {state.exit_code}")
        if state.output_file:
            lines.append(f"  log {state.output_file}")
        return "\n".join(lines)

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(BgTool())
