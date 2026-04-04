"""Intelligent decision engine for HyperAuto system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openlaoke.core.hyperauto.types import Decision, DecisionType, HyperAutoState, SubTask

if TYPE_CHECKING:
    from openlaoke.core.hyperauto.config import HyperAutoConfig


class RiskLevel(StrEnum):
    """Risk levels for decision options."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionCategory(StrEnum):
    """Categories of decisions."""

    EXECUTION_STRATEGY = "execution_strategy"
    TOOL_SELECTION = "tool_selection"
    SKILL_CREATION = "skill_creation"
    PROJECT_INIT = "project_init"
    ERROR_HANDLING = "error_handling"
    RESOURCE_ALLOCATION = "resource_allocation"


@dataclass
class Context:
    """Execution context for decision making."""

    state: HyperAutoState = HyperAutoState.IDLE
    task: SubTask | None = None
    available_tools: list[str] = field(default_factory=list)
    available_skills: list[str] = field(default_factory=list)
    project_info: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "task": self.task.to_dict() if self.task else None,
            "available_tools": self.available_tools,
            "available_skills": self.available_skills,
            "project_info": self.project_info,
            "constraints": self.constraints,
            "history": self.history,
            "metadata": self.metadata,
        }


@dataclass
class DecisionOption:
    """A possible decision option."""

    action: str = ""
    description: str = ""
    expected_outcome: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = 0.0
    reasoning: str = ""
    alternatives: list[str] = field(default_factory=list)
    category: DecisionCategory = DecisionCategory.EXECUTION_STRATEGY
    parameters: dict[str, Any] = field(default_factory=dict)
    rollback_plan: str | None = None
    estimated_duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "description": self.description,
            "expected_outcome": self.expected_outcome,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
            "category": self.category.value,
            "parameters": self.parameters,
            "rollback_plan": self.rollback_plan,
            "estimated_duration": self.estimated_duration,
            "metadata": self.metadata,
        }


@dataclass
class RiskAssessment:
    """Risk assessment for a decision option."""

    option_id: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    risk_factors: list[str] = field(default_factory=list)
    mitigation_strategies: list[str] = field(default_factory=list)
    impact_score: float = 0.0
    probability_score: float = 0.0
    overall_risk_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "risk_level": self.risk_level.value,
            "risk_factors": self.risk_factors,
            "mitigation_strategies": self.mitigation_strategies,
            "impact_score": self.impact_score,
            "probability_score": self.probability_score,
            "overall_risk_score": self.overall_risk_score,
            "metadata": self.metadata,
        }


