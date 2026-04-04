"""Batch tool - Execute multiple tool calls in parallel or sequence."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class ToolCallSpec(BaseModel):
    tool_name: str = Field(description="Name of the tool to call")
    args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool call")


class BatchInput(BaseModel):
    calls: list[ToolCallSpec] = Field(description="List of tool calls to execute")
    parallel: bool = Field(default=True, description="Execute calls in parallel (default: True)")
    stop_on_error: bool = Field(default=False, description="Stop on first error (default: False)")


class BatchTool(Tool):
    """Execute multiple tool calls in a single batch."""

    name = "Batch"
    description = (
        "Execute multiple tool calls in a single batch operation. "
        "Supports both parallel (default) and sequential execution. "
        "Use stop_on_error to control error handling. "
        "Returns aggregated results from all tool calls."
    )
    input_schema = BatchInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        calls_raw = kwargs.get("calls", [])
        parallel = kwargs.get("parallel", True)
        stop_on_error = kwargs.get("stop_on_error", False)

        if not calls_raw:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: calls list is required",
                is_error=True,
            )

        # Convert dict calls to ToolCallSpec if needed
        calls: list[ToolCallSpec] = []
        for call in calls_raw:
            if isinstance(call, ToolCallSpec):
                calls.append(call)
            elif isinstance(call, dict):
                calls.append(ToolCallSpec(**call))
            else:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Invalid call spec type: {type(call)}",
                    is_error=True,
                )

        if len(calls) > 50:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Too many calls ({len(calls)}). Maximum is 50.",
                is_error=True,
            )

        results = []
        errors = []

        if parallel:
            tasks = [self._execute_tool(ctx, call_spec, i) for i, call_spec in enumerate(calls)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    error_msg = f"Call {i} ({calls[i].tool_name}): {result}"
                    errors.append(error_msg)
                    if stop_on_error:
                        break
                    results.append(f"ERROR: {error_msg}")
                else:
                    result_str = str(result)
                    results.append(result_str)
                    if "ERROR:" in result_str and stop_on_error:
                        errors.append(result_str)
                        break
        else:
            for i, call_spec in enumerate(calls):
                try:
                    result = await self._execute_tool(ctx, call_spec, i)
                    results.append(result)
                    if "ERROR:" in result and stop_on_error:
                        errors.append(result)
                        break
                except Exception as e:
                    error_msg = f"Call {i} ({call_spec.tool_name}): {e}"
                    errors.append(error_msg)
                    results.append(f"ERROR: {error_msg}")
                    if stop_on_error:
                        break

        output_parts = []
        for i, (call_spec, result) in enumerate(zip(calls, results, strict=False)):
            output_parts.append(f"--- Call {i}: {call_spec.tool_name} ---")
            output_parts.append(result)
            output_parts.append("")

        if errors and not stop_on_error:
            output_parts.append(f"\nCompleted with {len(errors)} error(s)")

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(output_parts),
            is_error=len(errors) > 0,
        )

    async def _execute_tool(self, ctx: ToolContext, call_spec: ToolCallSpec, index: int) -> str:
        tool_name = call_spec.tool_name
        args = call_spec.args

        tool = (
            ctx.app_state.tool_registry.get(tool_name)
            if hasattr(ctx.app_state, "tool_registry")
            else None
        )

        if not tool:
            registry = self._get_registry()
            if registry:
                tool = registry.get(tool_name)

        if not tool:
            return f"ERROR: Unknown tool: {tool_name}"

        try:
            result = await tool.call(ctx, **args)

            if isinstance(result.content, str):
                return result.content
            elif isinstance(result.content, list):
                return str(result.content)
            else:
                return str(result.content)

        except Exception as e:
            return f"ERROR: {e}"

    def _get_registry(self) -> ToolRegistry | None:
        from openlaoke.tools.register import register_all_tools

        registry = ToolRegistry()
        register_all_tools(registry)
        return registry


def register(registry: ToolRegistry) -> None:
    registry.register(BatchTool())
