"""Insomnia Engine - Persistent background execution that survives terminal disconnect."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class InsomniaTask:
    """A task to be executed in insomnia mode."""

    task_id: str
    prompt: str
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    status: str = "pending"
    result: str | None = None
    error: str | None = None
    iterations: int = 0
    max_iterations: int = 100

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
        }


@dataclass
class InsomniaLogEntry:
    """A single log entry."""

    timestamp: float
    level: str
    message: str
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert log entry to dictionary."""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "task_id": self.task_id,
        }


class InsomniaEngine:
    """Engine for persistent background execution.

    This engine allows AI to continue working even when the user disconnects
    or closes the terminal. It persists state to disk and can resume from
    where it left off.

    Features:
    - Task queue with persistent storage
    - Auto-resume on restart
    - Logging to disk
    - Supports all modes: REPL, sub-agents, streaming, HyperAuto
    - Configurable max iterations
    - Auto-accept permissions in insomnia mode
    """

    STATE_PATH = os.path.expanduser("~/.openlaoke/insomnia_state.json")
    LOG_PATH = os.path.expanduser("~/.openlaoke/insomnia_log.json")

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self._running = False
        self._current_task: InsomniaTask | None = None
        self._task_queue: list[InsomniaTask] = []
        self._log: list[InsomniaLogEntry] = []
        self._api_client = None
        self._tool_registry = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the insomnia engine."""
        self.app_state.insomnia_mode = True
        self.app_state.insomnia_auto_accept = True
        self._running = True
        self._stop_event.clear()

        self._load_state()
        self._log_event("info", "Insomnia engine started")

        if self.app_state.insomnia_log_path:
            self.app_state.insomnia_log_path = self.app_state.insomnia_log_path
        else:
            self.app_state.insomnia_log_path = self.LOG_PATH

        self.app_state._persist()

    async def stop(self) -> None:
        """Stop the insomnia engine."""
        self._running = False
        self.app_state.insomnia_mode = False
        self._stop_event.set()
        self._save_state()
        self._log_event("info", "Insomnia engine stopped")
        self.app_state._persist()

    async def add_task(self, prompt: str, max_iterations: int | None = None) -> str:
        """Add a task to the queue."""
        import uuid

        task_id = f"insomnia_{uuid.uuid4().hex[:8]}"
        task = InsomniaTask(
            task_id=task_id,
            prompt=prompt,
            max_iterations=max_iterations or self.app_state.insomnia_max_iterations,
        )
        self._task_queue.append(task)
        self.app_state.insomnia_task_queue.append(
            {
                "task_id": task.task_id,
                "prompt": task.prompt,
                "created_at": task.created_at,
                "status": task.status,
                "max_iterations": task.max_iterations,
            }
        )
        self._save_state()
        self._log_event("info", f"Task added: {task_id}", task_id)

        if self._running and not self._current_task:
            asyncio.create_task(self._process_queue())

        return task_id

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        for i, task in enumerate(self._task_queue):
            if task.task_id == task_id:
                if self._current_task and self._current_task.task_id == task_id:
                    self._stop_event.set()
                    await asyncio.sleep(0.1)
                    self._stop_event.clear()
                self._task_queue.pop(i)
                task.status = "cancelled"
                self._update_queue_state()
                self._log_event("info", f"Task cancelled: {task_id}", task_id)
                return True
        return False

    async def clear_queue(self) -> int:
        """Clear all pending tasks."""
        count = len(self._task_queue)
        self._task_queue = [t for t in self._task_queue if t.status == "running"]
        self._update_queue_state()
        self._log_event("info", f"Queue cleared: {count} tasks removed")
        return count

    def get_status(self) -> dict[str, Any]:
        """Get current insomnia engine status."""
        return {
            "running": self._running,
            "current_task": self._current_task.to_dict() if self._current_task else None,
            "queue_size": len(self._task_queue),
            "queue": [t.to_dict() for t in self._task_queue],
            "total_iterations": sum(t.iterations for t in self._task_queue if t.completed_at),
            "log_entries": len(self._log),
        }

    def get_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent log entries."""
        return [entry.to_dict() for entry in self._log[-limit:]]

    async def _process_queue(self) -> None:
        """Process tasks in the queue."""
        while self._running and self._task_queue:
            task = self._task_queue[0]
            if task.status == "cancelled":
                self._task_queue.pop(0)
                self._update_queue_state()
                continue

            self._current_task = task
            task.status = "running"
            task.started_at = time.time()
            self._update_queue_state()
            self._log_event("info", f"Task started: {task.task_id}", task.task_id)

            try:
                result = await self._execute_task(task)
                task.result = result
                task.status = "completed"
                task.completed_at = time.time()
                self._log_event("info", f"Task completed: {task.task_id}", task.task_id)
            except asyncio.CancelledError:
                task.status = "cancelled"
                task.completed_at = time.time()
                self._log_event("warn", f"Task cancelled: {task.task_id}", task.task_id)
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                task.completed_at = time.time()
                self._log_event("error", f"Task failed: {task.task_id}: {e}", task.task_id)

            self._task_queue.pop(0)
            self._current_task = None
            self._update_queue_state()
            self._save_state()

    async def _execute_task(self, task: InsomniaTask) -> str:
        """Execute a single task with full tool-use loop."""
        from openlaoke.core.config_wizard import get_proxy_url
        from openlaoke.core.multi_provider_api import MultiProviderClient
        from openlaoke.core.system_prompt import build_system_prompt
        from openlaoke.core.tool import ToolContext, ToolRegistry
        from openlaoke.tools.register import register_all_tools
        from openlaoke.types.core_types import AssistantMessage, MessageRole

        registry = ToolRegistry()
        register_all_tools(registry)

        config = self.app_state.multi_provider_config
        if not config or not config.is_configured():
            raise RuntimeError("No provider configured")

        app_config = getattr(self.app_state, "app_config", None)
        proxy = get_proxy_url(app_config) if app_config else None

        api = MultiProviderClient(config, proxy=proxy)

        messages = [
            {"role": msg.role.value, "content": msg.content} for msg in self.app_state.messages
        ]
        messages.append({"role": "user", "content": task.prompt})

        system_prompt = build_system_prompt(self.app_state, registry.get_all_for_prompt())

        result_parts = []
        iteration = 0

        try:
            while iteration < task.max_iterations and self._running:
                iteration += 1
                task.iterations = iteration

                self._log_event(
                    "debug",
                    f"Iteration {iteration}/{task.max_iterations}",
                    task.task_id,
                )

                tools = registry.get_all_for_prompt()
                response, usage, cost = await api.send_message(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools if iteration < task.max_iterations - 1 else None,
                    model=self.app_state.session_config.model,
                )

                self.app_state.accumulate_tokens(usage)
                self.app_state.accumulate_cost(cost)

                if response.content:
                    result_parts.append(response.content)

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content,
                }
                if response.tool_uses:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tu.id,
                            "type": "function",
                            "function": {
                                "name": tu.name,
                                "arguments": json.dumps(tu.input),
                            },
                        }
                        for tu in response.tool_uses
                    ]
                messages.append(assistant_msg)

                self.app_state.add_message(
                    AssistantMessage(
                        role=MessageRole.ASSISTANT,
                        content=response.content or "",
                        tool_uses=response.tool_uses,
                    )
                )

                if not response.tool_uses:
                    break

                for tool_use in response.tool_uses:
                    if not self._running:
                        break

                    tool = registry.get(tool_use.name)
                    if not tool:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_use.id,
                                "content": f"Unknown tool: {tool_use.name}",
                            }
                        )
                        continue

                    ctx = ToolContext(
                        app_state=self.app_state,
                        tool_use_id=tool_use.id,
                    )

                    validation = tool.validate_input(tool_use.input)
                    if not validation.result:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_use.id,
                                "content": f"Validation error: {validation.message}",
                            }
                        )
                        continue

                    result = await tool.call(ctx, **tool_use.input)
                    result_content = (
                        result.content if isinstance(result.content, str) else str(result.content)
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_use.id,
                            "content": result_content,
                        }
                    )

                    self._log_event(
                        "debug",
                        f"Tool executed: {tool_use.name}",
                        task.task_id,
                    )

                    self.app_state._persist()

        finally:
            await api.close()

        return "\n".join(result_parts) if result_parts else "(no output)"

    def _save_state(self) -> None:
        """Save engine state to disk."""
        try:
            os.makedirs(os.path.dirname(self.STATE_PATH), exist_ok=True)
            state = {
                "running": self._running,
                "current_task": self._current_task.to_dict() if self._current_task else None,
                "task_queue": [t.to_dict() for t in self._task_queue],
                "log": [e.to_dict() for e in self._log[-1000:]],
                "saved_at": time.time(),
            }
            with open(self.STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception:
            pass

    def _load_state(self) -> None:
        """Load engine state from disk."""
        if not os.path.exists(self.STATE_PATH):
            return

        try:
            with open(self.STATE_PATH, encoding="utf-8") as f:
                state = json.load(f)

            self._running = state.get("running", False)
            self._log = [InsomniaLogEntry(**entry) for entry in state.get("log", [])]

            queue_data = state.get("task_queue", [])
            self._task_queue = []
            for data in queue_data:
                task = InsomniaTask(
                    task_id=data["task_id"],
                    prompt=data["prompt"],
                    created_at=data.get("created_at", time.time()),
                    started_at=data.get("started_at"),
                    completed_at=data.get("completed_at"),
                    status=data.get("status", "pending"),
                    result=data.get("result"),
                    error=data.get("error"),
                    iterations=data.get("iterations", 0),
                    max_iterations=data.get("max_iterations", 100),
                )
                if task.status not in ("completed", "failed", "cancelled"):
                    task.status = "pending"
                self._task_queue.append(task)

            if self._running and self._task_queue:
                self._log_event("info", "Resumed from saved state with pending tasks")
        except Exception:
            pass

    def _update_queue_state(self) -> None:
        """Update the app_state task queue."""
        self.app_state.insomnia_task_queue = [
            {
                "task_id": t.task_id,
                "prompt": t.prompt,
                "created_at": t.created_at,
                "started_at": t.started_at,
                "completed_at": t.completed_at,
                "status": t.status,
                "max_iterations": t.max_iterations,
                "iterations": t.iterations,
            }
            for t in self._task_queue
        ]

    def _log_event(self, level: str, message: str, task_id: str | None = None) -> None:
        """Log an event."""
        entry = InsomniaLogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            task_id=task_id,
        )
        self._log.append(entry)

        if self.app_state.insomnia_log_path:
            try:
                os.makedirs(os.path.dirname(self.app_state.insomnia_log_path), exist_ok=True)
                with open(self.app_state.insomnia_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except Exception:
                pass

    async def close(self) -> None:
        """Close the engine and clean up resources."""
        await self.stop()
