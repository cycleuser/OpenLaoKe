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
from openlaoke.utils.diff import diff_lines
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
        if (
            ctx.file_state is not None
            and hasattr(ctx.file_state, "was_read")
            and not ctx.file_state.was_read(abs_path)
        ):
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

            # Read old content for diff (if file existed)
            old_content = ""
            if not was_new:
                try:
                    with open(abs_path, encoding="utf-8", errors="replace") as f:
                        old_content = f.read()
                except (OSError, UnicodeDecodeError):
                    old_content = ""

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Compute and append diff
            diff_text = diff_lines(abs_path, old_content, content, not was_new)

            action = "Created" if was_new else "Updated"
            lines = content.count("\n") + 1
            chars = len(content)

            result_content = f"{action} {abs_path} ({lines} lines, {chars} chars)"
            if diff_text and diff_text not in ("(no changes)", "(empty new file)"):
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
                content=f"Error writing file: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        from openlaoke.utils.path_safety import resolve_path

        return resolve_path(path, cwd)

    def _validate_path(self, resolved: str, cwd: str) -> str | None:
        from openlaoke.utils.path_safety import validate_path

        return validate_path(resolved, cwd)


def register(registry: ToolRegistry) -> None:
    registry.register(WriteTool())
