"""Agent supervisor integration for verification and evolution."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from openlaoke.core.hyperauto.types import Decision, DecisionType, SubTask, SubTaskStatus
from openlaoke.core.supervisor import SupervisionResult, TaskSupervisor

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class AgentSupervisorIntegration:
    """Integrates supervisor into HyperAuto agent for verification and evolution."""

    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.supervisor = TaskSupervisor(app_state)

    async def verify_completion(self, context: Any, task_id: str) -> SupervisionResult:
        """Verify that the task is truly completed."""
        artifacts: dict[str, Any] = {
            "content": "",
            "output_files": [],
            "working_dir": self.app_state.cwd,
        }

        for task in context.sub_tasks:
            if task.status == SubTaskStatus.COMPLETED and task.result:
                tool_results = task.result.get("tool_results", [])
                for tr in tool_results:
                    if tr.get("tool") in ["Write", "Edit", "Bash"]:
                        result_text = tr.get("result", "")
                        if "created" in result_text.lower() or "written" in result_text.lower():
                            file_match = re.search(
                                r"['\"]([^'\"]+\.(c|h|py|md|txt))['\"]", result_text
                            )
                            if file_match:
                                artifacts["output_files"].append(file_match.group(1))

                final_response = task.result.get("final_response", "")
                artifacts["content"] += final_response + "\n"

        result = await self.supervisor.check_completion(task_id, artifacts)
        return result

    def evolve_strategy(
        self, verification_result: SupervisionResult, context: Any
    ) -> list[SubTask]:
        """Evolve strategy based on verification failure."""
        new_tasks = []
        missing = verification_result.missing_requirements

        if missing:
            for i, req in enumerate(missing[:3]):
                new_task = SubTask(
                    name=f"address_missing_{i}",
                    description=f"Address requirement: {req}",
                    priority=100 + i,
                    dependencies=[],
                    metadata={
                        "type": "fix",
                        "from_verification": True,
                        "retry_reason": verification_result.retry_reason.value
                        if verification_result.retry_reason
                        else None,
                    },
                )
                new_tasks.append(new_task)

        context.decisions.append(
            Decision(
                type=DecisionType.RETRY,
                confidence=0.7,
                reasoning=f"Task incomplete: {verification_result.completion_percentage:.1f}%. Missing: {missing[:3]}",
                action="evolve_strategy",
                parameters={
                    "missing_requirements": missing,
                    "completion_pct": verification_result.completion_percentage,
                },
                executed=True,
            )
        )

        return new_tasks

    def get_retry_prompt(
        self, verification_result: SupervisionResult, original_request: str
    ) -> str:
        """Generate retry prompt based on verification failure."""
        return self.supervisor.get_retry_prompt(original_request, verification_result)
