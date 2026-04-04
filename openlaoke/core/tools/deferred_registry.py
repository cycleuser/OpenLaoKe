"""Deferred tool registry for lazy loading."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.tool import Tool


ESSENTIAL_TOOLS: set[str] = {
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
}

DEFERRED_TOOLS: set[str] = {
    "WebSearch",
    "WebFetch",
    "LSP",
    "Git",
    "Batch",
    "NotebookEdit",
    "Plan",
    "Agent",
    "TaskKill",
    "Todo",
    "Question",
    "LS",
    "ApplyPatch",
}


@dataclass
class DeferredTool:
    """Represents a tool that can be loaded on demand."""

    name: str
    description: str
    loader: Callable[[], Awaitable[Tool]] | Callable[[], Tool]
    is_loaded: bool = False
    always_load: bool = False
    priority: int = 0
    search_hint: str = ""
    aliases: list[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DeferredTool):
            return self.name == other.name
        return False


@dataclass
class ToolInfo:
    """Lightweight info about a tool without loading it."""

    name: str
    description: str
    search_hint: str = ""
    aliases: list[str] = field(default_factory=list)
    is_loaded: bool = False
    always_load: bool = False


class DeferredRegistry:
    """Registry for deferred tools with metadata."""

    def __init__(self) -> None:
        self._deferred: dict[str, DeferredTool] = {}
        self._essential: set[str] = ESSENTIAL_TOOLS.copy()
        self._deferred_set: set[str] = DEFERRED_TOOLS.copy()

    def register(
        self,
        name: str,
        description: str,
        loader: Callable[[], Awaitable[Tool]] | Callable[[], Tool],
        always_load: bool = False,
        priority: int = 0,
        search_hint: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        """Register a deferred tool."""
        self._deferred[name] = DeferredTool(
            name=name,
            description=description,
            loader=loader,
            always_load=always_load,
            priority=priority,
            search_hint=search_hint,
            aliases=aliases or [],
        )

    def get(self, name: str) -> DeferredTool | None:
        """Get deferred tool info by name."""
        return self._deferred.get(name)

    def get_by_alias(self, alias: str) -> DeferredTool | None:
        """Get deferred tool by alias."""
        for tool in self._deferred.values():
            if alias in tool.aliases:
                return tool
        return None

    def is_essential(self, name: str) -> bool:
        """Check if tool is essential (always loaded)."""
        tool = self._deferred.get(name)
        return name in self._essential or (tool is not None and tool.always_load)

    def is_deferred(self, name: str) -> bool:
        """Check if tool should be deferred."""
        return name in self._deferred_set or name in self._deferred

    def get_all_deferred(self) -> list[DeferredTool]:
        """Get all registered deferred tools."""
        return list(self._deferred.values())

    def get_all_essential_names(self) -> set[str]:
        """Get names of essential tools."""
        return self._essential.copy()

    def get_all_deferred_names(self) -> set[str]:
        """Get names of deferred tools."""
        return self._deferred_set.copy()

    def get_tool_info(self, name: str) -> ToolInfo | None:
        """Get lightweight info about a tool."""
        deferred = self._deferred.get(name)
        if deferred:
            return ToolInfo(
                name=deferred.name,
                description=deferred.description,
                search_hint=deferred.search_hint,
                aliases=deferred.aliases,
                is_loaded=deferred.is_loaded,
                always_load=deferred.always_load,
            )
        return None

    def mark_loaded(self, name: str) -> None:
        """Mark a tool as loaded."""
        if name in self._deferred:
            self._deferred[name].is_loaded = True

    def add_essential(self, name: str) -> None:
        """Add a tool to essential set."""
        self._essential.add(name)

    def add_deferred(self, name: str) -> None:
        """Add a tool to deferred set."""
        self._deferred_set.add(name)

    def search(self, query: str) -> list[DeferredTool]:
        """Search deferred tools by name or description."""
        query_lower = query.lower()
        results: list[DeferredTool] = []
        for tool in self._deferred.values():
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
                or query_lower in tool.search_hint.lower()
                or any(query_lower in alias.lower() for alias in tool.aliases)
            ):
                results.append(tool)
        return sorted(results, key=lambda t: t.priority, reverse=True)

    def to_dict(self) -> dict[str, Any]:
        """Export registry state."""
        return {
            "essential": list(self._essential),
            "deferred": list(self._deferred_set),
            "registered": [
                {
                    "name": t.name,
                    "description": t.description,
                    "is_loaded": t.is_loaded,
                    "always_load": t.always_load,
                    "priority": t.priority,
                }
                for t in self._deferred.values()
            ],
        }
