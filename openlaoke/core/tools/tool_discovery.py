"""Tool discovery system for automatic tool detection."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openlaoke.core.tools.deferred_registry import DeferredRegistry

if TYPE_CHECKING:
    from openlaoke.core.tool import Tool


@dataclass
class DiscoveryResult:
    """Result of tool discovery."""

    discovered: list[str]
    loaded: list[str]
    failed: list[str]
    total: int


class ToolDiscovery:
    """Automatic tool discovery from modules."""

    def __init__(self, registry: DeferredRegistry | None = None) -> None:
        self._registry = registry or DeferredRegistry()
        self._tool_modules: list[str] = []
        self._discovered: dict[str, str] = {}

    def add_module_path(self, module_path: str) -> None:
        """Add a module path to scan for tools."""
        self._tool_modules.append(module_path)

    def add_directory(self, directory: Path) -> None:
        """Add a directory to scan for tool modules."""
        if directory.exists():
            for py_file in directory.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                module_name = py_file.stem
                full_path = f"{directory.parent.name}.{module_name}"
                self._tool_modules.append(full_path)

    def discover_tools(self) -> DiscoveryResult:
        """Discover all tools from registered modules."""
        result = DiscoveryResult(discovered=[], loaded=[], failed=[], total=0)

        for module_path in self._tool_modules:
            try:
                module = importlib.import_module(module_path)
                self._scan_module(module, result)
            except ImportError as e:
                result.failed.append(f"{module_path}: {e}")

        result.total = len(result.discovered)
        return result

    def _scan_module(self, module: Any, result: DiscoveryResult) -> None:
        """Scan a module for tool classes."""
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and self._is_tool_class(obj):
                tool_name = getattr(obj, "name", name)
                description = getattr(obj, "description", "")
                search_hint = getattr(obj, "search_hint", "")
                aliases = getattr(obj, "aliases", [])
                defer_loading = getattr(obj, "defer_loading", False)
                always_load = getattr(obj, "always_load", False)

                self._discovered[tool_name] = module.__name__

                if defer_loading and not always_load:
                    result.discovered.append(tool_name)
                    tool_class = obj
                    self._registry.register(
                        name=tool_name,
                        description=description,
                        loader=lambda cls=tool_class: cls(),
                        always_load=always_load,
                        search_hint=search_hint,
                        aliases=list(aliases) if aliases else [],
                    )
                else:
                    result.loaded.append(tool_name)

    def _is_tool_class(self, obj: Any) -> bool:
        """Check if a class is a tool."""
        from openlaoke.core.tool import Tool

        try:
            return (
                inspect.isclass(obj)
                and issubclass(obj, Tool)
                and obj is not Tool
                and not inspect.isabstract(obj)
            )
        except TypeError:
            return False

    def get_discovered_tools(self) -> dict[str, str]:
        """Get all discovered tools and their modules."""
        return self._discovered.copy()

    def get_registry(self) -> DeferredRegistry:
        """Get the deferred registry."""
        return self._registry

    def auto_register_from_tools_dir(self, base_package: str = "openlaoke.tools") -> None:
        """Auto-register tools from openlaoke.tools directory."""
        try:
            tools_package = importlib.import_module(base_package)
            package_path = (
                Path(tools_package.__file__).parent
                if tools_package.__file__
                else Path("openlaoke/tools")
            )

            self.add_directory(package_path)
        except ImportError:
            pass

    def create_loader_function(self, module_path: str, class_name: str) -> Callable[[], Tool]:
        """Create a loader function for a tool."""

        def loader() -> Tool:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            instance: Tool = cls()
            return instance

        return loader

    def to_dict(self) -> dict[str, Any]:
        """Export discovery state."""
        return {
            "modules": self._tool_modules,
            "discovered": self._discovered,
        }
