"""TodoWrite tool - manage todo lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


@dataclass
class TodoItem:
    content: str
    status: Literal["pending", "in_progress", "completed", "cancelled"] = "pending"
    priority: Literal["high", "medium", "low"] = "medium"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TodoInput(BaseModel):
    todos: list[dict[str, Any]] = Field(
        description="List of todo items. Each item has 'content' (required), 'status' (pending/in_progress/completed/cancelled), and 'priority' (high/medium/low)"
    )


class TodoWriteTool(Tool):
    """Manage a todo list for tracking tasks."""

    name = "TodoWrite"
    description = (
        "Manages a todo list for tracking tasks. "
        "Use this to track progress on complex multi-step tasks. "
        "Each todo item has content, status (pending/in_progress/completed/cancelled), and priority (high/medium/low). "
        "The todo list is persisted across conversations."
    )
    input_schema = TodoInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    def __init__(self) -> None:
        self._todos: list[TodoItem] = []

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        todos_data = kwargs.get("todos", [])

        if not isinstance(todos_data, list):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: todos must be a list",
                is_error=True,
            )

        new_todos: list[TodoItem] = []
        for item in todos_data:
            if not isinstance(item, dict):
                continue
            content = item.get("content", "")
            if not content:
                continue
            status = item.get("status", "pending")
            if status not in ("pending", "in_progress", "completed", "cancelled"):
                status = "pending"
            priority = item.get("priority", "medium")
            if priority not in ("high", "medium", "low"):
                priority = "medium"
            new_todos.append(
                TodoItem(
                    content=content,
                    status=status,
                    priority=priority,
                )
            )

        self._todos = new_todos

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=self._render_todos(),
            is_error=False,
        )

    def _render_todos(self) -> str:
        if not self._todos:
            return "Todo list is empty"

        lines = ["Current todo list:\n"]
        priority_order = {"high": 0, "medium": 1, "low": 2}
        status_icon = {
            "pending": "○",
            "in_progress": "◐",
            "completed": "●",
            "cancelled": "✕",
        }

        sorted_todos = sorted(
            self._todos,
            key=lambda t: (priority_order.get(t.priority, 1), t.content),
        )

        for todo in sorted_todos:
            icon = status_icon.get(todo.status, "○")
            priority_marker = "!" if todo.priority == "high" else " "
            lines.append(f"  {icon} {priority_marker} {todo.content}")
            if todo.status == "in_progress":
                lines.append(f"      Status: {todo.status}")

        summary = {
            "pending": sum(1 for t in self._todos if t.status == "pending"),
            "in_progress": sum(1 for t in self._todos if t.status == "in_progress"),
            "completed": sum(1 for t in self._todos if t.status == "completed"),
            "cancelled": sum(1 for t in self._todos if t.status == "cancelled"),
        }
        lines.append(
            f"\nSummary: {summary['completed']} done, {summary['in_progress']} in progress, {summary['pending']} pending"
        )

        return "\n".join(lines)


def register(registry: ToolRegistry) -> None:
    registry.register(TodoWriteTool())
