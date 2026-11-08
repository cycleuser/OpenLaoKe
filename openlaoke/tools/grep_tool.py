"""Grep tool - content search with structure awareness.

Beyond plain matching this tool answers the two questions a small model
otherwise spends a whole Read call on: which definition a hit belongs to, and
what a file contains at the top level.  ``mode=find`` matches file names and
``mode=outline`` lists definitions, so a survey does not need to open anything.
"""

from __future__ import annotations

import os
import re
from typing import Any

import pathspec
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

MODES = ("grep", "find", "outline")


class GrepInput(BaseModel):
    pattern: str = Field(
        default="",
        description="Regex for mode=grep; a name glob (e.g. '*_test.py') for mode=find; unused for mode=outline",
    )
    path: str = Field(default=".", description="File or directory to search in")
    glob: str | None = Field(
        default=None, description="File glob pattern to filter by (e.g., '*.py')"
    )
    mode: str = Field(
        default="grep",
        description=(
            "'grep' (default) matches file contents, 'find' matches file names, "
            "'outline' lists the classes and functions of the matched files"
        ),
    )
    output_mode: str = Field(
        default="content",
        description="grep only: 'content' (default), 'files_with_matches', 'count'",
    )
    paths_only: bool = Field(
        default=False,
        description="grep only: list file names instead of matching lines (cheapest option)",
    )
    max_regions: int = Field(
        default=8,
        description="grep only: maximum separate match regions per file before the rest are skipped",
    )
    show_structure: bool = Field(
        default=True,
        description="grep only: annotate each hit with the class or function that contains it",
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
    max_regions: int = 8,
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
        if max_regions > 0 and len(groups) > max_regions:
            groups = groups[:max_regions]
            hit_cap = True
        matched_set = set(matched_line_nums)
        for group in groups:
            for n in group:
                marker = ":" if n in matched_set else "-"
                entries.append((rel_path, n, file_lines[n - 1].rstrip(), marker))
    else:
        regions = 0
        previous: int | None = None
        for n in matched_line_nums:
            if previous is None or n > previous + 1:
                regions += 1
                if max_regions > 0 and regions > max_regions:
                    hit_cap = True
                    break
            entries.append((rel_path, n, file_lines[n - 1].rstrip(), ":"))
            previous = n

    return entries, match_count, hit_cap


class GrepTool(Tool):
    """Search file contents, file names, or file outlines."""

    name = "Grep"
    description = (
        "Search code and files. mode='grep' (default) matches contents by regex and labels each "
        "hit with the class or function containing it, so you rarely need to Read a file just for "
        "context; mode='find' matches file names by glob; mode='outline' lists the classes and "
        "functions of the matched files with line ranges. Use paths_only=true or "
        "output_mode='files_with_matches' to keep results cheap."
    )
    input_schema = GrepInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        mode = str(kwargs.get("mode") or "grep")
        if mode not in MODES:
            return self._error(ctx, f"Error: mode must be one of {', '.join(MODES)}")

        pattern = kwargs.get("pattern", "") or ""
        search_path = kwargs.get("path", ".")
        glob_pattern = kwargs.get("glob")
        case_sensitive = kwargs.get("case_sensitive", False)
        max_results = kwargs.get("max_results", 100)
        context = max(0, int(kwargs.get("context", 0) or 0))
        multiline = bool(kwargs.get("multiline", False))
        paths_only = bool(kwargs.get("paths_only", False))
        output_mode = (
            "files_with_matches" if paths_only else str(kwargs.get("output_mode") or "content")
        )
        max_regions = max(0, int(kwargs.get("max_regions", 8) or 0))
        show_structure = bool(kwargs.get("show_structure", True))

        abs_path = self._resolve_path(search_path, ctx.app_state.get_cwd())

        from openlaoke.utils.path_safety import validate_read_path

        path_error = validate_read_path(abs_path, ctx.app_state.get_cwd())
        if path_error:
            return self._error(ctx, path_error)

        if mode == "find":
            return self._find(ctx, abs_path, pattern, glob_pattern, max_results)
        if mode == "outline":
            return self._outline(ctx, abs_path, pattern, glob_pattern, max_results)

        if not pattern:
            return self._error(ctx, "Error: pattern is required for mode=grep")

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            if multiline:
                flags |= re.DOTALL
            regex = re.compile(pattern, flags)
        except re.error as e:
            return self._error(ctx, f"Error: Invalid regex pattern: {e}")

        if os.path.isfile(abs_path):
            entries, found, hit_cap = _search_file(
                abs_path,
                os.path.basename(abs_path),
                regex,
                multiline,
                context,
                max_results,
                max_regions,
            )
            return self._render_content(
                ctx,
                [(os.path.basename(abs_path), n, t, m) for _p, n, t, m in entries],
                found,
                hit_cap,
                abs_path,
                output_mode,
                show_structure,
                max_results,
                base_dir=os.path.dirname(abs_path) or ".",
            )

        if not os.path.isdir(abs_path):
            return self._error(ctx, f"Error: Directory not found: {abs_path}")

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
                    file_path,
                    rel_path,
                    regex,
                    multiline,
                    context,
                    max_results - match_count,
                    max_regions,
                )
                results.extend(entries)
                match_count += found
                if hit_cap:
                    truncated = True
                    break

            if truncated:
                break

        return self._render_content(
            ctx,
            results,
            match_count,
            truncated,
            abs_path,
            output_mode,
            show_structure,
            max_results,
            base_dir=abs_path,
        )

    def _render_content(
        self,
        ctx: ToolContext,
        results: list[tuple[str, int, str, str]],
        match_count: int,
        truncated: bool,
        searched: str,
        output_mode: str,
        show_structure: bool,
        max_results: int,
        base_dir: str = ".",
    ) -> ToolResultBlock:
        if output_mode == "files_with_matches":
            files = sorted({r[0] for r in results})
            body = "\n".join(files) if files else "No matches found"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Files with matches ({len(files)}):\n{body}",
            )

        if output_mode == "count":
            counts: dict[str, int] = {}
            for path, _, _, marker in results:
                if marker != ":":
                    continue
                counts[path] = counts.get(path, 0) + 1
            body = "\n".join(f"{path}: {count}" for path, count in sorted(counts.items()))
            return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=f"Match counts:\n{body}")

        if not results:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No matches in {searched}",
            )

        from openlaoke.utils.symbols import index_file, label_for

        cache: dict[str, list[Any]] = {}
        base = base_dir
        lines: list[str] = []
        prev: tuple[str, int] | None = None
        for path, line_num, text, marker in results:
            if prev is not None and (path, line_num) != (prev[0], prev[1] + 1):
                lines.append("--")
            sep = ":" if marker == ":" else "-"
            row = f"{path}{sep}{line_num}{sep} {text}"
            if show_structure and marker == ":":
                full = path if os.path.isabs(path) else os.path.join(base, path)
                if os.path.isfile(full):
                    if full not in cache:
                        cache[full] = index_file(full)
                    label = label_for(cache[full], line_num)
                    if label:
                        row += f"   [in {label}]"
            lines.append(row)
            prev = (path, line_num)

        content = "\n".join(lines)
        if truncated:
            content += f"\n\n... (truncated at {max_results} results)"

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Found {match_count} match(es):\n{content}",
        )

    def _iter_files(
        self, root: str, name_glob: str | None, pattern: str, limit: int
    ) -> list[tuple[str, str]]:
        """Collect (abs, rel) pairs matching a name glob, capped at ``limit``."""
        from fnmatch import fnmatch

        gitignore = self._load_gitignore(root) if os.path.isdir(root) else None
        found: list[tuple[str, str]] = []
        targets = [root] if os.path.isfile(root) else []
        for start in targets:
            if self._name_matches(os.path.basename(start), name_glob, pattern):
                found.append((start, os.path.basename(start)))
            return found

        for dir_path, dirs, files in os.walk(root):
            rel_root = os.path.relpath(dir_path, root)
            if rel_root == ".":
                rel_root = ""
            drop = []
            for d in dirs:
                rel = os.path.join(rel_root, d) if rel_root else d
                if gitignore and gitignore.match_file(rel + "/"):
                    drop.append(d)
            for d in drop:
                dirs.remove(d)
            for f in files:
                rel = os.path.join(rel_root, f) if rel_root else f
                if gitignore and gitignore.match_file(rel):
                    continue
                if name_glob and not fnmatch(f, name_glob):
                    continue
                if pattern and not self._name_matches(f, None, pattern):
                    continue
                found.append((os.path.join(dir_path, f), rel))
                if len(found) >= limit:
                    return found
        return found

    @staticmethod
    def _name_matches(name: str, name_glob: str | None, pattern: str) -> bool:
        from fnmatch import fnmatch

        if name_glob and not fnmatch(name, name_glob):
            return False
        if pattern:
            probe = pattern if any(char in pattern for char in "*?[") else f"*{pattern}*"
            return fnmatch(name, probe)
        return True

    def _find(
        self, ctx: ToolContext, root: str, pattern: str, glob: str | None, limit: int
    ) -> ToolResultBlock:
        if not (pattern or glob):
            return self._error(ctx, "Error: mode=find needs 'pattern' or 'glob' as a name pattern")
        if not os.path.exists(root):
            return self._error(ctx, f"Error: Path not found: {root}")
        found = self._iter_files(root, glob, pattern, limit)
        if not found:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content=f"No files matching '{pattern or glob}'"
            )
        body = "\n".join(rel for _abs, rel in sorted(found, key=lambda item: item[1]))
        suffix = "\n\n... (capped)" if len(found) >= limit else ""
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Found {len(found)} file(s):\n{body}{suffix}",
        )

    def _outline(
        self, ctx: ToolContext, root: str, pattern: str, glob: str | None, limit: int
    ) -> ToolResultBlock:
        if not os.path.exists(root):
            return self._error(ctx, f"Error: Path not found: {root}")
        if os.path.isfile(root):
            files = [(root, os.path.basename(root))]
        else:
            files = self._iter_files(root, glob, pattern, limit)
            if not files:
                probe = glob or pattern
                if not probe:
                    return self._error(ctx, "Error: mode=outline needs 'path' to a file, or a glob")
                files = self._iter_files(root, glob, "", limit)
        if not files:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content="No files matched for outline"
            )

        from openlaoke.utils.symbols import index_file

        blocks: list[str] = []
        for full, rel in sorted(files, key=lambda item: item[1])[:limit]:
            symbols = index_file(full)
            if not symbols:
                blocks.append(f"{rel}: no recognised definitions")
                continue
            rows = [f"{rel}:"]
            rows.extend(
                f"  {symbol.kind} {symbol.name}  L{symbol.start}-{symbol.end}" for symbol in symbols
            )
            blocks.append("\n".join(rows))
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="\n\n".join(blocks)[:16000])

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)

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
