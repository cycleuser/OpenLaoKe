"""Core ExploreMode class for autonomous code exploration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openlaoke.core.explorer.architecture import ArchitectureExplorer
from openlaoke.core.explorer.code_understanding import CodeUnderstandingEngine
from openlaoke.core.explorer.discovery import DiscoverySystem
from openlaoke.core.explorer.exploration_strategy import ExplorationStrategy
from openlaoke.core.explorer.hypothesis import HypothesisGenerator
from openlaoke.core.explorer.reasoning import ReasoningEngine

if TYPE_CHECKING:
    pass


@dataclass
class ArchitectureAnalysis:
    """Result of architecture exploration."""

    project_path: Path
    structure: dict[str, Any]
    design_patterns: list[str]
    dependencies: dict[str, list[str]]
    code_smells: list[dict[str, Any]]
    improvement_suggestions: list[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": str(self.project_path),
            "structure": self.structure,
            "design_patterns": self.design_patterns,
            "dependencies": self.dependencies,
            "code_smells": self.code_smells,
            "improvement_suggestions": self.improvement_suggestions,
            "timestamp": self.timestamp,
        }


@dataclass
class CodeUnderstanding:
    """Result of code understanding analysis."""

    file_path: Path
    semantic_summary: str
    intent: str
    behavior_model: dict[str, Any]
    complexity_score: float
    quality_metrics: dict[str, float]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "semantic_summary": self.semantic_summary,
            "intent": self.intent,
            "behavior_model": self.behavior_model,
            "complexity_score": self.complexity_score,
            "quality_metrics": self.quality_metrics,
            "timestamp": self.timestamp,
        }


@dataclass
class Hypothesis:
    """Represents a hypothesis about the codebase."""

    id: str
    description: str
    confidence: float
    evidence: list[str]
    validation_status: str = "pending"
    validation_result: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "validation_status": self.validation_status,
            "validation_result": self.validation_result,
            "timestamp": self.timestamp,
        }


@dataclass
class ValidationResult:
    """Result of hypothesis validation."""

    hypothesis_id: str
    is_valid: bool
    confidence: float
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    recommendations: list[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


@dataclass
class Pattern:
    """Represents a discovered pattern in the codebase."""

    id: str
    name: str
    pattern_type: str
    occurrences: list[dict[str, Any]]
    confidence: float
    description: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pattern_type": self.pattern_type,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "description": self.description,
            "timestamp": self.timestamp,
        }


@dataclass
class KnowledgeGraph:
    """Knowledge graph built from explorations."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metadata: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class ExplorationPlan:
    """Plan for an exploration session."""

    goal: str
    steps: list[dict[str, Any]]
    estimated_duration: float
    priority: str = "medium"
    required_tools: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "estimated_duration": self.estimated_duration,
            "priority": self.priority,
            "required_tools": self.required_tools,
            "timestamp": self.timestamp,
        }


@dataclass
class ExplorationResult:
    """Result of executing an exploration plan."""

    plan_id: str
    success: bool
    findings: list[dict[str, Any]]
    insights: list[str]
    metrics: dict[str, float]
    error: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "success": self.success,
            "findings": self.findings,
            "insights": self.insights,
            "metrics": self.metrics,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ExplorationSession:
    """Represents a complete exploration session."""

    session_id: str
    goal: str
    analyses: list[dict[str, Any]]
    hypotheses: list[Hypothesis]
    patterns: list[Pattern]
    knowledge_graph: KnowledgeGraph | None
    duration: float
    success: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "analyses": self.analyses,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "patterns": [p.to_dict() for p in self.patterns],
            "knowledge_graph": self.knowledge_graph.to_dict() if self.knowledge_graph else None,
            "duration": self.duration,
            "success": self.success,
            "timestamp": self.timestamp,
        }


