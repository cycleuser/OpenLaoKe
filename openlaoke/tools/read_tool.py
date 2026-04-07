"""Read tool - read file contents."""

from __future__ import annotations

import os
from typing import Any

import chardet
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class ReadInput(BaseModel):
    file_path: str = Field(description="Path to the file to read")
    offset: int | None = Field(default=None, description="Start reading from this line (1-indexed)")
    limit: int | None = Field(default=None, description="Maximum number of lines to read")


class ReadTool(Tool):
    """Read the contents of a file."""

    name = "Read"
    description = (
        "Read the contents of a file. Supports text files, code files, and more. "
        "Use offset and limit to read specific ranges of large files."
    )
    input_schema = ReadInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset")
        limit = kwargs.get("limit")

        if not file_path:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path is required",
                is_error=True,
            )

        abs_path = self._resolve_path(file_path, ctx.app_state.get_cwd())

        if not os.path.exists(abs_path):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: File not found: {abs_path}",
                is_error=True,
            )

        if os.path.isdir(abs_path):
            entries = os.listdir(abs_path)
            entries.sort()
            dirs = [e + "/" for e in entries if os.path.isdir(os.path.join(abs_path, e))]
            files = [e for e in entries if not os.path.isdir(os.path.join(abs_path, e))]
            content = f"Directory listing for {abs_path}:\n"
            for d in dirs:
                content += f"  {d}\n"
            for f in files:
                content += f"  {f}\n"
            return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

        try:
            with open(abs_path, "rb") as file_handle:
                raw = file_handle.read()

            detected = chardet.detect(raw) or {}
            encoding = detected.get("encoding") or "utf-8"

            try:
                text = raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                text = raw.decode("utf-8", errors="replace")

            lines = text.split("\n")

            if offset is not None:
                start = max(0, offset - 1)
                lines = lines[start:]

            if limit is not None:
                lines = lines[:limit]

            total_lines = len(text.split("\n"))
            shown_start = offset if offset else 1
            shown_end = shown_start + len(lines) - 1

            numbered = []
            for i, line in enumerate(lines):
                numbered.append(f"{shown_start + i}: {line}")

            content = "\n".join(numbered)

            if total_lines > len(lines):
                content += f"\n\n... ({total_lines - len(lines)} more lines, use offset={shown_end + 1} to continue)"

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=content,
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
                content=f"Error reading file: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))


def register(registry: ToolRegistry) -> None:
    registry.register(ReadTool())
