"""Middleware context for request processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.state import AppState
    from openlaoke.core.tool import Tool
    from openlaoke.types.core_types import Message


@dataclass
class MiddlewareContext:
    """Context passed through the middleware chain.

    Contains all the information needed for middleware to process requests.
    """

    state: AppState
    messages: list[Message] = field(default_factory=list)
    current_tool: Tool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    request_type: str = "completion"
    aborted: bool = False
    error: Exception | None = None

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata value."""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value."""
        return self.metadata.get(key, default)

    def abort(self, reason: str | None = None) -> None:
        """Abort the middleware chain."""
        self.aborted = True
        if reason:
            self.metadata["abort_reason"] = reason

    def set_error(self, error: Exception) -> None:
        """Set an error to be handled by error middleware."""
        self.error = error

    def clear_error(self) -> None:
        """Clear the current error."""
        self.error = None
