"""Write tool - write file contents.

Includes:
- Preview (dry-run diff) for permission prompts
- Read-before-write guard: first attempt to write a file that hasn't been
  read this session is refused with a hint; second attempt is allowed.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import PreviewResult, Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock
from openlaoke.utils.file_history import track_file_edit

_WRITE_GUARD_ATTEMPTS: dict[str, int] = {}


class WriteInput(BaseModel):
    file_path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


class WriteTool(Tool):
    """Write content to a file, creating it if it doesn't exist."""

    name = "Write"
    description = (
        "Write content to a file, creating the file if it doesn't exist. "
        "This will overwrite the entire file contents. "
        "IMPORTANT: Both file_path and content parameters are REQUIRED. "
        "Example: Write(file_path='/path/to/file.txt', content='file contents here')"
    )
    input_schema = WriteInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    def preview(self, **kwargs: Any) -> PreviewResult:
        file_path = str(kwargs.get("file_path", ""))
        content = str(kwargs.get("content", ""))
        if not file_path:
            return PreviewResult(summary="Error: missing file_path")
        abs_path = os.path.abspath(file_path)
        new_lines = content.count("\n") + 1 if content else 0
        if os.path.exists(abs_path):
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    old = f.read()
                old_lines = old.count("\n") + 1 if old else 0
                return PreviewResult(
                    summary=f"Update {abs_path} ({old_lines}→{new_lines} lines)",
                    path=abs_path,
                    action="update",
                    lines_before=old_lines,
                    lines_after=new_lines,
                )
            except (OSError, UnicodeDecodeError):
                return PreviewResult(
                    summary=f"Update {abs_path} (binary file)",
                    path=abs_path,
                    action="update",
                )
        return PreviewResult(
            summary=f"Create {abs_path} ({new_lines} lines)",
            path=abs_path,
            action="create",
            lines_after=new_lines,
        )

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

        path_error = self._validate_path(abs_path, ctx.app_state.get_cwd())
        if path_error:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=path_error,
                is_error=True,
            )

        # --- read-before-write guard ---
        if ctx.file_state is not None and hasattr(ctx.file_state, "was_read") and not ctx.file_state.was_read(abs_path):
            key = f"{ctx.app_state.session_id}:{abs_path}"
            attempts = _WRITE_GUARD_ATTEMPTS.get(key, 0)
            if attempts < 1:
                _WRITE_GUARD_ATTEMPTS[key] = attempts + 1
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=(
                        f"Guard: '{abs_path}' has not been read this session. "
                        "Small models often overwrite files with incorrect content "
                        "when they haven't seen what's already there. "
                        "Read the file first, then write again. "
                        "(This guard will be bypassed on your next write attempt.)"
                    ),
                    is_error=False,
                )
            _WRITE_GUARD_ATTEMPTS[key] = attempts + 1

        try:
            os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)

            track_file_edit(abs_path, ctx.app_state.session_id)

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
    try:
        rel = os.path.relpath(child, parent)
        return not rel.startswith("..")
    except ValueError:
        return False


def _is_user_home_path(path: str) -> bool:
    home = os.path.realpath(os.path.expanduser("~"))
    home_parent = os.path.dirname(home)
    if path.startswith(home_parent + "/"):
        parts = path[len(home_parent) + 1 :].split("/", 1)
        if parts and os.path.basename(home).startswith(parts[0]):
            return True
    return False


def register(registry: ToolRegistry) -> None:
    registry.register(WriteTool())
