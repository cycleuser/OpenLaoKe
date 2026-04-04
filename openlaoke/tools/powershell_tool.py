"""PowerShell tool - execute PowerShell commands."""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class PowerShellInput(BaseModel):
    command: str = Field(description="The PowerShell command to execute")
    description: str = Field(default="", description="Brief description of what this command does")
    timeout: float | None = Field(default=None, description="Timeout in seconds")


class PowerShellTool(Tool):
    """Execute PowerShell commands."""

    name = "PowerShell"
    description = (
        "Execute PowerShell commands on Windows or PowerShell Core on Unix systems. "
        "Supports Windows scripting, system administration, and cross-platform compatibility. "
        "On Unix systems, requires PowerShell Core (pwsh) to be installed."
    )
    input_schema = PowerShellInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    def _get_powershell_cmd(self) -> str:
        """Get the PowerShell executable based on platform."""
        system = platform.system()
        if system == "Windows":
            return "powershell"
        return "pwsh"

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", 60.0)

        if not command.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: Empty command",
                is_error=True,
            )

        try:
            powershell = self._get_powershell_cmd()

            result = subprocess.run(
                [powershell, "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=ctx.app_state.get_cwd(),
            )

            output = result.stdout
            if result.stderr:
                output += f"\nStderr:\n{result.stderr}"

            if result.returncode != 0:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Command exited with code {result.returncode}\n\n{output}",
                    is_error=True,
                )

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=output if output else "(command completed successfully with no output)",
                is_error=False,
            )

        except FileNotFoundError:
            system = platform.system()
            if system == "Windows":
                msg = "PowerShell not found"
            else:
                msg = "PowerShell Core (pwsh) not found. Install with: brew install powershell (macOS) or see https://aka.ms/powershell"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: {msg}",
                is_error=True,
            )
        except subprocess.TimeoutExpired:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Command timed out after {timeout} seconds",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error executing PowerShell command: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(PowerShellTool())
