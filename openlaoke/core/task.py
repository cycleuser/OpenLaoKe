"""Task system with lifecycle management."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openlaoke.types.core_types import (
    TaskId,
    TaskState,
    TaskStatus,
    TaskType,
    is_terminal_task_status,
)

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class TaskHandle:
    """Handle to a running task for cleanup and monitoring."""

    task_id: str
    task: asyncio.Task | None = None
    cleanup: callable | None = None

    async def kill(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.cleanup:
            self.cleanup()


class TaskManager:
    """Manages the lifecycle of all tasks (bash, agent, etc.)."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self._id_generator = TaskId()
        self._handles: dict[str, TaskHandle] = {}
        self._output_dir = os.path.join(os.path.expanduser("~/.openlaoke"), "task_outputs")
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
    ) -> tuple[str, int]:
        state = self.create_task_state(TaskType.LOCAL_BASH, description, tool_use_id)
        state.status = TaskStatus.RUNNING
        self.app_state.update_task(state)

        env = os.environ.copy()
        env.update(self.app_state.get_env_vars())

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir or self.app_state.get_cwd(),
                env=env,
            )

            output_chunks: list[bytes] = []
            with open(state.output_file, "a", encoding="utf-8", errors="replace") as f:
                while True:
                    chunk = await proc.stdout.read(4096)
                    if not chunk:
                        break
                    output_chunks.append(chunk)
                    decoded = chunk.decode("utf-8", errors="replace")
                    f.write(decoded)
                    f.flush()
                    state.output_offset += len(decoded)
                    self.app_state.update_task(state)

            await proc.wait()
            exit_code = proc.returncode or 0

            state.status = TaskStatus.COMPLETED if exit_code == 0 else TaskStatus.FAILED
            state.end_time = time.time()
            state.exit_code = exit_code
            state.output = b"".join(output_chunks).decode("utf-8", errors="replace")
            self.app_state.update_task(state)

            return state.output, exit_code

        except asyncio.CancelledError:
            state.status = TaskStatus.KILLED
            state.end_time = time.time()
            self.app_state.update_task(state)
            raise
        except Exception as e:
            state.status = TaskStatus.FAILED
            state.end_time = time.time()
            state.output = str(e)
            state.exit_code = 1
            self.app_state.update_task(state)
            return str(e), 1

    async def run_agent(
        self,
        prompt: str,
        description: str,
        tool_use_id: str | None = None,
        subagent_type: str = "local",
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
