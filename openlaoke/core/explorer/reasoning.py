"""Reasoning engine for logical inference and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class ReasoningResult:
    """Result of a reasoning process."""

    conclusion: str
    confidence: float
    reasoning_type: str
    premises: list[str]
    evidence: list[str]
    counter_arguments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "reasoning_type": self.reasoning_type,
            "premises": self.premises,
            "evidence": self.evidence,
            "counter_arguments": self.counter_arguments,
        }


@dataclass
class LogicalRule:
    """Represents a logical rule for reasoning."""

    name: str
    pattern: str
    inference: str
    confidence_weight: float = 1.0

    def apply(self, premises: list[str]) -> str | None:
        """Apply the rule to premises."""
        return None


class ReasoningEngine:
    """Multi-modal reasoning engine for code exploration.

    This engine supports multiple reasoning types:
    - Inductive: From specific observations to general patterns
    - Deductive: From general rules to specific conclusions
    - Analogical: Drawing conclusions from similar cases
    - Causal: Understanding cause-effect relationships
    """

    def __init__(self) -> None:
        self._rules: list[LogicalRule] = self._initialize_rules()
        self._reasoning_history: list[ReasoningResult] = []

    def _initialize_rules(self) -> list[LogicalRule]:
        """Initialize basic logical rules."""
        return [
            LogicalRule(
                name="pattern_to_architecture",
                pattern="repeated_pattern",
                inference="architectural_design",
                confidence_weight=0.8,
            ),
            LogicalRule(
                name="dependency_to_coupling",
                pattern="high_dependency_count",
                inference="tight_coupling",
                confidence_weight=0.7,
            ),
            LogicalRule(
                name="complexity_to_maintainability",
                pattern="high_complexity",
                inference="low_maintainability",
                confidence_weight=0.75,
            ),
            LogicalRule(
                name="test_coverage_to_quality",
                pattern="low_test_coverage",
                inference="quality_risk",
                confidence_weight=0.65,
            ),
        ]

    async def reason(
        self, observations: list[dict[str, Any]], context: dict[str, Any] | None = None
    ) -> ReasoningResult:
        """Perform reasoning based on observations.

        Args:
            observations: List of observations to reason about
            context: Additional context for reasoning

        Returns:
            ReasoningResult with conclusion and confidence
        """
        context = context or {}

        reasoning_methods = [
            ("inductive", self._inductive_reasoning),
            ("deductive", self._deductive_reasoning),
            ("analogical", self._analogical_reasoning),
            ("causal", self._causal_reasoning),
        ]

        results: list[tuple[str, ReasoningResult]] = []
        for reasoning_type, method in reasoning_methods:
            try:
                result = await method(observations, context)
                results.append((reasoning_type, result))
            except Exception:
                pass

        if not results:
            return ReasoningResult(
                conclusion="Unable to draw conclusions",
                confidence=0.0,
                reasoning_type="none",
                premises=[],
                evidence=[],
            )

        best_type, best_result = max(results, key=lambda x: x[1].confidence)

        self._reasoning_history.append(best_result)
        return best_result

    async def _inductive_reasoning(
        self, observations: list[dict[str, Any]], context: dict[str, Any]
    ) -> ReasoningResult:
        """Inductive reasoning: specific to general."""
        premises: list[str] = []
        evidence: list[str] = []
        patterns: dict[str, int] = {}

        for obs in observations:
            obs_type = obs.get("type", "unknown")
            patterns[obs_type] = patterns.get(obs_type, 0) + 1

            if "data" in obs:
                data = obs["data"]
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, list) and value:
                            evidence.append(f"{key}: {len(value)} instances")
                        elif isinstance(value, (int, float)):
                            premises.append(f"{key} = {value}")

        most_common_pattern = max(patterns.items(), key=lambda x: x[1], default=(None, 0))

        if most_common_pattern[0]:
            conclusion = (
                f"Observed pattern: {most_common_pattern[0]} appears {most_common_pattern[1]} times"
            )
            confidence = min(0.9, most_common_pattern[1] / max(len(observations), 1) * 0.9)
        else:
            conclusion = "No clear pattern detected from observations"
            confidence = 0.1

        return ReasoningResult(
            conclusion=conclusion,
            confidence=confidence,
            reasoning_type="inductive",
            premises=premises[:10],
            evidence=evidence[:10],
        )

    async def _deductive_reasoning(
        self, observations: list[dict[str, Any]], context: dict[str, Any]
    ) -> ReasoningResult:
        """Deductive reasoning: general to specific."""
        premises: list[str] = []
        evidence: list[str] = []
        conclusions: list[str] = []

        for rule in self._rules:
            matching_observations = [
                obs for obs in observations if self._matches_pattern(obs, rule.pattern)
            ]

            if matching_observations:
                premises.append(f"Rule: {rule.name}")
                evidence.extend(
                    f"Observation matches {rule.pattern}" for _ in matching_observations[:3]
                )
                conclusions.append(rule.inference)

        if conclusions:
            final_conclusion = f"Based on rules: {', '.join(conclusions[:3])}"
            avg_confidence = sum(
                self._rules[i].confidence_weight for i in range(len(conclusions))
            ) / len(conclusions)
        else:
            final_conclusion = "No applicable rules for deduction"
            avg_confidence = 0.1

        return ReasoningResult(
            conclusion=final_conclusion,
            confidence=avg_confidence,
            reasoning_type="deductive",
            premises=premises,
            evidence=evidence,
        )

    def _matches_pattern(self, observation: dict[str, Any], pattern: str) -> bool:
        """Check if observation matches a pattern."""
        obs_type = observation.get("type", "")
        obs_data = observation.get("data", {})

        if pattern == "repeated_pattern":
            return "patterns" in obs_data and len(obs_data.get("patterns", [])) > 0
        elif pattern == "high_dependency_count":
            deps = obs_data.get("dependencies", {})
            graph = deps.get("graph", {})
            return len(graph.get("nodes", [])) > 10
        elif pattern == "high_complexity":
            return any(
                v.get("complexity", 0) > 10 for v in obs_data.values() if isinstance(v, dict)
            )
        elif pattern == "low_test_coverage":
            return "test" not in str(obs_data).lower()[:50]

        return pattern.lower() in obs_type.lower()

    async def _analogical_reasoning(
        self, observations: list[dict[str, Any]], context: dict[str, Any]
    ) -> ReasoningResult:
        """Analogical reasoning: comparing similar cases."""
        premises: list[str] = []
        evidence: list[str] = []
        similarities: list[str] = []

        known_cases = context.get("known_cases", [])

        for obs in observations:
            for known_case in known_cases:
                similarity_score = self._calculate_similarity(obs, known_case)
                if similarity_score > 0.6:
                    similarities.append(
                        f"Similar to {known_case.get('name', 'unknown')} ({similarity_score:.2f})"
                    )
                    premises.append(f"Observation type: {obs.get('type', 'unknown')}")
                    evidence.append(f"Known case: {known_case.get('conclusion', 'unknown')}")

        if similarities:
            conclusion = f"Analogous to known cases: {', '.join(similarities[:3])}"
            confidence = min(0.8, len(similarities) * 0.2)
        else:
            conclusion = "No similar cases found for analogy"
            confidence = 0.1

        return ReasoningResult(
            conclusion=conclusion,
            confidence=confidence,
            reasoning_type="analogical",
            premises=premises[:10],
            evidence=evidence[:10],
        )

    def _calculate_similarity(
        self, observation: dict[str, Any], known_case: dict[str, Any]
    ) -> float:
        """Calculate similarity between observation and known case."""
        obs_type = observation.get("type", "")
        case_type = known_case.get("type", "")

        if obs_type == case_type:
            return 0.8

        obs_data = observation.get("data", {})
        case_data = known_case.get("data", {})

        common_keys = set(obs_data.keys()) & set(case_data.keys())
        if not common_keys:
            return 0.0

        similarity = len(common_keys) / max(len(obs_data), len(case_data), 1)
        return min(0.7, similarity)

    async def _causal_reasoning(
        self, observations: list[dict[str, Any]], context: dict[str, Any]
    ) -> ReasoningResult:
        """Causal reasoning: understanding cause-effect."""
        premises: list[str] = []
        evidence: list[str] = []
        causal_chains: list[str] = []

        temporal_observations = sorted(observations, key=lambda x: x.get("timestamp", 0))

        for i, obs in enumerate(temporal_observations[:-1]):
            next_obs = temporal_observations[i + 1]

            potential_cause = obs.get("type", "")
            potential_effect = next_obs.get("type", "")

            if self._is_causal_relationship(potential_cause, potential_effect):
                causal_chains.append(f"{potential_cause} → {potential_effect}")
                premises.append(f"Before: {potential_cause}")
                evidence.append(f"After: {potential_effect}")

        if causal_chains:
            conclusion = f"Detected causal chains: {', '.join(causal_chains[:3])}"
            confidence = 0.6
        else:
            conclusion = "No clear causal relationships detected"
            confidence = 0.1

        return ReasoningResult(
            conclusion=conclusion,
            confidence=confidence,
            reasoning_type="causal",
            premises=premises[:10],
            evidence=evidence[:10],
        )

    def _is_causal_relationship(self, cause_type: str, effect_type: str) -> bool:
        """Check if there's a potential causal relationship."""
        causal_rules = {
            "architecture": ["patterns", "code_smells"],
            "patterns": ["hypotheses"],
            "hypotheses": ["validation"],
            "code_understanding": ["complexity"],
        }

        return effect_type in causal_rules.get(cause_type, [])

    async def infer_architecture_style(self, architecture_data: dict[str, Any]) -> ReasoningResult:
        """Infer the architecture style from analysis."""
        patterns = architecture_data.get("design_patterns", [])
        dependencies = architecture_data.get("dependencies", {})
        structure = architecture_data.get("structure", {})

        observations = [
            {"type": "patterns", "data": {"patterns": patterns}},
            {"type": "dependencies", "data": dependencies},
            {"type": "structure", "data": structure},
        ]

        result = await self.reason(observations)

        style_indicators: list[str] = []
        if "factory" in patterns or "singleton" in patterns:
            style_indicators.append("Object-oriented design")
        if "decorator" in patterns:
            style_indicators.append("Functional composition")
        if len(dependencies.get("graph", {}).get("nodes", [])) > 20:
            style_indicators.append("Modular architecture")

        if style_indicators:
            result.conclusion = f"Architecture style: {', '.join(style_indicators)}"
            result.confidence = max(result.confidence, 0.7)

        return result

    async def infer_quality_issues(self, quality_metrics: dict[str, float]) -> ReasoningResult:
        """Infer quality issues from metrics."""
        premises: list[str] = []
        evidence: list[str] = []
        issues: list[str] = []

        for metric, value in quality_metrics.items():
            premises.append(f"{metric} = {value}")

            if metric == "documentation_coverage" and value < 30:
                issues.append("Poor documentation coverage")
                evidence.append("Documentation coverage below 30%")
            elif metric == "complexity_score" and value > 10:
                issues.append("High complexity")
                evidence.append("Complexity score exceeds threshold")
            elif metric == "avg_function_length" and value > 30:
                issues.append("Long functions")
                evidence.append("Average function length > 30 lines")

        if issues:
            conclusion = f"Quality issues detected: {', '.join(issues)}"
            confidence = 0.75
        else:
            conclusion = "Quality metrics within acceptable range"
            confidence = 0.6

        return ReasoningResult(
            conclusion=conclusion,
            confidence=confidence,
            reasoning_type="deductive",
            premises=premises,
            evidence=evidence,
        )

    def get_reasoning_history(self) -> list[ReasoningResult]:
        """Get the history of reasoning results."""
        return list(self._reasoning_history)

    async def multi_step_reasoning(
        self, observations: list[dict[str, Any]], steps: int = 3
    ) -> list[ReasoningResult]:
        """Perform multi-step reasoning process."""
        results: list[ReasoningResult] = []
        current_obs = observations

        for step in range(steps):
            result = await self.reason(current_obs)
            results.append(result)

            new_obs = [
                {
                    "type": "reasoning_step",
                    "data": result.to_dict(),
                    "timestamp": step,
                }
            ]
            current_obs = observations + new_obs

        return results
