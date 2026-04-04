"""Task executor for running tasks with lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from openlaoke.types.core_types import TaskStatus

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0


@dataclass
class ExecutionResult:
    """Result of a task execution."""

    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    retries: int = 0


class TaskExecutor:
    """Executor for running individual tasks."""

    def __init__(
        self,
        max_workers: int = 3,
        max_retries: int = MAX_RETRIES,
        retry_delay: float = RETRY_DELAY,
    ):
        """Initialize the task executor.

        Args:
            max_workers: Maximum number of worker threads.
            max_retries: Maximum number of retry attempts.
            retry_delay: Delay between retries in seconds.
        """
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task-exec-")
        self._futures: dict[str, Future] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        task_id: str,
        func: Callable,
        *args,
        timeout: float | None = None,
        retries: int = 0,
        **kwargs,
    ) -> ExecutionResult:
        """Execute a function with timeout and retry support.

        Args:
            task_id: Task identifier.
            func: Function to execute.
            *args: Positional arguments for the function.
            timeout: Timeout in seconds.
            retries: Number of retry attempts.
            **kwargs: Keyword arguments for the function.

        Returns:
            Execution result.
        """
        started_at = time.time()
        result = ExecutionResult(
            task_id=task_id,
            status=TaskStatus.RUNNING,
            started_at=started_at,
        )

        for attempt in range(max(1, retries + 1)):
            try:
                future = self._pool.submit(func, *args, **kwargs)
                async with self._lock:
                    self._futures[task_id] = future

                try:

                    def get_result(f: Future = future, t: float | None = timeout) -> Any:
                        return f.result(timeout=t)

                    output = await asyncio.get_event_loop().run_in_executor(
                        None,
                        get_result,
                    )

                    result.status = TaskStatus.COMPLETED
                    result.result = output
                    result.completed_at = time.time()
                    return result

                except TimeoutError:
                    logger.warning(
                        f"Task {task_id} timed out on attempt {attempt + 1}/{retries + 1}"
                    )
                    if attempt < retries:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    result.status = TaskStatus.FAILED
                    result.error = f"Timeout after {timeout}s"
                    result.completed_at = time.time()
                    return result

            except Exception as e:
                logger.error(f"Task {task_id} failed on attempt {attempt + 1}/{retries + 1}: {e}")
                if attempt < retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                result.status = TaskStatus.FAILED
                result.error = str(e)
                result.completed_at = time.time()
                return result

            finally:
                async with self._lock:
                    self._futures.pop(task_id, None)

        result.status = TaskStatus.FAILED
        result.error = "Max retries exceeded"
        result.completed_at = time.time()
        return result

    async def execute_async(
        self,
        task_id: str,
        coro: Any,
        timeout: float | None = None,
    ) -> ExecutionResult:
        """Execute an async coroutine with timeout.

        Args:
            task_id: Task identifier.
            coro: Coroutine to execute.
            timeout: Timeout in seconds.

        Returns:
            Execution result.
        """
        started_at = time.time()
        result = ExecutionResult(
            task_id=task_id,
            status=TaskStatus.RUNNING,
            started_at=started_at,
        )

        try:
            if timeout:
                output = await asyncio.wait_for(coro, timeout=timeout)
            else:
                output = await coro

            result.status = TaskStatus.COMPLETED
            result.result = output
            result.completed_at = time.time()
            return result

        except TimeoutError:
            logger.warning(f"Async task {task_id} timed out after {timeout}s")
            result.status = TaskStatus.FAILED
            result.error = f"Timeout after {timeout}s"
            result.completed_at = time.time()
            return result

        except asyncio.CancelledError:
            logger.info(f"Async task {task_id} was cancelled")
            result.status = TaskStatus.KILLED
            result.error = "Task cancelled"
            result.completed_at = time.time()
            raise

        except Exception as e:
            logger.error(f"Async task {task_id} failed: {e}")
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.completed_at = time.time()
            return result

    def cancel(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Task identifier.

        Returns:
            True if task was cancelled, False if not found.
        """
        future = self._futures.get(task_id)
        if future and not future.done():
            cancelled = future.cancel()
            if cancelled:
                logger.info(f"Cancelled task {task_id}")
            return cancelled
        return False

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor.

        Args:
            wait: Whether to wait for pending tasks.
        """
        self._pool.shutdown(wait=wait)
        logger.info("Task executor shutdown")

    def get_active_tasks(self) -> list[str]:
        """Get list of active task IDs.

        Returns:
            List of task IDs currently running.
        """
        return [task_id for task_id, future in self._futures.items() if not future.done()]

    def get_task_count(self) -> int:
        """Get number of active tasks.

        Returns:
            Number of tasks currently running.
        """
        return len([f for f in self._futures.values() if not f.done()])
