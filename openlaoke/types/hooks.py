"""Hook type definitions for extensibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class HookType(str, Enum):
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


@dataclass
class HookContext:
    """Context passed to hook handlers."""
    hook_type: HookType
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    tool_name: str = ""
    task_id: str = ""


@dataclass
class HookResult:
    """Result returned by a hook handler."""
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    should_abort: bool = False


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
