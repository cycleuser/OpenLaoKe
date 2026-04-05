"""Safe execution boundary checker.

Ensures tools never access unauthorized directories.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Set


@dataclass
class ExecutionBoundary:
    """Defines safe execution boundaries."""

    allowed_paths: Set[Path]
    denied_paths: Set[Path]

    @classmethod
    def from_cwd(cls, cwd: str | Path) -> "ExecutionBoundary":
        """Create boundary from current working directory."""
        cwd_path = Path(cwd).resolve()

        return cls(
            allowed_paths={cwd_path},
            denied_paths=set(),
        )

    def is_path_allowed(self, path: str | Path) -> bool:
        """Check if a path is within allowed boundaries."""
        try:
            target = Path(path).resolve()
        except (OSError, ValueError):
            return False

        # Check if explicitly denied
        if target in self.denied_paths:
            return False

        # Check if in allowed paths
        for allowed in self.allowed_paths:
            try:
                target.relative_to(allowed)
                return True
            except ValueError:
                pass

        return False

    def check_path(self, path: str | Path, operation: str = "access") -> tuple[bool, str]:
        """Check path and return (allowed, message)."""
        if self.is_path_allowed(path):
            return True, "OK"

        target = Path(path).resolve()
        return False, f"Unauthorized {operation}: {target} is outside working directory"


class SafeToolWrapper:
    """Wraps tool execution with safety checks."""

    def __init__(self, boundary: ExecutionBoundary):
        self.boundary = boundary

    def check_bash_command(self, command: str) -> tuple[bool, str]:
        """Check if bash command is safe."""
        # Extract paths from command
        import re

        # Find potential file paths in command
        path_patterns = [
            r"/[\w/.-]+",
            r"~/[\w/.-]+",
            r"\./[\w/.-]+",
            r"\.\./[\w/.-]+",
        ]

        for pattern in path_patterns:
            matches = re.findall(pattern, command)
            for match in matches:
                allowed, msg = self.boundary.check_path(match, "bash path")
                if not allowed:
                    return False, msg

        return True, "OK"

    def check_read_path(self, path: str) -> tuple[bool, str]:
        """Check if read operation is allowed."""
        return self.boundary.check_path(path, "read")

    def check_write_path(self, path: str) -> tuple[bool, str]:
        """Check if write operation is allowed."""
        return self.boundary.check_path(path, "write")

    def should_skip_for_creation(self, user_input: str) -> bool:
        """Determine if tool calls should be skipped for creation tasks."""
        from openlaoke.core.tool_adapter import ToolCallAdapter

        adapter = ToolCallAdapter("unknown")
        return adapter.should_skip_context_gathering(user_input)


def create_safe_wrapper(cwd: str | Path) -> SafeToolWrapper:
    """Create a safe tool wrapper for the given directory."""
    boundary = ExecutionBoundary.from_cwd(cwd)
    return SafeToolWrapper(boundary)
