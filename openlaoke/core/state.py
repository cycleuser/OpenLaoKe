"""Centralized application state management."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openlaoke.types.core_types import (
    CostInfo,
    Message,
    TaskState,
    TaskStatus,
    TokenUsage,
)
from openlaoke.types.permissions import PermissionConfig

if TYPE_CHECKING:
    from openlaoke.types.providers import MultiProviderConfig


@dataclass
class SessionConfig:
    """Configuration for a session."""

    model: str = "gemma3:1b"
    max_tokens: int = 8192
    temperature: float = 1.0
    top_p: float = 1.0
    thinking_budget: int = 0
    allowed_tools: list[str] = field(default_factory=list)
    system_prompt_suffix: str = ""


@dataclass
class AppState:
    """Centralized immutable state for the application.

    All state updates go through set_app_state(), reads through get_app_state().
    State is persisted to disk for session recovery.
    """

    session_id: str = ""
    cwd: str = ""
    messages: list[Message] = field(default_factory=list)
    tasks: dict[str, TaskState] = field(default_factory=dict)
    permission_config: PermissionConfig = field(default_factory=PermissionConfig.defaults)
    session_config: SessionConfig = field(default_factory=SessionConfig)
    env_vars: dict[str, str] = field(default_factory=dict)
    is_running: bool = False
    is_thinking: bool = False
    current_tool_use_id: str | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    cost_info: CostInfo = field(default_factory=CostInfo)
    error_message: str | None = None
    pending_user_input: str | None = None
    clipboard_content: str = ""
    working_directory: str = ""
    project_root: str | None = None
    git_branch: str | None = None
    theme: str = "dark"
    vim_mode: bool = False
    verbose: bool = False
    auto_accept: bool = False
    resume_session: bool = True
    local_mode: bool = False
    multi_provider_config: MultiProviderConfig | None = None
    app_config: Any = None
    active_skills: list[str] = field(default_factory=list)
    insomnia_mode: bool = False
    insomnia_task_queue: list[dict[str, Any]] = field(default_factory=list)
    insomnia_max_iterations: int = 1000
    insomnia_auto_accept: bool = True
    insomnia_log_path: str | None = None

    _listeners: list[Callable[[AppState], None]] = field(default_factory=list, repr=False)
    _persist_path: str | None = None

    def __post_init__(self) -> None:
        if not self.cwd:
            self.cwd = os.getcwd()
        if not self.working_directory:
            self.working_directory = self.cwd

    def get_cwd(self) -> str:
        """Get current working directory."""
        return self.cwd

    def set_cwd(self, path: str) -> None:
        """Set current working directory and sync working_directory."""
        self.cwd = os.path.abspath(path)
        self.working_directory = self.cwd

    def get_env_vars(self) -> dict[str, str]:
        """Get merged environment variables (system + session overrides)."""
        env = os.environ.copy()
        env.update(self.env_vars)
        return env

    def add_message(self, message: Message) -> None:
        """Add message to history with timestamp, notify listeners, and persist."""
        message.timestamp = time.time()
        self.messages.append(message)
        self._notify()
        self._persist()

    def get_messages(self) -> list[Message]:
        """Get a copy of all messages."""
        return list(self.messages)

    def get_last_message(self) -> Message | None:
        """Get most recent message or None if history is empty."""
        return self.messages[-1] if self.messages else None

    def get_message_count(self) -> int:
        """Get total number of messages in history."""
        return len(self.messages)

    def add_task(self, task: TaskState) -> None:
        """Register a new task and notify listeners."""
        self.tasks[task.id] = task
        self._notify()

    def update_task(self, task: TaskState) -> None:
        """Update task state and persist changes."""
        self.tasks[task.id] = task
        self._notify()
        self._persist()

    def get_task(self, task_id: str) -> TaskState | None:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> list[TaskState]:
        return list(self.tasks.values())

    def get_active_tasks(self) -> list[TaskState]:
        return [
            t
            for t in self.tasks.values()
            if t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED)
        ]

    def accumulate_tokens(self, usage: TokenUsage) -> None:
        self.token_usage.accumulate(usage)

    def accumulate_cost(self, cost: CostInfo) -> None:
        self.cost_info.input_cost += cost.input_cost
        self.cost_info.output_cost += cost.output_cost
        self.cost_info.cache_read_cost += cost.cache_read_cost
        self.cost_info.cache_creation_cost += cost.cache_creation_cost

    def set_error(self, message: str | None) -> None:
        self.error_message = message
        self._notify()

    def set_pending_input(self, value: str | None) -> None:
        self.pending_user_input = value
        self._notify()

    def subscribe(self, listener: Callable[[AppState], None]) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[AppState], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            with suppress(Exception):
                listener(self)

    def set_persist_path(self, path: str) -> None:
        self._persist_path = path

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            data = {
                "session_id": self.session_id,
                "cwd": self.cwd,
                "messages": [m.to_dict() for m in self.messages],
                "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
                "token_usage": {
                    "input_tokens": self.token_usage.input_tokens,
                    "output_tokens": self.token_usage.output_tokens,
                    "cache_read_tokens": self.token_usage.cache_read_tokens,
                    "cache_creation_tokens": self.token_usage.cache_creation_tokens,
                },
                "cost_info": {
                    "input_cost": self.cost_info.input_cost,
                    "output_cost": self.cost_info.output_cost,
                    "cache_read_cost": self.cost_info.cache_read_cost,
                    "cache_creation_cost": self.cost_info.cache_creation_cost,
                },
                "insomnia_mode": self.insomnia_mode,
                "insomnia_task_queue": self.insomnia_task_queue,
                "insomnia_max_iterations": self.insomnia_max_iterations,
                "insomnia_auto_accept": self.insomnia_auto_accept,
                "insomnia_log_path": self.insomnia_log_path,
            }
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cwd": self.cwd,
            "message_count": len(self.messages),
            "task_count": len(self.tasks),
            "is_running": self.is_running,
            "token_usage": {
                "input_tokens": self.token_usage.input_tokens,
                "output_tokens": self.token_usage.output_tokens,
            },
            "cost_info": {
                "total_cost": self.cost_info.total_cost,
            },
        }


def create_app_state(
    cwd: str | None = None,
    model: str = "claude-sonnet-4-20250514",
    persist_path: str | None = None,
    **kwargs: Any,
) -> AppState:
    """Factory for creating AppState with sensible defaults."""
    session_id = f"session_{int(time.time())}"
    state = AppState(
        session_id=session_id,
        cwd=cwd or os.getcwd(),
        session_config=SessionConfig(model=model),
        **kwargs,
    )
    if persist_path:
        state.set_persist_path(persist_path)
    return state
