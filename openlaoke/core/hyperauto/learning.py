"""Automatic learning system for experience collection and knowledge extraction."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from openlaoke.core.hyperauto.workflow import WorkflowResult


class ExperienceType(StrEnum):
    """Types of experiences collected."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    LEARNED = "learned"


class KnowledgeCategory(StrEnum):
    """Categories of extracted knowledge."""

    TASK_PATTERN = "task_pattern"
    ERROR_RESOLUTION = "error_resolution"
    OPTIMIZATION = "optimization"
    BEST_PRACTICE = "best_practice"
    TOOL_USAGE = "tool_usage"
    WORKFLOW_EFFICIENCY = "workflow_efficiency"


class PatternType(StrEnum):
    """Types of recognized patterns."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    ITERATIVE = "iterative"
    ADAPTIVE = "adaptive"


class StrategyType(StrEnum):
    """Types of execution strategies."""

    STANDARD = "standard"
    OPTIMIZED = "optimized"
    AGGRESSIVE = "aggressive"
    CAUTIOUS = "cautious"
    ADAPTIVE = "adaptive"


@dataclass
class Experience:
    """Collected experience from workflow execution."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    workflow_id: str = ""
    task: str = ""
    type: ExperienceType = ExperienceType.SUCCESS
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0
    steps: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    outcome: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "task": self.task,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "steps": self.steps,
            "tools_used": self.tools_used,
            "decisions": self.decisions,
            "outcome": self.outcome,
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class Knowledge:
    """Extracted knowledge from experiences."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    category: KnowledgeCategory = KnowledgeCategory.TASK_PATTERN
    title: str = ""
    description: str = ""
    source_experiences: list[str] = field(default_factory=list)
    confidence: float = 0.0
    applicability: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    usage_count: int = 0
    success_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "source_experiences": self.source_experiences,
            "confidence": self.confidence,
            "applicability": self.applicability,
            "conditions": self.conditions,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "metadata": self.metadata,
        }


@dataclass
class Pattern:
    """Recognized execution pattern."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    type: PatternType = PatternType.SEQUENTIAL
    name: str = ""
    description: str = ""
    sequence: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    success_rate: float = 0.0
    avg_duration: float = 0.0
    sample_count: int = 0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "sequence": self.sequence,
            "conditions": self.conditions,
            "success_rate": self.success_rate,
            "avg_duration": self.avg_duration,
            "sample_count": self.sample_count,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class Strategy:
    """Execution strategy derived from patterns."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    type: StrategyType = StrategyType.STANDARD
    name: str = ""
    description: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    priority_order: list[str] = field(default_factory=list)
    estimated_duration: float = 0.0
    confidence: float = 0.0
    based_on_patterns: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    alternatives: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "priority_order": self.priority_order,
            "estimated_duration": self.estimated_duration,
            "confidence": self.confidence,
            "based_on_patterns": self.based_on_patterns,
            "conditions": self.conditions,
            "alternatives": self.alternatives,
            "metadata": self.metadata,
        }


@dataclass
class EnhancedStrategy:
    """Enhanced strategy with applied learning."""

    base_strategy: Strategy
    enhancements: list[str] = field(default_factory=list)
    applied_knowledge: list[str] = field(default_factory=list)
    confidence_boost: float = 0.0
    expected_improvement: float = 0.0
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_strategy": self.base_strategy.to_dict(),
            "enhancements": self.enhancements,
            "applied_knowledge": self.applied_knowledge,
            "confidence_boost": self.confidence_boost,
            "expected_improvement": self.expected_improvement,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


@dataclass
class LearningSession:
    """A complete learning session."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    experiences_collected: int = 0
    knowledge_extracted: int = 0
    patterns_recognized: int = 0
    strategies_optimized: int = 0
    knowledge_persisted: bool = False
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "experiences_collected": self.experiences_collected,
            "knowledge_extracted": self.knowledge_extracted,
            "patterns_recognized": self.patterns_recognized,
            "strategies_optimized": self.strategies_optimized,
            "knowledge_persisted": self.knowledge_persisted,
            "summary": self.summary,
            "metadata": self.metadata,
        }


