"""Timeout control system for task execution."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15 * 60  # 15 minutes


@dataclass
class TimeoutInfo:
    """Information about a timeout."""

    task_id: str
    timeout: float
    started_at: float
    deadline: float
    handle: asyncio.TimerHandle | None = None


class TimeoutHandler:
    """Handler for managing task timeouts."""

    def __init__(self, default_timeout: float = DEFAULT_TIMEOUT):
        """Initialize the timeout handler.

        Args:
            default_timeout: Default timeout in seconds.
        """
        self.default_timeout = default_timeout
        self._timeouts: dict[str, TimeoutInfo] = {}
        self._lock = asyncio.Lock()

    async def with_timeout(
        self,
        coro: Any,
        timeout: float | None = None,
        task_id: str | None = None,
    ) -> Any:
        """Execute a coroutine with timeout.

        Args:
            coro: Coroutine to execute.
            timeout: Timeout in seconds (uses default if None).
            task_id: Optional task identifier for tracking.

        Returns:
            Result of the coroutine.

        Raises:
            asyncio.TimeoutError: If timeout occurs.
        """
        timeout = timeout or self.default_timeout

        if task_id:
            await self._register_timeout(task_id, timeout)

        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            return result
        except TimeoutError:
            logger.warning(f"Task {task_id or 'unknown'} timed out after {timeout}s")
            raise
        finally:
            if task_id:
                await self._cancel_timeout(task_id)

    def set_timeout(
        self,
        task_id: str,
        timeout: float,
        callback: Callable[[], None],
    ) -> asyncio.TimerHandle:
        """Set a timeout callback for a task.

        Args:
            task_id: Task identifier.
            timeout: Timeout in seconds.
            callback: Callback to invoke on timeout.

        Returns:
            Timer handle that can be used to cancel.
        """
        loop = asyncio.get_event_loop()
        handle = loop.call_later(timeout, callback)

        info = TimeoutInfo(
            task_id=task_id,
            timeout=timeout,
            started_at=time.time(),
            deadline=time.time() + timeout,
            handle=handle,
        )
        self._timeouts[task_id] = info

        logger.debug(f"Set timeout for task {task_id}: {timeout}s")
        return handle

    def cancel_timeout(self, task_id: str) -> bool:
        """Cancel a timeout for a task.

        Args:
            task_id: Task identifier.

        Returns:
            True if timeout was cancelled, False if not found.
        """
        info = self._timeouts.pop(task_id, None)
        if info and info.handle:
            info.handle.cancel()
            logger.debug(f"Cancelled timeout for task {task_id}")
            return True
        return False

    async def extend_timeout(
        self,
        task_id: str,
        additional: float,
        callback: Callable[[], None] | None = None,
    ) -> bool:
        """Extend the timeout for a task.

        Args:
            task_id: Task identifier.
            additional: Additional time in seconds.
            callback: Optional new callback for the extended timeout.

        Returns:
            True if timeout was extended, False if not found.
        """
        async with self._lock:
            info = self._timeouts.get(task_id)
            if not info:
                return False

            if info.handle:
                info.handle.cancel()

            new_timeout = info.timeout + additional
            loop = asyncio.get_event_loop()

            handle = loop.call_later(new_timeout, callback) if callback else None

            info.timeout = new_timeout
            info.deadline = time.time() + new_timeout
            info.handle = handle

            logger.debug(
                f"Extended timeout for task {task_id} by {additional}s (total: {new_timeout}s)"
            )
            return True

    def get_remaining_time(self, task_id: str) -> float | None:
        """Get remaining time before timeout.

        Args:
            task_id: Task identifier.

        Returns:
            Remaining seconds, or None if not found.
        """
        info = self._timeouts.get(task_id)
        if not info:
            return None

        remaining = info.deadline - time.time()
        return max(0.0, remaining)

    def get_timeout_info(self, task_id: str) -> TimeoutInfo | None:
        """Get timeout info for a task.

        Args:
            task_id: Task identifier.

        Returns:
            Timeout info, or None if not found.
        """
        return self._timeouts.get(task_id)

    def list_active_timeouts(self) -> list[TimeoutInfo]:
        """List all active timeouts.

        Returns:
            List of timeout information.
        """
        return list(self._timeouts.values())

    def clear_all(self) -> None:
        """Clear all timeouts."""
        for _task_id, info in list(self._timeouts.items()):
            if info.handle:
                info.handle.cancel()
        self._timeouts.clear()
        logger.debug("Cleared all timeouts")

    async def _register_timeout(self, task_id: str, timeout: float) -> None:
        """Register a timeout for tracking.

        Args:
            task_id: Task identifier.
            timeout: Timeout in seconds.
        """
        async with self._lock:
            info = TimeoutInfo(
                task_id=task_id,
                timeout=timeout,
                started_at=time.time(),
                deadline=time.time() + timeout,
            )
            self._timeouts[task_id] = info

    async def _cancel_timeout(self, task_id: str) -> None:
        """Cancel a timeout (async version).

        Args:
            task_id: Task identifier.
        """
        async with self._lock:
            self.cancel_timeout(task_id)
