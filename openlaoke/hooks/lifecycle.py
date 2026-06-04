"""Standardized 11-event hook model (lifecycle).

This module complements :mod:`openlaoke.core.hook_system` with a flat
list of 11 named lifecycle events and helpers for invoking them
either synchronously or asynchronously.

The names are intentionally stable so external plugins can register
against them. Exit codes:

* ``exit 0`` — pass
* ``exit 2`` — block on ``PreToolUse`` / ``UserPromptSubmit``
* ``PostLLMCall`` — rewrites the reasoning block (cannot block, cannot
  fail)

Output per stream is capped at 256 KiB.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class HookEvent(StrEnum):
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    POST_LLM_CALL = "PostLLMCall"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    SUBAGENT_STOP = "SubagentStop"
    NOTIFICATION = "Notification"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"


# Events where exit 2 from a hook BLOCKS the operation.
_BLOCKING_EVENTS = frozenset(
    {
        HookEvent.PRE_TOOL_USE,
        HookEvent.USER_PROMPT_SUBMIT,
    }
)


# Events that are advisory only (cannot block).
_ADVISORY_EVENTS = frozenset(
    {
        HookEvent.POST_LLM_CALL,
        HookEvent.POST_TOOL_USE,
        HookEvent.STOP,
        HookEvent.SESSION_END,
        HookEvent.SUBAGENT_STOP,
        HookEvent.NOTIFICATION,
        HookEvent.POST_COMPACT,
    }
)


@dataclass
class HookPayload:
    """JSON payload delivered to a hook handler."""

    event: str
    session_id: str
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    system_prompt: str = ""
    reasoning: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """Hook handler return value."""

    exit_code: int = 0
    output: str = ""
    transformed: dict[str, Any] = field(default_factory=dict)


HookHandler = Callable[[HookPayload], HookResult | Awaitable[HookResult]]


@dataclass
class HookSpec:
    name: str
    event: HookEvent
    handler: HookHandler
    scope: str = "project"
    enabled: bool = True
    priority: int = 0


_MAX_OUTPUT_BYTES = 256 * 1024


class HookRegistryV2:
    """Flat 11-event hook registry.

    Project hooks override user hooks; both override built-ins. Hooks
    are matched on ``(event, name)``.
    """

    def __init__(self) -> None:
        self._hooks: dict[HookEvent, list[HookSpec]] = {event: [] for event in HookEvent}

    def register(self, spec: HookSpec) -> None:
        if spec.event not in self._hooks:
            raise ValueError(f"unknown hook event: {spec.event}")
        existing = self._hooks[spec.event]
        for i, h in enumerate(existing):
            if h.name == spec.name:
                existing[i] = spec
                return
        existing.append(spec)
        existing.sort(key=lambda h: h.priority, reverse=True)

    def unregister(self, event: HookEvent, name: str) -> bool:
        hooks = self._hooks.get(event, [])
        for i, h in enumerate(hooks):
            if h.name == name:
                hooks.pop(i)
                return True
        return False

    def list_hooks(self, event: HookEvent | None = None) -> list[HookSpec]:
        if event is None:
            all_hooks: list[HookSpec] = []
            for hooks in self._hooks.values():
                all_hooks.extend(hooks)
            return all_hooks
        return list(self._hooks.get(event, []))

    async def fire(
        self,
        event: HookEvent,
        payload: HookPayload,
    ) -> tuple[HookResult, dict[str, Any]]:
        """Fire all hooks for an event and aggregate their output.

        Returns ``(aggregate_result, transformed_fields)``. For
        ``PostLLMCall`` the transformed ``reasoning`` field wins; for
        ``PreCompact`` the ``extra_summary`` field is added to the
        summary prompt.
        """
        hooks = self._hooks.get(event, [])
        agg_exit = 0
        agg_output: list[str] = []
        transformed: dict[str, Any] = {}
        start = time.monotonic()
        for hook in hooks:
            if not hook.enabled:
                continue
            if agg_exit == 2 and event in _BLOCKING_EVENTS:
                break
            try:
                result = hook.handler(payload)
                if inspect.iscoroutine(result):
                    result = await result
            except Exception as exc:
                logger.debug("Hook %s error: %s", hook.name, exc)
                continue
            if not isinstance(result, HookResult):
                continue
            output = (result.output or "")[:_MAX_OUTPUT_BYTES]
            agg_output.append(output)
            if result.exit_code == 2 and event in _BLOCKING_EVENTS:
                agg_exit = 2
            transformed.update(result.transformed)
        (time.monotonic() - start) * 1000
        agg = HookResult(
            exit_code=agg_exit,
            output="\n".join(agg_output),
            transformed=transformed,
        )
        return agg, transformed

    def fire_sync(
        self,
        event: HookEvent,
        payload: HookPayload,
    ) -> tuple[HookResult, dict[str, Any]]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.fire(event, payload))
        future = asyncio.run_coroutine_threadsafe(self.fire(event, payload), loop)
        return future.result()
