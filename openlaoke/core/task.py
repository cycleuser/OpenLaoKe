"""Task system with lifecycle management."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from openlaoke.types.core_types import (
    TaskId,
    TaskState,
    TaskStatus,
    TaskType,
    is_terminal_task_status,
)

if TYPE_CHECKING:
    from openlaoke.core.state import AppState

DEFAULT_AUTO_BACKGROUND_MS = 3000.0


@dataclass
class TaskHandle:
    """Handle to a running task for cleanup and monitoring."""

    task_id: str
    task: asyncio.Task | None = None
    cleanup: Callable[..., Any] | None = None

    async def kill(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        if self.cleanup:
            self.cleanup()


@dataclass
class BashOutcome:
    """Result of one bash run, foreground or handed to the background.

    ``exit_code`` is None when the command was still running at the deadline:
    either it was killed on an explicit timeout (``timed_out``) or it was left
    running and can be polled through the ``Bg`` tool (``backgrounded``).
    """

    output: str
    exit_code: int | None
    task_id: str = ""
    backgrounded: bool = False
    timed_out: bool = False

    @property
    def finished(self) -> bool:
        return not self.backgrounded and not self.timed_out


class TaskManager:
    """Manages the lifecycle of all tasks (bash, agent, etc.)."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self._id_generator = TaskId()
        self._handles: dict[str, TaskHandle] = {}
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._output_dir = os.path.join(os.path.expanduser("~/.openlaoke"), "task_outputs")
        try:
            os.makedirs(self._output_dir, exist_ok=True)
            # Verify write access
            _test = os.path.join(self._output_dir, ".write_test")
            with open(_test, "w") as _f:
                _f.write("ok")
            os.remove(_test)
        except (PermissionError, OSError):
            import tempfile as _tempfile

            self._output_dir = os.path.join(_tempfile.gettempdir(), "openlaoke_task_outputs")
            os.makedirs(self._output_dir, exist_ok=True)

    def _get_output_path(self, task_id: str) -> str:
        return os.path.join(self._output_dir, f"{task_id}.log")

    def create_task_state(
        self,
        task_type: TaskType,
        description: str,
        tool_use_id: str | None = None,
    ) -> TaskState:
        task_id = self._id_generator.generate(task_type)
        state = TaskState(
            id=task_id,
            type=task_type,
            status=TaskStatus.PENDING,
            description=description,
            tool_use_id=tool_use_id,
            start_time=time.time(),
            output_file=self._get_output_path(task_id),
        )
        self.app_state.add_task(state)
        return state

    async def run_bash(
        self,
        command: str,
        description: str,
        timeout: float | None = None,
        tool_use_id: str | None = None,
        working_dir: str | None = None,
        auto_background_ms: float | None = DEFAULT_AUTO_BACKGROUND_MS,
    ) -> BashOutcome:
        """Run a shell command, handing it to the background when it overruns.

        ``timeout`` is a hard deadline: the process is killed and the call
        reports a timeout.  ``auto_background_ms`` is a soft one: past it the
        command keeps running, the call returns its task id, and ``Bg`` can be
        used to read or cancel it.  Output goes to a file rather than a growing
        buffer, so a long-lived background job costs no memory.
        """
        state = self.create_task_state(TaskType.LOCAL_BASH, description, tool_use_id)
        state.status = TaskStatus.RUNNING
        self.app_state.update_task(state)

        env = self.app_state.snapshot_env()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir or self.app_state.get_cwd(),
                env=env,
                start_new_session=True,
            )
        except Exception as e:
            state.status = TaskStatus.FAILED
            state.end_time = time.time()
            state.output = str(e)
            state.exit_code = 1
            self.app_state.update_task(state)
            return BashOutcome(str(e), 1, state.id)

        pump = asyncio.create_task(self._pump_output(state, proc))
        self._handles[state.id] = TaskHandle(
            task_id=state.id, task=pump, cleanup=lambda: self._handles.pop(state.id, None)
        )
        self._procs[state.id] = proc

        budget = timeout
        if budget is None and auto_background_ms is not None and auto_background_ms >= 0:
            budget = auto_background_ms / 1000.0

        if budget is None:
            await pump
        else:
            done, _pending = await asyncio.wait({pump}, timeout=budget)
            if not done:
                if timeout is not None:
                    await self._terminate(state, proc)
                    return BashOutcome(self.tail_output(state, 40), None, state.id, timed_out=True)
                pending = self.tail_output(state, 40)
                return BashOutcome(pending, None, state.id, backgrounded=True)

        return BashOutcome(
            self.read_output(state), state.exit_code if state.exit_code is not None else 0, state.id
        )

    async def _pump_output(self, state: TaskState, proc: asyncio.subprocess.Process) -> int:
        """Copy the child's output to its log file until it exits."""
        try:
            with open(state.output_file, "a", encoding="utf-8", errors="replace") as sink:
                while proc.stdout is not None:
                    chunk = await proc.stdout.read(4096)
                    if not chunk:
                        break
                    decoded = chunk.decode("utf-8", errors="replace")
                    sink.write(decoded)
                    sink.flush()
                    state.output_offset += len(decoded)
            await proc.wait()
        except asyncio.CancelledError:
            if proc.returncode is None:
                with suppress(ProcessLookupError, OSError):
                    proc.kill()
                with suppress(Exception):
                    await proc.wait()
            state.status = TaskStatus.KILLED
            state.end_time = state.end_time or time.time()
            self.app_state.update_task(state)
            raise

        exit_code = proc.returncode or 0
        state.exit_code = exit_code
        state.status = TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
        state.end_time = time.time()
        self.app_state.update_task(state)
        return exit_code

    async def _terminate(self, state: TaskState, proc: asyncio.subprocess.Process) -> None:
        handle = self._handles.pop(state.id, None)
        if handle and handle.task and not handle.task.done():
            handle.task.cancel()
            with suppress(asyncio.CancelledError):
                await handle.task
        if proc.returncode is None:
            with suppress(ProcessLookupError, OSError):
                proc.kill()
            with suppress(Exception):
                await proc.wait()
        if not is_terminal_task_status(state.status):
            state.status = TaskStatus.KILLED
            state.end_time = time.time()
            state.exit_code = None
            self.app_state.update_task(state)

    def read_output(self, state: TaskState, offset: int = 0, limit: int | None = None) -> str:
        """Read a task's log from disk. ``offset`` is a character position."""
        path = state.output_file
        if not path or not os.path.exists(path):
            return state.output
        try:
            with open(path, encoding="utf-8", errors="replace") as source:
                if offset:
                    source.seek(0)
                    source.read(offset)
                return source.read() if limit is None else source.read(limit)
        except OSError:
            return state.output

    def tail_output(self, state: TaskState, lines: int = 40) -> str:
        text = self.read_output(state)
        rows = text.splitlines()
        return "\n".join(rows[-lines:]) if rows else ""

    async def wait_for(self, task_id: str, timeout: float | None = None) -> TaskState | None:
        handle = self._handles.get(task_id)
        if handle and handle.task and not handle.task.done():
            with suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(handle.task), timeout=timeout)
        return self.app_state.get_task(task_id)

    async def cancel(self, task_id: str) -> bool:
        state = self.app_state.get_task(task_id)
        if state is None or is_terminal_task_status(state.status):
            return False
        proc = self._procs.get(task_id)
        if proc is not None:
            await self._terminate(state, proc)
            return True
        self.kill_task(task_id)
        return True

    async def run_agent(
        self,
        prompt: str,
        description: str,
        tool_use_id: str | None = None,
        subagent_type: str = "local",
        resume_from: str | None = None,
    ) -> str:
        state = self.create_task_state(TaskType.LOCAL_AGENT, description, tool_use_id)
        state.status = TaskStatus.RUNNING
        self.app_state.update_task(state)

        try:
            from openlaoke.core.agent_runner import run_subagent

            result = await run_subagent(
                prompt=prompt,
                description=description,
                app_state=self.app_state,
                task_state=state,
                resume_from=resume_from,
            )

            state.status = TaskStatus.COMPLETED
            state.end_time = time.time()
            state.output = result
            self.app_state.update_task(state)

            return result

        except asyncio.CancelledError:
            state.status = TaskStatus.KILLED
            state.end_time = time.time()
            self.app_state.update_task(state)
            raise
        except Exception as e:
            state.status = TaskStatus.FAILED
            state.end_time = time.time()
            state.output = str(e)
            self.app_state.update_task(state)
            return f"Agent failed: {e}"

    def kill_task(self, task_id: str) -> None:
        if task_id in self._handles:
            handle = self._handles[task_id]
            asyncio.ensure_future(handle.kill())
            del self._handles[task_id]

        state = self.app_state.get_task(task_id)
        if state and not is_terminal_task_status(state.status):
            state.status = TaskStatus.KILLED
            state.end_time = time.time()
            self.app_state.update_task(state)

    def get_active_tasks(self) -> list[TaskState]:
        return [t for t in self.app_state.get_all_tasks() if not is_terminal_task_status(t.status)]


def get_task_manager(app_state: AppState) -> TaskManager:
    """Return the session's single TaskManager.

    One instance per state matters: the handle table and the live process
    table live on it, so a second manager would be unable to cancel or wait on
    a job the first one started.
    """
    existing = getattr(app_state, "_task_manager", None)
    if isinstance(existing, TaskManager):
        return existing
    manager = TaskManager(app_state)
    app_state._task_manager = manager
    return manager
