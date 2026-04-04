"""Exploration strategy and execution planning."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.explorer.explorer import (
        ExplorationPlan,
        ExplorationResult,
        ExploreMode,
    )


@dataclass
class ExplorationStep:
    """Single step in an exploration plan."""

    step_id: str
    action: str
    target: str
    expected_duration: float
    priority: int = 1
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "expected_duration": self.expected_duration,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "status": self.status,
            "result": self.result,
        }


class ExplorationStrategy:
    """Manages exploration planning and execution strategies.

    This class provides:
    - Exploration plan creation
    - Strategy optimization
    - Execution coordination
    - Progress tracking
    """

    STRATEGY_TEMPLATES = {
        "quick_overview": {
            "description": "Quick overview of codebase structure",
            "steps": ["analyze_structure", "detect_patterns"],
            "estimated_duration": 30.0,
        },
        "deep_analysis": {
            "description": "Deep analysis of architecture and quality",
            "steps": [
                "analyze_structure",
                "detect_patterns",
                "analyze_dependencies",
                "detect_code_smells",
                "generate_hypotheses",
            ],
            "estimated_duration": 120.0,
        },
        "pattern_focus": {
            "description": "Focus on pattern discovery and analysis",
            "steps": ["detect_patterns", "analyze_patterns", "validate_patterns"],
            "estimated_duration": 60.0,
        },
        "quality_assessment": {
            "description": "Assess code quality and maintainability",
            "steps": [
                "detect_code_smells",
                "analyze_complexity",
                "assess_documentation",
                "generate_quality_hypotheses",
            ],
            "estimated_duration": 90.0,
        },
        "dependency_analysis": {
            "description": "Analyze module dependencies and coupling",
            "steps": [
                "analyze_dependencies",
                "detect_circular_dependencies",
                "measure_coupling",
                "suggest_refactoring",
            ],
            "estimated_duration": 75.0,
        },
    }

    GOAL_MAPPING = {
        "understand architecture": "deep_analysis",
        "find patterns": "pattern_focus",
        "assess quality": "quality_assessment",
        "analyze dependencies": "dependency_analysis",
        "quick exploration": "quick_overview",
        "full analysis": "deep_analysis",
    }

    def __init__(self) -> None:
        self._active_plans: dict[str, ExplorationPlan] = {}
        self._completed_executions: list[ExplorationResult] = []
        self._strategy_stats: dict[str, dict[str, Any]] = {}

    async def create_plan(self, goal: str, project_path: Path) -> ExplorationPlan:
        """Create an exploration plan based on goal.

        Args:
            goal: The exploration goal
            project_path: Path to the project

        Returns:
            ExplorationPlan with steps and duration
        """
        goal_lower = goal.lower()
        strategy_key = "deep_analysis"

        for goal_keyword, strategy in self.GOAL_MAPPING.items():
            if goal_keyword in goal_lower:
                strategy_key = strategy
                break

        template = self.STRATEGY_TEMPLATES[strategy_key]
        steps = await self._create_steps_from_template(template, project_path)

        estimated_duration_value = template.get("estimated_duration", 120.0)
        estimated_duration: float = (
            estimated_duration_value
            if isinstance(estimated_duration_value, float)
            else float(estimated_duration_value)
        )

        plan = ExplorationPlan(
            goal=goal,
            steps=steps,
            estimated_duration=estimated_duration,
            priority=self._determine_priority(goal),
            required_tools=self._determine_required_tools(steps),
        )

        self._active_plans[plan.goal] = plan
        return plan

    async def _create_steps_from_template(
        self, template: dict[str, Any], project_path: Path
    ) -> list[dict[str, Any]]:
        """Create concrete steps from template."""
        steps: list[dict[str, Any]] = []
        step_names = template.get("steps", [])

        for i, step_name in enumerate(step_names):
            step_id = f"step_{i + 1}"

            step = {
                "step_id": step_id,
                "action": self._get_step_action(step_name),
                "target": str(project_path),
                "expected_duration": self._get_step_duration(step_name),
                "priority": self._get_step_priority(step_name),
                "dependencies": self._get_step_dependencies(i),
                "status": "pending",
            }
            steps.append(step)

        return steps

    def _get_step_action(self, step_name: str) -> str:
        """Get the action description for a step."""
        action_mapping = {
            "analyze_structure": "Analyze project structure and organization",
            "detect_patterns": "Detect design patterns and conventions",
            "analyze_patterns": "Deep analysis of discovered patterns",
            "validate_patterns": "Validate and refine pattern hypotheses",
            "analyze_dependencies": "Analyze module dependencies and imports",
            "detect_circular_dependencies": "Detect circular dependency chains",
            "measure_coupling": "Measure coupling between modules",
            "suggest_refactoring": "Generate refactoring suggestions",
            "detect_code_smells": "Detect code smells and anti-patterns",
            "analyze_complexity": "Analyze code complexity metrics",
            "assess_documentation": "Assess documentation coverage",
            "generate_hypotheses": "Generate hypotheses about code behavior",
            "generate_quality_hypotheses": "Generate quality-related hypotheses",
        }
        return action_mapping.get(step_name, f"Execute {step_name}")

    def _get_step_duration(self, step_name: str) -> float:
        """Get estimated duration for a step."""
        duration_mapping = {
            "analyze_structure": 15.0,
            "detect_patterns": 10.0,
            "analyze_patterns": 20.0,
            "validate_patterns": 15.0,
            "analyze_dependencies": 20.0,
            "detect_circular_dependencies": 10.0,
            "measure_coupling": 15.0,
            "suggest_refactoring": 20.0,
            "detect_code_smells": 15.0,
            "analyze_complexity": 20.0,
            "assess_documentation": 10.0,
            "generate_hypotheses": 15.0,
            "generate_quality_hypotheses": 15.0,
        }
        return duration_mapping.get(step_name, 10.0)

    def _get_step_priority(self, step_name: str) -> int:
        """Get priority level for a step (1-5)."""
        priority_mapping = {
            "analyze_structure": 1,
            "detect_patterns": 2,
            "analyze_dependencies": 2,
            "detect_code_smells": 3,
            "generate_hypotheses": 4,
            "validate_patterns": 5,
            "measure_coupling": 3,
            "suggest_refactoring": 5,
        }
        return priority_mapping.get(step_name, 3)

    def _get_step_dependencies(self, step_index: int) -> list[str]:
        """Get dependencies for a step."""
        if step_index == 0:
            return []
        return [f"step_{step_index}"]

    def _determine_priority(self, goal: str) -> str:
        """Determine overall priority for the plan."""
        goal_lower = goal.lower()

        if any(kw in goal_lower for kw in ["urgent", "critical", "important"]):
            return "high"
        elif any(kw in goal_lower for kw in ["quick", "fast", "simple"]):
            return "low"
        else:
            return "medium"

    def _determine_required_tools(self, steps: list[dict[str, Any]]) -> list[str]:
        """Determine required tools for the plan."""
        tools: set[str] = set()

        for step in steps:
            action = step.get("action", "")
            if "structure" in action.lower():
                tools.add("file_reader")
                tools.add("ast_parser")
            elif "pattern" in action.lower():
                tools.add("pattern_detector")
                tools.add("regex_matcher")
            elif "dependency" in action.lower():
                tools.add("dependency_analyzer")
                tools.add("graph_builder")
            elif "complexity" in action.lower():
                tools.add("complexity_calculator")
            elif "hypothesis" in action.lower():
                tools.add("hypothesis_generator")

        return list(tools)

    async def execute(self, plan: ExplorationPlan, explorer: ExploreMode) -> ExplorationResult:
        """Execute an exploration plan.

        Args:
            plan: The exploration plan to execute
            explorer: The ExploreMode instance to use

        Returns:
            ExplorationResult with findings and insights
        """
        from openlaoke.core.explorer.explorer import ExplorationResult

        start_time = time.time()
        findings: list[dict[str, Any]] = []
        insights: list[str] = []
        errors: list[str] = []

        for step in plan.steps:
            step_id = step.get("step_id", "")
            action = step.get("action", "")
            target = step.get("target", "")

            step["status"] = "running"

            try:
                result = await self._execute_step(action, target, explorer)
                step["status"] = "completed"
                step["result"] = result
                findings.append(
                    {
                        "step_id": step_id,
                        "action": action,
                        "result": result,
                    }
                )

                if isinstance(result, dict):
                    if "summary" in result:
                        insights.append(f"{action}: {result['summary']}")
                    elif "patterns" in result:
                        insights.append(f"Found {len(result['patterns'])} patterns")
                    elif "hypotheses" in result:
                        insights.append(f"Generated {len(result['hypotheses'])} hypotheses")

            except Exception as e:
                step["status"] = "failed"
                errors.append(f"{step_id}: {str(e)}")

        duration = time.time() - start_time
        success = len(errors) == 0

        metrics = {
            "total_duration": duration,
            "steps_completed": sum(1 for s in plan.steps if s.get("status") == "completed"),
            "steps_failed": sum(1 for s in plan.steps if s.get("status") == "failed"),
            "findings_count": len(findings),
        }

        exploration_result: ExplorationResult = ExplorationResult(
            plan_id=plan.goal,
            success=success,
            findings=findings,
            insights=insights,
            metrics=metrics,
            error="; ".join(errors) if errors else None,
        )

        self._completed_executions.append(exploration_result)
        return exploration_result

    async def _execute_step(
        self, action: str, target: str, explorer: ExploreMode
    ) -> dict[str, Any]:
        """Execute a single step."""
        target_path = Path(target)

        if "structure" in action.lower():
            arch = await explorer.explore_architecture(target_path)
            return {
                "type": "architecture",
                "patterns": arch.design_patterns,
                "structure": arch.structure,
                "summary": f"Found {len(arch.design_patterns)} design patterns",
            }

        elif "pattern" in action.lower():
            patterns = await explorer.discover_patterns(target_path)
            return {
                "type": "patterns",
                "patterns": [p.to_dict() for p in patterns],
                "summary": f"Discovered {len(patterns)} patterns",
            }

        elif "dependency" in action.lower():
            arch = await explorer.explore_architecture(target_path)
            deps = arch.dependencies
            graph_data = deps.get("graph", {})
            nodes: list[Any] = []
            if isinstance(graph_data, dict):
                nodes = graph_data.get("nodes", [])
            return {
                "type": "dependencies",
                "graph": graph_data,
                "cycles": deps.get("cycles", []),
                "summary": f"Analyzed {len(nodes)} dependencies",
            }

        elif "code smell" in action.lower() or "quality" in action.lower():
            arch = await explorer.explore_architecture(target_path)
            smells = arch.code_smells
            return {
                "type": "code_smells",
                "smells": smells,
                "summary": f"Detected {len(smells)} code smells",
            }

        elif "hypothesis" in action.lower():
            observations = [{"type": "architecture_request", "target": str(target_path)}]
            hypotheses = await explorer.generate_hypotheses(observations)
            return {
                "type": "hypotheses",
                "hypotheses": [h.to_dict() for h in hypotheses],
                "summary": f"Generated {len(hypotheses)} hypotheses",
            }

        elif "complexity" in action.lower():
            if target_path.is_file():
                understanding = await explorer.understand_code(target_path)
                return {
                    "type": "complexity",
                    "complexity_score": understanding.complexity_score,
                    "metrics": understanding.quality_metrics,
                    "summary": f"Complexity: {understanding.complexity_score:.2f}",
                }
            else:
                return {"type": "complexity", "summary": "Complexity analysis pending"}

        else:
            return {"type": "general", "action": action, "summary": f"Executed {action}"}

    async def optimize_plan(
        self, plan: ExplorationPlan, execution_history: list[ExplorationResult]
    ) -> ExplorationPlan:
        """Optimize a plan based on execution history.

        Args:
            plan: The plan to optimize
            execution_history: Previous execution results

        Returns:
            Optimized exploration plan
        """
        avg_duration_per_step: dict[str, float] = {}

        for result in execution_history:
            for finding in result.findings:
                action = finding.get("action", "")
                if action in avg_duration_per_step:
                    avg_duration_per_step[action] = (
                        avg_duration_per_step[action] + result.metrics.get("total_duration", 0)
                    ) / 2
                else:
                    avg_duration_per_step[action] = result.metrics.get("total_duration", 0)

        optimized_steps: list[dict[str, Any]] = []
        for step in plan.steps:
            action = step.get("action", "")
            if action in avg_duration_per_step:
                step["expected_duration"] = avg_duration_per_step[action] * 0.9
            optimized_steps.append(step)

        high_priority_steps = sorted(
            optimized_steps, key=lambda s: s.get("priority", 3), reverse=True
        )

        reordered_steps: list[dict[str, Any]] = []
        added_steps: set[str] = set()

        for step in high_priority_steps:
            deps = step.get("dependencies", [])
            if all(dep in added_steps for dep in deps):
                reordered_steps.append(step)
                added_steps.add(step.get("step_id", ""))

        for step in optimized_steps:
            if step.get("step_id", "") not in added_steps:
                reordered_steps.append(step)

        optimized_plan = ExplorationPlan(
            goal=plan.goal,
            steps=reordered_steps,
            estimated_duration=sum(s.get("expected_duration", 10) for s in reordered_steps),
            priority=plan.priority,
            required_tools=plan.required_tools,
        )

        return optimized_plan

    def get_active_plan(self, goal: str) -> ExplorationPlan | None:
        """Get an active plan by goal."""
        return self._active_plans.get(goal)

    def get_execution_history(self) -> list[ExplorationResult]:
        """Get all completed executions."""
        return list(self._completed_executions)

    async def estimate_completion_time(self, plan: ExplorationPlan) -> dict[str, float]:
        """Estimate completion time for a plan."""
        total_estimated = sum(step.get("expected_duration", 10) for step in plan.steps)

        completed_executions = len(self._completed_executions)
        if completed_executions > 0:
            avg_error_rate = (
                sum(
                    abs(r.metrics.get("total_duration", 0) - r.metrics.get("estimated_duration", 0))
                    for r in self._completed_executions
                )
                / completed_executions
            )

            adjusted_estimate = total_estimated * (1 + avg_error_rate / 100)
        else:
            adjusted_estimate = total_estimated * 1.1

        return {
            "estimated_duration": total_estimated,
            "adjusted_estimate": adjusted_estimate,
            "confidence": 0.8 if completed_executions > 5 else 0.5,
        }

    def get_strategy_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics about strategy usage."""
        stats: dict[str, dict[str, Any]] = {}

        for strategy_key, template in self.STRATEGY_TEMPLATES.items():
            matching_executions: list[ExplorationResult] = [
                e
                for e in self._completed_executions
                if any(
                    isinstance(step, dict)
                    and str(step.get("action", "")).lower()
                    in str(template.get("description", "")).lower()
                    for step in []
                )
            ]

            if matching_executions:
                avg_duration = sum(
                    e.metrics.get("total_duration", 0) for e in matching_executions
                ) / len(matching_executions)
                success_rate = sum(1 for e in matching_executions if e.success) / len(
                    matching_executions
                )

                stats[strategy_key] = {
                    "usage_count": len(matching_executions),
                    "average_duration": avg_duration,
                    "success_rate": success_rate,
                }

        return stats