class ExploreMode:
    """Explore Mode - Autonomous exploration and understanding of codebases.

    This class orchestrates various exploration components to provide deep
    understanding of code architecture, patterns, and behaviors.
    """

    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()
        self.architecture_explorer = ArchitectureExplorer()
        self.code_understanding_engine = CodeUnderstandingEngine()
        self.reasoning_engine = ReasoningEngine()
        self.hypothesis_generator = HypothesisGenerator()
        self.discovery_system = DiscoverySystem()
        self.exploration_strategy = ExplorationStrategy()
        self._exploration_history: list[dict[str, Any]] = []
        self._knowledge_base: dict[str, Any] = {}

    async def explore_architecture(self, project_path: Path) -> ArchitectureAnalysis:
        """Explore and analyze project architecture.

        Args:
            project_path: Path to the project root

        Returns:
            ArchitectureAnalysis containing structure, patterns, and insights
        """
        analysis = await self.architecture_explorer.analyze(project_path)
        self._exploration_history.append(
            {
                "type": "architecture",
                "path": str(project_path),
                "timestamp": time.time(),
                "summary": analysis.to_dict(),
            }
        )
        return analysis

    async def understand_code(self, file_path: Path) -> CodeUnderstanding:
        """Deep understanding of a specific code file.

        Args:
            file_path: Path to the file to understand

        Returns:
            CodeUnderstanding with semantic analysis and intent
        """
        understanding = await self.code_understanding_engine.analyze(file_path)
        self._exploration_history.append(
            {
                "type": "code_understanding",
                "path": str(file_path),
                "timestamp": time.time(),
                "summary": understanding.to_dict(),
            }
        )
        return understanding

    async def generate_hypotheses(self, observations: list[dict[str, Any]]) -> list[Hypothesis]:
        """Generate hypotheses based on observations.

        Args:
            observations: List of observations from exploration

        Returns:
            List of generated hypotheses
        """
        hypotheses = await self.hypothesis_generator.generate(observations)
        for hyp in hypotheses:
            self._exploration_history.append(
                {
                    "type": "hypothesis",
                    "hypothesis_id": hyp.id,
                    "description": hyp.description,
                    "timestamp": hyp.timestamp,
                }
            )
        return hypotheses

    async def validate_hypothesis(self, hypothesis: Hypothesis) -> ValidationResult:
        """Validate a hypothesis through experimentation.

        Args:
            hypothesis: The hypothesis to validate

        Returns:
            ValidationResult with evidence and confidence
        """
        result = await self.hypothesis_generator.validate(hypothesis)
        hypothesis.validation_status = "validated" if result.is_valid else "refuted"
        hypothesis.validation_result = result.to_dict()
        return result

    async def discover_patterns(self, codebase: Path) -> list[Pattern]:
        """Discover patterns in the codebase.

        Args:
            codebase: Path to the codebase to analyze

        Returns:
            List of discovered patterns
        """
        patterns = await self.discovery_system.discover_patterns(codebase)
        for pattern in patterns:
            self._exploration_history.append(
                {
                    "type": "pattern",
                    "pattern_id": pattern.id,
                    "name": pattern.name,
                    "timestamp": pattern.timestamp,
                }
            )
        return patterns

    async def build_knowledge_graph(self, explorations: list[dict[str, Any]]) -> KnowledgeGraph:
        """Build a knowledge graph from exploration results.

        Args:
            explorations: List of exploration results

        Returns:
            KnowledgeGraph representing the discovered knowledge
        """
        graph = await self.discovery_system.build_knowledge_graph(explorations)
        self._knowledge_base["graph"] = graph.to_dict()
        return graph

    async def plan_exploration(self, goal: str) -> ExplorationPlan:
        """Create an exploration plan based on a goal.

        Args:
            goal: The exploration goal

        Returns:
            ExplorationPlan with steps and estimated duration
        """
        plan = await self.exploration_strategy.create_plan(goal, self.project_path)
        self._exploration_history.append(
            {
                "type": "plan",
                "goal": goal,
                "plan_id": plan.goal,
                "timestamp": plan.timestamp,
            }
        )
        return plan

    async def execute_exploration(self, plan: ExplorationPlan) -> ExplorationResult:
        """Execute an exploration plan.

        Args:
            plan: The exploration plan to execute

        Returns:
            ExplorationResult with findings and insights
        """
        result = await self.exploration_strategy.execute(plan, self)
        self._exploration_history.append(
            {
                "type": "execution",
                "plan_id": result.plan_id,
                "success": result.success,
                "timestamp": result.timestamp,
            }
        )
        return result

    async def self_directed_exploration(self) -> ExplorationSession:
        """Perform autonomous, self-directed exploration.

        The system will determine its own goals and exploration strategy
        based on the codebase structure and its current knowledge.

        Returns:
            ExplorationSession with complete exploration results
        """
        session_id = f"explore_{int(time.time())}"
        start_time = time.time()

        architecture = await self.explore_architecture(self.project_path)
        patterns = await self.discover_patterns(self.project_path)

        observations: list[dict[str, Any]] = [
            {"type": "architecture", "data": architecture.to_dict()},
            {"type": "patterns", "data": [p.to_dict() for p in patterns]},
        ]

        hypotheses = await self.generate_hypotheses(observations)

        validated_hypotheses: list[Hypothesis] = []
        for hyp in hypotheses[:3]:
            try:
                await self.validate_hypothesis(hyp)
                validated_hypotheses.append(hyp)
            except Exception:
                pass

        all_explorations: list[dict[str, Any]] = [
            {"type": "architecture", "data": architecture.to_dict()},
            {"type": "patterns", "data": [p.to_dict() for p in patterns]},
            {
                "type": "hypotheses",
                "data": [h.to_dict() for h in validated_hypotheses],
            },
        ]
        knowledge_graph = await self.build_knowledge_graph(all_explorations)

        duration = time.time() - start_time
        success = len(validated_hypotheses) > 0

        session = ExplorationSession(
            session_id=session_id,
            goal="Self-directed exploration of codebase",
            analyses=[architecture.to_dict()],
            hypotheses=validated_hypotheses,
            patterns=patterns,
            knowledge_graph=knowledge_graph,
            duration=duration,
            success=success,
        )

        self._exploration_history.append(
            {
                "type": "session",
                "session_id": session_id,
                "duration": duration,
                "success": success,
                "timestamp": session.timestamp,
            }
        )

        return session

    def get_exploration_history(self) -> list[dict[str, Any]]:
        """Get the complete exploration history."""
        return list(self._exploration_history)

    def get_knowledge_base(self) -> dict[str, Any]:
        """Get the accumulated knowledge base."""
        return dict(self._knowledge_base)

    async def explore_specific_goal(self, goal: str, depth: str = "medium") -> ExplorationResult:
        """Explore with a specific goal in mind.

        Args:
            goal: The specific exploration goal
            depth: Exploration depth (shallow, medium, deep)

        Returns:
            ExplorationResult with goal-specific findings
        """
        plan = await self.plan_exploration(goal)
        plan.priority = depth
        return await self.execute_exploration(plan)

    async def quick_analysis(self, path: Path) -> dict[str, Any]:
        """Perform a quick analysis of a file or directory.

        Args:
            path: Path to analyze

        Returns:
            Quick analysis results
        """
        if path.is_file():
            understanding = await self.understand_code(path)
            return {
                "type": "file",
                "path": str(path),
                "summary": understanding.semantic_summary,
                "intent": understanding.intent,
                "complexity": understanding.complexity_score,
            }
        elif path.is_dir():
            arch = await self.explore_architecture(path)
            return {
                "type": "directory",
                "path": str(path),
                "patterns": arch.design_patterns[:5],
                "structure": arch.structure,
                "suggestions": arch.improvement_suggestions[:3],
            }
        else:
            return {
                "type": "unknown",
                "path": str(path),
                "error": "Path does not exist",
            }
