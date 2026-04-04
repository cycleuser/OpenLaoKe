"""Edit tool - make targeted edits to files."""

from __future__ import annotations

import difflib
import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock
from openlaoke.utils.file_history import track_file_edit


class EditInput(BaseModel):
    file_path: str = Field(description="Path to the file to edit")
    old_string: str = Field(description="The exact text to find and replace")
    new_string: str = Field(description="The text to replace it with")
    replace_all: bool = Field(
        default=False, description="Replace all occurrences (default: only first)"
    )


class EditTool(Tool):
    """Make targeted edits to files by finding and replacing text."""

    name = "Edit"
    description = (
        "Make targeted edits to a file by replacing specific text. "
        "Provide the exact text to find (old_string) and the replacement (new_string). "
        "Use replace_all to replace all occurrences."
    )
    input_schema = EditInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

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

        try:
            with open(abs_path, encoding="utf-8") as f:
                original = f.read()

            track_file_edit(abs_path, ctx.app_state.session_id)

            if old_string not in original:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=self._suggest_matches(original, old_string, abs_path),
                    is_error=True,
                )

            if replace_all:
                updated = original.replace(old_string, new_string)
                count = original.count(old_string)
            else:
                updated = original.replace(old_string, new_string, 1)
                count = 1

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(updated)

            diff = self._generate_diff(original, updated, abs_path)

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Replaced {count} occurrence(s) in {abs_path}\n\n{diff}",
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error editing file: {e}",
                is_error=True,
            )

    def _generate_diff(self, original: str, updated: str, filename: str) -> str:
        orig_lines = original.splitlines(keepends=True)
        new_lines = updated.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            n=3,
        )
        return "".join(diff)

    def _suggest_matches(self, content: str, search: str, filename: str) -> str:
        lines = content.split("\n")
        search_lower = search.lower()

        similar_lines = []
        for i, line in enumerate(lines):
            if search_lower in line.lower():
                similar_lines.append((i + 1, line.strip()))

        if similar_lines:
            suggestions = "\n".join(f"  Line {num}: {text}" for num, text in similar_lines[:10])
            return (
                f"Error: Exact text not found in {filename}.\n"
                f"Similar lines found:\n{suggestions}\n\n"
                f"Make sure old_string matches the exact text in the file, "
                f"including whitespace and line endings."
            )
        return f"Error: Text not found in {filename}. No similar lines found."

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))


def register(registry: ToolRegistry) -> None:
    registry.register(EditTool())
