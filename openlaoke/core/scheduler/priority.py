"""Priority queue implementation for task scheduling."""

from __future__ import annotations

import heapq
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class PrioritizedItem:
    """An item in the priority queue.

    Lower priority values are processed first (higher priority).
    """

    priority: int
    sequence: int = field(compare=True)
    item: Any = field(compare=False)


class PriorityQueue:
    """Thread-safe priority queue for task scheduling."""

    def __init__(self, maxsize: int = 0):
        """Initialize the priority queue.

        Args:
            maxsize: Maximum size of the queue (0 = unlimited).
        """
        self._queue: list[PrioritizedItem] = []
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._maxsize = maxsize
        self._sequence = 0

    def put(
        self, item: Any, priority: int = 0, block: bool = True, timeout: float | None = None
    ) -> bool:
        """Put an item into the queue with a priority.

        Args:
            item: Item to put in the queue.
            priority: Priority of the item (lower = higher priority).
            block: Whether to block if queue is full.
            timeout: Timeout for blocking.

        Returns:
            True if item was added, False otherwise.
        """
        with self._not_full:
            if self._maxsize > 0:
                if not block and len(self._queue) >= self._maxsize:
                    return False
                if timeout is not None:
                    if not self._not_full.wait_for(
                        lambda: len(self._queue) < self._maxsize, timeout=timeout
                    ):
                        return False
                elif block:
                    while len(self._queue) >= self._maxsize:
                        self._not_full.wait()

            with self._lock:
                prioritized = PrioritizedItem(
                    priority=priority,
                    sequence=self._sequence,
                    item=item,
                )
                self._sequence += 1
                heapq.heappush(self._queue, prioritized)

            self._not_empty.notify()
            return True

    def get(self, block: bool = True, timeout: float | None = None) -> Any | None:
        """Remove and return an item from the queue.

        Args:
            block: Whether to block if queue is empty.
            timeout: Timeout for blocking.

        Returns:
            The item, or None if timeout.
        """
        with self._not_empty:
            if not block and not self._queue:
                return None

            if timeout is not None:
                if not self._not_empty.wait_for(lambda: bool(self._queue), timeout=timeout):
                    return None
            elif block:
                while not self._queue:
                    self._not_empty.wait()

            with self._lock:
                if not self._queue:
                    return None
                prioritized = heapq.heappop(self._queue)

            self._not_full.notify()
            return prioritized.item

    def peek(self) -> Any | None:
        """Peek at the next item without removing it.

        Returns:
            The next item, or None if queue is empty.
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0].item

    def qsize(self) -> int:
        """Return the approximate size of the queue."""
        with self._lock:
            return len(self._queue)

    def empty(self) -> bool:
        """Return True if the queue is empty."""
        with self._lock:
            return not self._queue

    def full(self) -> bool:
        """Return True if the queue is full."""
        with self._lock:
            return self._maxsize > 0 and len(self._queue) >= self._maxsize

    def clear(self) -> None:
        """Clear all items from the queue."""
        with self._lock:
            self._queue.clear()

    def items(self) -> list[Any]:
        """Get all items in the queue (for inspection)."""
        with self._lock:
            return [p.item for p in sorted(self._queue)]
