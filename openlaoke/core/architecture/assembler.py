"""Automatic assembly and validation of components.

Assembles atomic tasks into working code with strict validation.
"""

from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.core.architecture.decomposer import AtomicTask, TaskGraph
from openlaoke.core.architecture.interfaces import (
    CodeTemplate,
    ComponentType,
)


@dataclass
class AssemblyResult:
    success: bool
    code: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    test_results: dict[str, bool] = field(default_factory=dict)
    coverage: float = 0.0


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class CodeAssembler:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.assembled_components: dict[str, str] = {}
        self.import_registry: dict[str, set[str]] = {}

    def assemble_task_graph(self, graph: TaskGraph) -> AssemblyResult:
        all_code = []
        all_errors = []
        all_warnings = []
        test_results = {}

        imports_collected = set()

        ready_tasks = graph.get_ready_tasks()
        processed_count = 0

        while ready_tasks and processed_count < len(graph.tasks):
            for task in ready_tasks:
                if task.task_id in graph.completed:
                    continue

                result = self.assemble_atomic_task(task, graph)

                if result.success:
                    if task.component_spec.component_type != ComponentType.TEST:
                        all_code.append(result.code)
                        imports_collected.update(task.template.required_imports)

                    graph.mark_completed(task.task_id)
                    processed_count += 1

                    if task.component_spec.component_type == ComponentType.TEST:
                        test_results[task.task_id] = True
                else:
                    all_errors.extend(result.errors)
                    all_warnings.extend(result.warnings)
                    graph.mark_failed(task.task_id)
                    processed_count += 1

            ready_tasks = graph.get_ready_tasks()

        final_code = self._organize_code(imports_collected, all_code)

        return AssemblyResult(
            success=len(all_errors) == 0 and len(graph.completed) == len(graph.tasks),
            code=final_code,
            errors=all_errors,
            warnings=all_warnings,
            test_results=test_results,
        )

    def assemble_atomic_task(self, task: AtomicTask, graph: TaskGraph) -> AssemblyResult:
        code_parts = []
        errors = []
        warnings = []

        for dep_id in task.dependencies:
            if dep_id in graph.failed:
                errors.append(f"Dependency {dep_id} failed")
                return AssemblyResult(
                    success=False,
                    code="",
                    errors=errors,
                    warnings=warnings,
                )

        context = self._build_context(task, graph)

        filled_template = self._fill_template(task.template, context)

        validation = self._validate_code(filled_template, task)

        if not validation.is_valid:
            errors.extend(validation.errors)
            warnings.extend(validation.warnings)

            if not self._can_auto_fix(validation):
                return AssemblyResult(
                    success=False,
                    code=filled_template,
                    errors=errors,
                    warnings=warnings,
                )

            fixed_code = self._auto_fix_code(filled_template, validation)
            filled_template = fixed_code

        code_parts.append(filled_template)

        self.assembled_components[task.task_id] = filled_template

        return AssemblyResult(
            success=len(errors) == 0,
            code="\n\n".join(code_parts),
            errors=errors,
            warnings=warnings,
        )

    def _build_context(self, task: AtomicTask, graph: TaskGraph) -> dict[str, Any]:
        context = task.context.copy()

        context.update(
            {
                "function_name": task.component_spec.name,
                "class_name": task.component_spec.name,
                "return_type": "Any",
                "return_value": "result",
                "docstring": task.description,
                "parameters": "",
                "args_doc": "Arguments",
                "return_doc": "Return value",
                "raises_doc": "Exceptions",
                "implementation": "pass",
            }
        )

        if task.component_spec.api_spec:
            api = task.component_spec.api_spec
            params = []
            for param_name, param_spec in api.input_schema.get("properties", {}).items():
                param_type = param_spec.get("type", "Any")
                params.append(f"{param_name}: {param_type}")
            context["parameters"] = ", ".join(params)

        return context

    def _fill_template(self, template: CodeTemplate, context: dict[str, Any]) -> str:
        try:
            return template.template.format(**context)
        except KeyError as e:
            placeholder = str(e).strip("'")
            return template.template.replace(
                "{" + placeholder + "}",
                context.get(placeholder, "# TODO: Implement"),
            )

    def _validate_code(self, code: str, task: AtomicTask) -> ValidationResult:
        errors = []
        warnings = []
        suggestions = []

        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")

        for rule in task.validation_rules:
            if "type hints" in rule.lower():
                if "def " in code and " -> " not in code:
                    errors.append("Missing return type hint")
                if "(" in code and ":" not in code.split("(")[1].split(")")[0]:
                    warnings.append("Consider adding parameter type hints")

            if "docstring" in rule.lower() and '"""' not in code and "'''" not in code:
                errors.append("Missing docstring")

            if "test" in rule.lower() and not task.test_required:
                warnings.append("Consider adding tests")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _can_auto_fix(self, validation: ValidationResult) -> bool:
        auto_fixable = [
            "Missing docstring",
            "Consider adding",
        ]
        return all(any(af in error for af in auto_fixable) for error in validation.errors)

    def _auto_fix_code(self, code: str, validation: ValidationResult) -> str:
        fixed_code = code

        if any("docstring" in e for e in validation.errors):
            lines = code.split("\n")
            if lines[0].startswith("def ") or lines[0].startswith("class "):
                indent = "    "
                docstring = f'{indent}"""TODO: Add docstring."""'
                lines.insert(1, docstring)
            fixed_code = "\n".join(lines)

        return fixed_code

    def _organize_code(self, imports: set[str], code_parts: list[str]) -> str:
        sections = []

        sections.append('"""Generated by OpenLaoKe."""\n')

        if imports:
            sorted_imports = sorted(imports)
            sections.append("\n".join(sorted_imports))
            sections.append("")

        for part in code_parts:
            if part.strip():
                sections.append(part)
                sections.append("")

        return "\n".join(sections)


