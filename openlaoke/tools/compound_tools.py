"""Compound tools - combine multiple tool operations into single calls.

Reduces sequential tool calls for better efficiency with small models.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class CompoundReadAndPatchInput(BaseModel):
    file_path: str = Field(description="Path to the file to read and patch")
    old_text: str = Field(description="Text to find")
    new_text: str = Field(description="Text to replace with")
    offset: int | None = Field(default=None, description="Optional starting line to read from")


class CompoundFindAndReadInput(BaseModel):
    pattern: str = Field(description="Glob pattern to find files")
    path: str = Field(default=".", description="Directory to search in")
    max_files: int = Field(default=10, description="Max files to read")


class CompoundSearchAndReadInput(BaseModel):
    pattern: str = Field(description="Regex pattern to search")
    file_glob: str | None = Field(default=None, description="File pattern to filter (e.g. '*.py')")
    max_results: int = Field(default=5, description="Max search results to return with context")
    context_lines: int = Field(default=3, description="Lines of context around matches")


class ReadAndPatchTool(Tool):
    """Read a file and apply a patch in a single operation."""

    name = "ReadAndPatch"
    description = (
        "Read a file and apply a text replacement in a single operation. "
        "Combines Read + Edit for small models that lose context across multiple sequential calls. "
        "The result shows the file after the patch is applied."
    )
    input_schema = CompoundReadAndPatchInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        from openlaoke.tools.edit_tool import EditTool
        from openlaoke.tools.read_tool import ReadTool

        file_path = kwargs.get("file_path", "")
        old_text = kwargs.get("old_text", "")
        new_text = kwargs.get("new_text", "")
        offset = kwargs.get("offset")

        if not file_path or not old_text:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path and old_text are required",
                is_error=True,
            )

        read_tool = ReadTool()
        edit_tool = EditTool()

        read_result = await read_tool.call(ctx, file_path=file_path, offset=offset)
        if read_result.is_error:
            return read_result

        edit_result = await edit_tool.call(ctx, file_path=file_path, old_text=old_text, new_text=new_text)
        if edit_result.is_error:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"File read succeeded:\n{read_result.content}\n\nPatch failed: {edit_result.content}",
                is_error=True,
            )

        combined = (
            f"File read:\n{read_result.content}\n\n"
            f"Patch applied: '{old_text}' -> '{new_text}'\n"
            f"{edit_result.content}"
        )
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=combined, is_error=False)


class FindAndReadTool(Tool):
    """Find files by glob pattern and read the matching ones."""

    name = "FindAndRead"
    description = (
        "Find files matching a glob pattern and read their contents in one operation. "
        "Combines Glob + Read. Reads up to max_files matching files."
    )
    input_schema = CompoundFindAndReadInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        from openlaoke.tools.glob_tool import GlobTool
        from openlaoke.tools.read_tool import ReadTool

        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        max_files = kwargs.get("max_files", 10)

        if not pattern:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: pattern is required",
                is_error=True,
            )

        glob_tool = GlobTool()
        glob_result = await glob_tool.call(ctx, pattern=pattern, path=search_path)
        if glob_result.is_error:
            return glob_result

        lines = glob_result.content.strip().split("\n")
        file_paths = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
        file_paths = file_paths[:max_files]

        if not file_paths:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No files found matching: {pattern}",
                is_error=False,
            )

        read_tool = ReadTool()
        outputs = [f"Found {len(file_paths)} file(s) matching '{pattern}':\n"]
        for fp in file_paths:
            r = await read_tool.call(ctx, file_path=fp, limit=100)
            outputs.append(r.content if not r.is_error else f"Error reading {fp}: {r.content}")
            outputs.append("")

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(outputs),
            is_error=False,
        )


class SearchAndReadTool(Tool):
    """Search file contents and read matching files in one operation."""

    name = "SearchAndRead"
    description = (
        "Search code with regex and read the matching file contents in one operation. "
        "Combines Grep + Read. Returns search results with surrounding context."
    )
    input_schema = CompoundSearchAndReadInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        from openlaoke.tools.grep_tool import GrepTool

        pattern = kwargs.get("pattern", "")
        file_glob = kwargs.get("file_glob")
        max_results = kwargs.get("max_results", 5)

        if not pattern:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: pattern is required",
                is_error=True,
            )

        grep_tool = GrepTool()
        grep_kwargs: dict[str, Any] = {"pattern": pattern, "max_results": max_results}
        if file_glob:
            grep_kwargs["glob"] = file_glob

        grep_result = await grep_tool.call(ctx, **grep_kwargs)
        if grep_result.is_error:
            return grep_result

        combined = f"Search results for '{pattern}':\n{grep_result.content}"

        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=combined, is_error=False)


def register(registry: ToolRegistry) -> None:
    registry.register(ReadAndPatchTool())
    registry.register(FindAndReadTool())
    registry.register(SearchAndReadTool())
