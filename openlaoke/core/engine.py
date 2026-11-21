"""One agent loop, used by every caller.

There were three copies of the same loop: the interactive REPL, the sub-agent
runner, and the non-interactive CLI. They drifted - the sub-agent path still
sent tool results in an internal format, and neither of the two small loops
checked permissions or validated arguments the way the REPL did. This module is
the shared one:

* message shaping (assistant turn with ``tool_calls``, tool results keyed by id),
* tool dispatch with validation, an allow-list, and a permission callback,
* iteration limits and an abort signal,
* a state-save callback so the sub-agent runner can persist between steps.

The REPL keeps its own streaming shell - it owns rich rendering, hooks, the
result ledger and compaction - but it now uses the same message helpers defined
here, so the shapes cannot diverge again.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from openlaoke.core.state import AppState
from openlaoke.core.tool import ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock, ToolUseBlock

STOP_DONE = "done"
STOP_MAX_ITERATIONS = "max_iterations"
STOP_ABORTED = "aborted"
STOP_ERROR = "error"


def tool_calls_payload(tool_uses: list[Any]) -> list[dict[str, Any]]:
    """The ``tool_calls`` array for an assistant message."""
    return [
        {
            "id": tool_use.id,
            "type": "function",
            "function": {
                "name": tool_use.name,
                "arguments": json.dumps(tool_use.input, ensure_ascii=False),
            },
        }
        for tool_use in tool_uses
    ]


def assistant_turn(content: str, tool_uses: list[Any] | None = None) -> dict[str, Any]:
    """One assistant message, from the parts the streaming path actually has."""
    message: dict[str, Any] = {"role": "assistant"}
    if content:
        message["content"] = content
    if tool_uses:
        message["tool_calls"] = tool_calls_payload(tool_uses)
    return message


def assistant_message(response: Any) -> dict[str, Any]:
    """Turn one provider response into the next assistant message."""
    return assistant_turn(
        getattr(response, "content", "") or "",
        getattr(response, "tool_uses", None) or [],
    )


def tool_result_message(tool_use_id: str, content: str) -> dict[str, Any]:
    """The canonical tool-result message shape."""
    return {"role": "tool", "tool_call_id": tool_use_id, "content": content}


@dataclass
class EnginePolicy:
    """What one loop is allowed to do, and what it reports as it goes."""

    max_iterations: int = 50
    tools: list[dict[str, Any]] | None = None
    allow_tools: set[str] | None = None
    check_tool: Callable[[str, dict[str, Any]], bool] | None = None
    on_text: Callable[[str], None] | None = None
    on_tool_start: Callable[[ToolUseBlock], None] | None = None
    on_tool_end: Callable[[ToolUseBlock, ToolResultBlock], None] | None = None
    transform_result: Callable[[ToolUseBlock, ToolResultBlock], ToolResultBlock] | None = None
    should_stop: Callable[[], bool] | None = None
    save_state: Callable[[int, list[dict[str, Any]], list[str], str], None] | None = None
    # Reliability / efficiency knobs. They match what the interactive REPL
    # already does, so the non-interactive and sub-agent paths stop drifting.
    repair_tool_calls: bool = True
    max_repeat_calls: int = 3
    parallel_readonly: bool = True


@dataclass
class EngineResult:
    text_parts: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    stop_reason: str = STOP_DONE
    error: str = ""

    @property
    def text(self) -> str:
        return "\n".join(part for part in self.text_parts if part)

    @property
    def ok(self) -> bool:
        return self.stop_reason in (STOP_DONE, STOP_MAX_ITERATIONS)


async def execute_tool(
    app_state: AppState,
    registry: ToolRegistry,
    tool_use: ToolUseBlock,
    policy: EnginePolicy | None = None,
) -> ToolResultBlock:
    """Run one tool call with the checks every caller should have."""
    policy = policy or EnginePolicy()
    tool = registry.get(tool_use.name)
    if tool is None:
        names = sorted(t.name for t in registry.get_all())
        preview = ", ".join(names[:12])
        more = "" if len(names) <= 12 else f" (+{len(names) - 12} more)"
        return _error(
            tool_use.id,
            f"Unknown tool: {tool_use.name}. Available tools: {preview}{more}",
        )

    if policy.allow_tools is not None and tool_use.name not in policy.allow_tools:
        return _error(tool_use.id, f"Tool '{tool_use.name}' is not enabled for this agent")

    if policy.check_tool is not None and not policy.check_tool(tool_use.name, tool_use.input):
        return _error(tool_use.id, f"Permission denied for {tool_use.name}")

    validation = tool.validate_input(tool_use.input)
    if not validation.result:
        return _error(tool_use.id, f"Validation error: {validation.message}")

    ctx = ToolContext(app_state=app_state, tool_use_id=tool_use.id)
    if policy.on_tool_start is not None:
        policy.on_tool_start(tool_use)
    result = await tool.safe_call(ctx, **tool_use.input)
    if policy.transform_result is not None:
        result = policy.transform_result(tool_use, result)
    if policy.on_tool_end is not None:
        policy.on_tool_end(tool_use, result)
    return result


async def run_loop(
    *,
    app_state: AppState,
    api: Any,
    registry: ToolRegistry,
    system_prompt: str,
    messages: list[dict[str, Any]],
    policy: EnginePolicy,
    model: str = "",
    on_usage: Callable[[Any, Any], None] | None = None,
    send_kwargs: dict[str, Any] | None = None,
) -> EngineResult:
    """Drive one conversation to its end and return what happened.

    ``messages`` is mutated in place so a caller can resume from it.
    """
    result = EngineResult(messages=messages)
    iteration = 0

    validator = None
    if policy.repair_tool_calls:
        try:
            from openlaoke.core.small_model_optimizations import ToolCallValidator

            validator = ToolCallValidator()
            validator.set_tools(registry)
        except Exception:  # noqa: BLE001 - repair is optional, never fatal
            validator = None
    repeat_counts: dict[str, int] = {}

    try:
        while iteration < policy.max_iterations:
            if policy.should_stop is not None and policy.should_stop():
                result.stop_reason = STOP_ABORTED
                break

            iteration += 1
            result.iterations = iteration

            tools = policy.tools
            if tools is not None and iteration >= policy.max_iterations:
                # The final turn is text-only, so the model has to answer
                # instead of starting work it cannot finish.
                tools = None

            response, usage, cost = await api.send_message(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                model=model or getattr(getattr(app_state, "session_config", None), "model", ""),
                **(send_kwargs or {}),
            )

            if usage is not None:
                app_state.accumulate_tokens(usage)
            if cost is not None:
                app_state.accumulate_cost(cost)
            if on_usage is not None:
                on_usage(usage, cost)

            content = getattr(response, "content", "") or ""
            if content:
                result.text_parts.append(content)
                if policy.on_text is not None:
                    policy.on_text(content)

            messages.append(assistant_message(response))
            tool_uses = getattr(response, "tool_uses", None) or []

            if policy.save_state is not None:
                policy.save_state(iteration, messages, result.text_parts, "running")

            if not tool_uses:
                if not content and getattr(response, "stop_reason", None) == "length":
                    result.stop_reason = STOP_ERROR
                    result.error = (
                        "The model hit the output token limit before producing an answer. "
                        "Raise max_tokens or reduce the request size."
                    )
                    break
                result.stop_reason = STOP_DONE
                break

            # Repair names/arguments the way the REPL does, so a small typo
            # costs nothing instead of a wasted turn.
            if validator is not None:
                repaired: list[ToolUseBlock] = []
                for tu in tool_uses:
                    name, args, _hint = validator.validate(tu.name, tu.input)
                    repaired.append(ToolUseBlock(id=tu.id, name=name, input=args))
                tool_uses = repaired

            # Break out of identical-call loops instead of burning the step budget.
            blocked: set[int] = set()
            if policy.max_repeat_calls > 0:
                for idx, tu in enumerate(tool_uses):
                    key = f"{tu.name}:{json.dumps(tu.input, sort_keys=True, default=str)}"
                    repeat_counts[key] = repeat_counts.get(key, 0) + 1
                    if repeat_counts[key] > policy.max_repeat_calls:
                        blocked.add(idx)

            runnable_idx = [idx for idx in range(len(tool_uses)) if idx not in blocked]
            results: list[ToolResultBlock | None] = [None] * len(tool_uses)
            for idx in blocked:
                tu = tool_uses[idx]
                results[idx] = _error(
                    tu.id,
                    f"Refused: '{tu.name}' was already called {policy.max_repeat_calls} "
                    "times with identical arguments. Change the arguments or the approach.",
                )

            if (
                policy.parallel_readonly
                and len(runnable_idx) > 1
                and all(registry.is_readonly(tool_uses[idx].name) for idx in runnable_idx)
            ):
                gathered = await asyncio.gather(
                    *[
                        execute_tool(app_state, registry, tool_uses[idx], policy)
                        for idx in runnable_idx
                    ],
                    return_exceptions=True,
                )
                for idx, out in zip(runnable_idx, gathered, strict=True):
                    tu = tool_uses[idx]
                    results[idx] = (
                        _error(tu.id, f"Error: {out}")
                        if isinstance(out, BaseException)
                        else out
                    )
            else:
                for idx in runnable_idx:
                    results[idx] = await execute_tool(
                        app_state, registry, tool_uses[idx], policy
                    )

            for tu, res in zip(tool_uses, results, strict=True):
                assert res is not None
                messages.append(tool_result_message(tu.id, _as_text(res.content)))

            if policy.save_state is not None:
                policy.save_state(iteration, messages, result.text_parts, "running")
        else:
            result.stop_reason = STOP_MAX_ITERATIONS

    except Exception as exc:  # noqa: BLE001 - reported through the result
        result.stop_reason = STOP_ERROR
        result.error = str(exc)

    return result


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _error(tool_use_id: str, message: str) -> ToolResultBlock:
    return ToolResultBlock(tool_use_id=tool_use_id, content=message, is_error=True)
