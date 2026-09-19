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
    context: int = Field(
        default=0,
        description="Number of context lines around each match (like rg -C)",
    )
    multiline: bool = Field(
        default=False,
        description="Allow the pattern to span multiple lines (DOTALL matching)",
    )


def _search_file(
    file_path: str,
    rel_path: str,
    regex: re.Pattern[str],
    multiline: bool,
    context: int,
    remaining: int,
) -> tuple[list[tuple[str, int, str, str]], int, bool]:
    """Search one file. Returns (entries, match_count, hit_cap).

    Entries are (rel_path, line_num, text, marker) where marker is ':'
    for matched lines and '-' for context lines.
    """
    if remaining <= 0:
        return [], 0, True
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            text_content = fh.read()
    except (PermissionError, OSError):
        return [], 0, False

    file_lines = text_content.splitlines()
    entries: list[tuple[str, int, str, str]] = []
    match_count = 0
    hit_cap = False

    if multiline:
        matched_line_nums: list[int] = []
        for m in regex.finditer(text_content):
            line_num = text_content.count("\n", 0, m.start()) + 1
            if not matched_line_nums or matched_line_nums[-1] != line_num:
                matched_line_nums.append(line_num)
                match_count += 1
                if match_count >= remaining:
                    hit_cap = True
                    break
    else:
        matched_line_nums = [i + 1 for i, line in enumerate(file_lines) if regex.search(line)]
        if len(matched_line_nums) > remaining:
            matched_line_nums = matched_line_nums[:remaining]
            hit_cap = True
        match_count = len(matched_line_nums)

    if not matched_line_nums:
        return [], 0, False

    if context > 0:
        groups: list[list[int]] = []
        for n in matched_line_nums:
            lo = max(1, n - context)
            hi = min(len(file_lines), n + context)
            window = list(range(lo, hi + 1))
            if groups and window[0] <= groups[-1][-1] + 1:
                groups[-1].extend(x for x in window if x > groups[-1][-1])
            else:
                groups.append(window)
        matched_set = set(matched_line_nums)
        for group in groups:
            for n in group:
                marker = ":" if n in matched_set else "-"
                entries.append((rel_path, n, file_lines[n - 1].rstrip(), marker))
    else:
        for n in matched_line_nums:
            entries.append((rel_path, n, file_lines[n - 1].rstrip(), ":"))

    return entries, match_count, hit_cap


class GrepTool(Tool):
    """Search file contents using regular expressions."""

    name = "Grep"
    description = (
        "Search for a regex pattern in file contents across a directory. "
        "Supports glob filtering, case sensitivity, context lines (like rg -C), "
        "multiline matching, and multiple output modes."
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
        context = max(0, int(kwargs.get("context", 0) or 0))
        multiline = bool(kwargs.get("multiline", False))

        if not pattern:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: pattern is required",
                is_error=True,
            )

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            if multiline:
                flags |= re.DOTALL
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Invalid regex pattern: {e}",
                is_error=True,
            )

        abs_path = self._resolve_path(search_path, ctx.app_state.get_cwd())

        from openlaoke.utils.path_safety import validate_read_path

        path_error = validate_read_path(abs_path, ctx.app_state.get_cwd())
        if path_error:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=path_error,
                is_error=True,
            )

        if not os.path.isdir(abs_path):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Directory not found: {abs_path}",
                is_error=True,
            )

        gitignore = self._load_gitignore(abs_path)
        results: list[tuple[str, int, str, str]] = []
        match_count = 0
        truncated = False

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
                entries, found, hit_cap = _search_file(
                    file_path, rel_path, regex, multiline, context, max_results - match_count
                )
                results.extend(entries)
                match_count += found
                if hit_cap:
                    truncated = True
                    break

            if truncated:
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
            for path, _, _, marker in results:
                if marker != ":":
                    continue
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
        prev: tuple[str, int] | None = None
        for path, line_num, text, marker in results:
            if prev is not None and (path, line_num) != (prev[0], prev[1] + 1):
                lines.append("--")
            sep = ":" if marker == ":" else "-"
            lines.append(f"{path}{sep}{line_num}{sep} {text}")
            prev = (path, line_num)

        content = "\n".join(lines)
        if truncated:
            content += f"\n\n... (truncated at {max_results} results)"

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Found {match_count} match(es):\n{content}",
            is_error=False,
        )

    def _load_gitignore(self, path: str) -> pathspec.PathSpec | None:
        gitignore_path = os.path.join(path, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path) as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        return None

    def _resolve_path(self, path: str, cwd: str) -> str:
        from openlaoke.utils.path_safety import resolve_path

        return resolve_path(path, cwd)


def register(registry: ToolRegistry) -> None:
    registry.register(GrepTool())
