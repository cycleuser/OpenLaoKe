"""Plan tool - Manage plan mode for structured task planning."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class PlanInput(BaseModel):
    action: str = Field(description="Plan action: enter, exit, update, status, append, prepend")
    plan_content: str | None = Field(
        default=None, description="Plan content (required for enter/update/append/prepend actions)"
    )


class PlanTool(Tool):
    """Manage plan mode for structured task planning."""

    name = "Plan"
    description = (
        "Manage plan mode for structured task planning. "
        "Actions: 'enter' (start planning with content), 'exit' (finish planning), "
        "'update' (replace plan content), 'status' (show current plan), "
        "'append' (add to plan), 'prepend' (insert at start of plan). "
        "Plan mode helps organize complex tasks into actionable steps."
    )
    input_schema = PlanInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action", "").lower().strip()
        plan_content = kwargs.get("plan_content")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required. Use: enter, exit, update, status, append, prepend",
                is_error=True,
            )

        valid_actions = {"enter", "exit", "update", "status", "append", "prepend"}
        if action not in valid_actions:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Unknown action: {action}\nValid actions: {', '.join(sorted(valid_actions))}",
                is_error=True,
            )

        if action in {"enter", "update", "append", "prepend"} and not plan_content:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: plan_content is required for action '{action}'",
                is_error=True,
            )

        try:
            result = self._handle_action(ctx, action, plan_content)
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=result,
                is_error=False,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Plan error: {e}",
                is_error=True,
            )

    def _handle_action(self, ctx: ToolContext, action: str, plan_content: str | None) -> str:
        plan_state = self._get_plan_state(ctx)

        if action == "enter":
            plan_state["active"] = True
            plan_state["content"] = plan_content or ""
            plan_state["steps"] = self._parse_steps(plan_content or "")
            return f"Entered plan mode.\n\nPlan:\n{plan_content}"

        elif action == "exit":
            if not plan_state.get("active"):
                return "Not in plan mode."

            completed = plan_state.get("completed_steps", [])
            total = len(plan_state.get("steps", []))

            summary = f"Exited plan mode.\nCompleted {len(completed)}/{total} steps."
            plan_state["active"] = False
            return summary

        elif action == "update":
            if not plan_state.get("active"):
                return "Not in plan mode. Use 'enter' first."
            plan_state["content"] = plan_content or ""
            plan_state["steps"] = self._parse_steps(plan_content or "")
            return f"Plan updated.\n\nNew plan:\n{plan_content}"

        elif action == "status":
            if not plan_state.get("active"):
                return "Not in plan mode."

            content = plan_state.get("content", "No plan content.")
            steps = plan_state.get("steps", [])
            completed = plan_state.get("completed_steps", [])

            status_lines = [f"Plan Status: {len(completed)}/{len(steps)} steps completed", ""]
            status_lines.append("Plan:")
            status_lines.append(content)
            status_lines.append("")

            if steps:
                status_lines.append("Steps:")
                for i, step in enumerate(steps, 1):
                    check = "[x]" if i - 1 in completed else "[ ]"
                    status_lines.append(f"  {check} {i}. {step}")

            return "\n".join(status_lines)

        elif action == "append":
            if not plan_state.get("active"):
                return "Not in plan mode. Use 'enter' first."
            current = plan_state.get("content", "")
            new_content = current + "\n\n" + (plan_content or "")
            plan_state["content"] = new_content
            plan_state["steps"] = self._parse_steps(new_content)
            return f"Appended to plan.\n\nUpdated plan:\n{new_content}"

        elif action == "prepend":
            if not plan_state.get("active"):
                return "Not in plan mode. Use 'enter' first."
            current = plan_state.get("content", "")
            new_content = (plan_content or "") + "\n\n" + current
            plan_state["content"] = new_content
            plan_state["steps"] = self._parse_steps(new_content)
            return f"Prepended to plan.\n\nUpdated plan:\n{new_content}"

        return f"Unknown action: {action}"

    def _get_plan_state(self, ctx: ToolContext) -> dict[str, Any]:
        if not hasattr(ctx.app_state, "_plan_state"):
            default_state: dict[str, Any] = {
                "active": False,
                "content": "",
                "steps": [],
                "completed_steps": [],
            }
            ctx.app_state._plan_state = default_state
            return default_state
        state = ctx.app_state._plan_state
        return state if isinstance(state, dict) else {}

    def _parse_steps(self, content: str) -> list[str]:
        steps = []
        lines = content.split("\n")

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                steps.append(stripped[2:])
            elif stripped and stripped[0].isdigit() and ". " in stripped:
                idx = stripped.find(". ")
                if idx > 0:
                    steps.append(stripped[idx + 2 :])

        return steps


def register(registry: ToolRegistry) -> None:
    registry.register(PlanTool())
