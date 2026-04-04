"""Brief tool - enable brief response mode for concise outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class BriefInput(BaseModel):
    mode: Literal["on", "off", "toggle"] = Field(
        default="toggle",
        description="Brief mode action: 'on' to enable, 'off' to disable, 'toggle' to switch",
    )
    max_length: int | None = Field(
        default=None,
        description="Maximum response length in characters when brief mode is on",
        ge=50,
        le=1000,
    )


class BriefTool(Tool):
    """Control brief response mode for shorter, more concise outputs."""

    name = "Brief"
    description = (
        "Enable or disable brief response mode. "
        "When enabled, responses are shortened to be more concise. "
        "Use 'on' to enable, 'off' to disable, or 'toggle' to switch state. "
        "Useful for quick interactions when detailed output is not needed."
    )
    input_schema = BriefInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        mode = kwargs.get("mode", "toggle")
        max_length = kwargs.get("max_length", 200)

        current_state = getattr(ctx.app_state, "brief_mode", False)

        if mode == "on":
            new_state = True
        elif mode == "off":
            new_state = False
        else:
            new_state = not current_state

        if hasattr(ctx.app_state, "brief_mode"):
            ctx.app_state.brief_mode = new_state
        if hasattr(ctx.app_state, "brief_max_length") and max_length:
            ctx.app_state.brief_max_length = max_length

        status = "enabled" if new_state else "disabled"
        message = f"Brief mode {status}"
        if new_state and max_length:
            message += f" (max length: {max_length} chars)"

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=message,
            is_error=False,
        )


def register(registry: ToolRegistry) -> None:
    registry.register(BriefTool())