class LearningSystem:
    """Automatic learning system for experience collection and knowledge extraction.

    Features:
    - Experience collection from workflow execution
    - Knowledge extraction from success/failure cases
    - Pattern recognition for successful execution
    - Strategy optimization for future execution
    - Knowledge persistence for long-term learning
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or Path.home() / ".openlaoke" / "learning"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._experiences: list[Experience] = []
        self._knowledge: dict[str, Knowledge] = {}
        self._patterns: dict[str, Pattern] = {}
        self._strategies: dict[str, Strategy] = {}
        self._session: LearningSession | None = None

        self._load_knowledge()

    def collect_experience(self, workflow_result: WorkflowResult) -> Experience:
        """Collect experience data from workflow execution."""
        exp_type = ExperienceType.SUCCESS if workflow_result.success else ExperienceType.FAILURE

        if not workflow_result.success and workflow_result.error:
            exp_type = ExperienceType.FAILURE
        elif workflow_result.success and len(workflow_result.execution_results) > 0:
            partial_failures = [r for r in workflow_result.execution_results if not r.success]
            if partial_failures:
                exp_type = ExperienceType.PARTIAL

        steps = [step.task_id for step in workflow_result.execution_plan.steps]
        tools_used = self._extract_tools_used(workflow_result)
        decisions = self._extract_decisions(workflow_result)
        outcome = self._determine_outcome(workflow_result)
        context = workflow_result.metadata

        experience = Experience(
            workflow_id=workflow_result.workflow_id,
            task=workflow_result.task_tree.root_task,
            type=exp_type,
            duration=workflow_result.total_duration,
            steps=steps,
            tools_used=tools_used,
            decisions=decisions,
            outcome=outcome,
            context=context,
        )

        self._experiences.append(experience)

        if self._session:
            self._session.experiences_collected += 1

        return experience

    def extract_knowledge(self, experiences: list[Experience]) -> Knowledge:
        """Extract knowledge from collected experiences."""
        successful = [e for e in experiences if e.type == ExperienceType.SUCCESS]
        failed = [e for e in experiences if e.type == ExperienceType.FAILURE]

        category = self._determine_knowledge_category(experiences)
        title = self._generate_knowledge_title(experiences)
        description = self._generate_knowledge_description(experiences)

        source_ids = [e.id for e in experiences]
        confidence = self._calculate_confidence(experiences)
        applicability = self._determine_applicability(experiences)
        conditions = self._extract_conditions(experiences)
        recommendations = self._generate_recommendations(successful, failed)

        knowledge = Knowledge(
            category=category,
            title=title,
            description=description,
            source_experiences=source_ids,
            confidence=confidence,
            applicability=applicability,
            conditions=conditions,
            recommendations=recommendations,
        )

        self._knowledge[knowledge.id] = knowledge

        if self._session:
            self._session.knowledge_extracted += 1

        return knowledge

    def recognize_patterns(self, knowledge: Knowledge) -> list[Pattern]:
        """Recognize execution patterns from knowledge."""
        patterns: list[Pattern] = []

        related_experiences = [e for e in self._experiences if e.id in knowledge.source_experiences]

        if not related_experiences:
            return patterns

        sequential_pattern = self._extract_sequential_pattern(related_experiences)
        if sequential_pattern:
            patterns.append(sequential_pattern)

        parallel_pattern = self._extract_parallel_pattern(related_experiences)
        if parallel_pattern:
            patterns.append(parallel_pattern)

        conditional_pattern = self._extract_conditional_pattern(related_experiences)
        if conditional_pattern:
            patterns.append(conditional_pattern)

        for pattern in patterns:
            self._patterns[pattern.id] = pattern

        if self._session:
            self._session.patterns_recognized += len(patterns)

        return patterns

    def optimize_strategy(self, patterns: list[Pattern]) -> Strategy:
        """Optimize execution strategy based on recognized patterns."""
        if not patterns:
            return Strategy(
                type=StrategyType.STANDARD,
                name="default_strategy",
                description="Default strategy with no pattern data",
            )

        best_pattern = max(patterns, key=lambda p: p.success_rate)

        strategy_type = self._determine_strategy_type(best_pattern)
        name = f"optimized_{best_pattern.name}"
        description = f"Strategy optimized from pattern: {best_pattern.description}"

        steps = self._generate_strategy_steps(best_pattern)
        priority_order = best_pattern.sequence.copy()
        estimated_duration = best_pattern.avg_duration
        confidence = best_pattern.success_rate
        based_on = [p.id for p in patterns]
        conditions = best_pattern.conditions.copy()
        alternatives = self._generate_alternatives(patterns)

        strategy = Strategy(
            type=strategy_type,
            name=name,
            description=description,
            steps=steps,
            priority_order=priority_order,
            estimated_duration=estimated_duration,
            confidence=confidence,
            based_on_patterns=based_on,
            conditions=conditions,
            alternatives=alternatives,
        )

        self._strategies[strategy.id] = strategy

        if self._session:
            self._session.strategies_optimized += 1

        return strategy

    def persist_knowledge(self, knowledge: Knowledge) -> bool:
        """Persist learned knowledge to storage."""
        try:
            knowledge_file = self._storage_dir / f"knowledge_{knowledge.id}.json"

            with open(knowledge_file, "w", encoding="utf-8") as f:
                json.dump(knowledge.to_dict(), f, ensure_ascii=False, indent=2)

            patterns_file = self._storage_dir / "patterns.json"
            patterns_data = {pid: p.to_dict() for pid, p in self._patterns.items()}
            with open(patterns_file, "w", encoding="utf-8") as f:
                json.dump(patterns_data, f, ensure_ascii=False, indent=2)

            strategies_file = self._storage_dir / "strategies.json"
            strategies_data = {sid: s.to_dict() for sid, s in self._strategies.items()}
            with open(strategies_file, "w", encoding="utf-8") as f:
                json.dump(strategies_data, f, ensure_ascii=False, indent=2)

            if self._session:
                self._session.knowledge_persisted = True

            return True

        except Exception:
            return False

    def load_knowledge(self) -> Knowledge:
        """Load persisted knowledge from storage."""
        self._load_knowledge()

        if self._knowledge:
            latest = max(self._knowledge.values(), key=lambda k: k.updated_at)
            return latest

        return Knowledge(
            category=KnowledgeCategory.TASK_PATTERN,
            title="empty_knowledge",
            description="No knowledge loaded from storage",
        )

    def apply_learning(self, task: str) -> EnhancedStrategy:
        """Apply learned knowledge to enhance strategy for a task."""
        base_strategy = self._find_best_strategy(task)

        if not base_strategy:
            base_strategy = Strategy(
                type=StrategyType.STANDARD,
                name="default",
                description="Default strategy when no learned knowledge available",
            )

        relevant_knowledge = self._find_relevant_knowledge(task)
        enhancements: list[str] = []
        applied_ids: list[str] = []
        confidence_boost = 0.0

        for knowledge in relevant_knowledge:
            if self._is_applicable(knowledge, task):
                enhancements.extend(knowledge.recommendations[:2])
                applied_ids.append(knowledge.id)
                confidence_boost += knowledge.confidence * 0.1
                knowledge.usage_count += 1

        expected_improvement = min(confidence_boost * 0.5, 0.3)
        reasoning = self._generate_enhancement_reasoning(relevant_knowledge, task)

        return EnhancedStrategy(
            base_strategy=base_strategy,
            enhancements=enhancements,
            applied_knowledge=applied_ids,
            confidence_boost=min(confidence_boost, 0.5),
            expected_improvement=expected_improvement,
            reasoning=reasoning,
        )

    def start_session(self) -> LearningSession:
        """Start a new learning session."""
        self._session = LearningSession()
        return self._session

    def end_session(self) -> LearningSession | None:
        """End the current learning session."""
        if self._session:
            self._session.end_time = time.time()
            self._session.summary = self._generate_session_summary()
            self._persist_session()
        return self._session

    def get_all_experiences(self) -> list[Experience]:
        """Get all collected experiences."""
        return self._experiences.copy()

    def get_all_knowledge(self) -> dict[str, Knowledge]:
        """Get all extracted knowledge."""
        return self._knowledge.copy()

    def get_all_patterns(self) -> dict[str, Pattern]:
        """Get all recognized patterns."""
        return self._patterns.copy()

    def get_all_strategies(self) -> dict[str, Strategy]:
        """Get all optimized strategies."""
        return self._strategies.copy()

    def _load_knowledge(self) -> None:
        """Load persisted knowledge from storage."""
        try:
            patterns_file = self._storage_dir / "patterns.json"
            if patterns_file.exists():
                with open(patterns_file, encoding="utf-8") as f:
                    patterns_data = json.load(f)
                for pid, pdata in patterns_data.items():
                    self._patterns[pid] = Pattern(
                        id=pid,
                        type=PatternType(pdata.get("type", PatternType.SEQUENTIAL.value)),
                        name=pdata.get("name", ""),
                        description=pdata.get("description", ""),
                        sequence=pdata.get("sequence", []),
                        conditions=pdata.get("conditions", {}),
                        success_rate=pdata.get("success_rate", 0.0),
                        avg_duration=pdata.get("avg_duration", 0.0),
                        sample_count=pdata.get("sample_count", 0),
                        tags=pdata.get("tags", []),
                        metadata=pdata.get("metadata", {}),
                    )

            strategies_file = self._storage_dir / "strategies.json"
            if strategies_file.exists():
                with open(strategies_file, encoding="utf-8") as f:
                    strategies_data = json.load(f)
                for sid, sdata in strategies_data.items():
                    self._strategies[sid] = Strategy(
                        id=sid,
                        type=StrategyType(sdata.get("type", StrategyType.STANDARD.value)),
                        name=sdata.get("name", ""),
                        description=sdata.get("description", ""),
                        steps=sdata.get("steps", []),
                        priority_order=sdata.get("priority_order", []),
                        estimated_duration=sdata.get("estimated_duration", 0.0),
                        confidence=sdata.get("confidence", 0.0),
                        based_on_patterns=sdata.get("based_on_patterns", []),
                        conditions=sdata.get("conditions", {}),
                        alternatives=sdata.get("alternatives", []),
                        metadata=sdata.get("metadata", {}),
                    )

            for kf in self._storage_dir.glob("knowledge_*.json"):
                with open(kf, encoding="utf-8") as f:
                    kdata = json.load(f)
                kid = kdata.get("id", kf.stem.replace("knowledge_", ""))
                self._knowledge[kid] = Knowledge(
                    id=kid,
                    category=KnowledgeCategory(
                        kdata.get("category", KnowledgeCategory.TASK_PATTERN.value)
                    ),
                    title=kdata.get("title", ""),
                    description=kdata.get("description", ""),
                    source_experiences=kdata.get("source_experiences", []),
                    confidence=kdata.get("confidence", 0.0),
                    applicability=kdata.get("applicability", []),
                    conditions=kdata.get("conditions", {}),
                    recommendations=kdata.get("recommendations", []),
                    created_at=kdata.get("created_at", 0.0),
                    updated_at=kdata.get("updated_at", 0.0),
                    usage_count=kdata.get("usage_count", 0),
                    success_rate=kdata.get("success_rate", 0.0),
                    metadata=kdata.get("metadata", {}),
                )

        except Exception:
            pass

    def _extract_tools_used(self, result: WorkflowResult) -> list[str]:
        """Extract tools used from workflow result."""
        tools: set[str] = set()
        for step in result.execution_plan.steps:
            metadata = step.metadata
            if "tools" in metadata:
                tools.update(metadata["tools"])
        return list(tools)

    def _extract_decisions(self, result: WorkflowResult) -> list[str]:
        """Extract decisions from workflow result."""
        decisions: list[str] = []
        context = result.metadata.get("context", {})
        if "decisions" in context:
            for d in context["decisions"]:
                decisions.append(d.get("type", "unknown"))
        return decisions

    def _determine_outcome(self, result: WorkflowResult) -> str:
        """Determine outcome description from workflow result."""
        if result.success:
            return f"Successfully completed {len(result.execution_results)} tasks"
        else:
            if result.error:
                return f"Failed: {result.error}"
            return f"Partially completed {len([r for r in result.execution_results if r.success])} tasks"

    def _determine_knowledge_category(self, experiences: list[Experience]) -> KnowledgeCategory:
        """Determine knowledge category from experiences."""
        successful = [e for e in experiences if e.type == ExperienceType.SUCCESS]
        failed = [e for e in experiences if e.type == ExperienceType.FAILURE]

        if failed and not successful:
            return KnowledgeCategory.ERROR_RESOLUTION
        elif len(successful) > len(failed):
            return KnowledgeCategory.BEST_PRACTICE
        else:
            return KnowledgeCategory.TASK_PATTERN

    def _generate_knowledge_title(self, experiences: list[Experience]) -> str:
        """Generate knowledge title from experiences."""
        if not experiences:
            return "unknown_knowledge"

        tasks = [e.task for e in experiences]
        common_task = self._find_common_task(tasks)

        exp_types = [e.type for e in experiences]
        if ExperienceType.FAILURE in exp_types:
            return f"Error handling for {common_task}"
        elif ExperienceType.SUCCESS in exp_types:
            return f"Success pattern for {common_task}"
        else:
            return f"Pattern for {common_task}"

    def _generate_knowledge_description(self, experiences: list[Experience]) -> str:
        """Generate knowledge description from experiences."""
        if not experiences:
            return "No experiences to describe"

        avg_duration = sum(e.duration for e in experiences) / len(experiences)
        success_count = len([e for e in experiences if e.type == ExperienceType.SUCCESS])

        return f"Derived from {len(experiences)} experiences. "
        f"Average duration: {avg_duration:.2f}s. "
        f"Success rate: {success_count / len(experiences):.2%}"

    def _calculate_confidence(self, experiences: list[Experience]) -> float:
        """Calculate confidence level from experiences."""
        if not experiences:
            return 0.0

        success_weight = 0.8
        sample_weight = 0.2

        success_rate = len([e for e in experiences if e.type == ExperienceType.SUCCESS]) / len(
            experiences
        )
        sample_factor = min(len(experiences) / 10, 1.0)

        return success_rate * success_weight + sample_factor * sample_weight

    def _determine_applicability(self, experiences: list[Experience]) -> list[str]:
        """Determine applicability scope from experiences."""
        tasks = [e.task for e in experiences]
        keywords: set[str] = set()

        for task in tasks:
            words = task.lower().split()
            keywords.update([w for w in words if len(w) > 3])

        return list(keywords)[:10]

    def _extract_conditions(self, experiences: list[Experience]) -> dict[str, Any]:
        """Extract conditions from experiences."""
        conditions: dict[str, Any] = {}

        durations = [e.duration for e in experiences]
        if durations:
            conditions["avg_duration"] = sum(durations) / len(durations)
            conditions["max_duration"] = max(durations)

        tools: set[str] = set()
        for e in experiences:
            tools.update(e.tools_used)
        conditions["required_tools"] = list(tools)

        return conditions

    def _generate_recommendations(
        self, successful: list[Experience], failed: list[Experience]
    ) -> list[str]:
        """Generate recommendations from successful and failed experiences."""
        recommendations: list[str] = []

        if successful:
            common_tools = self._find_common_tools(successful)
            if common_tools:
                recommendations.append(f"Use tools: {', '.join(common_tools[:3])}")

            common_steps = self._find_common_steps(successful)
            if common_steps:
                recommendations.append(f"Follow sequence: {' -> '.join(common_steps[:3])}")

        if failed:
            error_patterns = self._extract_error_patterns(failed)
            for pattern in error_patterns[:2]:
                recommendations.append(f"Avoid: {pattern}")

        return recommendations

    def _extract_sequential_pattern(self, experiences: list[Experience]) -> Pattern | None:
        """Extract sequential execution pattern."""
        sequences: list[list[str]] = []
        for e in experiences:
            if e.steps:
                sequences.append(e.steps)

        if not sequences:
            return None

        common_sequence = self._find_longest_common_sequence(sequences)
        if not common_sequence:
            return None

        success_exps = [e for e in experiences if e.type == ExperienceType.SUCCESS and e.steps]
        success_rate = len(success_exps) / len(experiences) if experiences else 0.0
        avg_duration = (
            sum(e.duration for e in experiences) / len(experiences) if experiences else 0.0
        )

        return Pattern(
            type=PatternType.SEQUENTIAL,
            name="sequential_execution",
            description=f"Sequential execution pattern with {len(common_sequence)} steps",
            sequence=common_sequence,
            success_rate=success_rate,
            avg_duration=avg_duration,
            sample_count=len(experiences),
        )

    def _extract_parallel_pattern(self, experiences: list[Experience]) -> Pattern | None:
        """Extract parallel execution pattern."""
        parallel_groups: dict[str, int] = {}

        for e in experiences:
            context = e.context
            if "parallel_groups" in context:
                for group in context["parallel_groups"]:
                    parallel_groups[group] = parallel_groups.get(group, 0) + 1

        if not parallel_groups:
            return None

        common_parallel = [g for g, c in parallel_groups.items() if c >= len(experiences) / 2]

        if not common_parallel:
            return None

        success_exps = [e for e in experiences if e.type == ExperienceType.SUCCESS]
        success_rate = len(success_exps) / len(experiences) if experiences else 0.0

        return Pattern(
            type=PatternType.PARALLEL,
            name="parallel_execution",
            description=f"Parallel execution pattern with {len(common_parallel)} groups",
            sequence=common_parallel,
            success_rate=success_rate,
            avg_duration=sum(e.duration for e in experiences) / len(experiences),
            sample_count=len(experiences),
            conditions={"parallel_groups": common_parallel},
        )

    def _extract_conditional_pattern(self, experiences: list[Experience]) -> Pattern | None:
        """Extract conditional execution pattern."""
        conditions_map: dict[str, list[str]] = {}

        for e in experiences:
            if e.decisions:
                for decision in e.decisions:
                    if decision not in conditions_map:
                        conditions_map[decision] = []
                    conditions_map[decision].append(e.id)

        if not conditions_map:
            return None

        frequent_conditions = {
            d: ids for d, ids in conditions_map.items() if len(ids) >= len(experiences) / 3
        }

        if not frequent_conditions:
            return None

        success_exps = [e for e in experiences if e.type == ExperienceType.SUCCESS]
        success_rate = len(success_exps) / len(experiences) if experiences else 0.0

        return Pattern(
            type=PatternType.CONDITIONAL,
            name="conditional_execution",
            description=f"Conditional execution based on {len(frequent_conditions)} decision types",
            sequence=list(frequent_conditions.keys()),
            success_rate=success_rate,
            avg_duration=sum(e.duration for e in experiences) / len(experiences),
            sample_count=len(experiences),
            conditions={"decision_types": list(frequent_conditions.keys())},
        )

    def _determine_strategy_type(self, pattern: Pattern) -> StrategyType:
        """Determine strategy type from pattern."""
        if pattern.success_rate >= 0.9:
            return StrategyType.AGGRESSIVE
        elif pattern.success_rate >= 0.7:
            return StrategyType.OPTIMIZED
        elif pattern.success_rate >= 0.5:
            return StrategyType.STANDARD
        else:
            return StrategyType.CAUTIOUS

    def _generate_strategy_steps(self, pattern: Pattern) -> list[dict[str, Any]]:
        """Generate strategy steps from pattern."""
        steps: list[dict[str, Any]] = []

        for i, step_id in enumerate(pattern.sequence):
            steps.append(
                {
                    "step_id": step_id,
                    "order": i,
                    "type": pattern.type.value,
                    "required": True,
                }
            )

        return steps

    def _generate_alternatives(self, patterns: list[Pattern]) -> list[str]:
        """Generate alternative strategies from patterns."""
        alternatives: list[str] = []

        sorted_patterns = sorted(patterns, key=lambda p: p.success_rate, reverse=True)

        for pattern in sorted_patterns[1:3]:
            alternatives.append(pattern.name)

        return alternatives

    def _find_best_strategy(self, task: str) -> Strategy | None:
        """Find the best matching strategy for a task."""
        task_lower = task.lower()

        best_match: Strategy | None = None
        best_score = 0.0

        for strategy in self._strategies.values():
            score = self._calculate_strategy_match(strategy, task_lower)
            if score > best_score:
                best_score = score
                best_match = strategy

        return best_match

    def _find_relevant_knowledge(self, task: str) -> list[Knowledge]:
        """Find knowledge relevant to a task."""
        task_lower = task.lower()
        relevant: list[Knowledge] = []

        for knowledge in self._knowledge.values():
            for app in knowledge.applicability:
                if app in task_lower:
                    relevant.append(knowledge)
                    break

        return sorted(relevant, key=lambda k: k.confidence, reverse=True)[:5]

    def _is_applicable(self, knowledge: Knowledge, task: str) -> bool:
        """Check if knowledge is applicable to a task."""
        task_lower = task.lower()
        return any(app in task_lower for app in knowledge.applicability)

    def _generate_enhancement_reasoning(self, knowledge: list[Knowledge], task: str) -> str:
        """Generate reasoning for enhancements."""
        if not knowledge:
            return "No specific knowledge applied"

        titles = [k.title for k in knowledge[:3]]
        return f"Applied knowledge from: {', '.join(titles)}"

    def _find_common_task(self, tasks: list[str]) -> str:
        """Find common task pattern."""
        if not tasks:
            return "unknown"

        words: dict[str, int] = {}
        for task in tasks:
            for word in task.lower().split():
                if len(word) > 3:
                    words[word] = words.get(word, 0) + 1

        if not words:
            return tasks[0]

        return max(words, key=lambda w: words.get(w, 0))

    def _find_common_tools(self, experiences: list[Experience]) -> list[str]:
        """Find commonly used tools."""
        tool_counts: dict[str, int] = {}
        for e in experiences:
            for tool in e.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1

        return [t for t, c in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)][:5]

    def _find_common_steps(self, experiences: list[Experience]) -> list[str]:
        """Find common execution steps."""
        step_counts: dict[str, int] = {}
        for e in experiences:
            for step in e.steps:
                step_counts[step] = step_counts.get(step, 0) + 1

        return [s for s, c in sorted(step_counts.items(), key=lambda x: x[1], reverse=True)][:5]

    def _find_longest_common_sequence(self, sequences: list[list[str]]) -> list[str]:
        """Find longest common sequence among sequences."""
        if not sequences:
            return []

        if len(sequences) == 1:
            return sequences[0]

        common: list[str] = []
        first = sequences[0]

        for i in range(len(first)):
            if all(len(s) > i and s[i] == first[i] for s in sequences):
                common.append(first[i])
            else:
                break

        return common

    def _extract_error_patterns(self, experiences: list[Experience]) -> list[str]:
        """Extract error patterns from failed experiences."""
        patterns: list[str] = []

        for e in experiences:
            if e.type == ExperienceType.FAILURE and e.outcome:
                patterns.append(e.outcome[:50])

        return patterns

    def _calculate_strategy_match(self, strategy: Strategy, task_lower: str) -> float:
        """Calculate how well a strategy matches a task."""
        score = strategy.confidence

        for condition_key, condition_value in strategy.conditions.items():
            if condition_key in task_lower:
                score += 0.1
            if isinstance(condition_value, list):
                for val in condition_value:
                    if val in task_lower:
                        score += 0.05

        return score

    def _generate_session_summary(self) -> str:
        """Generate summary for learning session."""
        if not self._session:
            return ""

        duration = (self._session.end_time or time.time()) - self._session.start_time

        return (
            f"Learning session completed. "
            f"Collected {self._session.experiences_collected} experiences, "
            f"extracted {self._session.knowledge_extracted} knowledge items, "
            f"recognized {self._session.patterns_recognized} patterns, "
            f"optimized {self._session.strategies_optimized} strategies. "
            f"Duration: {duration:.2f}s"
        )

    def _persist_session(self) -> None:
        """Persist session data to storage."""
        if not self._session:
            return

        try:
            session_file = self._storage_dir / f"session_{self._session.id}.json"
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(self._session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


__all__ = [
    "LearningSystem",
    "Experience",
    "Knowledge",
    "Pattern",
    "Strategy",
    "EnhancedStrategy",
    "LearningSession",
    "ExperienceType",
    "KnowledgeCategory",
    "PatternType",
    "StrategyType",
]
