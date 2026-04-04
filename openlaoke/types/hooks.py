"""Hook type definitions for extensibility."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from openlaoke.types.core_types import Message


class HookType(StrEnum):
    """Types of hooks that can be registered."""

    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_API_CALL = "pre_api_call"
    POST_API_CALL = "post_api_call"
    ON_MESSAGE = "on_message"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"
    ON_TASK_START = "on_task_start"
    ON_TASK_END = "on_task_end"
    ON_ERROR = "on_error"
    PRE_COMPACT = "pre_compact"
    POST_COMPACT = "post_compact"
    STOP = "stop"
    STOP_FAILURE = "stop_failure"
    SUBAGENT_START = "subagent_start"
    SUBAGENT_STOP = "subagent_stop"
    TEAMMATE_IDLE = "teammate_idle"
    CONFIG_CHANGE = "config_change"
    CWD_CHANGED = "cwd_changed"
    FILE_CHANGED = "file_changed"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_DENIED = "permission_denied"
    NOTIFICATION = "notification"
    USER_PROMPT_SUBMIT = "user_prompt_submit"


@dataclass
class HookCommand:
    """Hook command configuration for shell-based hooks."""

    type: str = "command"
    command: str | None = None
    shell: str = "bash"
    timeout: int = 60000
    prompt: str | None = None


@dataclass
class FunctionHook:
    """Function-based hook with embedded callback."""

    type: str = "function"
    id: str | None = None
    timeout: int = 30000
    callback: Callable[[list[Message]], bool] | None = None
    error_message: str = ""
    status_message: str | None = None


@dataclass
class HookMatcher:
    """Hook matcher for filtering hooks by conditions."""

    event: HookType
    matchers: list[dict[str, Any]] = field(default_factory=list)
    command: HookCommand | None = None
    function: FunctionHook | None = None
    skill_root: str | None = None


@dataclass
class HookContext:
    """Context passed to hook handlers."""

    hook_type: HookType
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    tool_name: str = ""
    task_id: str = ""
    agent_id: str | None = None
    agent_type: str | None = None
    cwd: str = ""
    transcript_path: str = ""


@dataclass
class HookResult:
    """Result returned by a hook handler."""

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    should_abort: bool = False
    outcome: str = "success"
    blocking_error: str | None = None
    prevent_continuation: bool = False
    stop_reason: str | None = None
    permission_behavior: str | None = None
    additional_context: str | None = None


@dataclass
class StopHooksResult:
    """Result from Stop hooks execution."""

    should_stop: bool = False
    reason: str | None = None
    modified_response: str | None = None


@dataclass
class SessionHooksState:
    """Session-level hook state for tracking registered hooks."""

    hooks: dict[HookType, list[HookMatcher]] = field(default_factory=dict)
    results: list[HookResult] = field(default_factory=list)
    enabled: bool = True


class HookHandler(Protocol):
    """Protocol for hook handler functions."""

    async def __call__(self, ctx: HookContext) -> HookResult: ...


@dataclass
class HookRegistration:
    """A registered hook handler."""

    hook_type: HookType
    handler: HookHandler
    priority: int = 0
    name: str = ""


@dataclass
class PromptRequest:
    """Request to a prompt hook."""

    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptResponse:
    """Response from a prompt hook."""

    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    modified: bool = False


HOOK_EVENTS: list[HookType] = [
    HookType.PRE_TOOL_CALL,
    HookType.POST_TOOL_CALL,
    HookType.POST_API_CALL,
    HookType.PRE_API_CALL,
    HookType.ON_MESSAGE,
    HookType.ON_SESSION_START,
    HookType.ON_SESSION_END,
    HookType.ON_TASK_START,
    HookType.ON_TASK_END,
    HookType.ON_ERROR,
    HookType.PRE_COMPACT,
    HookType.POST_COMPACT,
    HookType.STOP,
    HookType.STOP_FAILURE,
    HookType.SUBAGENT_START,
    HookType.SUBAGENT_STOP,
    HookType.TEAMMATE_IDLE,
    HookType.CONFIG_CHANGE,
    HookType.CWD_CHANGED,
    HookType.FILE_CHANGED,
    HookType.PERMISSION_REQUEST,
    HookType.PERMISSION_DENIED,
    HookType.NOTIFICATION,
    HookType.USER_PROMPT_SUBMIT,
]


def is_hook_event(value: str) -> bool:
    """Check if a string is a valid hook event type."""
    return value in [h.value for h in HookType]
