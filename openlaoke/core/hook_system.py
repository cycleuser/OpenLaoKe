"""Hook-based plugin system inspired by codg's 15-hook architecture.

codg's hook pattern: (ReadOnly Input, Mutable Output) => error
Hooks cannot break the chain (errors are logged, not propagated).
Each hook can incrementally modify the output.
Short-circuit hooks (Handled flag) allow plugins to fully take over a behavior.

Inspired by:
- codg: 15 hook types, priority sorting, short-circuit on Handled
- opencode: shell-based hooks, approval/block/modify semantics
- Openclaude: async hook execution, tool input modification
"""

from __future__ import annotations

import asyncio
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

    Inspired by codg: input=ReadOnly, output=Mutable pointer pattern.
    Hooks modify specific fields; unset fields (None) mean no modification.
    """

    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    tool_error: str | None = None
    system_prompt: str | None = None
    messages: list[dict[str, Any]] | None = None
    error_message: str | None = None
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


class HookSystem:
    """Hook-based extension system with 15 extension points.

    Hook types (inspired by codg):
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

    Short-circuit hooks (codg pattern): oauth_token, provider_resolve, error_handle
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
    ]

    SHORT_CIRCUIT_TYPES = {"oauth_token", "provider_resolve", "error_handle"}

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
    ) -> None:
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
        )
        self._hooks[hook_type].append(reg)
        self._hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)

    def _find_hook(self, hook_type: str, name: str) -> HookRegistration | None:
        for hook in self._hooks.get(hook_type, []):
            if hook.name == name:
                return hook
        return None

    def unregister(self, hook_type: str, name: str) -> bool:
        hooks = self._hooks.get(hook_type, [])
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
        """
        if output is None:
            output = HookOutput()

        hooks = self._hooks.get(hook_type, [])
        start_time = time.monotonic()
        executed_count = 0

        for hook in hooks:
            if not hook.enabled:
                continue
            if output.handled and hook_type in self.SHORT_CIRCUIT_TYPES:
                break

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

        elapsed = (time.monotonic() - start_time) * 1000
        self._record_stats(hook_type, executed_count, elapsed)

        return output

    async def execute_hooks_async(
        self,
        hook_type: str,
        input_data: HookInput,
        output: HookOutput | None = None,
    ) -> HookOutput:
        """Execute all hooks (sync + async) for a given type."""
        if output is None:
            output = HookOutput()

        hooks = self._hooks.get(hook_type, [])
        start_time = time.monotonic()
        executed_count = 0

        for hook in hooks:
            if not hook.enabled:
                continue
            if output.handled and hook_type in self.SHORT_CIRCUIT_TYPES:
                break

            try:
                if hook.is_async:
                    await hook.fn(input_data, output)
                else:
                    hook.fn(input_data, output)
                executed_count += 1
            except Exception as e:
                logger.debug("Hook %s error: %s", hook.name, e)

        elapsed = (time.monotonic() - start_time) * 1000
        self._record_stats(hook_type, executed_count, elapsed)

        return output

    def has_hooks(self, hook_type: str) -> bool:
        return bool(self._hooks.get(hook_type, []))

    def get_hook_count(self, hook_type: str) -> int:
        return len(self._hooks.get(hook_type, []))

    def get_enabled_hooks(self, hook_type: str) -> list[HookRegistration]:
        return [h for h in self._hooks.get(hook_type, []) if h.enabled]

    def get_stats(self) -> dict[str, Any]:
        return dict(self._hook_stats)

    def _record_stats(self, hook_type: str, executed_count: int, elapsed_ms: float) -> None:
        if hook_type not in self._hook_stats:
            self._hook_stats[hook_type] = {
                "total_executions": 0,
                "total_hooks_called": 0,
                "total_time_ms": 0.0,
                "avg_time_ms": 0.0,
            }
        stats = self._hook_stats[hook_type]
        stats["total_executions"] += 1
        stats["total_hooks_called"] += executed_count
        stats["total_time_ms"] += elapsed_ms
        stats["avg_time_ms"] = stats["total_time_ms"] / stats["total_executions"]

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
