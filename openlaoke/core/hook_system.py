"""Hook-based plugin system inspired by codg's 15-hook architecture.

codg's hook pattern: (ReadOnly Input, Mutable Output) => error
Hooks cannot break the chain (errors are logged, not propagated).
Each hook can incrementally modify the output.
Short-circuit hooks (Handled flag) allow plugins to fully take over a behavior.

This module provides the core hook infrastructure for OpenLaoKe.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


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
    """Mutable output that hooks can modify."""

    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    tool_error: str | None = None
    system_prompt: str | None = None
    messages: list[dict[str, Any]] | None = None
    error_message: str | None = None
    handled: bool = False
    skip_execution: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


HookFn = Callable[[HookInput, HookOutput], None]


@dataclass
class HookRegistration:
    """A registered hook with metadata."""

    name: str
    hook_type: str
    fn: HookFn
    priority: int = 0
    enabled: bool = True
    plugin_name: str = ""


class HookSystem:
    """Hook-based extension system with 15 extension points.

    Hook types (inspired by codg):
    1. Tools - modify tool definitions
    2. ChatParams - modify temperature, top_p before LLM request
    3. ChatHeaders - inject custom HTTP headers
    4. PermissionAsk - auto-approve/deny tool permission requests
    5. ShellEnv - inject environment variables before shell execution
    6. ToolExecuteBefore - modify tool arguments before execution
    7. ToolExecuteAfter - modify tool output after execution
    8. SystemPromptTransform - append/modify system prompt
    9. OAuthToken - custom OAuth token resolution
    10. ConfigTransform - dynamically override config values
    11. ProviderResolve - override provider API endpoint/key/headers
    12. SessionStart - hook on session begin
    13. SessionEnd - hook on session end
    14. MessageTransform - transform messages before LLM or to user
    15. ErrorHandle - handle/retry/override errors
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

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookRegistration]] = {
            hook_type: [] for hook_type in self.HOOK_TYPES
        }
        self._hook_stats: dict[str, dict[str, Any]] = {}

    def register(
        self,
        hook_type: str,
        name: str,
        fn: HookFn,
        priority: int = 0,
        plugin_name: str = "",
    ) -> None:
        """Register a hook for a specific hook type."""
        if hook_type not in self._hooks:
            raise ValueError(f"Unknown hook type: {hook_type}. Valid types: {self.HOOK_TYPES}")

        reg = HookRegistration(
            name=name,
            hook_type=hook_type,
            fn=fn,
            priority=priority,
            plugin_name=plugin_name,
        )
        self._hooks[hook_type].append(reg)
        self._hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)

    def unregister(self, hook_type: str, name: str) -> bool:
        """Unregister a hook by name."""
        hooks = self._hooks.get(hook_type, [])
        for i, hook in enumerate(hooks):
            if hook.name == name:
                hooks.pop(i)
                return True
        return False

    def enable_hook(self, hook_type: str, name: str) -> bool:
        hooks = self._hooks.get(hook_type, [])
        for hook in hooks:
            if hook.name == name:
                hook.enabled = True
                return True
        return False

    def disable_hook(self, hook_type: str, name: str) -> bool:
        hooks = self._hooks.get(hook_type, [])
        for hook in hooks:
            if hook.name == name:
                hook.enabled = True
                return False
        return False

    def execute_hooks(
        self,
        hook_type: str,
        input_data: HookInput,
        output: HookOutput | None = None,
    ) -> HookOutput:
        """Execute all registered hooks for a given type.

        Hooks are executed in priority order (highest first).
        Errors are caught and logged, not propagated.
        If a hook sets handled=True, subsequent hooks are skipped.
        """
        if output is None:
            output = HookOutput()

        hooks = self._hooks.get(hook_type, [])
        start_time = time.monotonic()

        for hook in hooks:
            if not hook.enabled:
                continue
            if output.handled:
                break

            with contextlib.suppress(Exception):
                hook.fn(input_data, output)

        elapsed = (time.monotonic() - start_time) * 1000
        self._record_stats(hook_type, len(hooks), elapsed)

        return output

    def has_hooks(self, hook_type: str) -> bool:
        return bool(self._hooks.get(hook_type, []))

    def get_hook_count(self, hook_type: str) -> int:
        return len(self._hooks.get(hook_type, []))

    def get_stats(self) -> dict[str, Any]:
        return dict(self._hook_stats)

    def _record_stats(self, hook_type: str, count: int, elapsed_ms: float) -> None:
        if hook_type not in self._hook_stats:
            self._hook_stats[hook_type] = {
                "total_executions": 0,
                "total_hooks_called": 0,
                "total_time_ms": 0.0,
                "avg_time_ms": 0.0,
            }
        stats = self._hook_stats[hook_type]
        stats["total_executions"] += 1
        stats["total_hooks_called"] += count
        stats["total_time_ms"] += elapsed_ms
        stats["avg_time_ms"] = stats["total_time_ms"] / stats["total_executions"]

    def clear(self) -> None:
        """Clear all registered hooks (for testing)."""
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
