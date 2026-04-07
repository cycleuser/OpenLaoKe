"""Intent-based task processing pipeline.

Integrates intent parsing, spec conversion, and task decomposition
into a unified workflow for small models.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openlaoke.core.architecture.decomposer import (
    AtomicTask,
    FineGrainedDecomposer,
    TaskGraph,
)
from openlaoke.core.architecture.interfaces import ComponentSpec
from openlaoke.core.intent_parser import (
    IntentParser,
    IntentType,
    ProgrammingIntent,
)
from openlaoke.core.intent_to_spec import IntentToSpecConverter
from openlaoke.core.model_assessment.types import ModelTier


@dataclass
class ProcessingPipelineResult:
    success: bool
    intent: ProgrammingIntent
    specs: list[ComponentSpec]
    tasks: list[AtomicTask]
    task_graph: TaskGraph | None
    errors: list[str]
    warnings: list[str]
    ready_to_execute: bool


class IntentBasedPipeline:
    def __init__(
        self,
        model_tier: ModelTier = ModelTier.TIER_5_LIMITED,
        working_directory: Path | None = None,
    ) -> None:
        self.model_tier = model_tier
        self.parser = IntentParser()
        self.converter = IntentToSpecConverter(model_tier)
        self.decomposer = FineGrainedDecomposer(model_tier)
        self.working_directory = working_directory or Path.cwd()

    def process_request(self, user_request: str) -> ProcessingPipelineResult:
        intent = self.parser.parse(user_request)

        if intent.intent_type == IntentType.UNKNOWN:
            self.parser.suggest_clarifications(intent)
            return ProcessingPipelineResult(
                success=False,
                intent=intent,
                specs=[],
                tasks=[],
                task_graph=None,
                errors=["Unable to understand the request"],
                warnings=[],
                ready_to_execute=False,
            )

        spec_result = self.converter.convert(intent)

        if not spec_result.success:
            return ProcessingPipelineResult(
                success=False,
                intent=intent,
                specs=spec_result.specs,
                tasks=[],
                task_graph=None,
                errors=spec_result.errors,
                warnings=spec_result.warnings,
                ready_to_execute=False,
            )

        all_tasks = []
        for spec in spec_result.specs:
            if spec.component_type.value == "module":
                module_tasks = self.decomposer.decompose_module(spec)
                all_tasks.extend(module_tasks)
            elif spec.component_type.value == "class":
                class_tasks = self.decomposer.decompose_class(spec)
                all_tasks.extend(class_tasks)
            elif spec.component_type.value == "function":
                function_tasks = self.decomposer.decompose_function(spec)
                all_tasks.extend(function_tasks)
            else:
                atomic_task = self._create_atomic_task_from_spec(spec)
                all_tasks.append(atomic_task)

        task_graph = TaskGraph(root_task_id="root")
        for task in all_tasks:
            task_graph.add_task(task)

        ready_tasks = task_graph.get_ready_tasks()

        return ProcessingPipelineResult(
            success=True,
            intent=intent,
            specs=spec_result.specs,
            tasks=all_tasks,
            task_graph=task_graph,
            errors=spec_result.errors,
            warnings=spec_result.warnings,
            ready_to_execute=len(ready_tasks) > 0,
        )

    def get_execution_plan(self, result: ProcessingPipelineResult) -> dict[str, Any]:
        if not result.success or not result.task_graph:
            return {}

        plan = {
            "total_tasks": len(result.tasks),
            "ready_tasks": [],
            "pending_tasks": [],
            "estimated_lines_total": sum(t.estimated_lines for t in result.tasks),
        }

        for task in result.tasks:
            task_info = {
                "task_id": task.task_id,
                "description": task.description,
                "estimated_lines": task.estimated_lines,
                "dependencies": task.dependencies,
                "component_type": task.component_spec.component_type.value,
            }

            if task.task_id in result.task_graph.completed:
                continue
            elif all(dep in result.task_graph.completed for dep in task.dependencies):
                plan["ready_tasks"].append(task_info)
            else:
                plan["pending_tasks"].append(task_info)

        return plan

    def generate_task_prompt(self, task: AtomicTask, context: dict[str, Any] | None = None) -> str:
        if context is None:
            context = {}
        prompt_parts = [
            f"Task: {task.description}",
            f"Estimated complexity: {task.estimated_lines} lines",
            "",
            "Requirements:",
        ]

        for rule in task.validation_rules:
            prompt_parts.append(f"  - {rule}")

        if task.component_spec.api_spec:
            api = task.component_spec.api_spec
            prompt_parts.extend(
                [
                    "",
                    "Input parameters:",
                ]
            )

            for param_name, param_spec in api.input_schema.get("properties", {}).items():
                param_type = param_spec.get("type", "any")
                param_desc = param_spec.get("description", "")
                prompt_parts.append(f"  - {param_name}: {param_type} ({param_desc})")

            prompt_parts.extend(
                [
                    "",
                    "Expected output:",
                    f"  {api.output_schema.get('type', 'any')}",
                ]
            )

        prompt_parts.extend(
            [
                "",
                "Important constraints:",
                f"  - Maximum {self.decomposer.max_lines_per_task} lines of code",
                f"  - Maximum {self.decomposer.max_params_per_function} parameters",
                "  - MUST be syntactically correct Python",
                "  - MUST have complete type hints",
                "  - MUST have docstring",
                "",
                "Write ONLY this specific function/class. Do NOT write the entire program.",
                "",
                "Template to fill:",
                task.template.template,
            ]
        )

        return "\n".join(prompt_parts)

    def validate_task_result(self, task: AtomicTask, code: str) -> tuple[bool, list[str]]:
        import ast

        errors = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")
            return False, errors

        lines = code.strip().split("\n")
        max_allowed_lines = max(task.estimated_lines * 3, 20)
        if len(lines) > max_allowed_lines:
            errors.append(f"Code too long: {len(lines)} lines > {max_allowed_lines} allowed")

        non_empty_lines = [
            line for line in lines if line.strip() and not line.strip().startswith("#")
        ]
        if len(non_empty_lines) > 25:
            errors.append(f"Too many non-empty lines: {len(non_empty_lines)} > 25")

        for rule in task.validation_rules:
            if "type hints" in rule.lower() and "def " in code and " -> " not in code:
                pass

            if "docstring" in rule.lower() and '"""' not in code and "'''" not in code:
                pass

        return len(errors) == 0, errors

    def _create_atomic_task_from_spec(self, spec: ComponentSpec) -> AtomicTask:
        from openlaoke.core.architecture.interfaces import get_template_for_component

        template = get_template_for_component(spec.component_type)

        return AtomicTask(
            task_id=spec.name,
            description=f"Implement {spec.name}",
            component_spec=spec,
            template=template,
            estimated_lines=self.decomposer.max_lines_per_task,
            test_required=True,
            validation_rules=template.validation_rules,
        )


def create_pipeline_for_model(
    model_tier: ModelTier,
    working_directory: Path | None = None,
) -> IntentBasedPipeline:
    return IntentBasedPipeline(model_tier, working_directory)
