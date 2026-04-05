"""Incremental development workflow for small models.

Orchestrates the complete workflow: decomposition → implementation → assembly → validation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.core.architecture.assembler import (
    AssemblyResult,
    CodeAssembler,
    IntegrationValidator,
)
from openlaoke.core.architecture.decomposer import (
    AtomicTask,
    FineGrainedDecomposer,
    TaskGraph,
    create_decomposer_for_model,
)
from openlaoke.core.architecture.interfaces import (
    ComponentSpec,
    ComponentType,
    TaskSize,
    estimate_task_complexity,
)
from openlaoke.core.model_assessment.types import ModelTier
from openlaoke.core.state import AppState


@dataclass
class WorkflowStep:
    step_id: str
    task: AtomicTask
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    result: AssemblyResult | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None


@dataclass
class IncrementalWorkflow:
    workflow_id: str
    project_spec: dict[str, Any]
    model: str
    model_tier: ModelTier
    decomposer: FineGrainedDecomposer
    assembler: CodeAssembler
    validator: IntegrationValidator
    task_graph: TaskGraph | None = None
    steps: dict[str, WorkflowStep] = field(default_factory=dict)
    current_step: str | None = None
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)

    def get_progress(self) -> dict[str, Any]:
        total = len(self.steps)
        completed = len(self.completed_steps)
        failed = len(self.failed_steps)
        pending = total - completed - failed

        return {
            "workflow_id": self.workflow_id,
            "total_steps": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "current_step": self.current_step,
        }


class IncrementalOrchestrator:
    def __init__(self, app_state: AppState, model: str, model_tier: ModelTier):
        self.app_state = app_state
        self.model = model
        self.model_tier = model_tier
        self.decomposer = create_decomposer_for_model(model_tier)
        self.project_root = Path(app_state.cwd)
        self.assembler = CodeAssembler(self.project_root)
        self.validator = IntegrationValidator(self.project_root)
        self.workflows: dict[str, IncrementalWorkflow] = {}

    def create_workflow(self, project_spec: dict[str, Any]) -> IncrementalWorkflow:
        workflow_id = f"workflow_{int(time.time() * 1000)}"

        workflow = IncrementalWorkflow(
            workflow_id=workflow_id,
            project_spec=project_spec,
            model=self.model,
            model_tier=self.model_tier,
            decomposer=self.decomposer,
            assembler=self.assembler,
            validator=self.validator,
        )

        workflow.task_graph = self.decomposer.decompose_project(project_spec)

        for task_id, task in workflow.task_graph.tasks.items():
            step = WorkflowStep(
                step_id=task_id,
                task=task,
                max_attempts=self._get_max_attempts_for_task(task),
            )
            workflow.steps[task_id] = step

        self.workflows[workflow_id] = workflow
        return workflow

    def execute_workflow(self, workflow_id: str) -> AssemblyResult:
        if workflow_id not in self.workflows:
            return AssemblyResult(
                success=False,
                code="",
                errors=[f"Workflow {workflow_id} not found"],
            )

        workflow = self.workflows[workflow_id]

        if not workflow.task_graph:
            return AssemblyResult(
                success=False,
                code="",
                errors=["No task graph available"],
            )

        while True:
            ready_steps = self._get_ready_steps(workflow)

            if not ready_steps:
                break

            for step in ready_steps:
                workflow.current_step = step.step_id
                step.status = "in_progress"
                step.started_at = time.time()

                result = self._execute_step(step, workflow)

                step.result = result
                step.completed_at = time.time()
                step.attempts += 1

                if result.success:
                    step.status = "completed"
                    workflow.completed_steps.append(step.step_id)
                    workflow.task_graph.mark_completed(step.step_id)
                else:
                    if step.attempts >= step.max_attempts:
                        step.status = "failed"
                        workflow.failed_steps.append(step.step_id)
                        workflow.task_graph.mark_failed(step.step_id)
                        step.error = "\n".join(result.errors)
                    else:
                        step.status = "retrying"

        return self.assembler.assemble_task_graph(workflow.task_graph)

    def _get_ready_steps(self, workflow: IncrementalWorkflow) -> list[WorkflowStep]:
        ready = []

        for step_id, step in workflow.steps.items():
            if step.status in ["completed", "failed"]:
                continue

            if step.status == "in_progress":
                continue

            if step.status == "retrying" and step.attempts < step.max_attempts:
                deps_satisfied = all(
                    dep_id in workflow.completed_steps for dep_id in step.task.dependencies
                )
                if deps_satisfied:
                    ready.append(step)
                continue

            if step.status == "pending":
                deps_satisfied = all(
                    dep_id in workflow.completed_steps for dep_id in step.task.dependencies
                )
                if deps_satisfied:
                    ready.append(step)

        ready.sort(key=lambda s: s.task.estimated_lines)

        return ready[:1]

    def _execute_step(self, step: WorkflowStep, workflow: IncrementalWorkflow) -> AssemblyResult:
        return self.assembler.assemble_atomic_task(step.task, workflow.task_graph)

    def _get_max_attempts_for_task(self, task: AtomicTask) -> int:
        base_attempts = {
            ModelTier.TIER_1_ADVANCED: 2,
            ModelTier.TIER_2_CAPABLE: 3,
            ModelTier.TIER_3_MODERATE: 4,
            ModelTier.TIER_4_BASIC: 5,
            ModelTier.TIER_5_LIMITED: 8,
        }

        attempts = base_attempts[self.model_tier]

        complexity = estimate_task_complexity(task.component_spec)
        if complexity == TaskSize.LARGE:
            attempts += 2
        elif complexity == TaskSize.MEDIUM:
            attempts += 1

        return attempts

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any] | None:
        if workflow_id not in self.workflows:
            return None

        workflow = self.workflows[workflow_id]
        progress = workflow.get_progress()

        step_details = []
        for step_id, step in workflow.steps.items():
            step_details.append(
                {
                    "step_id": step_id,
                    "description": step.task.description,
                    "status": step.status,
                    "attempts": step.attempts,
                    "max_attempts": step.max_attempts,
                    "error": step.error,
                }
            )

        return {
            **progress,
            "steps": step_details,
            "model": workflow.model,
            "model_tier": workflow.model_tier.value,
        }

    def save_workflow_state(self, workflow_id: str) -> None:
        if workflow_id not in self.workflows:
            return

        workflow = self.workflows[workflow_id]
        state_file = self.project_root / ".openlaoke" / "workflows" / f"{workflow_id}.json"

        state_file.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "workflow_id": workflow.workflow_id,
            "model": workflow.model,
            "model_tier": workflow.model_tier.value,
            "progress": workflow.get_progress(),
            "completed_steps": workflow.completed_steps,
            "failed_steps": workflow.failed_steps,
        }

        state_file.write_text(json.dumps(state, indent=2))

    def load_workflow_state(self, workflow_id: str) -> IncrementalWorkflow | None:
        state_file = self.project_root / ".openlaoke" / "workflows" / f"{workflow_id}.json"

        if not state_file.exists():
            return None

        state = json.loads(state_file.read_text())

        if workflow_id not in self.workflows:
            return None

        workflow = self.workflows[workflow_id]
        workflow.completed_steps = state.get("completed_steps", [])
        workflow.failed_steps = state.get("failed_steps", [])

        return workflow


def create_orchestrator_for_model(app_state: AppState, model: str) -> IncrementalOrchestrator:
    from openlaoke.core.model_assessment.assessor import ModelAssessor
    from openlaoke.types.providers import MultiProviderConfig

    config = MultiProviderConfig.defaults()
    assessor = ModelAssessor(config)
    tier = assessor.get_tier(model)

    return IncrementalOrchestrator(app_state, model, tier)
