"""Tool search tool - search and discover available tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class ToolSearchInput(BaseModel):
    action: Literal["search", "list", "info", "suggest"] = Field(description="Tool search action")
    query: str | None = Field(default=None, description="Search query for tool name or description")
    tool_name: str | None = Field(default=None, description="Specific tool name to get info about")
    task: str | None = Field(default=None, description="Task description for tool suggestions")


class ToolSearchTool(Tool):
    """Search and discover available tools."""

    name = "ToolSearch"
    description = (
        "Search for available tools by name or description. "
        "List all registered tools, get detailed info about a specific tool, "
        "or get tool suggestions based on a task description. "
        "Supports lazy loading of tools for better performance."
    )
    input_schema = ToolSearchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action")
        query = kwargs.get("query")
        tool_name = kwargs.get("tool_name")
        task = kwargs.get("task")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        try:
            if action == "search":
                if not query:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: query is required for search action",
                        is_error=True,
                    )

                registry = self._get_registry(ctx)
                tools = registry.search(query)

                if not tools:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"No tools found matching: {query}",
                        is_error=False,
                    )

                results = []
                for tool in tools:
                    results.append(f"- {tool.name}: {tool.description[:100]}...")

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Found {len(tools)} tool(s):\n" + "\n".join(results),
                    is_error=False,
                )

            elif action == "list":
                registry = self._get_registry(ctx)
                tools = registry.get_all()

                if not tools:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="No tools registered",
                        is_error=False,
                    )

                results = []
                for tool in sorted(tools, key=lambda t: t.name):
                    read_only = " [RO]" if tool.is_read_only else ""
                    destructive = " [D]" if tool.is_destructive else ""
                    approval = " [A]" if tool.requires_approval else ""
                    results.append(
                        f"- {tool.name}{read_only}{destructive}{approval}: {tool.description[:80]}..."
                    )

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Registered tools ({len(tools)}):\n" + "\n".join(results),
                    is_error=False,
                )

            elif action == "info":
                if not tool_name:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: tool_name is required for info action",
                        is_error=True,
                    )

                registry = self._get_registry(ctx)
                found_tool: Tool | None = registry.get(tool_name)

                if not found_tool:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"Tool not found: {tool_name}",
                        is_error=True,
                    )

                info = [
                    f"Name: {found_tool.name}",
                    f"Description: {found_tool.description}",
                    f"Read-only: {found_tool.is_read_only}",
                    f"Destructive: {found_tool.is_destructive}",
                    f"Concurrency-safe: {found_tool.is_concurrency_safe}",
                    f"Requires approval: {found_tool.requires_approval}",
                    "",
                    "Input schema:",
                ]

                schema = found_tool.get_input_schema()
                if "properties" in schema:
                    for prop_name, prop_info in schema["properties"].items():
                        required = prop_name in schema.get("required", [])
                        req_str = " (required)" if required else ""
                        desc = prop_info.get("description", "No description")
                        info.append(f"  - {prop_name}{req_str}: {desc}")
                else:
                    info.append("  No input parameters")

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content="\n".join(info),
                    is_error=False,
                )

            elif action == "suggest":
                if not task:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: task is required for suggest action",
                        is_error=True,
                    )

                registry = self._get_registry(ctx)
                tools = registry.get_all()

                suggestions = self._suggest_tools(task, tools)

                if not suggestions:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"No tool suggestions for task: {task}",
                        is_error=False,
                    )

                results = []
                for tool, reason in suggestions:
                    results.append(f"- {tool.name}: {reason}")

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Suggested tools for '{task}':\n" + "\n".join(results),
                    is_error=False,
                )

            else:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Unknown action: {action}",
                    is_error=True,
                )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error during tool search: {e}",
                is_error=True,
            )

    def _get_registry(self, ctx: ToolContext) -> ToolRegistry:
        """Get the tool registry from app state."""
        if hasattr(ctx.app_state, "tool_registry"):
            reg: ToolRegistry = ctx.app_state.tool_registry
            return reg
        return ToolRegistry()

    def _suggest_tools(self, task: str, tools: list[Tool]) -> list[tuple[Tool, str]]:
        """Suggest tools based on task description."""
        task_lower = task.lower()
        suggestions: list[tuple[Tool, str]] = []

        keywords = {
            "read": ("Read", "Read file contents"),
            "write": ("Write", "Write content to files"),
            "edit": ("Edit", "Edit existing files"),
            "bash": ("Bash", "Execute shell commands"),
            "shell": ("Bash", "Execute shell commands"),
            "command": ("Bash", "Execute shell commands"),
            "git": ("Git", "Git version control operations"),
            "search": ("Grep", "Search file contents"),
            "grep": ("Grep", "Search file contents"),
            "find": ("Glob", "Find files by pattern"),
            "glob": ("Glob", "Find files by pattern"),
            "list": ("Ls", "List directory contents"),
            "directory": ("Ls", "List directory contents"),
            "fetch": ("WebFetch", "Fetch web content"),
            "url": ("WebFetch", "Fetch web content"),
            "web": ("WebFetch", "Fetch web content"),
            "sleep": ("Sleep", "Pause execution"),
            "wait": ("Sleep", "Pause execution"),
            "browser": ("WebBrowser", "Browser automation"),
            "tmux": ("Tmux", "Terminal session management"),
            "terminal": ("Tmux", "Terminal session management"),
            "powershell": ("PowerShell", "Execute PowerShell commands"),
            "cron": ("Cron", "Manage scheduled tasks"),
            "schedule": ("Cron", "Manage scheduled tasks"),
            "repl": ("REPL", "Interactive coding environment"),
            "todo": ("Todo", "Manage todo list"),
            "task": ("Todo", "Manage todo list"),
        }

        for keyword, (tool_name, reason) in keywords.items():
            if keyword in task_lower:
                for tool in tools:
                    if tool.name.lower() == tool_name.lower():
                        if tool not in [t for t, _ in suggestions]:
                            suggestions.append((tool, reason))
                        break

        return suggestions[:5]


def register(registry: ToolRegistry) -> None:
    registry.register(ToolSearchTool())
