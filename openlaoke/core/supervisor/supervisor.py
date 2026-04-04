"""Task supervisor - ensures user tasks are completed."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from openlaoke.core.supervisor.checker import TaskCompletionChecker
from openlaoke.core.supervisor.requirements import TaskRequirements

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class RetryReason(StrEnum):
    INCOMPLETE_OUTPUT = "incomplete_output"
    MISSING_REQUIREMENTS = "missing_requirements"
    ERROR_OCCURRED = "error_occurred"
    QUALITY_ISSUE = "quality_issue"
    AI_DETECTED = "ai_detected"


@dataclass
class SupervisedTask:
    original_request: str
    requirements: list[TaskRequirements]
    status: TaskStatus = TaskStatus.PENDING
    completion_percentage: float = 0.0
    attempts: int = 0
    max_attempts: int = 5
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    last_check_time: float = 0.0
    retry_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SupervisionResult:
    task_id: str
    is_complete: bool
    completion_percentage: float
    missing_requirements: list[str]
    suggested_actions: list[str]
    should_retry: bool
    retry_reason: RetryReason | None = None
    feedback: str = ""


class TaskSupervisor:
    """Supervises task execution to ensure completion.

    Core responsibilities:
    1. Parse user requests into verifiable requirements
    2. Monitor task progress throughout execution
    3. Detect incomplete or low-quality outputs
    4. Trigger retries with specific feedback
    5. Escalate when automatic recovery fails
    """

    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.tasks: dict[str, SupervisedTask] = {}
        self.checker = TaskCompletionChecker()
        self._supervision_enabled = True
        self._anti_ai_mode = True

    def parse_request(self, user_request: str) -> SupervisedTask:
        requirements = self._extract_requirements(user_request)

        task = SupervisedTask(
            original_request=user_request,
            requirements=requirements,
            status=TaskStatus.PENDING,
        )

        task_id = f"task_{int(time.time() * 1000)}"
        self.tasks[task_id] = task

        return task

    def _extract_requirements(self, request: str) -> list[TaskRequirements]:
        requirements = []
        request_lower = request.lower()

        if any(word in request_lower for word in ["写", "write", "撰写", "创建"]):
            if "文章" in request_lower or "article" in request_lower or "paper" in request_lower:
                requirements.extend(
                    [
                        TaskRequirements(
                            name="document_created",
                            description="Target document must be created",
                            check_type="file_exists",
                            critical=True,
                        ),
                        TaskRequirements(
                            name="sufficient_length",
                            description="Document must have substantial content (min 3000 words)",
                            check_type="word_count",
                            threshold=3000,
                            critical=True,
                        ),
                        TaskRequirements(
                            name="proper_structure",
                            description="Document must have academic structure with sections",
                            check_type="structure",
                            patterns=["Introduction", "Conclusion", "References"],
                            critical=True,
                        ),
                        TaskRequirements(
                            name="has_citations",
                            description="Document must include citations",
                            check_type="contains",
                            patterns=["[1]", "[2]", "References", "参考文献"],
                            critical=False,
                        ),
                        TaskRequirements(
                            name="anti_ai_quality",
                            description="Content must not have AI-typical patterns",
                            check_type="anti_ai_check",
                            critical=True,
                        ),
                        TaskRequirements(
                            name="references_downloaded",
                            description="All cited references must be downloaded to pdf/ directory",
                            check_type="references_exist",
                            critical=True,
                        ),
                        TaskRequirements(
                            name="has_real_citations",
                            description="Document must cite REAL papers with downloadable sources",
                            check_type="citations_quality",
                            critical=False,
                        ),
                    ]
                )

        if any(word in request_lower for word in ["对比", "compare", "分析", "analyze"]):
            requirements.extend(
                [
                    TaskRequirements(
                        name="comparison_table",
                        description="Must include comparison table or matrix",
                        check_type="contains",
                        patterns=["|", "Table", "表格", "对比"],
                        critical=False,
                    ),
                    TaskRequirements(
                        name="quantitative_data",
                        description="Must include specific numbers and measurements",
                        check_type="has_numbers",
                        critical=True,
                    ),
                ]
            )

        if any(word in request_lower for word in ["图表", "figure", "diagram", "svg"]):
            requirements.extend(
                [
                    TaskRequirements(
                        name="figures_created",
                        description="Must create visual figures/diagrams",
                        check_type="files_created",
                        patterns=["*.svg", "*.png", "*.pdf"],
                        critical=True,
                    ),
                ]
            )

        if any(word in request_lower for word in ["代码", "code", "实现"]):
            requirements.extend(
                [
                    TaskRequirements(
                        name="code_included",
                        description="Must include code examples",
                        check_type="contains",
                        patterns=["```", "def ", "class ", "function "],
                        critical=True,
                    ),
                ]
            )

        if not requirements:
            requirements.append(
                TaskRequirements(
                    name="task_completed",
                    description="Task should show evidence of completion",
                    check_type="general",
                    critical=True,
                )
            )

        return requirements

    async def check_completion(
        self,
        task_id: str,
        artifacts: dict[str, Any],
    ) -> SupervisionResult:
        if task_id not in self.tasks:
            return SupervisionResult(
                task_id=task_id,
                is_complete=False,
                completion_percentage=0.0,
                missing_requirements=["Task not found"],
                suggested_actions=["Restart task"],
                should_retry=False,
            )

        task = self.tasks[task_id]
        task.artifacts = artifacts
        task.last_check_time = time.time()

        missing = []
        completed_count = 0
        total_weight = 0.0

        for req in task.requirements:
            is_satisfied = await self.checker.check_requirement(req, artifacts)

            if is_satisfied:
                completed_count += 1
                total_weight += req.weight
            else:
                missing.append(req.description)

        critical_missing = [
            req.description
            for req in task.requirements
            if req.critical and not await self.checker.check_requirement(req, artifacts)
        ]

        completion = (completed_count / len(task.requirements)) * 100 if task.requirements else 0.0

        is_complete = len(critical_missing) == 0 and completion >= 80.0

        should_retry = (
            not is_complete and task.attempts < task.max_attempts and len(critical_missing) > 0
        )

        retry_reason = None
        if should_retry:
            if any("AI" in m or "anti-ai" in m.lower() for m in missing):
                retry_reason = RetryReason.AI_DETECTED
            elif any("length" in m.lower() or "word" in m.lower() for m in missing):
                retry_reason = RetryReason.INCOMPLETE_OUTPUT
            elif critical_missing:
                retry_reason = RetryReason.MISSING_REQUIREMENTS
            else:
                retry_reason = RetryReason.QUALITY_ISSUE

        suggested_actions = self._generate_suggestions(missing, retry_reason)

        feedback = self._generate_feedback(task, missing, completion)

        result = SupervisionResult(
            task_id=task_id,
            is_complete=is_complete,
            completion_percentage=completion,
            missing_requirements=missing,
            suggested_actions=suggested_actions,
            should_retry=should_retry,
            retry_reason=retry_reason,
            feedback=feedback,
        )

        if is_complete:
            task.status = TaskStatus.COMPLETED
        elif should_retry:
            task.status = TaskStatus.RETRYING
            task.attempts += 1
            task.retry_history.append(
                {
                    "attempt": task.attempts,
                    "reason": retry_reason.value if retry_reason else None,
                    "missing": missing,
                    "timestamp": time.time(),
                }
            )

        return result

    def _generate_suggestions(
        self,
        missing: list[str],
        retry_reason: RetryReason | None,
    ) -> list[str]:
        suggestions = []

        if retry_reason == RetryReason.AI_DETECTED:
            suggestions.extend(
                [
                    "Add specific numbers and measurements to support claims",
                    "Include real citations from actual papers (search WebSearch)",
                    "Reference specific code files with line numbers",
                    "Remove generic bullet-point lists, write full paragraphs",
                    "Add technical depth: explain HOW and WHY, not just WHAT",
                ]
            )

        if retry_reason == RetryReason.INCOMPLETE_OUTPUT:
            suggestions.extend(
                [
                    "Expand content to meet minimum word count",
                    "Add more detailed explanations for each section",
                    "Include additional examples and case studies",
                ]
            )

        if retry_reason == RetryReason.MISSING_REQUIREMENTS:
            for item in missing[:3]:
                suggestions.append(f"Address requirement: {item}")

        if retry_reason == RetryReason.QUALITY_ISSUE:
            suggestions.extend(
                [
                    "Review content for technical accuracy",
                    "Add comparative analysis with specific data",
                    "Include visualizations or tables",
                ]
            )

        return suggestions

    def _generate_feedback(
        self,
        task: SupervisedTask,
        missing: list[str],
        completion: float,
    ) -> str:
        if completion >= 80.0:
            return ""

        lines = [
            f"⚠️ Task completion: {completion:.1f}%",
            "",
            "Missing requirements:",
        ]

        for i, item in enumerate(missing[:5], 1):
            lines.append(f"  {i}. {item}")

        if task.attempts > 0:
            lines.append(f"\nAttempt {task.attempts}/{task.max_attempts}")

        if self._anti_ai_mode and any("AI" in m for m in missing):
            lines.extend(
                [
                    "",
                    "🔧 Anti-AI Quality Issues Detected:",
                    "  - Content appears to use AI-typical patterns",
                    "  - Add SPECIFIC: numbers, citations, code references",
                    "  - Remove GENERIC: lists without substance, vague claims",
                    "  - Reference REAL: actual papers, actual code lines",
                ]
            )

        return "\n".join(lines)

    def get_task_status(self, task_id: str) -> SupervisedTask | None:
        return self.tasks.get(task_id)

    def should_escalate(self, task_id: str) -> bool:
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        return task.attempts >= task.max_attempts and task.status != TaskStatus.COMPLETED

    def get_retry_prompt(self, task_id: str, result: SupervisionResult) -> str:
        if task_id not in self.tasks:
            return ""

        task = self.tasks[task_id]

        prompt_parts = [
            f"The previous attempt did not fully complete the task (Attempt {task.attempts}/{task.max_attempts}).",
            "",
            "Original request:",
            f"  {task.original_request}",
            "",
            f"Completion: {result.completion_percentage:.1f}%",
            "",
            "Issues to fix:",
        ]

        for i, issue in enumerate(result.missing_requirements[:5], 1):
            prompt_parts.append(f"  {i}. {issue}")

        prompt_parts.extend(
            [
                "",
                "Required actions:",
            ]
        )

        for i, action in enumerate(result.suggested_actions[:5], 1):
            prompt_parts.append(f"  {i}. {action}")

        if result.retry_reason == RetryReason.AI_DETECTED:
            prompt_parts.extend(
                [
                    "",
                    "⚠️ CRITICAL: Anti-AI Quality Check Failed",
                    "Your previous output was detected as AI-generated due to:",
                    "  - Generic bullet points without substance",
                    "  - Vague claims without evidence",
                    "  - Missing specific numbers and citations",
                    "",
                    "You MUST:",
                    "  1. Search for REAL papers using WebSearch and cite them properly",
                    "  2. Include SPECIFIC numbers: 'X% improvement', 'Y lines of code'",
                    "  3. Reference ACTUAL code: 'file.py:157 implements lazy loading'",
                    "  4. Write COMPLETE paragraphs, not fragmented lists",
                    "  5. Explain HOW and WHY, provide technical depth",
                ]
            )

        prompt_parts.extend(
            [
                "",
                "Please continue the task and address all missing requirements.",
                "Focus on producing HIGH-QUALITY, SPECIFIC, EVIDENCE-BASED content.",
            ]
        )

        return "\n".join(prompt_parts)

    def enable_supervision(self, enabled: bool = True) -> None:
        self._supervision_enabled = enabled

    def enable_anti_ai_mode(self, enabled: bool = True) -> None:
        self._anti_ai_mode = enabled
        self.checker.enable_anti_ai_check(enabled)
