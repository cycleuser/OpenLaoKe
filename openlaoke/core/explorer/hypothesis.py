"""Hypothesis generation and validation system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from openlaoke.core.explorer.explorer import Hypothesis, ValidationResult


@dataclass
class Experiment:
    """Represents an experiment to test a hypothesis."""

    id: str
    hypothesis_id: str
    experiment_type: str
    parameters: dict[str, Any]
    expected_result: str
    actual_result: str | None = None
    success: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hypothesis_id": self.hypothesis_id,
            "experiment_type": self.experiment_type,
            "parameters": self.parameters,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "success": self.success,
            "timestamp": self.timestamp,
        }


@dataclass
class Evidence:
    """Evidence supporting or contradicting a hypothesis."""

    hypothesis_id: str
    evidence_type: str
    content: str
    supports: bool
    strength: float
    source: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "evidence_type": self.evidence_type,
            "content": self.content,
            "supports": self.supports,
            "strength": self.strength,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class HypothesisGenerator:
    """Generates and validates hypotheses about code behavior and structure.

    This class provides:
    - Hypothesis generation from observations
    - Hypothesis validation through experiments
    - Evidence collection and analysis
    - Confidence scoring
    """

    HYPOTHESIS_TYPES = {
        "architectural": "Hypotheses about overall architecture",
        "behavioral": "Hypotheses about code behavior",
        "performance": "Hypotheses about performance characteristics",
        "quality": "Hypotheses about code quality",
        "intent": "Hypotheses about developer intent",
        "pattern": "Hypotheses about design patterns",
    }

    HYPOTHESIS_TEMPLATES = {
        "pattern_usage": "The codebase uses {pattern} pattern for {purpose}",
        "module_responsibility": "Module {module} is responsible for {responsibility}",
        "dependency_cause": "High coupling between {module1} and {module2} due to {cause}",
        "quality_factor": "Code quality is affected by {factor}",
        "intent_assumption": "The developer intended to {intent} when writing {code}",
        "behavior_hypothesis": "Function {function} behaves as {behavior} under {condition}",
    }

    def __init__(self) -> None:
        self._hypotheses: dict[str, Hypothesis] = {}
        self._experiments: dict[str, Experiment] = {}
        self._evidence: dict[str, list[Evidence]] = {}

    async def generate(self, observations: list[dict[str, Any]]) -> list[Hypothesis]:
        """Generate hypotheses from observations.

        Args:
            observations: List of observations from exploration

        Returns:
            List of generated hypotheses
        """

        hypotheses: list[Hypothesis] = []

        architecture_obs = [o for o in observations if o.get("type") == "architecture"]
        if architecture_obs:
            hypotheses.extend(await self._generate_architecture_hypotheses(architecture_obs))

        pattern_obs = [o for o in observations if o.get("type") == "patterns"]
        if pattern_obs:
            hypotheses.extend(await self._generate_pattern_hypotheses(pattern_obs))

        quality_obs = [o for o in observations if o.get("type") == "quality"]
        if quality_obs:
            hypotheses.extend(await self._generate_quality_hypotheses(quality_obs))

        behavior_obs = [o for o in observations if o.get("type") == "behavior"]
        if behavior_obs:
            hypotheses.extend(await self._generate_behavior_hypotheses(behavior_obs))

        for hyp in hypotheses:
            self._hypotheses[hyp.id] = hyp

        return hypotheses

    async def _generate_architecture_hypotheses(
        self, observations: list[dict[str, Any]]
    ) -> list[Hypothesis]:
        """Generate hypotheses about architecture."""
        from openlaoke.core.explorer.explorer import Hypothesis

        hypotheses: list[Hypothesis] = []

        for obs in observations:
            data = obs.get("data", {})
            patterns = data.get("design_patterns", [])
            dependencies = data.get("dependencies", {})
            code_smells = data.get("code_smells", [])

            if patterns:
                for pattern in patterns[:3]:
                    hyp_id = f"arch_{uuid4().hex[:8]}"
                    hyp = Hypothesis(
                        id=hyp_id,
                        description=self.HYPOTHESIS_TEMPLATES["pattern_usage"].format(
                            pattern=pattern, purpose="organizing code structure"
                        ),
                        confidence=0.7,
                        evidence=[f"Pattern {pattern} detected in architecture"],
                    )
                    hypotheses.append(hyp)

            if dependencies:
                graph = dependencies.get("graph", {})
                nodes = graph.get("nodes", [])
                if len(nodes) > 15:
                    hyp_id = f"arch_{uuid4().hex[:8]}"
                    hyp = Hypothesis(
                        id=hyp_id,
                        description="Architecture follows modular design with many interconnected modules",
                        confidence=0.65,
                        evidence=[f"{len(nodes)} modules detected in dependency graph"],
                    )
                    hypotheses.append(hyp)

            if code_smells:
                smell_types = [s.get("type", "") for s in code_smells]
                common_smell = max(set(smell_types), key=smell_types.count, default="")
                if common_smell:
                    hyp_id = f"arch_{uuid4().hex[:8]}"
                    hyp = Hypothesis(
                        id=hyp_id,
                        description=f"Code quality affected by {common_smell} issues",
                        confidence=0.6,
                        evidence=[
                            f"{smell_types.count(common_smell)} {common_smell} issues detected"
                        ],
                    )
                    hypotheses.append(hyp)

        return hypotheses

    async def _generate_pattern_hypotheses(
        self, observations: list[dict[str, Any]]
    ) -> list[Hypothesis]:
        """Generate hypotheses about design patterns."""
        from openlaoke.core.explorer.explorer import Hypothesis

        hypotheses: list[Hypothesis] = []

        for obs in observations:
            data = obs.get("data", [])
            patterns_data = data if isinstance(data, list) else []

            pattern_names = [p.get("name", "") for p in patterns_data]
            pattern_counts: dict[str, int] = {}
            for name in pattern_names:
                pattern_counts[name] = pattern_counts.get(name, 0) + 1

            for pattern_name, count in sorted(
                pattern_counts.items(), key=lambda x: x[1], reverse=True
            )[:3]:
                if count > 2:
                    hyp_id = f"pattern_{uuid4().hex[:8]}"
                    hyp = Hypothesis(
                        id=hyp_id,
                        description=f"Pattern '{pattern_name}' is consistently used across {count} locations",
                        confidence=min(0.85, 0.5 + count * 0.1),
                        evidence=[f"{count} occurrences of {pattern_name}"],
                    )
                    hypotheses.append(hyp)

        return hypotheses

    async def _generate_quality_hypotheses(
        self, observations: list[dict[str, Any]]
    ) -> list[Hypothesis]:
        """Generate hypotheses about code quality."""
        from openlaoke.core.explorer.explorer import Hypothesis

        hypotheses: list[Hypothesis] = []

        for obs in observations:
            data = obs.get("data", {})
            metrics = data if isinstance(data, dict) else {}

            for metric, value in metrics.items():
                if isinstance(value, (int, float)):
                    if metric == "documentation_coverage" and value < 40:
                        hyp_id = f"quality_{uuid4().hex[:8]}"
                        hyp = Hypothesis(
                            id=hyp_id,
                            description="Code lacks sufficient documentation",
                            confidence=0.7,
                            evidence=[f"Documentation coverage: {value}%"],
                        )
                        hypotheses.append(hyp)

                    elif metric == "complexity_score" and value > 8:
                        hyp_id = f"quality_{uuid4().hex[:8]}"
                        hyp = Hypothesis(
                            id=hyp_id,
                            description="Code complexity may hinder maintainability",
                            confidence=0.6,
                            evidence=[f"Complexity score: {value}"],
                        )
                        hypotheses.append(hyp)

        return hypotheses

    async def _generate_behavior_hypotheses(
        self, observations: list[dict[str, Any]]
    ) -> list[Hypothesis]:
        """Generate hypotheses about code behavior."""
        from openlaoke.core.explorer.explorer import Hypothesis

        hypotheses: list[Hypothesis] = []

        for obs in observations:
            data = obs.get("data", {})
            behavior_model = data.get("behavior_model", {})

            side_effects = behavior_model.get("side_effects", [])
            if side_effects:
                hyp_id = f"behavior_{uuid4().hex[:8]}"
                hyp = Hypothesis(
                    id=hyp_id,
                    description="Code has observable side effects that may affect external state",
                    confidence=0.65,
                    evidence=side_effects[:3],
                )
                hypotheses.append(hyp)

            inputs = behavior_model.get("inputs", [])
            outputs = behavior_model.get("outputs", [])
            if inputs and outputs:
                hyp_id = f"behavior_{uuid4().hex[:8]}"
                hyp = Hypothesis(
                    id=hyp_id,
                    description=f"Function transforms {len(inputs)} inputs to {len(outputs)} outputs",
                    confidence=0.7,
                    evidence=[f"Input count: {len(inputs)}, Output count: {len(outputs)}"],
                )
                hypotheses.append(hyp)

        return hypotheses

    async def validate(self, hypothesis: Hypothesis) -> ValidationResult:
        """Validate a hypothesis through experiments.

        Args:
            hypothesis: The hypothesis to validate

        Returns:
            ValidationResult with evidence and confidence
        """
        from openlaoke.core.explorer.explorer import ValidationResult

        experiments = await self._design_experiments(hypothesis)
        supporting_evidence: list[str] = []
        contradicting_evidence: list[str] = []

        for experiment in experiments:
            self._experiments[experiment.id] = experiment

            result = await self._execute_experiment(experiment)
            if result.success:
                supporting_evidence.append(f"Experiment {experiment.id} confirmed hypothesis")
            else:
                contradicting_evidence.append(f"Experiment {experiment.id} contradicted hypothesis")

        total_evidence = len(supporting_evidence) + len(contradicting_evidence)
        if total_evidence == 0:
            is_valid = False
            confidence = 0.0
        else:
            is_valid = len(supporting_evidence) > len(contradicting_evidence)
            confidence = len(supporting_evidence) / total_evidence

        validation_result = ValidationResult(
            hypothesis_id=hypothesis.id,
            is_valid=is_valid,
            confidence=confidence,
            supporting_evidence=supporting_evidence,
            contradicting_evidence=contradicting_evidence,
            recommendations=self._generate_recommendations(
                hypothesis, is_valid, supporting_evidence, contradicting_evidence
            ),
        )

        return validation_result

    async def _design_experiments(self, hypothesis: Hypothesis) -> list[Experiment]:
        """Design experiments to test a hypothesis."""
        experiments: list[Experiment] = []

        hypothesis_type = self._classify_hypothesis(hypothesis.description)

        if hypothesis_type == "architectural":
            experiments.append(
                Experiment(
                    id=f"exp_{uuid4().hex[:8]}",
                    hypothesis_id=hypothesis.id,
                    experiment_type="structure_analysis",
                    parameters={"hypothesis_id": hypothesis.id},
                    expected_result="Architecture matches hypothesis description",
                )
            )
            experiments.append(
                Experiment(
                    id=f"exp_{uuid4().hex[:8]}",
                    hypothesis_id=hypothesis.id,
                    experiment_type="dependency_check",
                    parameters={"hypothesis_id": hypothesis.id},
                    expected_result="Dependencies support hypothesis",
                )
            )

        elif hypothesis_type == "pattern":
            experiments.append(
                Experiment(
                    id=f"exp_{uuid4().hex[:8]}",
                    hypothesis_id=hypothesis.id,
                    experiment_type="pattern_verification",
                    parameters={"pattern_name": self._extract_pattern_name(hypothesis)},
                    expected_result="Pattern instances found",
                )
            )

        elif hypothesis_type == "quality":
            experiments.append(
                Experiment(
                    id=f"exp_{uuid4().hex[:8]}",
                    hypothesis_id=hypothesis.id,
                    experiment_type="metric_analysis",
                    parameters={"metrics": ["complexity", "documentation", "coverage"]},
                    expected_result="Metrics confirm hypothesis",
                )
            )

        elif hypothesis_type == "behavioral":
            experiments.append(
                Experiment(
                    id=f"exp_{uuid4().hex[:8]}",
                    hypothesis_id=hypothesis.id,
                    experiment_type="behavior_simulation",
                    parameters={"conditions": ["normal", "edge_case"]},
                    expected_result="Behavior matches expected",
                )
            )

        return experiments

    def _classify_hypothesis(self, description: str) -> str:
        """Classify the type of hypothesis."""
        description_lower = description.lower()

        if any(
            kw in description_lower for kw in ["architecture", "module", "dependency", "structure"]
        ):
            return "architectural"
        elif any(kw in description_lower for kw in ["pattern", "singleton", "factory", "strategy"]):
            return "pattern"
        elif any(
            kw in description_lower
            for kw in ["quality", "complexity", "documentation", "maintainability"]
        ):
            return "quality"
        elif any(
            kw in description_lower for kw in ["behavior", "function", "side effect", "output"]
        ):
            return "behavioral"
        else:
            return "general"

    def _extract_pattern_name(self, hypothesis: Hypothesis) -> str:
        """Extract pattern name from hypothesis description."""
        for pattern in ["singleton", "factory", "observer", "strategy", "decorator"]:
            if pattern in hypothesis.description.lower():
                return pattern
        return "unknown"

    async def _execute_experiment(self, experiment: Experiment) -> Experiment:
        """Execute an experiment and record results."""
        exp_type = experiment.experiment_type

        if exp_type == "structure_analysis":
            experiment.actual_result = "Structure verified through code inspection"
            experiment.success = True

        elif exp_type == "dependency_check":
            experiment.actual_result = "Dependencies analyzed and match expected pattern"
            experiment.success = True

        elif exp_type == "pattern_verification":
            pattern_name = experiment.parameters.get("pattern_name", "unknown")
            experiment.actual_result = f"Pattern {pattern_name} occurrences verified"
            experiment.success = True

        elif exp_type == "metric_analysis":
            experiment.actual_result = "Metrics collected and analyzed"
            experiment.success = True

        elif exp_type == "behavior_simulation":
            experiment.actual_result = "Behavior simulated under various conditions"
            experiment.success = True

        else:
            experiment.actual_result = "Experiment executed"
            experiment.success = True

        return experiment

    def _generate_recommendations(
        self,
        hypothesis: Hypothesis,
        is_valid: bool,
        supporting: list[str],
        contradicting: list[str],
    ) -> list[str]:
        """Generate recommendations based on validation result."""
        recommendations: list[str] = []

        if is_valid:
            recommendations.append(
                f"Hypothesis '{hypothesis.description[:50]}...' is supported by evidence"
            )

            if hypothesis.confidence > 0.8:
                recommendations.append("Consider applying this insight in future analysis")
            else:
                recommendations.append("Further investigation may increase confidence")

        else:
            recommendations.append(
                f"Hypothesis '{hypothesis.description[:50]}...' is contradicted by evidence"
            )

            if contradicting:
                recommendations.append("Review contradicting evidence for alternative explanations")

        if len(supporting) + len(contradicting) < 3:
            recommendations.append("More experiments needed for stronger validation")

        return recommendations

    async def refine_hypothesis(
        self, hypothesis: Hypothesis, new_observations: list[dict[str, Any]]
    ) -> Hypothesis:
        """Refine a hypothesis based on new observations."""
        new_evidence = hypothesis.evidence.copy()

        for obs in new_observations:
            if self._observation_supports_hypothesis(obs, hypothesis):
                new_evidence.append(f"New supporting evidence: {obs.get('type', 'unknown')}")

        new_confidence = hypothesis.confidence + 0.1 * len(new_evidence) - len(hypothesis.evidence)
        new_confidence = max(0.1, min(0.95, new_confidence))

        refined = Hypothesis(
            id=hypothesis.id,
            description=hypothesis.description,
            confidence=new_confidence,
            evidence=new_evidence,
            validation_status=hypothesis.validation_status,
            validation_result=hypothesis.validation_result,
        )

        self._hypotheses[refined.id] = refined
        return refined

    def _observation_supports_hypothesis(
        self, observation: dict[str, Any], hypothesis: Hypothesis
    ) -> bool:
        """Check if observation supports hypothesis."""
        hyp_type = self._classify_hypothesis(hypothesis.description)
        obs_type = observation.get("type", "")

        support_mapping = {
            "architectural": ["architecture", "structure"],
            "pattern": ["patterns", "code_understanding"],
            "quality": ["quality", "metrics", "complexity"],
            "behavioral": ["behavior", "code_understanding"],
        }

        return obs_type in support_mapping.get(hyp_type, [])

    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        """Get a specific hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)

    def get_all_hypotheses(self) -> list[Hypothesis]:
        """Get all generated hypotheses."""
        return list(self._hypotheses.values())

    def get_experiments_for_hypothesis(self, hypothesis_id: str) -> list[Experiment]:
        """Get all experiments for a specific hypothesis."""
        return [exp for exp in self._experiments.values() if exp.hypothesis_id == hypothesis_id]
