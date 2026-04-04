"""Tool executor for HyperAuto - executes tools based on AI decisions."""

from __future__ import annotations

import asyncio
import json
import traceback
from typing import TYPE_CHECKING, Any

from openlaoke.types.core_types import ToolResultBlock

if TYPE_CHECKING:
    from openlaoke.core.state import AppState
    from openlaoke.core.tool import ToolRegistry


class ToolExecutor:
    """Executes tools for HyperAuto agent."""

    def __init__(self, app_state: AppState, tool_registry: ToolRegistry | None = None):
        self.app_state = app_state
        self._tool_registry = tool_registry

    async def get_tool_registry(self) -> ToolRegistry:
        """Get or create tool registry."""
        if self._tool_registry is None:
            from openlaoke.core.tool import ToolRegistry
            from openlaoke.tools.register import register_all_tools

            self._tool_registry = ToolRegistry()
            register_all_tools(self._tool_registry)
        return self._tool_registry

    async def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResultBlock:
        """Execute a single tool call."""
        print(f"[EXECUTOR] Executing tool: {tool_name}")
        print(f"[EXECUTOR] Input: {json.dumps(tool_input, indent=2)[:500]}...")

        try:
            registry = await self.get_tool_registry()
            tool = await registry.get_async(tool_name)

            if not tool:
                print(f"[EXECUTOR] Tool not found: {tool_name}")
                return ToolResultBlock(
                    type="tool_result",
                    tool_use_id="unknown",
                    content=f"Error: Tool '{tool_name}' not found",
                    is_error=True,
                )

            from openlaoke.core.tool import ToolContext

            ctx = ToolContext(
                app_state=self.app_state,
                tool_use_id=f"ha_tool_{asyncio.get_event_loop().time()}",
            )

            result = await tool.call(ctx, **tool_input)

            print(f"[EXECUTOR] Tool result: {result.is_error=}")
            if result.is_error:
                print(
                    f"[EXECUTOR] Error: {result.content[:200] if isinstance(result.content, str) else result.content}"
                )
            else:
                content_preview = (
                    result.content[:200]
                    if isinstance(result.content, str)
                    else str(result.content)[:200]
                )
                print(f"[EXECUTOR] Success: {content_preview}...")

            return result

        except Exception as e:
            print(f"[EXECUTOR] Exception: {e}")
            print(f"[EXECUTOR] Traceback:\n{traceback.format_exc()}")
            return ToolResultBlock(
                type="tool_result",
                tool_use_id="error",
                content=f"Exception executing tool: {e}",
                is_error=True,
            )

    async def execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[ToolResultBlock]:
        """Execute multiple tool calls in sequence."""
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", tool_call.get("function", {}).get("name", ""))
            tool_input = tool_call.get("input", tool_call.get("function", {}).get("arguments", {}))

            if isinstance(tool_input, str):
                try:
                    tool_input = json.loads(tool_input)
                except json.JSONDecodeError:
                    tool_input = {}

            result = await self.execute_tool(tool_name, tool_input)
            results.append(result)

        return results

    async def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get schemas for all available tools."""
        registry = await self.get_tool_registry()
        tools = await registry.get_all_async()

        schemas = []
        for tool in tools:
            schema = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.get_input_schema(),
            }
            schemas.append(schema)

        return schemas
