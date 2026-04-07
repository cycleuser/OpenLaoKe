"""Base middleware class and event types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any

from openlaoke.core.middleware.context import MiddlewareContext


@dataclass
class Event:
    """Event emitted during middleware processing."""

    type: str
    data: dict[str, Any]
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class MessageEvent(Event):
    """Event for message additions."""

    def __init__(self, content: str, role: str = "assistant", **kwargs: Any) -> None:
        super().__init__(
            type="message",
            data={"content": content, "role": role},
            **kwargs,
        )


@dataclass
class ToolCallEvent(Event):
    """Event for tool call start."""

    def __init__(
        self,
        tool_name: str,
        tool_use_id: str,
        tool_input: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(
            type="tool_call",
            data={
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "tool_input": tool_input,
            },
            **kwargs,
        )


@dataclass
class ToolResultEvent(Event):
    """Event for tool call completion."""

    def __init__(
        self,
        tool_use_id: str,
        result: str | dict[str, Any],
        is_error: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            type="tool_result",
            data={
                "tool_use_id": tool_use_id,
                "result": result,
                "is_error": is_error,
            },
            **kwargs,
        )


@dataclass
class ProgressEvent(Event):
    """Event for progress updates."""

    def __init__(
        self,
        message: str,
        percentage: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            type="progress",
            data={"message": message, "percentage": percentage},
            **kwargs,
        )


@dataclass
class ErrorEvent(Event):
    """Event for error conditions."""

    def __init__(self, error: str, error_type: str = "unknown", **kwargs: Any) -> None:
        super().__init__(
            type="error",
            data={"error": error, "error_type": error_type},
            **kwargs,
        )


NextMiddleware = Callable[[MiddlewareContext], AsyncGenerator[Event, None]]


class Middleware(ABC):
    """Base class for all middleware.

    Middleware can intercept and modify the request/response flow.
    Each middleware can:
    - Pre-process the context before passing to the next middleware
    - Post-process events from downstream middleware
    - Short-circuit the chain by not calling next_middleware
    """

    @property
    def name(self) -> str:
        """Get the middleware name."""
        return self.__class__.__name__

    @abstractmethod
    def setup(self, context: MiddlewareContext) -> None:
        """Called before the middleware chain starts.

        Override this to perform initialization.
        """

    @abstractmethod
    def teardown(self, context: MiddlewareContext) -> None:
        """Called after the middleware chain completes.

        Override this to perform cleanup.
        """

    @abstractmethod
    def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        """Process the request.

        Args:
            context: The middleware context
            next_middleware: Function to call the next middleware in the chain

        Yields:
            Events generated during processing
        """
        ...


class SyncMiddleware(Middleware):
    """Base class for synchronous middleware.

    For middleware that doesn't need to yield events downstream.
    """

    def process(self, context: MiddlewareContext) -> list[Event]:
        """Process the context and return events.

        Override this method to perform synchronous processing.

        Args:
            context: The middleware context

        Returns:
            List of events generated during processing
        """
        return []

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        """Process events, then pass to next middleware."""
        for event in self.process(context):
            yield event

        if not context.aborted:
            async for event in next_middleware(context):
                yield event
