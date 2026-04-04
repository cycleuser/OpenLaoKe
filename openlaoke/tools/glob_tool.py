"""Glob tool - find files by pattern."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pathspec
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern to match files (e.g., '**/*.py')")
    path: str = Field(default=".", description="Directory to search in")


class GlobTool(Tool):
    """Find files matching a glob pattern."""

    name = "Glob"
    description = (
        "Fast file pattern matching using glob patterns. "
        "Supports ** for recursive matching. Respects .gitignore."
    )
    input_schema = GlobInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")

        if not pattern:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: pattern is required",
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
        matches = []
        max_results = 1000

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
                rel_path = os.path.join(rel_root, f) if rel_root else f
                if gitignore and gitignore.match_file(rel_path):
                    continue

                if self._match_pattern(rel_path, pattern):
                    matches.append(rel_path)
                    if len(matches) >= max_results:
                        break

            if len(matches) >= max_results:
                break

        matches.sort()

        if not matches:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No files matching '{pattern}' in {abs_path}",
                is_error=False,
            )

        truncated = len(matches) > max_results
        display = matches[:max_results]
        content = "\n".join(display)
        if truncated:
            content += f"\n\n... ({len(matches) - max_results} more results)"

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Found {len(matches)} file(s):\n{content}",
            is_error=False,
        )

    def _match_pattern(self, path: str, pattern: str) -> bool:
        from fnmatch import fnmatch
        return fnmatch(path, pattern) or fnmatch(os.path.basename(path), pattern)

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
    registry.register(GlobTool())
