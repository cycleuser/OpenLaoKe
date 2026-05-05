"""Edit tool - edit file contents."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock
from openlaoke.utils.file_history import track_file_edit


class EditInput(BaseModel):
    file_path: str = Field(description="Path to the file to edit")
    old_text: str = Field(description="Text to find and replace")
    new_text: str = Field(description="Replacement text")


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

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        file_path = kwargs.get("file_path", "")
        old_text = kwargs.get("old_text", "")
        new_text = kwargs.get("new_text", "")

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
                for i, line in enumerate(lines):
                    if old_text.lower() in line.lower() or line.lower() in old_text.lower():
                        similar.append(f"Line {i + 1}: {line.strip()}")

                msg = f"Error: Text not found in {file_path}"
                if similar:
                    msg += "\n\nSimilar lines found:\n" + "\n".join(similar[:5])
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=msg,
                    is_error=True,
                )

            new_content = original.replace(old_text, new_text, 1)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Edited {abs_path}",
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
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))

    def _validate_path(self, resolved: str, cwd: str) -> str | None:
        real_resolved = os.path.realpath(resolved)
        real_cwd = os.path.realpath(cwd)
        home = os.path.realpath(os.path.expanduser("~"))

        if not _contains(real_cwd, real_resolved) and not _contains(home, real_resolved):
            if _is_user_home_path(resolved):
                return None
            return f"Path '{resolved}' is outside workspace and home directory"
        return None


def _contains(parent: str, child: str) -> bool:
    """Check if child path is inside parent (inspired by opencode)."""
    try:
        rel = os.path.relpath(child, parent)
        return not rel.startswith("..")
    except ValueError:
        return False


def _is_user_home_path(path: str) -> bool:
    """Check if path is under user home directory, allowing truncated usernames."""
    home = os.path.realpath(os.path.expanduser("~"))
    home_parent = os.path.dirname(home)
    if path.startswith(home_parent + "/"):
        parts = path[len(home_parent) + 1 :].split("/", 1)
        if parts and os.path.basename(home).startswith(parts[0]):
            return True
    return False


def register(registry: ToolRegistry) -> None:
    registry.register(EditTool())
