"""Task scheduler for managing concurrent task execution."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from openlaoke.core.scheduler.executor import TaskExecutor
from openlaoke.core.scheduler.priority import PriorityQueue
from openlaoke.core.scheduler.timeout import TimeoutHandler
from openlaoke.types.core_types import TaskStatus

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 3
DEFAULT_TIMEOUT = 15 * 60  # 15 minutes


@dataclass
class ScheduledTask:
    """A task scheduled for execution."""

    id: str
    func: Any
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: int = 0
    timeout: float | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    retries: int = 0

    def __post_init__(self) -> None:
        if not self.kwargs:
            self.kwargs = {}


@dataclass
class TaskResult:
    """Result of a scheduled task."""

    task_id: str
    status: TaskStatus
    result: Any | None = None
    error: str | None = None
    duration: float | None = None


class TaskScheduler:
    """Manages concurrent task execution with priority and timeout support."""

    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT,
        default_timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize the task scheduler.

        Args:
            max_concurrent: Maximum concurrent tasks.
            default_timeout: Default timeout in seconds.
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout

        self.executor = TaskExecutor(max_workers=max_concurrent)
        self.timeout_handler = TimeoutHandler(default_timeout=default_timeout)
        self.queue = PriorityQueue()

        self.tasks: dict[str, ScheduledTask] = {}
        self.results: dict[str, TaskResult] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._worker_task: asyncio.Task | None = None

    async def submit(
        self,
        func: Any,
        *args,
        priority: int = 0,
        timeout: float | None = None,
        retries: int = 0,
        task_id: str | None = None,
        **kwargs,
    ) -> TaskResult:
        """Submit a task for execution.

        Args:
            func: Function or coroutine to execute.
            *args: Positional arguments.
            priority: Task priority (lower = higher priority).
            timeout: Timeout in seconds.
            retries: Number of retry attempts.
            task_id: Optional task identifier.
            **kwargs: Keyword arguments.

        Returns:
            Task execution result.
        """
        task_id = task_id or f"task_{uuid4().hex[:8]}"
        timeout = timeout or self.default_timeout

        scheduled = ScheduledTask(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
            status=TaskStatus.PENDING,
            retries=retries,
        )

        async with self._lock:
            self.tasks[task_id] = scheduled

        self.queue.put(scheduled, priority=priority)
        logger.info(f"Submitted task {task_id} with priority {priority}")

        return await self._wait_for_result(task_id, timeout=timeout)

    async def submit_batch(
        self,
        tasks: list[tuple[Any, tuple, dict]],
        parallel: bool = True,
        priority: int = 0,
        timeout: float | None = None,
    ) -> list[TaskResult]:
        """Submit multiple tasks for execution.

        Args:
            tasks: List of (func, args, kwargs) tuples.
            parallel: Whether to run tasks in parallel.
            priority: Priority for all tasks.
            timeout: Timeout for each task.

        Returns:
            List of task results.
        """
        if parallel:
            coros = [
                self.submit(func, *args, priority=priority, timeout=timeout, **kwargs)
                for func, args, kwargs in tasks
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)
            parallel_results: list[TaskResult] = []
            for r in results:
                if isinstance(r, TaskResult):
                    parallel_results.append(r)
                else:
                    parallel_results.append(
                        TaskResult(
                            task_id="error",
                            status=TaskStatus.FAILED,
                            error=str(r),
                        )
                    )
            return parallel_results
        else:
            sequential_results: list[TaskResult] = []
            for func, args, kwargs in tasks:
                result = await self.submit(
                    func, *args, priority=priority, timeout=timeout, **kwargs
                )
                sequential_results.append(result)
            return sequential_results

    async def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task.

        Args:
            task_id: Task identifier.

        Returns:
            True if task was cancelled.
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status == TaskStatus.RUNNING:
                cancelled = self.executor.cancel(task_id)
                if cancelled:
                    task.status = TaskStatus.KILLED
                    task.error = "Cancelled by user"
                    task.completed_at = time.time()
                    self._save_result(task)
                return cancelled

            elif task.status == TaskStatus.PENDING:
                task.status = TaskStatus.KILLED
                task.error = "Cancelled before execution"
                task.completed_at = time.time()
                self._save_result(task)
                return True

            return False

    async def get_status(self, task_id: str) -> TaskStatus:
        """Get the status of a task.

        Args:
            task_id: Task identifier.

        Returns:
            Current task status.
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if task:
                return task.status
            result = self.results.get(task_id)
            if result:
                return result.status
            return TaskStatus.PENDING

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Get the result of a completed task.

        Args:
            task_id: Task identifier.

        Returns:
            Task result if available.
        """
        async with self._lock:
            return self.results.get(task_id)

    async def wait_all(self) -> None:
        """Wait for all pending tasks to complete."""
        while True:
            async with self._lock:
                pending = [
                    t
                    for t in self.tasks.values()
                    if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
                ]
                if not pending:
                    return
            await asyncio.sleep(0.1)

    async def shutdown(self) -> None:
        """Shutdown the scheduler."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task

        await self.wait_all()
        self.executor.shutdown(wait=True)
        self.timeout_handler.clear_all()

        logger.info("Task scheduler shutdown complete")

    async def start(self) -> None:
        """Start the scheduler worker."""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Task scheduler started")

    def _save_result(self, task: ScheduledTask) -> None:
        """Save task result.

        Args:
            task: Task to save.
        """
        duration = None
        if task.started_at and task.completed_at:
            duration = task.completed_at - task.started_at

        result = TaskResult(
            task_id=task.id,
            status=task.status,
            result=task.result,
            error=task.error,
            duration=duration,
        )
        self.results[task.id] = result

    async def _worker_loop(self) -> None:
        """Worker loop that processes tasks from the queue."""
        while self._running:
            task = self.queue.get(block=True, timeout=0.1)
            if not task:
                continue

            async with self._lock:
                if task.status == TaskStatus.KILLED:
                    continue
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

            await self._execute_task(task)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task.

        Args:
            task: Task to execute.
        """
        try:
            if asyncio.iscoroutinefunction(task.func):
                result = await self.executor.execute_async(
                    task.id,
                    task.func(*task.args, **task.kwargs),
                    timeout=task.timeout,
                )
            else:
                result = await self.executor.execute(
                    task.id,
                    task.func,
                    *task.args,
                    timeout=task.timeout,
                    retries=task.retries,
                    **task.kwargs,
                )

            async with self._lock:
                task.status = result.status
                task.result = result.result
                task.error = result.error
                task.completed_at = result.completed_at
                self._save_result(task)

            logger.info(f"Task {task.id} completed with status {task.status.value}")

        except Exception as e:
            logger.error(f"Task {task.id} execution error: {e}")
            async with self._lock:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = time.time()
                self._save_result(task)

    async def _wait_for_result(self, task_id: str, timeout: float | None = None) -> TaskResult:
        """Wait for a task result.

        Args:
            task_id: Task identifier.
            timeout: Maximum wait time.

        Returns:
            Task result.
        """
        timeout = timeout or self.default_timeout
        start = time.time()

        while True:
            async with self._lock:
                result = self.results.get(task_id)
                if result:
                    return result

            elapsed = time.time() - start
            if elapsed > timeout:
                async with self._lock:
                    task = self.tasks.get(task_id)
                    if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                        task.status = TaskStatus.FAILED
                        task.error = "Wait timeout"
                        task.completed_at = time.time()
                        self._save_result(task)
                    return self.results.get(task_id) or TaskResult(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error="Wait timeout",
                    )

            await asyncio.sleep(0.05)

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics.

        Returns:
            Statistics dictionary.
        """
        pending = len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
        running = len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING])
        completed = len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED])
        killed = len([t for t in self.tasks.values() if t.status == TaskStatus.KILLED])

        return {
            "queue_size": self.queue.qsize(),
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "killed": killed,
            "total": len(self.tasks),
            "results": len(self.results),
        }