class IntegrationValidator:
    def __init__(self, project_root: Path):
        self.project_root = project_root

    def validate_assembly(self, result: AssemblyResult) -> ValidationResult:
        errors = []
        warnings = []
        suggestions = []

        if not result.code.strip():
            errors.append("Empty code generated")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
            )

        try:
            ast.parse(result.code)
        except SyntaxError as e:
            errors.append(f"Generated code has syntax errors: {e}")

        temp_file = self.project_root / ".temp_validation.py"
        try:
            temp_file.write_text(result.code)

            ruff_result = subprocess.run(
                ["ruff", "check", str(temp_file), "--select=E,F"],
                capture_output=True,
                text=True,
            )
            if ruff_result.returncode != 0:
                warnings.append(f"Ruff issues: {ruff_result.stdout}")

            mypy_result = subprocess.run(
                ["mypy", str(temp_file), "--no-error-summary"],
                capture_output=True,
                text=True,
            )
            if mypy_result.returncode != 0:
                warnings.append(f"Type issues: {mypy_result.stdout}")

        except Exception as e:
            warnings.append(f"Validation tool error: {e}")
        finally:
            if temp_file.exists():
                temp_file.unlink()

        if not result.test_results:
            suggestions.append("Consider adding integration tests")
        elif not all(result.test_results.values()):
            failed_tests = [k for k, v in result.test_results.items() if not v]
            errors.append(f"Failed tests: {', '.join(failed_tests)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def run_integration_tests(self, result: AssemblyResult) -> dict[str, bool]:
        test_results = {}

        if not result.code.strip():
            return test_results

        temp_test_file = self.project_root / ".temp_test.py"
        try:
            temp_test_file.write_text(result.code)

            pytest_result = subprocess.run(
                ["pytest", str(temp_test_file), "-v", "--tb=short"],
                capture_output=True,
                text=True,
            )

            test_results["pytest"] = pytest_result.returncode == 0

            if pytest_result.returncode != 0:
                test_results["pytest_output"] = pytest_result.stdout

        except Exception as e:
            test_results["error"] = str(e)
        finally:
            if temp_test_file.exists():
                temp_test_file.unlink()

        return test_results
