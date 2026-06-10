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


@dataclass
class PreviewResult:
    """The result of a tool's dry-run preview.

    ``summary`` is a human-readable one-liner of what the tool *would* do.
    ``diff_hint`` is a structured description for the permission prompt:
    ``{type}`` is "create" / "update" / "delete" / "noop".
    ``path`` is the primary file path affected.
    ``lines_changed`` is an estimate for display only.
    """

    summary: str = ""
    path: str = ""
    action: str = "noop"
    lines_before: int = 0
    lines_after: int = 0

    def one_line(self) -> str:
        if self.action == "create":
            return f"Create {self.path} ({self.lines_after} lines)"
        if self.action == "update":
            delta = self.lines_after - self.lines_before
            sign = "+" if delta >= 0 else ""
            return f"Update {self.path} ({sign}{delta} lines)"
        if self.action == "delete":
            return f"Delete {self.path} ({self.lines_before} lines)"
        return self.summary or "No effect"


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

    def preview(self, **kwargs: Any) -> PreviewResult:
        """Return a dry-run preview of what the tool *would* do.

        Default returns a noop. Writer tools override this so the
        permission gate can show the user what will change before
        asking for approval.
        """
        return PreviewResult()

    def get_description(self) -> str:
        """Return the tool description for the system prompt."""
        return self.description

    def get_input_schema(self) -> dict[str, Any]:
        """Return the JSON schema for tool input validation."""
        if isinstance(self.input_schema, dict):
            return self.input_schema
        if self.input_schema is not None and hasattr(self.input_schema, "model_json_schema"):
            return self.input_schema.model_json_schema()
        return {}

    def validate_input(self, input_data: dict[str, Any]) -> ValidationResult:
        """Validate tool input before execution with full type checking."""
        if isinstance(self.input_schema, dict):
            return self._validate_schema_dict(input_data, self.input_schema)
        if self.input_schema is not None and hasattr(self.input_schema, "model_json_schema"):
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
        type_map: dict[str, type | tuple[type, ...]] = {
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
                if not isinstance(value, expected) or (isinstance(value, bool) and expected is int):
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

    _DEFAULT_READONLY_TOOLS: frozenset[str] = frozenset({
        "Read", "ReadFile", "Glob", "Grep", "LSP", "ListDirectory",
        "WebSearch", "WebFetch", "ToolSearch", "Brief", "Plan", "Lsp",
        "NotebookRead", "ReadTracker",
    })
    _DEFAULT_WRITER_TOOLS: frozenset[str] = frozenset({
        "Write", "Edit", "Bash", "ApplyPatch", "Batch", "Git",
        "CodeRunner", "Agent", "NotebookWrite", "MultiEdit",
    })

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._deferred_loaders: dict[str, Callable[[], Tool] | Callable[[], Awaitable[Tool]]] = {}
        self._deferred_info: dict[str, DeferredToolInfo] = {}
        self._load_locks: dict[str, asyncio.Lock] = {}
        self._frozen_schemas: list[dict[str, Any]] | None = None
        self._frozen: bool = False

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
            if name not in self._load_locks:
                self._load_locks[name] = asyncio.Lock()
            lock = self._load_locks[name]
            async with lock:
                if name in self._tools:
                    return self._tools[name]
                loader = self._deferred_loaders.get(name)
                if loader is None:
                    return None
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
                if name in self._load_locks:
                    del self._load_locks[name]
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
        if self._frozen and self._frozen_schemas is not None:
            return self._frozen_schemas
        tools = self.get_all()
        schemas = [
            {
                "name": tool.name,
                "description": tool.get_description(),
                "input_schema": tool.get_input_schema(),
            }
            for tool in tools
        ]
        if self._frozen:
            self._frozen_schemas = schemas
        return schemas

    def freeze(self) -> None:
        """Freeze the tool set for the session.

        After freezing, get_all_for_prompt() returns cached schemas.
        New tool registrations are still tracked but don't affect the
        prompt schemas (they're communicated via invoke_skill or
        [session context] instead).
        """
        if not self._frozen_schemas:
            self._frozen_schemas = self.get_all_for_prompt()
        self._frozen = True

    def thaw(self) -> None:
        """Unfreeze — tool schemas will be rebuilt on next get_all_for_prompt()."""
        self._frozen = False
        self._frozen_schemas = None

    @property
    def is_frozen(self) -> bool:
        return self._frozen

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

    def is_readonly(self, name: str) -> bool:
        """Check if a tool is read-only. Used for parallel dispatch decisions."""
        tool = self._tools.get(name)
        if tool is not None:
            return tool.is_read_only
        if name in ToolRegistry._DEFAULT_READONLY_TOOLS:
            return True
        if name in ToolRegistry._DEFAULT_WRITER_TOOLS:
            return False
        return False

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
