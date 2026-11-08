"""CodeMode tool - run Python to aggregate instead of calling tools in a loop.

The economic argument: one script that reads forty files and prints five lines
costs one tool result. Forty Read calls cost forty results, forty turns of
context, and the pruning that follows. Use it when the work is a computation
over the workspace rather than a single file operation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.code_sandbox import DEFAULT_TIMEOUT, MAX_OUTPUT_CHARS, run_code
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

HELPERS = """Available helpers (all paths confined to the workspace):
  read(path) -> str            write(path, text) -> int
  append(path, text) -> int    ls(path=".") -> list[str]
  exists(path) -> bool         glob(pattern) -> list[str]
  walk() -> list[str]          grep(pattern, path=".", limit=200) -> list[str]
Standard library is available except process, network and FFI modules.
`open` is guarded to the workspace; `os.system`/`popen`/`exec*` raise."""


class CodeModeInput(BaseModel):
    code: str = Field(
        description=(
            "Python source to run. Print what you need; only stdout/stderr come back. "
            "Helpers: read/write/append/ls/exists/glob/walk/grep."
        )
    )
    timeout: float = Field(
        default=DEFAULT_TIMEOUT,
        description="Seconds before the process is killed (default 30, max 120)",
    )


class CodeModeTool(Tool):
    """Run Python in a restricted subprocess confined to the workspace."""

    name = "CodeMode"
    description = (
        "Run a Python script over the workspace instead of issuing one tool call per file. "
        "Use it for aggregation (count, parse, diff, summarise many files), for calculations, "
        "or when a loop of Read/Grep calls would cost many turns. The sandbox confines paths "
        "to the workspace, blocks process, network and FFI modules, and kills the process at "
        "the timeout. Print the result you want back.\n\n" + HELPERS
    )
    input_schema = CodeModeInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        code = str(kwargs.get("code") or "")
        if not code.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content="Error: code is required", is_error=True
            )
        try:
            timeout = float(kwargs.get("timeout") or DEFAULT_TIMEOUT)
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        timeout = max(1.0, min(120.0, timeout))

        result = await run_code(
            code,
            cwd=ctx.app_state.get_cwd(),
            timeout=timeout,
            max_output=MAX_OUTPUT_CHARS,
        )
        if result.timed_out:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=(
                    f"CodeMode timed out after {timeout:g}s and the process was killed. "
                    "Narrow the work (fewer files, a cheaper loop) or raise the timeout."
                ),
                is_error=True,
            )

        body = result.output.strip()
        if result.exit_code not in (0, None):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Script failed (exit {result.exit_code}):\n{body or '(no output)'}",
                is_error=True,
            )
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=body or "(the script produced no output)",
        )


def register(registry: ToolRegistry) -> None:
    registry.register(CodeModeTool())
