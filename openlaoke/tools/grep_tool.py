"""Grep tool - search file contents."""

from __future__ import annotations

import os
import re
from typing import Any

import pathspec
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class GrepInput(BaseModel):
    pattern: str = Field(description="Regex pattern to search for")
    path: str = Field(default=".", description="Directory to search in")
    glob: str | None = Field(
        default=None, description="File glob pattern to filter by (e.g., '*.py')"
    )
    output_mode: str = Field(
        default="content",
        description="Output mode: 'content' (default), 'files_with_matches', 'count'",
    )
    case_sensitive: bool = Field(default=False, description="Case-sensitive search")
    max_results: int = Field(default=100, description="Maximum number of results")


class GrepTool(Tool):
    """Search file contents using regular expressions."""

    name = "Grep"
    description = (
        "Search for a regex pattern in file contents across a directory. "
        "Supports glob filtering, case sensitivity options, and multiple output modes."
    )
    input_schema = GrepInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        glob_pattern = kwargs.get("glob")
        output_mode = kwargs.get("output_mode", "content")
        case_sensitive = kwargs.get("case_sensitive", False)
        max_results = kwargs.get("max_results", 100)

        if not pattern:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: pattern is required",
                is_error=True,
            )

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Invalid regex pattern: {e}",
                is_error=True,
            )

        abs_path = self._resolve_path(search_path, ctx.app_state.get_cwd())

        if not os.path.isdir(abs_path):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Directory not found: {abs_path}",
                is_error=True,
            )

        gitignore = self._load_gitignore(abs_path)
        results: list[tuple[str, int, str]] = []

        for root, dirs, files in os.walk(abs_path):
            rel_root = os.path.relpath(root, abs_path)
            if rel_root == ".":
                rel_root = ""

            dirs_to_remove = []
            for d in dirs:
                rel_path = os.path.join(rel_root, d) if rel_root else d
                if gitignore and gitignore.match_file(rel_path + "/"):
                    dirs_to_remove.append(d)
            for d in dirs_to_remove:
                dirs.remove(d)

            for f in files:
                if glob_pattern:
                    from fnmatch import fnmatch

                    if not fnmatch(f, glob_pattern):
                        continue

                rel_path = os.path.join(rel_root, f) if rel_root else f
                if gitignore and gitignore.match_file(rel_path):
                    continue

                file_path = os.path.join(root, f)
                try:
                    with open(file_path, encoding="utf-8", errors="replace") as fh:
                        for line_num, line in enumerate(fh, 1):
                            if regex.search(line):
                                results.append((rel_path, line_num, line.rstrip()))
                                if len(results) >= max_results:
                                    break
                except (PermissionError, OSError):
                    continue

                if len(results) >= max_results:
                    break

            if len(results) >= max_results:
                break

        if output_mode == "files_with_matches":
            files = sorted(set(r[0] for r in results))
            content = "\n".join(files) if files else "No matches found"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Files with matches ({len(files)}):\n{content}",
            )

        if output_mode == "count":
            counts: dict[str, int] = {}
            for path, _, _ in results:
                counts[path] = counts.get(path, 0) + 1
            content = "\n".join(f"{path}: {count}" for path, count in sorted(counts.items()))
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Match counts:\n{content}",
            )

        if not results:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No matches for '{pattern}' in {abs_path}",
                is_error=False,
            )

        lines = []
        for path, line_num, text in results:
            lines.append(f"{path}:{line_num}: {text}")

        content = "\n".join(lines)
        if len(results) >= max_results:
            content += f"\n\n... (truncated at {max_results} results)"

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Found {len(results)} match(es):\n{content}",
            is_error=False,
        )

    def _load_gitignore(self, path: str) -> pathspec.PathSpec | None:
        gitignore_path = os.path.join(path, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path) as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        return None

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))


def register(registry: ToolRegistry) -> None:
    registry.register(GrepTool())
