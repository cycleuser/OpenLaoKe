"""Batch tool - several independent calls in one turn.

Off by default, because it asks the model to emit a nested structure and weak
models fail that far more often than they fail a flat call; when it does work it
saves a whole round trip per group of independent reads.

What it will not do: run a destructive tool. A batch bypasses the interactive
permission prompt that a direct call gets, so a write inside a batch would be an
unapproved write. Destructive calls are refused with a pointer to call them
directly; nesting a batch inside a batch is refused too.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

MAX_CALLS = 10
PER_RESULT_CHAR_CAP = 8000


class BatchCall(BaseModel):
    tool: str = Field(description="Exact tool name")
    args: dict[str, Any] = Field(default_factory=dict, description="Arguments for that tool")


class BatchInput(BaseModel):
    calls: list[BatchCall] = Field(description="1-10 independent calls, executed concurrently")
    stop_on_error: bool = Field(
        default=False,
        description="Cancel the remaining calls as soon as one fails (default: run them all)",
    )


class BatchTool(Tool):
    """Run independent tool calls concurrently."""

    name = "Batch"
    description = (
        "Run 1-10 independent read-only tool calls in one turn instead of one per turn. Use it "
        "only when the calls truly do not depend on each other's output. Writes and destructive "
        "tools cannot be batched: call them directly so they get a permission prompt. A call "
        "cannot contain another Batch."
    )
    input_schema = BatchInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        registry = getattr(ctx.app_state, "_tool_registry", None)
        if registry is None:
            return self._error(
                ctx, "Error: Batch needs the tool registry; call it through the REPL."
            )

        raw_calls = kwargs.get("calls") or []
        if not isinstance(raw_calls, list) or not raw_calls:
            return self._error(ctx, "Error: calls must be a non-empty list")
        if len(raw_calls) > MAX_CALLS:
            return self._error(
                ctx, f"Error: at most {MAX_CALLS} calls per batch, got {len(raw_calls)}"
            )

        prepared: list[tuple[str, Tool, dict[str, Any]]] = []
        for index, raw in enumerate(raw_calls, start=1):
            name, args = self._unpack(raw)
            if not name:
                return self._error(ctx, f"Error: call #{index} has no tool name")
            if name == self.name:
                return self._error(ctx, "Error: a Batch cannot contain another Batch")
            tool = registry.get(name)
            if tool is None:
                return self._error(ctx, f"Error: unknown tool '{name}' in call #{index}")
            if tool.is_destructive or getattr(tool, "requires_approval", False):
                return self._error(
                    ctx,
                    f"Error: '{name}' is destructive and cannot run inside a batch. "
                    "Call it directly so the user can approve it.",
                )
            prepared.append((name, tool, args))

        stop_on_error = bool(kwargs.get("stop_on_error", False))
        tasks = [
            asyncio.create_task(self._invoke(ctx, index, name, tool, args))
            for index, (name, tool, args) in enumerate(prepared, start=1)
        ]
        results: list[str] = []
        failed = False
        for task in tasks:
            outcome = await task
            results.append(outcome[0])
            if outcome[1]:
                failed = True
                if stop_on_error:
                    for other in tasks:
                        if not other.done():
                            other.cancel()
        header = f"{len(prepared)} call(s) run" + (", stopped at the first error" if failed else "")
        body = "\n\n".join(results)
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=f"{header}\n\n{body}")

    async def _invoke(
        self, ctx: ToolContext, index: int, name: str, tool: Tool, args: dict[str, Any]
    ) -> tuple[str, bool]:
        inner = ToolContext(
            app_state=ctx.app_state,
            tool_use_id=f"{ctx.tool_use_id}-batch-{index}",
            agent_id=ctx.agent_id,
            abort_signal=ctx.abort_signal,
            file_state=ctx.file_state,
            git_store=ctx.git_store,
        )
        try:
            result = await tool.call(inner, **args)
        except Exception as exc:  # a failing call must not take the batch down
            return f"[{index}] {name} raised {type(exc).__name__}: {exc}", True

        content = result.content if isinstance(result.content, str) else json.dumps(result.content)
        if len(content) > PER_RESULT_CHAR_CAP:
            content = (
                content[:PER_RESULT_CHAR_CAP]
                + f"\n... (truncated, {len(content) - PER_RESULT_CHAR_CAP} chars omitted)"
            )
        status = "error" if result.is_error else "ok"
        return f"[{index}] {name} ({status})\n{content or '(no output)'}", bool(result.is_error)

    @staticmethod
    def _unpack(raw: Any) -> tuple[str, dict[str, Any]]:
        if isinstance(raw, BatchCall):
            return raw.tool.strip(), dict(raw.args)
        if isinstance(raw, dict):
            name = str(raw.get("tool") or raw.get("name") or "").strip()
            args = raw.get("args") or raw.get("arguments") or {}
            return name, dict(args) if isinstance(args, dict) else {}
        return "", {}

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(BatchTool())
