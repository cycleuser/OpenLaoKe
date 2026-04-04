"""Agent tool - spawn sub-agents for parallel work."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class AgentInput(BaseModel):
    prompt: str = Field(description="The prompt to give the sub-agent")
    description: str = Field(
        default="", description="Brief description of what the agent should do"
    )
    subagent_type: str = Field(default="general-purpose", description="Type of sub-agent to use")


class AgentTool(Tool):
    """Spawn a sub-agent to handle complex tasks in parallel."""

    name = "Agent"
    description = (
        "Launch a sub-agent to work on a task in parallel. "
        "Use this for independent work that can be done concurrently. "
        "The sub-agent has access to all the same tools."
    )
    input_schema = AgentInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        prompt = kwargs.get("prompt", "")
        description = kwargs.get("description", "")
        subagent_type = kwargs.get("subagent_type", "general-purpose")

        if not prompt.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: prompt is required",
                is_error=True,
            )

        from openlaoke.core.task import TaskManager

        task_mgr = TaskManager(ctx.app_state)

        try:
            result = await task_mgr.run_agent(
                prompt=prompt,
                description=description or prompt[:100],
                tool_use_id=ctx.tool_use_id,
                subagent_type=subagent_type,
            )

            max_output = 20000
            if len(result) > max_output:
                result = (
                    result[:max_output]
                    + f"\n\n... (output truncated, {len(result) - max_output} chars omitted)"
                )

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Agent result ({subagent_type}):\n\n{result}",
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Agent failed: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(AgentTool())
