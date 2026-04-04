"""Base Tool system - all tools inherit from this."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from openlaoke.types.core_types import (
    PermissionResult,
    TaskType,
    ToolProgress,
    ToolResultBlock,
    ToolUseBlock,
    ValidationResult,
)
from openlaoke.types.permissions import PermissionConfig

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class ToolContext:
    """Context passed to tool calls."""
    app_state: AppState
    tool_use_id: str
    agent_id: str | None = None
    abort_signal: Any = None


class Tool(ABC):
    """Base class for all tools. Subclasses implement specific capabilities."""

    name: str = "base_tool"
    description: str = ""
    input_schema: type[BaseModel] | dict[str, Any] = {}
    task_type: TaskType = TaskType.LOCAL_BASH
    is_read_only: bool = False
    is_destructive: bool = False
    is_concurrency_safe: bool = True
    requires_approval: bool = False

    @abstractmethod
    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        """Execute the tool with the given input."""
        ...

    def get_description(self) -> str:
        """Return the tool description for the system prompt."""
        return self.description

    def get_input_schema(self) -> dict[str, Any]:
        """Return the JSON schema for tool input validation."""
        if isinstance(self.input_schema, dict):
            return self.input_schema
        if hasattr(self.input_schema, "model_json_schema"):
            return self.input_schema.model_json_schema()
        return {}

    def validate_input(self, input_data: dict[str, Any]) -> ValidationResult:
        """Validate tool input before execution."""
        if isinstance(self.input_schema, dict):
            required = self.input_schema.get("required", [])
            properties = self.input_schema.get("properties", {})
            for field_name in required:
                if field_name not in input_data:
                    return ValidationResult(
                        result=False,
                        message=f"Missing required field: {field_name}",
                        error_code=400,
                    )
            for field_name, value in input_data.items():
                if field_name in properties:
                    field_type = properties[field_name].get("type")
                    if field_type == "string" and not isinstance(value, str):
                        return ValidationResult(
                            result=False,
                            message=f"Field '{field_name}' must be a string",
                            error_code=400,
                        )
        return ValidationResult(result=True)

    def check_permissions(
        self,
        input_data: dict[str, Any],
        permission_config: PermissionConfig,
    ) -> PermissionResult:
        """Check if the tool call is permitted."""
        return permission_config.check_tool(self.name)

    def get_progress(self, ctx: ToolContext, **kwargs: Any) -> ToolProgress | None:
        """Return current progress for long-running tools."""
        return None

    def render_result(self, result: ToolResultBlock) -> str:
        """Render the tool result for display in the terminal."""
        if isinstance(result.content, str):
            return result.content
        return json.dumps(result.content, indent=2)

    def get_deny_message(self, input_data: dict[str, Any]) -> str:
        """Message shown when the tool call is denied."""
        return f"Tool '{self.name}' was denied by the user."


class ToolRegistry:
    """Registry for all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._deferred_loaders: dict[str, callable] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_deferred(self, name: str, loader: callable) -> None:
        self._deferred_loaders[name] = loader

    def get(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]
        if name in self._deferred_loaders:
            tool = self._deferred_loaders[name]()
            self._tools[name] = tool
            del self._deferred_loaders[name]
            return tool
        return None

    def get_all(self) -> list[Tool]:
        for loader_name, loader in list(self._deferred_loaders.items()):
            tool = loader()
            self._tools[loader_name] = tool
            del self._deferred_loaders[loader_name]
        return list(self._tools.values())

    def get_all_for_prompt(self) -> list[dict[str, Any]]:
        tools = self.get_all()
        return [
            {
                "name": tool.name,
                "description": tool.get_description(),
                "input_schema": tool.get_input_schema(),
            }
            for tool in tools
        ]

    def search(self, query: str) -> list[Tool]:
        query_lower = query.lower()
        results = []
        for tool in self.get_all():
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                results.append(tool)
        return results
