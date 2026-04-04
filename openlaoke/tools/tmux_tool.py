"""Tmux tool - manage tmux sessions."""

from __future__ import annotations

import subprocess
from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class TmuxInput(BaseModel):
    action: Literal["create", "attach", "detach", "list", "kill", "send", "split", "resize"] = (
        Field(description="Tmux action to perform")
    )
    session_name: str | None = Field(default=None, description="Name of the tmux session")
    command: str | None = Field(default=None, description="Command to send to session")
    direction: Literal["h", "v", None] = Field(
        default=None, description="Split direction: h (horizontal) or v (vertical)"
    )
    size: int | None = Field(default=None, description="Size for split pane")


class TmuxTool(Tool):
    """Manage tmux sessions for persistent terminal sessions."""

    name = "Tmux"
    description = (
        "Manage tmux sessions for persistent terminal sessions. "
        "Supports creating, attaching, detaching, listing, and killing sessions. "
        "Also supports sending commands, splitting panes, and resizing. "
        "Useful for long-running processes and terminal multiplexing."
    )
    input_schema = TmuxInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        try:
            if action == "create":
                session_name = kwargs.get("session_name")
                if not session_name:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: session_name is required for create action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["tmux", "new-session", "-d", "-s", session_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error creating session: {result.stderr}",
                        is_error=True,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Created tmux session: {session_name}",
                    is_error=False,
                )

            elif action == "attach":
                session_name = kwargs.get("session_name")
                if not session_name:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: session_name is required for attach action",
                        is_error=True,
                    )

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"To attach to session '{session_name}', run: tmux attach -t {session_name}",
                    is_error=False,
                )

            elif action == "detach":
                result = subprocess.run(
                    ["tmux", "detach"],
                    capture_output=True,
                    text=True,
                )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content="Detached from tmux session",
                    is_error=False,
                )

            elif action == "list":
                result = subprocess.run(
                    ["tmux", "list-sessions"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="No active tmux sessions",
                        is_error=False,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=result.stdout,
                    is_error=False,
                )

            elif action == "kill":
                session_name = kwargs.get("session_name")
                if not session_name:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: session_name is required for kill action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error killing session: {result.stderr}",
                        is_error=True,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Killed tmux session: {session_name}",
                    is_error=False,
                )

            elif action == "send":
                session_name = kwargs.get("session_name")
                command = kwargs.get("command")
                if not session_name or not command:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: session_name and command are required for send action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, command, "Enter"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error sending command: {result.stderr}",
                        is_error=True,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Sent command to session {session_name}: {command}",
                    is_error=False,
                )

            elif action == "split":
                session_name = kwargs.get("session_name")
                direction = kwargs.get("direction", "h")
                size = kwargs.get("size")

                if not session_name:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: session_name is required for split action",
                        is_error=True,
                    )

                cmd = ["tmux", "split-window", f"-{direction}"]
                if size:
                    cmd.extend(["-l", str(size)])
                cmd.extend(["-t", session_name])

                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error splitting pane: {result.stderr}",
                        is_error=True,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Split pane in session {session_name}",
                    is_error=False,
                )

            elif action == "resize":
                session_name = kwargs.get("session_name")
                direction = kwargs.get("direction", "h")
                size = kwargs.get("size", 10)

                if not session_name:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: session_name is required for resize action",
                        is_error=True,
                    )

                result = subprocess.run(
                    ["tmux", "resize-pane", f"-{direction}", str(size), "-t", session_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Error resizing pane: {result.stderr}",
                        is_error=True,
                    )
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Resized pane in session {session_name}",
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
                content="Error: tmux is not installed. Install with: brew install tmux (macOS) or apt install tmux (Linux)",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error during tmux operation: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(TmuxTool())
