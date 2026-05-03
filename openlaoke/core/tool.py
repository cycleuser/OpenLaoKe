"""Base Tool system - all tools inherit from this."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from openlaoke.types.core_types import (
    PermissionResult,
    TaskType,
    ToolProgress,
    ToolResultBlock,
    ValidationResult,
)
from openlaoke.types.permissions import PermissionConfig

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class ToolContext:
    app_state: AppState
    tool_use_id: str
    agent_id: str | None = None
    abort_signal: Any = None
    file_state: Any = None
    git_store: Any = None


class Tool(ABC):
    """Base class for all tools. Subclasses implement specific capabilities."""

    name: str = "base_tool"
    description: str = ""
    input_schema: type[BaseModel] | dict[str, Any] | None = None
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
        """Validate tool input before execution with full type checking."""
        if isinstance(self.input_schema, dict):
            return self._validate_schema_dict(input_data, self.input_schema)
        if hasattr(self.input_schema, "model_json_schema"):
            try:
                schema = self.input_schema.model_json_schema()
                return self._validate_schema_dict(input_data, schema)
            except Exception:
                pass
        return ValidationResult(result=True)

    @staticmethod
    def _validate_schema_dict(
        input_data: dict[str, Any], schema: dict[str, Any]
    ) -> ValidationResult:
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for field_name in required:
            if field_name not in input_data or input_data.get(field_name) is None:
                return ValidationResult(
                    result=False,
                    message=f"Missing required field: {field_name}",
                    error_code=400,
                )
        for field_name, value in input_data.items():
            if field_name not in properties or value is None:
                continue
            field_type = properties[field_name].get("type")
            if field_type and field_type in type_map:
                expected = type_map[field_type]
                if not isinstance(value, expected):
                    return ValidationResult(
                        result=False,
                        message=f"Field '{field_name}' must be {field_type}, got {type(value).__name__}",
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


class DeferredToolInfo:
    """Info about a deferred tool without loading it."""

    def __init__(
        self,
        name: str,
        description: str = "",
        search_hint: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.search_hint = search_hint
        self.aliases = aliases or []


class ToolRegistry:
    """Registry for all available tools with lazy loading support."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._deferred_loaders: dict[str, Callable[[], Tool] | Callable[[], Awaitable[Tool]]] = {}
        self._deferred_info: dict[str, DeferredToolInfo] = {}
        self._load_locks: dict[str, asyncio.Lock] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_deferred(
        self, name: str, loader: Callable[[], Tool] | Callable[[], Awaitable[Tool]]
    ) -> None:
        self._deferred_loaders[name] = loader
        self._deferred_info[name] = DeferredToolInfo(name)

    def register_deferred_with_info(
        self,
        name: str,
        loader: Callable[[], Tool] | Callable[[], Awaitable[Tool]],
        description: str = "",
        search_hint: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        self._deferred_loaders[name] = loader
        self._deferred_info[name] = DeferredToolInfo(name, description, search_hint, aliases)

    def get(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]
        if name in self._deferred_loaders:
            loader = self._deferred_loaders[name]
            if asyncio.iscoroutinefunction(loader):
                return None
            sync_loader = cast(Callable[[], Tool], loader)
            tool = sync_loader()
            self._tools[name] = tool
            del self._deferred_loaders[name]
            return tool
        return None

    async def get_async(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]
        if name in self._deferred_loaders:
            lock = self._load_locks.setdefault(name, asyncio.Lock())
            async with lock:
                if name in self._tools:
                    return self._tools[name]
                loader = self._deferred_loaders[name]
                tool: Tool
                if asyncio.iscoroutinefunction(loader):
                    async_loader = cast(Callable[[], Awaitable[Tool]], loader)
                    tool = await async_loader()
                else:
                    sync_loader = cast(Callable[[], Tool], loader)
                    tool = sync_loader()
                self._tools[name] = tool
                del self._deferred_loaders[name]
                if name in self._deferred_info:
                    del self._deferred_info[name]
                return tool
        return None

    def is_loaded(self, name: str) -> bool:
        return name in self._tools

    def is_deferred(self, name: str) -> bool:
        return name in self._deferred_loaders

    def get_deferred_info(self, name: str) -> DeferredToolInfo | None:
        return self._deferred_info.get(name)

    def get_all_deferred_info(self) -> list[DeferredToolInfo]:
        return list(self._deferred_info.values())

    def get_loaded(self) -> list[Tool]:
        return list(self._tools.values())

    def get_all(self) -> list[Tool]:
        for loader_name in list(self._deferred_loaders.keys()):
            loader = self._deferred_loaders[loader_name]
            if not asyncio.iscoroutinefunction(loader):
                sync_loader = cast(Callable[[], Tool], loader)
                tool = sync_loader()
                self._tools[loader_name] = tool
                del self._deferred_loaders[loader_name]
                if loader_name in self._deferred_info:
                    del self._deferred_info[loader_name]
        return list(self._tools.values())

    async def get_all_async(self) -> list[Tool]:
        for loader_name in list(self._deferred_loaders.keys()):
            await self.get_async(loader_name)
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

    def get_deferred_for_prompt(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for name, info in self._deferred_info.items():
            results.append(
                {
                    "name": name,
                    "description": info.description,
                    "search_hint": info.search_hint,
                    "aliases": info.aliases,
                    "defer_loading": True,
                }
            )
        return results

    def search(self, query: str) -> list[Tool]:
        query_lower = query.lower()
        results = []
        for tool in self.get_all():
            if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                results.append(tool)
        return results

    def search_deferred(self, query: str) -> list[DeferredToolInfo]:
        query_lower = query.lower()
        results: list[DeferredToolInfo] = []
        for info in self._deferred_info.values():
            if (
                query_lower in info.name.lower()
                or query_lower in info.description.lower()
                or query_lower in info.search_hint.lower()
                or any(query_lower in alias.lower() for alias in info.aliases)
            ):
                results.append(info)
        return results
