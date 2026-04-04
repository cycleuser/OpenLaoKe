"""Write tool - write file contents."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class WriteInput(BaseModel):
    file_path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


class WriteTool(Tool):
    """Write content to a file, creating it if it doesn't exist."""

    name = "Write"
    description = (
        "Write content to a file, creating the file if it doesn't exist. "
        "This will overwrite the entire file contents."
    )
    input_schema = WriteInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        if not file_path:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path is required",
                is_error=True,
            )

        abs_path = self._resolve_path(file_path, ctx.app_state.get_cwd())

        try:
            os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)

            was_new = not os.path.exists(abs_path)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

            action = "Created" if was_new else "Updated"
            lines = content.count("\n") + 1
            chars = len(content)

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"{action} {abs_path} ({lines} lines, {chars} chars)",
                is_error=False,
            )

        except PermissionError:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Permission denied: {abs_path}",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error writing file: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))


def register(registry: ToolRegistry) -> None:
    registry.register(WriteTool())
