"""Append tool - append content to end of file, creating if not exists."""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import PreviewResult, Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock
from openlaoke.utils.diff import diff_lines
from openlaoke.utils.file_history import track_file_edit


class AppendInput(BaseModel):
    file_path: str = Field(description="Path to the file to append to")
    content: str = Field(description="Content to append")


class AppendFileTool(Tool):
    """Append content to end of file, creating it if it doesn't exist."""

    name = "AppendFile"
    description = (
        "Append content to the end of a file. Creates the file if it doesn't exist. "
        "Example: AppendFile(file_path='log.txt', content='new log entry\\n')"
    )
    input_schema = AppendInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False
    requires_approval = True

    def preview(self, **kwargs: Any) -> PreviewResult:
        file_path = str(kwargs.get("file_path", ""))
        if not file_path:
            return PreviewResult(summary="Error: missing file_path")
        abs_path = os.path.abspath(file_path)
        return PreviewResult(summary=f"Append to {abs_path}", path=abs_path, action="update")

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        if not file_path:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path is required",
                is_error=True,
            )

        cwd = ctx.app_state.get_cwd() if hasattr(ctx.app_state, "get_cwd") else os.getcwd()
        if os.path.isabs(file_path):
            abs_path = os.path.normpath(file_path)
        else:
            abs_path = os.path.normpath(os.path.join(cwd, file_path))

        try:
            os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
            track_file_edit(abs_path, ctx.app_state.session_id)

            old_content = ""
            file_existed = os.path.exists(abs_path)
            if file_existed:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    old_content = f.read()

            new_content = old_content + content
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            diff_text = diff_lines(abs_path, old_content, new_content, file_existed)
            appended_bytes = len(content.encode("utf-8"))
            result = f"Appended {appended_bytes} bytes to {abs_path}"
            if diff_text and diff_text not in ("(no changes)",):
                result += f"\n{diff_text}"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=result,
                is_error=False,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(AppendFileTool())
