"""Apply patch tool - Apply unified diff patches to files."""

from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class ApplyPatchInput(BaseModel):
    patch_content: str = Field(description="The unified diff patch content to apply")
    file_path: str | None = Field(
        default=None,
        description="Target file path (optional, extracted from patch if not provided)",
    )


class ApplyPatchTool(Tool):
    """Apply unified diff patches to files."""

    name = "ApplyPatch"
    description = (
        "Apply a unified diff patch to files. Parses the patch content and applies "
        "the changes to the target files. Supports standard unified diff format. "
        "Can auto-detect target file from patch headers."
    )
    input_schema = ApplyPatchInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        patch_content = kwargs.get("patch_content", "")
        file_path = kwargs.get("file_path")

        if not patch_content.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: patch_content is required",
                is_error=True,
            )

        try:
            patches = self._parse_patch(patch_content)
            if not patches:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content="Error: No valid patches found in the content",
                    is_error=True,
                )

            results = []
            for patch in patches:
                target_file = file_path or patch.get("file")
                if not target_file:
                    results.append("Skipped patch: No target file specified")
                    continue

                abs_path = self._resolve_path(target_file, ctx.app_state.get_cwd())

                if not os.path.exists(abs_path):
                    results.append(f"Skipped {target_file}: File not found")
                    continue

                try:
                    result = self._apply_patch_to_file(abs_path, patch)
                    results.append(result)
                except Exception as e:
                    results.append(f"Error applying patch to {target_file}: {e}")

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="\n".join(results),
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error parsing patch: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))

    def _parse_patch(self, patch_content: str) -> list[dict[str, Any]]:
        patches = []
        current_patch: dict[str, Any] | None = None
        current_hunks: list[dict[str, Any]] = []
        current_hunk: dict[str, Any] | None = None

        lines = patch_content.split("\n")

        for line in lines:
            if line.startswith("--- "):
                if current_patch and current_hunks:
                    current_patch["hunks"] = current_hunks
                    patches.append(current_patch)
                current_patch = {"file": None, "hunks": []}
                current_hunks = []
                source = line[4:].strip()
                if source.startswith("a/"):
                    source = source[2:]
                current_patch["source"] = source.split("\t")[0]
            elif line.startswith("+++ "):
                if current_patch:
                    target = line[4:].strip()
                    if target.startswith("b/"):
                        target = target[2:]
                    current_patch["file"] = target.split("\t")[0]
            elif line.startswith("@@"):
                if current_patch:
                    match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                    if match:
                        if current_hunk:
                            current_hunks.append(current_hunk)
                        current_hunk = {
                            "old_start": int(match.group(1)),
                            "old_count": int(match.group(2) or 1),
                            "new_start": int(match.group(3)),
                            "new_count": int(match.group(4) or 1),
                            "lines": [],
                        }
            elif current_hunk is not None:
                if line.startswith("+"):
                    current_hunk["lines"].append(("add", line[1:]))
                elif line.startswith("-"):
                    current_hunk["lines"].append(("remove", line[1:]))
                elif line.startswith(" "):
                    current_hunk["lines"].append(("context", line[1:]))
                elif line == "":
                    current_hunk["lines"].append(("context", ""))

        if current_hunk:
            current_hunks.append(current_hunk)
        if current_patch and current_hunks:
            current_patch["hunks"] = current_hunks
            patches.append(current_patch)

        return patches

    def _apply_patch_to_file(self, file_path: str, patch: dict[str, Any]) -> str:
        with open(file_path, encoding="utf-8") as f:
            original_lines = f.read().split("\n")

        result_lines = original_lines[:]
        offset = 0
        changes_made = 0

        for hunk in patch.get("hunks", []):
            old_start = hunk["old_start"]
            hunk_lines = hunk["lines"]

            insert_pos = old_start - 1 + offset
            remove_count = sum(1 for t, _ in hunk_lines if t == "remove")

            new_hunk_lines = [
                line_content for t, line_content in hunk_lines if t in ("add", "context")
            ]

            start_pos = max(0, insert_pos)
            end_pos = start_pos + remove_count

            context_match = True
            for i, (t, line_content) in enumerate(hunk_lines):
                if (
                    t == "context"
                    and start_pos + i < len(result_lines)
                    and result_lines[start_pos + i] != line_content
                ):
                    context_match = False
                    break

            if not context_match:
                continue

            result_lines = result_lines[:start_pos] + new_hunk_lines + result_lines[end_pos:]
            offset += len(new_hunk_lines) - remove_count
            changes_made += 1

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(result_lines))

        return f"Applied {changes_made} hunk(s) to {file_path}"


def register(registry: ToolRegistry) -> None:
    registry.register(ApplyPatchTool())
