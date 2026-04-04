"""Cron tool - manage cron jobs."""

from __future__ import annotations

import platform
import subprocess
from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class CronInput(BaseModel):
    action: Literal["list", "add", "remove", "update"] = Field(description="Cron action to perform")
    expression: str | None = Field(default=None, description="Cron expression (e.g., '0 * * * *')")
    command: str | None = Field(default=None, description="Command to execute")
    job_id: str | None = Field(default=None, description="Job identifier for removal or update")
    comment: str | None = Field(default=None, description="Comment for the cron job")


class CronTool(Tool):
    """Manage cron jobs for scheduled tasks."""

    name = "Cron"
    description = (
        "Manage cron jobs for scheduled task execution. "
        "Supports listing, adding, removing, and updating cron jobs. "
        "Uses standard cron expression format. "
        "Note: Requires crontab to be available on the system."
    )
    input_schema = CronInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        system = platform.system()
        if system == "Windows":
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: Cron jobs are not supported on Windows. Use Task Scheduler instead.",
                is_error=True,
            )

        try:
            if action == "list":
                result = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    if "no crontab" in result.stderr.lower():
                        return ToolResultBlock(
                            tool_use_id=ctx.tool_use_id,
                            content="No cron jobs configured",
                            is_error=False,
                        )
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error listing cron jobs: {result.stderr}",
                        is_error=True,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=result.stdout or "No cron jobs configured",
                    is_error=False,
                )

            elif action == "add":
                expression = kwargs.get("expression")
                command = kwargs.get("command")
                comment = kwargs.get("comment", "")

                if not expression or not command:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: expression and command are required for add action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )

                current_cron = result.stdout if result.returncode == 0 else ""

                comment_str = f" # {comment}" if comment else ""
                new_job = f"{expression} {command}{comment_str}\n"

                updated_cron = current_cron + new_job

                process = subprocess.Popen(
                    ["crontab", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                _, stderr = process.communicate(input=updated_cron)

                if process.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error adding cron job: {stderr}",
                        is_error=True,
                    )

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Added cron job: {expression} {command}",
                    is_error=False,
                )

            elif action == "remove":
                job_id = kwargs.get("job_id")

                if not job_id:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: job_id is required for remove action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="No cron jobs configured",
                        is_error=False,
                    )

                lines = result.stdout.strip().split("\n")
                updated_lines = [line for line in lines if job_id not in line and line.strip()]

                updated_cron = "\n".join(updated_lines)
                if updated_lines:
                    updated_cron += "\n"

                process = subprocess.Popen(
                    ["crontab", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                _, stderr = process.communicate(input=updated_cron)

                if process.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error removing cron job: {stderr}",
                        is_error=True,
                    )

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Removed cron job containing: {job_id}",
                    is_error=False,
                )

            elif action == "update":
                job_id = kwargs.get("job_id")
                expression = kwargs.get("expression")
                command = kwargs.get("command")
                comment = kwargs.get("comment", "")

                if not job_id:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: job_id is required for update action",
                        is_error=True,
                    )

                if not expression or not command:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: expression and command are required for update action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="No cron jobs configured",
                        is_error=False,
                    )

                lines = result.stdout.strip().split("\n")
                updated_lines = []
                found = False

                for line in lines:
                    if job_id in line:
                        comment_str = f" # {comment}" if comment else ""
                        updated_lines.append(f"{expression} {command}{comment_str}")
                        found = True
                    elif line.strip():
                        updated_lines.append(line)

                if not found:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Job not found: {job_id}",
                        is_error=True,
                    )

                updated_cron = "\n".join(updated_lines) + "\n"

                process = subprocess.Popen(
                    ["crontab", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                _, stderr = process.communicate(input=updated_cron)

                if process.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error updating cron job: {stderr}",
                        is_error=True,
                    )

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Updated cron job: {expression} {command}",
                    is_error=False,
                )

            else:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Unknown action: {action}",
                    is_error=True,
                )

        except FileNotFoundError:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: crontab is not installed. Install cron package first.",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error managing cron jobs: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(CronTool())
