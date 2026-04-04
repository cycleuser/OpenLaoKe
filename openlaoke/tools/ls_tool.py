"""ListDirectory tool - list directory contents."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class ListDirectoryInput(BaseModel):
    path: str | None = Field(
        default=None, description="Directory path to list (defaults to current working directory)"
    )


class ListDirectoryTool(Tool):
    """List contents of a directory."""

    name = "ListDirectory"
    description = (
        "Lists the contents of a directory. "
        "Shows files and subdirectories with their sizes and modification times. "
        "Defaults to the current working directory if no path is specified."
    )
    input_schema = ListDirectoryInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        path = kwargs.get("path")

        if path is None:
            path = ctx.app_state.get_cwd()

        path = os.path.expanduser(path)

        if not os.path.exists(path):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Path does not exist: {path}",
                is_error=True,
            )

        if not os.path.isdir(path):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Not a directory: {path}",
                is_error=True,
            )

        try:
            entries = self._list_directory(path)

            output_lines = [f"Contents of {path}:\n"]
            output_lines.append(f"{'Type':<6} {'Size':>12} {'Modified':<20} {'Name'}")
            output_lines.append("-" * 60)

            for entry in entries:
                type_str = "DIR" if entry["is_dir"] else "FILE"
                size_str = self._format_size(entry["size"]) if not entry["is_dir"] else "-"
                mod_str = entry["modified"][:19] if entry["modified"] else "-"
                name = entry["name"] + ("/" if entry["is_dir"] else "")
                output_lines.append(f"{type_str:<6} {size_str:>12} {mod_str:<20} {name}")

            output_lines.append(f"\n{len(entries)} items total")

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="\n".join(output_lines),
                is_error=False,
            )

        except PermissionError:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Permission denied: {path}",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error listing directory: {e}",
                is_error=True,
            )

    def _list_directory(self, path: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        with os.scandir(path) as scanner:
            for entry in scanner:
                try:
                    stat = entry.stat()
                    entries.append(
                        {
                            "name": entry.name,
                            "is_dir": entry.is_dir(),
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )
                except OSError:
                    entries.append(
                        {
                            "name": entry.name,
                            "is_dir": entry.is_dir(),
                            "size": 0,
                            "modified": "",
                        }
                    )

        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return entries

    def _format_size(self, size: int) -> str:
        s: float = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if s < 1024:
                return f"{s:.1f}{unit}"
            s /= 1024
        return f"{s:.1f}PB"


def register(registry: ToolRegistry) -> None:
    registry.register(ListDirectoryTool())
