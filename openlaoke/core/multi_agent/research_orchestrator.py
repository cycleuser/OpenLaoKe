"""Research workflow orchestrator.

Coordinates the research agent pipeline:
researcher -> writer -> verifier -> reviewer
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openlaoke.core.multi_agent.research_agents import (
    ResearchAgentType,
    get_research_agent_profile,
)
from openlaoke.core.supervisor.provenance import ProvenanceRecord, VerificationStatus
from openlaoke.core.supervisor.slug_utils import ensure_output_dirs, generate_slug, get_output_paths

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class WorkflowStep:
    """A single step in the research workflow."""

    agent_type: ResearchAgentType
    task_description: str
    output_key: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class WorkflowResult:
    """Result of a complete research workflow."""

    slug: str
    topic: str
    steps_completed: int = 0
    total_steps: int = 0
    output_files: dict[str, str] = field(default_factory=dict)
    provenance: ProvenanceRecord | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.steps_completed == self.total_steps and not self.errors


class ResearchWorkflowOrchestrator:
    """Orchestrates research workflows using specialized agents."""

    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self._current_workflow: WorkflowResult | None = None

    def create_workflow(self, topic: str, workflow_type: str = "deepresearch") -> WorkflowResult:
        slug = generate_slug(topic)
        ensure_output_dirs()
        paths = get_output_paths(slug)

        provenance = ProvenanceRecord(
            topic=topic,
            slug=slug,
            plan_path=paths["plan"],
            output_path=paths["output"],
        )

        result = WorkflowResult(
            slug=slug,
            topic=topic,
            provenance=provenance,
        )

        if workflow_type == "deepresearch":
            result.total_steps = 4
        elif workflow_type == "lit":
            result.total_steps = 3
        elif workflow_type == "review":
            result.total_steps = 2
        else:
            result.total_steps = 1

        self._current_workflow = result
        return result

    def get_steps(self, workflow_type: str = "deepresearch") -> list[WorkflowStep]:
        if workflow_type == "deepresearch":
            return [
                WorkflowStep(
                    agent_type=ResearchAgentType.RESEARCHER,
                    task_description="Gather evidence from papers, web, and repos",
                    output_key="research",
                ),
                WorkflowStep(
                    agent_type=ResearchAgentType.WRITER,
                    task_description="Write draft from research notes",
                    output_key="draft",
                    depends_on=["research"],
                ),
                WorkflowStep(
                    agent_type=ResearchAgentType.VERIFIER,
                    task_description="Add citations and verify sources",
                    output_key="cited",
                    depends_on=["draft"],
                ),
                WorkflowStep(
                    agent_type=ResearchAgentType.REVIEWER,
                    task_description="Review the cited draft",
                    output_key="review",
                    depends_on=["cited"],
                ),
            ]
        elif workflow_type == "lit":
            return [
                WorkflowStep(
                    agent_type=ResearchAgentType.RESEARCHER,
                    task_description="Search and gather academic papers",
                    output_key="research",
                ),
                WorkflowStep(
                    agent_type=ResearchAgentType.WRITER,
                    task_description="Write literature review",
                    output_key="draft",
                    depends_on=["research"],
                ),
                WorkflowStep(
                    agent_type=ResearchAgentType.VERIFIER,
                    task_description="Verify citations",
                    output_key="cited",
                    depends_on=["draft"],
                ),
            ]
        elif workflow_type == "review":
            return [
                WorkflowStep(
                    agent_type=ResearchAgentType.REVIEWER,
                    task_description="Review the artifact",
                    output_key="review",
                ),
                WorkflowStep(
                    agent_type=ResearchAgentType.VERIFIER,
                    task_description="Verify review claims",
                    output_key="verification",
                    depends_on=["review"],
                ),
            ]
        return []

    def get_agent_prompt(self, agent_type: ResearchAgentType, task_context: str) -> str:
        profile = get_research_agent_profile(agent_type)
        return f"{profile.system_prompt}\n\n## Current Task\n{task_context}"

    def complete_step(self, output_key: str, output_content: str, output_path: str) -> None:
        if self._current_workflow is None:
            return

        self._current_workflow.steps_completed += 1
        self._current_workflow.output_files[output_key] = output_path

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_content)

    def finalize(self) -> WorkflowResult:
        if self._current_workflow is None:
            raise ValueError("No active workflow")

        if self._current_workflow.provenance:
            self._current_workflow.provenance.compute_verification_status()
            if self._current_workflow.errors:
                self._current_workflow.provenance.verification = VerificationStatus.BLOCKED
                for err in self._current_workflow.errors:
                    self._current_workflow.provenance.blocked_checks.append(err)
            self._current_workflow.provenance.save()

        result = self._current_workflow
        self._current_workflow = None
        return result
