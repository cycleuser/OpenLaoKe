"""Sleep tool - pause execution for specified duration."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class SleepInput(BaseModel):
    seconds: float = Field(description="Number of seconds to sleep", ge=0.0, le=3600.0)


class SleepTool(Tool):
    """Pause execution for a specified duration."""

    name = "Sleep"
    description = (
        "Pause execution for a specified number of seconds. "
        "Use for delays, waiting for async operations, or debugging. "
        "Maximum duration is 3600 seconds (1 hour)."
    )
    input_schema = SleepInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        seconds = kwargs.get("seconds", 0.0)

        if seconds <= 0:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Sleep duration must be greater than 0",
                is_error=True,
            )

        if seconds > 3600:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Sleep duration cannot exceed 3600 seconds (1 hour)",
                is_error=True,
            )

        try:
            await asyncio.sleep(seconds)
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Slept for {seconds} second(s)",
                is_error=False,
            )
        except asyncio.CancelledError:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Sleep was cancelled",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error during sleep: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(SleepTool())