@dataclass
class DecisionRecord:
    """Record of a made decision."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    decision: Decision | None = None
    context: Context | None = None
    options: list[DecisionOption] = field(default_factory=list)
    risk_assessments: list[RiskAssessment] = field(default_factory=list)
    selected_option: DecisionOption | None = None
    timestamp: float = field(default_factory=time.time)
    outcome: str | None = None
    success: bool = False
    lessons_learned: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "decision": self.decision.to_dict() if self.decision else None,
            "context": self.context.to_dict() if self.context else None,
            "options": [o.to_dict() for o in self.options],
            "risk_assessments": [r.to_dict() for r in self.risk_assessments],
            "selected_option": self.selected_option.to_dict() if self.selected_option else None,
            "timestamp": self.timestamp,
            "outcome": self.outcome,
            "success": self.success,
            "lessons_learned": self.lessons_learned,
            "metadata": self.metadata,
        }


class DecisionEngine:
    """Intelligent decision making engine for HyperAuto.

    Features:
    - Context-aware analysis
    - Multiple option generation
    - Risk assessment and mitigation
    - Confidence-based selection
    - Decision recording and learning
    """

    def __init__(
        self,
        config: HyperAutoConfig | None = None,
    ) -> None:
        self.config = config
        self._decision_history: list[DecisionRecord] = []
        self._learned_patterns: dict[str, list[str]] = {}
        self._risk_thresholds = {
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.7,
            RiskLevel.CRITICAL: 0.9,
        }

    def analyze_context(self, state: HyperAutoState, task: SubTask) -> Context:
        """Analyze the current execution context."""
        context = Context(
            state=state,
            task=task,
            available_tools=self._identify_available_tools(task),
            available_skills=self._identify_available_skills(task),
            project_info=self._gather_project_info(task),
            constraints=self._identify_constraints(state, task),
            history=self._get_relevant_history(task),
        )

        context.metadata["analysis_timestamp"] = time.time()
        context.metadata["task_type"] = self._classify_task_type(task)

        return context

    def generate_options(self, context: Context) -> list[DecisionOption]:
        """Generate possible decision options based on context."""
        options: list[DecisionOption] = []

        task_type = context.metadata.get("task_type", "generic")

        if task_type == "skill_creation":
            options.extend(self._generate_skill_creation_options(context))
        elif task_type == "project_init":
            options.extend(self._generate_project_init_options(context))
        elif task_type == "code_search":
            options.extend(self._generate_code_search_options(context))
        elif task_type == "error_handling":
            options.extend(self._generate_error_handling_options(context))
        elif task_type == "execution_strategy":
            options.extend(self._generate_execution_strategy_options(context))
        else:
            options.extend(self._generate_generic_options(context))

        for option in options:
            option.confidence = self.calculate_confidence(option, context)

        return options

    def assess_risks(self, options: list[DecisionOption]) -> list[RiskAssessment]:
        """Assess risks for each decision option."""
        assessments: list[RiskAssessment] = []

        for option in options:
            assessment = self._assess_single_option(option)
            assessments.append(assessment)

        return assessments

    def calculate_confidence(self, option: DecisionOption, context: Context) -> float:
        """Calculate confidence score for a decision option."""
        base_confidence = 0.5

        historical_confidence = self._get_historical_confidence(option.action)
        if historical_confidence > 0:
            base_confidence = historical_confidence

        context_match_score = self._calculate_context_match(option, context)
        resource_availability_score = self._check_resource_availability(option, context)
        constraint_compliance_score = self._check_constraint_compliance(option, context)

        confidence = (
            base_confidence * 0.3
            + context_match_score * 0.3
            + resource_availability_score * 0.2
            + constraint_compliance_score * 0.2
        )

        if option.risk_level == RiskLevel.CRITICAL:
            confidence *= 0.5
        elif option.risk_level == RiskLevel.HIGH:
            confidence *= 0.7
        elif option.risk_level == RiskLevel.MEDIUM:
            confidence *= 0.85

        return min(max(confidence, 0.0), 1.0)

    def select_best(self, options: list[DecisionOption]) -> Decision:
        """Select the best decision from available options."""
        if not options:
            return Decision(
                type=DecisionType.ABORT,
                confidence=0.0,
                reasoning="No options available",
                action="abort",
            )

        scored_options = []
        for option in options:
            score = self._calculate_selection_score(option)
            scored_options.append((option, score))

        scored_options.sort(key=lambda x: x[1], reverse=True)

        best_option = scored_options[0][0]

        decision_type = self._map_category_to_decision_type(best_option.category)

        decision = Decision(
            type=decision_type,
            confidence=best_option.confidence,
            reasoning=best_option.reasoning,
            action=best_option.action,
            parameters=best_option.parameters,
        )

        return decision

    def record_decision(self, decision: Decision, record: DecisionRecord) -> None:
        """Record a decision for future learning."""
        record.decision = decision
        record.outcome = "pending"
        record.success = False

        self._decision_history.append(record)

        self._update_learned_patterns(record)

    def make_decision(self, state: HyperAutoState, task: SubTask) -> Decision:
        """Complete decision making workflow."""
        context = self.analyze_context(state, task)

        options = self.generate_options(context)

        risk_assessments = self.assess_risks(options)

        decision = self.select_best(options)

        selected_option = next(
            (o for o in options if o.action == decision.action),
            options[0] if options else None,
        )

        record = DecisionRecord(
            context=context,
            options=options,
            risk_assessments=risk_assessments,
            selected_option=selected_option,
        )

        self.record_decision(decision, record)

        return decision

    def update_decision_outcome(
        self,
        decision_id: str,
        success: bool,
        outcome: str,
        lessons: list[str] | None = None,
    ) -> None:
        """Update the outcome of a recorded decision."""
        for record in self._decision_history:
            if record.decision and record.decision.id == decision_id:
                record.success = success
                record.outcome = outcome
                if lessons:
                    record.lessons_learned.extend(lessons)

                self._update_learned_patterns(record)
                break

    def get_decision_history(self) -> list[DecisionRecord]:
        """Get all recorded decisions."""
        return self._decision_history.copy()

    def get_learned_patterns(self) -> dict[str, list[str]]:
        """Get learned decision patterns."""
        return self._learned_patterns.copy()

    def _identify_available_tools(self, task: SubTask) -> list[str]:
        """Identify tools available for the task."""
        tools = ["bash", "read", "write", "edit", "grep", "glob"]

        task_metadata = task.metadata
        if task_metadata.get("requires_web"):
            tools.append("webfetch")
        if task_metadata.get("requires_browser"):
            tools.append("browse")

        return tools

    def _identify_available_skills(self, task: SubTask) -> list[str]:
        """Identify skills available for the task."""
        skills = ["debug", "qa", "ship", "review"]

        task_name = task.name.lower()
        if "test" in task_name:
            skills.append("qa")
        if "deploy" in task_name or "release" in task_name:
            skills.append("ship")
        if "bug" in task_name or "fix" in task_name:
            skills.append("debug")

        return skills

    def _gather_project_info(self, task: SubTask) -> dict[str, Any]:
        """Gather project information."""
        return {
            "language": task.metadata.get("language", "python"),
            "framework": task.metadata.get("framework", "unknown"),
            "has_tests": task.metadata.get("has_tests", False),
            "has_docs": task.metadata.get("has_docs", False),
        }

    def _identify_constraints(self, state: HyperAutoState, task: SubTask) -> dict[str, Any]:
        """Identify execution constraints."""
        constraints = {
            "time_limit": 300.0,
            "requires_confirmation": state != HyperAutoState.EXECUTING,
            "allow_parallel": task.priority < 5,
            "allow_rollback": True,
        }

        if self.config:
            constraints["time_limit"] = self.config.timeout_per_task
            constraints["requires_confirmation"] = (
                self.config.mode.value == "semi_auto" and state != HyperAutoState.EXECUTING
            )

        return constraints

    def _get_relevant_history(self, task: SubTask) -> list[dict[str, Any]]:
        """Get relevant decision history."""
        relevant = []

        for record in self._decision_history[-10:]:
            if record.context and record.context.task and record.context.task.name == task.name:
                relevant.append(record.to_dict())

        return relevant

    def _classify_task_type(self, task: SubTask) -> str:
        """Classify the type of task."""
        task_type = task.metadata.get("type", "generic")

        type_mapping = {
            "skill_creation": DecisionCategory.SKILL_CREATION.value,
            "project_init": DecisionCategory.PROJECT_INIT.value,
            "code_search": DecisionCategory.EXECUTION_STRATEGY.value,
            "dependency_install": DecisionCategory.EXECUTION_STRATEGY.value,
            "test_execution": DecisionCategory.EXECUTION_STRATEGY.value,
            "code_generation": DecisionCategory.EXECUTION_STRATEGY.value,
            "code_edit": DecisionCategory.EXECUTION_STRATEGY.value,
            "git_operation": DecisionCategory.EXECUTION_STRATEGY.value,
            "generic": DecisionCategory.EXECUTION_STRATEGY.value,
        }

        return type_mapping.get(task_type, DecisionCategory.EXECUTION_STRATEGY.value)

    def _generate_skill_creation_options(self, context: Context) -> list[DecisionOption]:
        """Generate options for skill creation."""
        return [
            DecisionOption(
                action="create_new_skill",
                description="Create a new skill from scratch",
                expected_outcome="New skill available for use",
                risk_level=RiskLevel.LOW,
                reasoning="Creating new skill provides reusable capability",
                category=DecisionCategory.SKILL_CREATION,
                rollback_plan="Delete created skill file",
                alternatives=["use_existing_skill", "modify_existing_skill"],
            ),
            DecisionOption(
                action="use_existing_skill",
                description="Use an existing skill if available",
                expected_outcome="Task completed with existing skill",
                risk_level=RiskLevel.LOW,
                reasoning="Using existing skill is faster and safer",
                category=DecisionCategory.SKILL_CREATION,
                alternatives=["create_new_skill"],
            ),
            DecisionOption(
                action="modify_existing_skill",
                description="Modify an existing skill for this task",
                expected_outcome="Adapted skill available",
                risk_level=RiskLevel.MEDIUM,
                reasoning="Modifying existing skill balances reuse and customization",
                category=DecisionCategory.SKILL_CREATION,
                rollback_plan="Restore original skill file",
                alternatives=["create_new_skill", "use_existing_skill"],
            ),
        ]

    def _generate_project_init_options(self, context: Context) -> list[DecisionOption]:
        """Generate options for project initialization."""
        return [
            DecisionOption(
                action="full_init",
                description="Initialize complete project structure",
                expected_outcome="Full project structure created",
                risk_level=RiskLevel.MEDIUM,
                reasoning="Full initialization provides complete setup",
                category=DecisionCategory.PROJECT_INIT,
                rollback_plan="Delete created files and directories",
                alternatives=["minimal_init", "skip_init"],
            ),
            DecisionOption(
                action="minimal_init",
                description="Initialize minimal essential structure",
                expected_outcome="Basic project structure created",
                risk_level=RiskLevel.LOW,
                reasoning="Minimal initialization reduces risk",
                category=DecisionCategory.PROJECT_INIT,
                rollback_plan="Delete created files",
                alternatives=["full_init", "skip_init"],
            ),
            DecisionOption(
                action="skip_init",
                description="Skip initialization if structure exists",
                expected_outcome="No changes to project structure",
                risk_level=RiskLevel.LOW,
                reasoning="Skipping is safe if structure exists",
                category=DecisionCategory.PROJECT_INIT,
                alternatives=["full_init", "minimal_init"],
            ),
        ]

    def _generate_code_search_options(self, context: Context) -> list[DecisionOption]:
        """Generate options for code search."""
        return [
            DecisionOption(
                action="broad_search",
                description="Search broadly across the codebase",
                expected_outcome="Comprehensive results",
                risk_level=RiskLevel.LOW,
                reasoning="Broad search ensures no missed references",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["targeted_search", "skip_search"],
            ),
            DecisionOption(
                action="targeted_search",
                description="Search in specific files or patterns",
                expected_outcome="Focused relevant results",
                risk_level=RiskLevel.LOW,
                reasoning="Targeted search is faster and more precise",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["broad_search"],
            ),
        ]

    def _generate_error_handling_options(self, context: Context) -> list[DecisionOption]:
        """Generate options for error handling."""
        return [
            DecisionOption(
                action="retry_with_adjustment",
                description="Retry with adjusted parameters",
                expected_outcome="Task completes successfully",
                risk_level=RiskLevel.MEDIUM,
                reasoning="Retry with adjustment addresses transient issues",
                category=DecisionCategory.ERROR_HANDLING,
                rollback_plan="Revert to original parameters",
                alternatives=["rollback", "abort", "escalate"],
            ),
            DecisionOption(
                action="rollback",
                description="Rollback changes and restart",
                expected_outcome="Clean state restored",
                risk_level=RiskLevel.HIGH,
                reasoning="Rollback ensures clean state but loses progress",
                category=DecisionCategory.ERROR_HANDLING,
                alternatives=["retry_with_adjustment", "abort"],
            ),
            DecisionOption(
                action="abort",
                description="Abort task and report error",
                expected_outcome="Task terminated safely",
                risk_level=RiskLevel.LOW,
                reasoning="Aborting prevents further damage",
                category=DecisionCategory.ERROR_HANDLING,
                alternatives=["retry_with_adjustment", "rollback"],
            ),
            DecisionOption(
                action="escalate",
                description="Escalate for human intervention",
                expected_outcome="Human decision made",
                risk_level=RiskLevel.LOW,
                reasoning="Escalation is safe for critical decisions",
                category=DecisionCategory.ERROR_HANDLING,
                alternatives=["retry_with_adjustment", "abort"],
            ),
        ]

    def _generate_execution_strategy_options(self, context: Context) -> list[DecisionOption]:
        """Generate options for execution strategy."""
        return [
            DecisionOption(
                action="parallel_execution",
                description="Execute tasks in parallel",
                expected_outcome="Faster completion",
                risk_level=RiskLevel.MEDIUM,
                reasoning="Parallel execution improves efficiency",
                category=DecisionCategory.EXECUTION_STRATEGY,
                rollback_plan="Switch to sequential execution",
                alternatives=["sequential_execution", "batch_execution"],
            ),
            DecisionOption(
                action="sequential_execution",
                description="Execute tasks sequentially",
                expected_outcome="Stable completion",
                risk_level=RiskLevel.LOW,
                reasoning="Sequential execution is safer",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["parallel_execution", "batch_execution"],
            ),
            DecisionOption(
                action="batch_execution",
                description="Execute in batches",
                expected_outcome="Balanced completion",
                risk_level=RiskLevel.LOW,
                reasoning="Batch execution balances speed and safety",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["parallel_execution", "sequential_execution"],
            ),
        ]

    def _generate_generic_options(self, context: Context) -> list[DecisionOption]:
        """Generate generic decision options."""
        return [
            DecisionOption(
                action="proceed_standard",
                description="Proceed with standard approach",
                expected_outcome="Task completed normally",
                risk_level=RiskLevel.LOW,
                reasoning="Standard approach is reliable",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["proceed_careful", "request_guidance"],
            ),
            DecisionOption(
                action="proceed_careful",
                description="Proceed with extra caution",
                expected_outcome="Task completed safely",
                risk_level=RiskLevel.LOW,
                reasoning="Careful approach minimizes risk",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["proceed_standard", "request_guidance"],
            ),
            DecisionOption(
                action="request_guidance",
                description="Request human guidance",
                expected_outcome="Human direction provided",
                risk_level=RiskLevel.LOW,
                reasoning="Human guidance ensures correctness",
                category=DecisionCategory.EXECUTION_STRATEGY,
                alternatives=["proceed_standard", "proceed_careful"],
            ),
        ]

    def _assess_single_option(self, option: DecisionOption) -> RiskAssessment:
        """Assess risk for a single option."""
        risk_factors: list[str] = []
        mitigation_strategies: list[str] = []

        if option.risk_level == RiskLevel.CRITICAL:
            risk_factors.extend(["high_failure_probability", "significant_impact"])
            mitigation_strategies.extend(["require_confirmation", "create_backup"])
        elif option.risk_level == RiskLevel.HIGH:
            risk_factors.extend(["moderate_failure_probability", "moderate_impact"])
            mitigation_strategies.extend(["add_validation", "enable rollback"])
        elif option.risk_level == RiskLevel.MEDIUM:
            risk_factors.append("low_failure_probability")
            mitigation_strategies.append("monitor_progress")
        else:
            risk_factors.append("minimal_risk")
            mitigation_strategies.append("standard_logging")

        if not option.rollback_plan:
            risk_factors.append("no_rollback_plan")
            mitigation_strategies.append("create_checkpoint")

        impact_score = self._risk_thresholds[option.risk_level]
        probability_score = 1.0 - option.confidence
        overall_risk_score = impact_score * probability_score

        return RiskAssessment(
            option_id=option.action,
            risk_level=option.risk_level,
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            impact_score=impact_score,
            probability_score=probability_score,
            overall_risk_score=overall_risk_score,
        )

    def _calculate_selection_score(self, option: DecisionOption) -> float:
        """Calculate overall selection score for an option."""
        confidence_weight = 0.4
        risk_weight = 0.3
        outcome_weight = 0.2
        rollback_weight = 0.1

        risk_score = 1.0 - self._risk_thresholds[option.risk_level]

        outcome_score = 0.8 if option.expected_outcome else 0.5

        rollback_score = 1.0 if option.rollback_plan else 0.5

        total_score = (
            option.confidence * confidence_weight
            + risk_score * risk_weight
            + outcome_score * outcome_weight
            + rollback_score * rollback_weight
        )

        historical_bonus = self._get_historical_success_rate(option.action)
        total_score += historical_bonus * 0.1

        return total_score

    def _calculate_context_match(self, option: DecisionOption, context: Context) -> float:
        """Calculate how well option matches context."""
        score = 0.5

        if option.category.value == context.metadata.get("task_type"):
            score += 0.3

        required_tools = option.parameters.get("required_tools", [])
        if all(tool in context.available_tools for tool in required_tools):
            score += 0.2

        return min(score, 1.0)

    def _check_resource_availability(self, option: DecisionOption, context: Context) -> float:
        """Check if resources are available for option."""
        score = 1.0

        if option.parameters.get("requires_web") and "webfetch" not in context.available_tools:
            score -= 0.3

        if option.parameters.get("requires_browser") and "browse" not in context.available_tools:
            score -= 0.3

        if option.parameters.get("requires_skill"):
            required_skill = option.parameters.get("requires_skill")
            if required_skill not in context.available_skills:
                score -= 0.2

        return max(score, 0.0)

    def _check_constraint_compliance(self, option: DecisionOption, context: Context) -> float:
        """Check if option complies with constraints."""
        score = 1.0

        constraints = context.constraints

        if constraints.get("requires_confirmation") and option.risk_level in (
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ):
            score -= 0.3

        if option.estimated_duration > constraints.get("time_limit", 300.0):
            score -= 0.2

        if not constraints.get("allow_parallel") and option.action == "parallel_execution":
            score -= 0.4

        if not constraints.get("allow_rollback") and option.rollback_plan:
            score -= 0.1

        return max(score, 0.0)

    def _map_category_to_decision_type(self, category: DecisionCategory) -> DecisionType:
        """Map decision category to decision type."""
        mapping = {
            DecisionCategory.SKILL_CREATION: DecisionType.SKILL_CREATION,
            DecisionCategory.PROJECT_INIT: DecisionType.PROJECT_INIT,
            DecisionCategory.ERROR_HANDLING: DecisionType.ABORT,
            DecisionCategory.EXECUTION_STRATEGY: DecisionType.TEST_EXECUTION,
            DecisionCategory.TOOL_SELECTION: DecisionType.CODE_SEARCH,
            DecisionCategory.RESOURCE_ALLOCATION: DecisionType.DEPENDENCY_INSTALL,
        }

        return mapping.get(category, DecisionType.SKILL_CREATION)

    def _get_historical_confidence(self, action: str) -> float:
        """Get historical confidence for an action."""
        matching_records = [
            r
            for r in self._decision_history
            if r.selected_option and r.selected_option.action == action
        ]

        if not matching_records:
            return 0.0

        total_confidence = sum(
            r.selected_option.confidence for r in matching_records if r.selected_option
        )
        return total_confidence / len(matching_records)

    def _get_historical_success_rate(self, action: str) -> float:
        """Get historical success rate for an action."""
        matching_records = [
            r
            for r in self._decision_history
            if r.selected_option and r.selected_option.action == action
        ]

        if not matching_records:
            return 0.0

        successful = sum(1 for r in matching_records if r.success)
        return successful / len(matching_records)

    def _update_learned_patterns(self, record: DecisionRecord) -> None:
        """Update learned patterns from a decision record."""
        if not record.success or not record.selected_option:
            return

        category = record.selected_option.category.value
        action = record.selected_option.action

        if category not in self._learned_patterns:
            self._learned_patterns[category] = []

        pattern = f"{action}_successful"
        if pattern not in self._learned_patterns[category]:
            self._learned_patterns[category].append(pattern)

        for lesson in record.lessons_learned:
            if lesson not in self._learned_patterns.get("lessons", []):
                if "lessons" not in self._learned_patterns:
                    self._learned_patterns["lessons"] = []
                self._learned_patterns["lessons"].append(lesson)
