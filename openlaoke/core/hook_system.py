"""Hook-based plugin system with 19 extension points.

Hooks cannot break the chain (errors are logged, not propagated).
Each hook can incrementally modify the output.
Short-circuit hooks (Handled flag) allow plugins to fully take over a behavior.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class HookInput:
    """Read-only input context for a hook."""

    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    tool_error: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    system_prompt: str = ""
    error_message: str = ""
    session_id: str = ""
    provider_name: str = ""
    model_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookOutput:
    """Mutable output that hooks can modify.

    Inspired by: input=ReadOnly, output=Mutable pointer pattern.
    Hooks modify specific fields; unset fields (None) mean no modification.
    ``feedback`` is only read on ``tool_feedback``: its text is handed back to
    the model on the next turn, so a plugin can tell the model what went wrong
    without the user having to relay it.
    """

    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    tool_error: str | None = None
    system_prompt: str | None = None
    messages: list[dict[str, Any]] | None = None
    error_message: str | None = None
    feedback: str | None = None
    handled: bool = False
    skip_execution: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


SyncHookFn = Callable[[HookInput, HookOutput], None]
AsyncHookFn = Callable[[HookInput, HookOutput], Awaitable[None]]


@dataclass
class HookRegistration:
    """A registered hook with metadata."""

    name: str
    hook_type: str
    fn: SyncHookFn | AsyncHookFn
    priority: int = 0
    enabled: bool = True
    plugin_name: str = ""
    is_async: bool = False
    timeout_ms: float = 0.0


class HookSystem:
    """Hook-based extension system with 19 extension points.

    Hook types:
    1. tools - modify tool definitions
    2. chat_params - modify temperature, top_p before LLM request
    3. chat_headers - inject custom HTTP headers
    4. permission_ask - auto-approve/deny tool permission requests
    5. shell_env - inject environment variables before shell execution
    6. tool_execute_before - modify tool arguments before execution
    7. tool_execute_after - modify tool output after execution
    8. system_prompt_transform - append/modify system prompt
    9. oauth_token - custom OAuth token resolution
    10. config_transform - dynamically override config values
    11. provider_resolve - override provider API endpoint/key/headers
    12. session_start - hook on session begin
    13. session_end - hook on session end
    14. message_transform - transform messages before LLM or to user
    15. error_handle - handle/retry/override errors
    16. turn_start - one agent turn is about to run
    17. turn_end - one agent turn finished, with its usage
    18. tool_gate - before permission: handled=True vetoes the call
    19. tool_feedback - after a call: feedback text is handed to the model

    Short-circuit hooks: oauth_token, provider_resolve, error_handle, tool_gate
    stop iterating on handled=True, enabling claim-based override.
    """

    HOOK_TYPES = [
        "tools",
        "chat_params",
        "chat_headers",
        "permission_ask",
        "shell_env",
        "tool_execute_before",
        "tool_execute_after",
        "system_prompt_transform",
        "oauth_token",
        "config_transform",
        "provider_resolve",
        "session_start",
        "session_end",
        "message_transform",
        "error_handle",
        "turn_start",
        "turn_end",
        "tool_gate",
        "tool_feedback",
    ]

    # Names jcode uses for the same extension points, so a plugin written
    # against that vocabulary registers without translation.
    TYPE_ALIASES = {
        "pre_tool": "tool_gate",
        "post_tool": "tool_execute_after",
        "pre_tool_transform": "tool_execute_before",
        "post_tool_feedback": "tool_feedback",
    }

    SHORT_CIRCUIT_TYPES = {
        "oauth_token",
        "provider_resolve",
        "error_handle",
        "tool_gate",
    }

    @classmethod
    def resolve_type(cls, hook_type: str) -> str:
        """Map an alias onto its canonical extension point."""
        return cls.TYPE_ALIASES.get(hook_type, hook_type)

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookRegistration]] = {
            hook_type: [] for hook_type in self.HOOK_TYPES
        }
        self._hook_stats: dict[str, dict[str, Any]] = {}

    def register(
        self,
        hook_type: str,
        name: str,
        fn: SyncHookFn | AsyncHookFn,
        priority: int = 0,
        plugin_name: str = "",
        timeout_ms: float = 0.0,
    ) -> None:
        """Register a hook.

        ``timeout_ms`` bounds an async hook; a sync hook cannot be preempted, so
        for those the budget is measured and reported in the stats instead.
        """
        hook_type = self.resolve_type(hook_type)
        if hook_type not in self._hooks:
            raise ValueError(f"Unknown hook type: {hook_type}. Valid types: {self.HOOK_TYPES}")

        is_async = asyncio.iscoroutinefunction(fn)
        reg = HookRegistration(
            name=name,
            hook_type=hook_type,
            fn=fn,
            priority=priority,
            plugin_name=plugin_name,
            is_async=is_async,
            timeout_ms=timeout_ms,
        )
        self._hooks[hook_type].append(reg)
        self._hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)

    def _find_hook(self, hook_type: str, name: str) -> HookRegistration | None:
        for hook in self._hooks.get(self.resolve_type(hook_type), []):
            if hook.name == name:
                return hook
        return None

    def unregister(self, hook_type: str, name: str) -> bool:
        hooks = self._hooks.get(self.resolve_type(hook_type), [])
        for i, hook in enumerate(hooks):
            if hook.name == name:
                hooks.pop(i)
                return True
        return False

    def enable_hook(self, hook_type: str, name: str) -> bool:
        hook = self._find_hook(hook_type, name)
        if hook:
            hook.enabled = True
            return True
        return False

    def disable_hook(self, hook_type: str, name: str) -> bool:
        hook = self._find_hook(hook_type, name)
        if hook:
            hook.enabled = False
            return True
        return False

    def execute_hooks(
        self,
        hook_type: str,
        input_data: HookInput,
        output: HookOutput | None = None,
    ) -> HookOutput:
        """Execute all sync hooks for a given type.

        Hooks are executed in priority order (highest first).
        Errors are caught and logged, not propagated.
        Short-circuit types stop on handled=True.

        A sync hook cannot be preempted, so ``timeout_ms`` is measured rather
        than enforced: an overrun is counted in the stats and logged, which is
        what the startup budget check reads.
        """
        hook_type = self.resolve_type(hook_type)
        if output is None:
            output = HookOutput()

        hooks = self._hooks.get(hook_type, [])
        start_time = time.monotonic()
        executed_count = 0
        overruns = 0

        for hook in hooks:
            if not hook.enabled:
                continue
            if output.handled and hook_type in self.SHORT_CIRCUIT_TYPES:
                break

            hook_start = time.monotonic()
            try:
                if hook.is_async:
                    logger.warning(
                        "Skipping async hook %s in sync context; use execute_hooks_async", hook.name
                    )
                    continue
                hook.fn(input_data, output)
                executed_count += 1
            except Exception as e:
                logger.debug("Hook %s error: %s", hook.name, e)
            else:
                if hook.timeout_ms > 0:
                    spent_ms = (time.monotonic() - hook_start) * 1000
                    if spent_ms > hook.timeout_ms:
                        overruns += 1
                        logger.warning(
                            "Hook %s took %.1fms, over its %.1fms budget",
                            hook.name,
                            spent_ms,
                            hook.timeout_ms,
                        )

        elapsed = (time.monotonic() - start_time) * 1000
        self._record_stats(hook_type, executed_count, elapsed, overruns)

        return output

    async def execute_hooks_async(
        self,
        hook_type: str,
        input_data: HookInput,
        output: HookOutput | None = None,
    ) -> HookOutput:
        """Execute all hooks (sync + async) for a given type.

        An async hook with ``timeout_ms`` set is bounded by it: a timeout is
        logged, counted, and treated as no modification rather than as a
        failure of the whole turn.
        """
        hook_type = self.resolve_type(hook_type)
        if output is None:
            output = HookOutput()

        hooks = self._hooks.get(hook_type, [])
        start_time = time.monotonic()
        executed_count = 0
        overruns = 0

        for hook in hooks:
            if not hook.enabled:
                continue
            if output.handled and hook_type in self.SHORT_CIRCUIT_TYPES:
                break

            try:
                if hook.is_async:
                    result = hook.fn(input_data, output)
                    if inspect.iscoroutine(result):
                        if hook.timeout_ms > 0:
                            await asyncio.wait_for(result, timeout=hook.timeout_ms / 1000)
                        else:
                            await result
                else:
                    hook.fn(input_data, output)
                executed_count += 1
            except TimeoutError:
                overruns += 1
                logger.warning(
                    "Hook %s timed out after %.1fms; its changes were skipped",
                    hook.name,
                    hook.timeout_ms,
                )
            except Exception as e:
                logger.debug("Hook %s error: %s", hook.name, e)

        elapsed = (time.monotonic() - start_time) * 1000
        self._record_stats(hook_type, executed_count, elapsed, overruns)

        return output

    def gate(self, input_data: HookInput) -> HookOutput:
        """Run ``tool_gate`` synchronously: the pre-permission veto point.

        Kept separate from ``execute_hooks`` so the caller reads one boolean
        and cannot forget which fields decide it: ``handled`` vetoes the call,
        ``skip_execution`` lets the tool run but suppresses its body, and
        ``tool_args`` replaces the arguments when a plugin rewrote them.
        """
        return self.execute_hooks("tool_gate", input_data)

    def has_hooks(self, hook_type: str) -> bool:
        return bool(self._hooks.get(self.resolve_type(hook_type), []))

    def get_hook_count(self, hook_type: str) -> int:
        return len(self._hooks.get(self.resolve_type(hook_type), []))

    def get_enabled_hooks(self, hook_type: str) -> list[HookRegistration]:
        return [hook for hook in self._hooks.get(self.resolve_type(hook_type), []) if hook.enabled]

    def get_stats(self) -> dict[str, Any]:
        return dict(self._hook_stats)

    def _record_stats(
        self, hook_type: str, executed_count: int, elapsed_ms: float, overruns: int = 0
    ) -> None:
        if hook_type not in self._hook_stats:
            self._hook_stats[hook_type] = {
                "total_executions": 0,
                "total_hooks_called": 0,
                "total_time_ms": 0.0,
                "avg_time_ms": 0.0,
                "timeouts": 0,
            }
        stats = self._hook_stats[hook_type]
        stats["total_executions"] += 1
        stats["total_hooks_called"] += executed_count
        stats["total_time_ms"] += elapsed_ms
        stats["avg_time_ms"] = stats["total_time_ms"] / stats["total_executions"]
        stats["timeouts"] += overruns

    def clear(self) -> None:
        for hook_type in self._hooks:
            self._hooks[hook_type] = []
        self._hook_stats.clear()


class HookRegistry:
    """Global hook registry for the application."""

    _instance: HookSystem | None = None

    @classmethod
    def get(cls) -> HookSystem:
        if cls._instance is None:
            cls._instance = HookSystem()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance:
            cls._instance.clear()
            cls._instance = None
