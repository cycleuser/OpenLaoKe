"""Bash tool - execute shell commands."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class BashInput(BaseModel):
    command: str = Field(description="The bash command to execute")
    description: str = Field(default="", description="Brief description of what this command does")
    timeout: float | None = Field(default=None, description="Timeout in seconds")


class BashTool(Tool):
    """Execute bash commands in the terminal."""

    name = "Bash"
    description = (
        "Execute a bash command in the current working directory. "
        "Use this for running scripts, installing packages, git operations, etc. "
        "Long-running commands will stream output."
    )
    input_schema = BashInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        command = kwargs.get("command", "")
        description = kwargs.get("description", "")
        timeout = kwargs.get("timeout")

        if not command.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: Empty command",
                is_error=True,
            )

        from openlaoke.core.task import TaskManager

        task_mgr = TaskManager(ctx.app_state)
        try:
            output, exit_code = await task_mgr.run_bash(
                command=command,
                description=description or command[:100],
                timeout=timeout,
                tool_use_id=ctx.tool_use_id,
                working_dir=ctx.app_state.get_cwd(),
            )

            max_output = 30000
            if len(output) > max_output:
                truncated = output[:max_output]
                output = f"{truncated}\n\n... (output truncated, {len(output) - max_output} chars omitted)"

            if exit_code != 0:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Command exited with code {exit_code}\n\n{output}",
                    is_error=True,
                )

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=output if output else "(command completed successfully with no output)",
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error executing command: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(BashTool())
