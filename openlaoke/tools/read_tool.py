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

        path_error = self._validate_path(abs_path, ctx.app_state.get_cwd())
        if path_error:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=path_error,
                is_error=True,
            )

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
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Directory listing:\n{', '.join(dirs + files)}",
                is_error=False,
            )

        try:
            file_size = os.path.getsize(abs_path)
            if file_size > 10 * 1024 * 1024:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: File too large ({file_size / 1024 / 1024:.1f}MB). Maximum is 10MB.",
                    is_error=True,
                )

            with open(abs_path, "rb") as f:
                raw = f.read()

            detected = chardet.detect(raw)
            encoding = detected.get("encoding", "utf-8") or "utf-8"

            try:
                content = raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                content = raw.decode("utf-8", errors="replace")

            lines = content.splitlines()

            start = max(0, offset - 1) if offset is not None else 0
            end = start + limit if limit is not None else len(lines)

            selected = lines[start:end]
            total_lines = len(lines)

            if ctx.file_state and hasattr(ctx.file_state, "record_read"):
                ctx.file_state.record_read(abs_path, content)

            header = f"File: {abs_path} ({total_lines} lines)\n"
            if offset or limit:
                header += f"Showing lines {start + 1}-{min(end, total_lines)} of {total_lines}\n"
            header += "-" * 40 + "\n"

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=header + "\n".join(selected),
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
        from openlaoke.utils.path_safety import resolve_path

        return resolve_path(path, cwd)

    def _validate_path(self, resolved: str, cwd: str) -> str | None:
        from openlaoke.utils.path_safety import validate_path

        return validate_path(resolved, cwd)


def register(registry: ToolRegistry) -> None:
    registry.register(ReadTool())
