"""Lazy tool loader for on-demand tool loading."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from openlaoke.core.tools.deferred_registry import DeferredRegistry, DeferredTool, ToolInfo

if TYPE_CHECKING:
    from openlaoke.core.tool import Tool


@dataclass
class LoaderStats:
    """Statistics about tool loading."""

    total_tools: int = 0
    loaded_tools: int = 0
    deferred_tools: int = 0
    load_count: int = 0
    cache_hits: int = 0


class LazyToolLoader:
    """Tool lazy loader - loads tools on demand to save resources."""

    def __init__(self) -> None:
        self.loaded_tools: dict[str, Tool] = {}
        self.deferred_tools: dict[str, DeferredTool] = {}
        self.always_load: set[str] = set()
        self.defer_loading: set[str] = set()
        self._registry: DeferredRegistry = DeferredRegistry()
        self._stats: LoaderStats = LoaderStats()
        self._load_lock: dict[str, asyncio.Lock] = {}

    def register_deferred(
        self,
        name: str,
        loader: Callable[[], Tool] | Callable[[], Awaitable[Tool]],
        description: str = "",
        always_load: bool = False,
        search_hint: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        """Register a deferred loading tool."""
        deferred = DeferredTool(
            name=name,
            description=description,
            loader=loader,
            always_load=always_load,
            search_hint=search_hint,
            aliases=aliases or [],
        )
        self.deferred_tools[name] = deferred
        self._registry.register(
            name=name,
            description=description,
            loader=loader,
            always_load=always_load,
            search_hint=search_hint,
            aliases=aliases,
        )
        self._stats.deferred_tools += 1
        self._stats.total_tools += 1

        if always_load:
            self.always_load.add(name)

    def register_loaded(self, name: str, tool: Tool) -> None:
        """Register an already-loaded tool."""
        self.loaded_tools[name] = tool
        self._stats.loaded_tools += 1
        self._stats.total_tools += 1

    async def get(self, name: str) -> Tool | None:
        """Get tool (load on demand if deferred)."""
        if name in self.loaded_tools:
            self._stats.cache_hits += 1
            return self.loaded_tools[name]

        if name in self.deferred_tools:
            lock = self._load_lock.setdefault(name, asyncio.Lock())
            async with lock:
                if name in self.loaded_tools:
                    self._stats.cache_hits += 1
                    return self.loaded_tools[name]

                deferred = self.deferred_tools[name]
                loader = deferred.loader

                tool: Tool
                if asyncio.iscoroutinefunction(loader):
                    async_loader = cast(Callable[[], Awaitable[Tool]], loader)
                    tool = await async_loader()
                else:
                    sync_loader = cast(Callable[[], Tool], loader)
                    tool = sync_loader()

                self.loaded_tools[name] = tool
                deferred.is_loaded = True
                self._registry.mark_loaded(name)
                self._stats.load_count += 1
                self._stats.loaded_tools += 1

                return tool

        return None

    def get_sync(self, name: str) -> Tool | None:
        """Get tool synchronously (only works for already-loaded tools)."""
        return self.loaded_tools.get(name)

    def is_loaded(self, name: str) -> bool:
        """Check if tool is already loaded."""
        return name in self.loaded_tools

    def is_deferred(self, name: str) -> bool:
        """Check if tool is deferred."""
        return name in self.deferred_tools

    async def preload_essential(self) -> None:
        """Preload all essential tools."""
        for name in list(self.always_load):
            if not self.is_loaded(name):
                await self.get(name)

    async def load_all(self) -> None:
        """Load all registered tools."""
        for name in list(self.deferred_tools.keys()):
            if not self.is_loaded(name):
                await self.get(name)

    async def load_by_names(self, names: list[str]) -> dict[str, Tool]:
        """Load specific tools by name."""
        results: dict[str, Tool] = {}
        for name in names:
            tool = await self.get(name)
            if tool:
                results[name] = tool
        return results

    def get_tool_info(self, name: str) -> ToolInfo | None:
        """Get tool info without loading."""
        return self._registry.get_tool_info(name)

    def get_all_loaded(self) -> list[Tool]:
        """Get all loaded tools."""
        return list(self.loaded_tools.values())

    def get_all_deferred_info(self) -> list[DeferredTool]:
        """Get info for all deferred tools."""
        return list(self.deferred_tools.values())

    def search(self, query: str) -> list[DeferredTool]:
        """Search deferred tools."""
        return self._registry.search(query)

    def get_stats(self) -> LoaderStats:
        """Get loading statistics."""
        return self._stats

    def get_loaded_names(self) -> set[str]:
        """Get names of loaded tools."""
        return set(self.loaded_tools.keys())

    def get_deferred_names(self) -> set[str]:
        """Get names of deferred tools."""
        return set(self.deferred_tools.keys())

    def clear_cache(self, name: str | None = None) -> None:
        """Clear loaded tool cache."""
        if name:
            if name in self.loaded_tools:
                del self.loaded_tools[name]
                if name in self.deferred_tools:
                    self.deferred_tools[name].is_loaded = False
                self._stats.loaded_tools -= 1
        else:
            self.loaded_tools.clear()
            for deferred in self.deferred_tools.values():
                deferred.is_loaded = False
            self._stats.loaded_tools = len(self.always_load)

    def to_dict(self) -> dict[str, Any]:
        """Export loader state."""
        return {
            "loaded": list(self.loaded_tools.keys()),
            "deferred": list(self.deferred_tools.keys()),
            "always_load": list(self.always_load),
            "stats": {
                "total_tools": self._stats.total_tools,
                "loaded_tools": self._stats.loaded_tools,
                "deferred_tools": self._stats.deferred_tools,
                "load_count": self._stats.load_count,
                "cache_hits": self._stats.cache_hits,
            },
        }
