"""Edit tool - edit file contents."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock
from openlaoke.utils.diff import diff_lines
from openlaoke.utils.file_history import track_file_edit
from openlaoke.utils.text_escapes import normalize_model_escapes


class EditInput(BaseModel):
    file_path: str = Field(description="Path to the file to edit")
    old_text: str = Field(description="Text to find and replace")
    new_text: str = Field(description="Replacement text")
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences of old_text (default false requires unique match)",
    )


class EditTool(Tool):
    """Edit a file by finding and replacing text."""

    name = "Edit"
    description = (
        "Edit a file by finding specific text and replacing it. "
        "Use this for targeted edits rather than rewriting entire files. "
        "Example: Edit(file_path='file.txt', old_text='old line', new_text='new line')"
    )
    input_schema = EditInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    def preview(self, **kwargs: Any):
        from openlaoke.core.tool import PreviewResult

        file_path = str(kwargs.get("file_path", ""))
        old_text = str(kwargs.get("old_text", ""))
        new_text = str(kwargs.get("new_text", ""))
        if not file_path or not old_text:
            return PreviewResult(summary="Error: missing file_path or old_text")
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return PreviewResult(
                summary=f"Error: {abs_path} does not exist", path=abs_path, action="noop"
            )
        try:
            with open(abs_path, encoding="utf-8", errors="replace") as f:
                original = f.read()
        except (OSError, UnicodeDecodeError):
            return PreviewResult(
                summary=f"Update {abs_path} (binary file)", path=abs_path, action="update"
            )
        count = original.count(old_text) if old_text else 0
        if count == 0:
            return PreviewResult(
                summary=f"Warning: old_text not found in {abs_path}", path=abs_path, action="noop"
            )
        old_lines = old_text.count("\n") + 1
        new_lines = new_text.count("\n") + 1
        return PreviewResult(
            summary=f"Replace {count} occurrence(s) in {abs_path} ({old_lines}→{new_lines} lines)",
            path=abs_path,
            action="update",
            lines_before=old_lines * count,
            lines_after=new_lines * count,
        )

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        old_text = normalize_model_escapes(
            str(kwargs.get("old_text", "") or kwargs.get("old_string", ""))
        )
        new_text = normalize_model_escapes(
            str(kwargs.get("new_text", "") or kwargs.get("new_string", ""))
        )
        replace_all = bool(kwargs.get("replace_all", False))

        if not file_path:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path is required",
                is_error=True,
            )

        if not old_text:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: old_text is required",
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

        try:
            with open(abs_path, encoding="utf-8") as f:
                original = f.read()

            track_file_edit(abs_path, ctx.app_state.session_id)

            if old_text not in original:
                lines = original.splitlines()
                similar = []
                old_lower = old_text.lower()
                min_len = max(4, len(old_text) // 3)
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    if (len(old_lower) >= 8 and old_lower[:min_len] in line_lower) or (
                        len(old_lower) >= 4 and old_lower in line_lower
                    ):
                        similar.append(f"Line {i + 1}: {line.strip()}")

                # Show file preview on not-found (like sekrun)
                preview = original
                if len(original) > 500:
                    preview = original[:250] + "\n...\n" + original[-250:]

                msg = f"Error: Text not found in {file_path}"
                if similar:
                    msg += "\n\nSimilar lines found:\n" + "\n".join(similar[:5])
                msg += f"\n\nFile preview:\n{preview}"
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=msg,
                    is_error=True,
                )

            # Uniqueness check: count occurrences (like sekrun's replace tool)
            first_idx = original.find(old_text)
            if replace_all:
                occurrences = original.count(old_text)
                new_content = original.replace(old_text, new_text)
            else:
                second_idx = original.find(old_text, first_idx + 1)
                if second_idx != -1:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=(
                            f"Error: old_text matches multiple locations in {file_path}. "
                            "Provide more surrounding context to make it unique, "
                            "or set replace_all=true to replace all occurrences."
                        ),
                        is_error=True,
                    )
                occurrences = 1
                new_content = original.replace(old_text, new_text, 1)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Compute and append diff
            diff_text = diff_lines(abs_path, original, new_content, True)
            result_content = (
                f"Replaced {occurrences} occurrence(s) in {abs_path}"
                if replace_all
                else f"Edited {abs_path}"
            )
            if diff_text and diff_text != "(no changes)":
                result_content += f"\n{diff_text}"

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=result_content,
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
                content=f"Error editing file: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        from openlaoke.utils.path_safety import resolve_path

        return resolve_path(path, cwd)

    def _validate_path(self, resolved: str, cwd: str) -> str | None:
        from openlaoke.utils.path_safety import validate_path

        return validate_path(resolved, cwd)


def register(registry: ToolRegistry) -> None:
    registry.register(EditTool())
