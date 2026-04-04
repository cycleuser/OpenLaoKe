"""Type definitions for HyperAuto system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class HyperAutoMode(StrEnum):
    """Operating modes for HyperAuto."""

    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"
    HYPER_AUTO = "hyper_auto"


class HyperAutoState(StrEnum):
    """States for HyperAuto workflow."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RETRYING = "retrying"
    REFLECTING = "reflecting"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"


class SubTaskStatus(StrEnum):
    """Status of a sub-task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DecisionType(StrEnum):
    """Types of automated decisions."""

    SKILL_CREATION = "skill_creation"
    PROJECT_INIT = "project_init"
    CODE_SEARCH = "code_search"
    DEPENDENCY_INSTALL = "dependency_install"
    TEST_EXECUTION = "test_execution"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    RETRY = "retry"
    ABORT = "abort"


@dataclass
class SubTask:
    """A sub-task in the HyperAuto workflow."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    description: str = ""
    status: SubTaskStatus = SubTaskStatus.PENDING
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class Decision:
    """An automated decision made by HyperAuto."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    type: DecisionType = DecisionType.SKILL_CREATION
    confidence: float = 0.0
    reasoning: str = ""
    action: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    executed: bool = False
    result: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "action": self.action,
            "parameters": self.parameters,
            "approved": self.approved,
            "executed": self.executed,
            "result": self.result,
        }


@dataclass
class Reflection:
    """A reflection on completed work."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    task_id: str = ""
    success: bool = False
    observations: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    learned_patterns: list[str] = field(default_factory=list)
    error_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "success": self.success,
            "observations": self.observations,
            "improvements": self.improvements,
            "learned_patterns": self.learned_patterns,
            "error_patterns": self.error_patterns,
        }


@dataclass
class WorkflowContext:
    """Context for a HyperAuto workflow execution."""

    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    original_request: str = ""
    current_state: HyperAutoState = HyperAutoState.IDLE
    sub_tasks: list[SubTask] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    reflections: list[Reflection] = field(default_factory=list)
    iteration: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    start_time: float = 0.0
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "original_request": self.original_request,
            "current_state": self.current_state.value,
            "sub_tasks": [t.to_dict() for t in self.sub_tasks],
            "decisions": [d.to_dict() for d in self.decisions],
            "reflections": [r.to_dict() for r in self.reflections],
            "iteration": self.iteration,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata,
        }

    def get_pending_tasks(self) -> list[SubTask]:
        return [t for t in self.sub_tasks if t.status == SubTaskStatus.PENDING]

    def get_running_tasks(self) -> list[SubTask]:
        return [t for t in self.sub_tasks if t.status == SubTaskStatus.RUNNING]

    def get_completed_tasks(self) -> list[SubTask]:
        return [t for t in self.sub_tasks if t.status == SubTaskStatus.COMPLETED]

    def get_failed_tasks(self) -> list[SubTask]:
        return [t for t in self.sub_tasks if t.status == SubTaskStatus.FAILED]
