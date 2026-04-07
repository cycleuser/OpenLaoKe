"""Atomic code generator for small models.

Generates code one atomic task at a time, ensuring each piece
is correct before moving to the next.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.core.architecture.decomposer import AtomicTask, TaskGraph
from openlaoke.core.code_validator import CodeValidator
from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase
from openlaoke.core.intent_pipeline import IntentBasedPipeline


@dataclass
class CodeGenerationResult:
    success: bool
    code: str
    task_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    test_passed: bool = False
    retry_needed: bool = False


class AtomicCodeGenerator:
    def __init__(self, pipeline: IntentBasedPipeline) -> None:
        self.pipeline = pipeline
        self.validator = CodeValidator()
        self.knowledge_base = EnhancedKnowledgeBase()
        self.completed_code: dict[str, str] = {}
        self.task_attempts: dict[str, int] = {}
        self.max_attempts_per_task = 3

    def generate_code_for_task(
        self, task: AtomicTask, previous_code: dict[str, str] | None = None
    ) -> CodeGenerationResult:
        if previous_code is None:
            previous_code = {}

        if task.task_id not in self.task_attempts:
            self.task_attempts[task.task_id] = 0

        self.task_attempts[task.task_id] += 1

        if self.task_attempts[task.task_id] > self.max_attempts_per_task:
            return CodeGenerationResult(
                success=False,
                code="",
                task_id=task.task_id,
                errors=[
                    f"Max attempts ({self.max_attempts_per_task}) reached for task {task.task_id}"
                ],
                retry_needed=False,
            )

        code = self._generate_from_template(task)

        is_valid, errors = self.pipeline.validate_task_result(task, code)

        if not is_valid:
            fixed_code = self._try_auto_fix(code, errors)
            if fixed_code:
                code = fixed_code
                is_valid, errors = self.pipeline.validate_task_result(task, code)

        return CodeGenerationResult(
            success=is_valid,
            code=code,
            task_id=task.task_id,
            errors=errors if not is_valid else [],
            warnings=[],
            test_passed=False,
            retry_needed=not is_valid
            and self.task_attempts[task.task_id] < self.max_attempts_per_task,
        )

    def assemble_final_code(self, task_graph: TaskGraph, completed_code: dict[str, str]) -> str:
        code_sections = []

        import_tasks = [
            tid for tid, task in task_graph.tasks.items() if "import" in task.description.lower()
        ]
        for task_id in import_tasks:
            if task_id in completed_code:
                code_sections.append(completed_code[task_id])

        main_tasks = [
            tid
            for tid, task in task_graph.tasks.items()
            if "import" not in task.description.lower()
            and "test" not in task.description.lower()
            and "export" not in task.description.lower()
        ]
        for task_id in main_tasks:
            if task_id in completed_code:
                code_sections.append(completed_code[task_id])

        export_tasks = [
            tid for tid, task in task_graph.tasks.items() if "export" in task.description.lower()
        ]
        for task_id in export_tasks:
            if task_id in completed_code:
                code_sections.append(completed_code[task_id])

        return "\n\n".join(code_sections)

    def _build_generation_prompt(self, task: AtomicTask, previous_code: dict[str, str]) -> str:
        base_prompt = self.pipeline.generate_task_prompt(task)

        if previous_code:
            deps_code = []
            for dep_id in task.dependencies:
                if dep_id in previous_code:
                    deps_code.append(f"# Dependency: {dep_id}\n{previous_code[dep_id]}")

            if deps_code:
                base_prompt += "\n\n# Previously completed code:\n" + "\n\n".join(deps_code)

        return base_prompt

    def _generate_from_template(self, task: AtomicTask) -> str:
        template = task.template.template

        context = self._build_context(task)

        knowledge = self._get_relevant_knowledge(task)

        if knowledge:
            knowledge_comments = self._format_knowledge_as_comments(knowledge, task)
            context["implementation"] = knowledge_comments + "\n    pass"
            context["docstring"] = f"{task.description}\n\n{knowledge['content'][:200]}"

        try:
            code = template.format(**context)
        except KeyError:
            code = self._fill_template_manually(template, context)

        if knowledge and "def " in code:
            code = self._inject_knowledge_into_code(code, knowledge)

        code = code.strip()

        if not code.endswith("\n"):
            code += "\n"

        return code

    def _get_relevant_knowledge(self, task: AtomicTask) -> dict[str, Any] | None:
        task_description = task.description.lower()

        keywords = []

        if any(word in task_description for word in ["benchmark", "cpu", "performance", "measure"]):
            keywords.extend(["benchmark", "cpu", "performance"])

        if any(
            word in task_description for word in ["calculate", "compute", "math", "sum", "average"]
        ):
            keywords.extend(["basics", "syntax"])

        if any(word in task_description for word in ["file", "read", "write", "json"]):
            keywords.extend(["file", "io", "json"])

        if any(word in task_description for word in ["class", "struct", "object"]):
            keywords.extend(["class", "struct", "basics"])

        if any(word in task_description for word in ["test", "validate", "check"]):
            keywords.extend(["test", "validation"])

        if any(word in task_description for word in ["error", "exception", "handle"]):
            keywords.extend(["error", "exception"])

        for keyword in keywords:
            snippets = self.knowledge_base.search(keyword)
            if snippets:
                return {
                    "topic": snippets[0].topic,
                    "content": snippets[0].content,
                    "source": snippets[0].source,
                    "tags": snippets[0].tags,
                }

        python_keywords = ["function", "method", "def", "import", "loop", "for", "if"]
        if any(kw in task_description for kw in python_keywords):
            snippets = self.knowledge_base.search("python_basics")
            if snippets:
                return {
                    "topic": snippets[0].topic,
                    "content": snippets[0].content,
                    "source": snippets[0].source,
                    "tags": snippets[0].tags,
                }

        return None

    def _format_knowledge_as_comments(self, knowledge: dict[str, Any], task: AtomicTask) -> str:
        content = knowledge.get("content", "")
        lines = content.strip().split("\n")

        relevant_lines = []
        for line in lines:
            if any(
                keyword in line.lower()
                for keyword in ["example", "def ", "class ", "import ", "for ", "if ", "return"]
            ):
                relevant_lines.append(line)
            if len(relevant_lines) >= 5:
                break

        if relevant_lines:
            return "    # " + "\n    # ".join(relevant_lines)

        return "    # Implementation needed"

    def _inject_knowledge_into_code(self, code: str, knowledge: dict[str, Any]) -> str:
        lines = code.split("\n")

        injected_lines = []
        function_indent = 0

        for i, line in enumerate(lines):
            injected_lines.append(line)

            if "def " in line and line.strip().endswith(":"):
                function_indent = len(line) - len(line.lstrip())

                next_idx = i + 1
                if next_idx < len(lines):
                    next_line = lines[next_idx]
                    next_indent = len(next_line) - len(next_line.lstrip())

                    if next_indent > function_indent and not next_line.strip().startswith('"""'):
                        knowledge_hint = self._extract_key_points(knowledge)
                        if knowledge_hint:
                            injected_lines.append(
                                " " * (function_indent + 4) + f"# {knowledge_hint}"
                            )

        return "\n".join(injected_lines)

    def _extract_key_points(self, knowledge: dict[str, Any]) -> str:
        content = knowledge.get("content", "")

        if "def " in content:
            match = content.find("def ")
            if match != -1:
                example_line = content[match : match + 100].split("\n")[0]
                return f"Example: {example_line.strip()}"

        if "import " in content:
            imports = [line.strip() for line in content.split("\n") if "import " in line][:2]
            if imports:
                return f"Use: {', '.join(imports)}"

        return f"Reference: {knowledge.get('source', 'Documentation')}"

    def _build_context(self, task: AtomicTask) -> dict[str, Any]:
        context = {
            "function_name": task.component_spec.name,
            "class_name": task.component_spec.name,
            "parameters": "",
            "return_type": "Any",
            "return_value": "result",
            "docstring": task.description,
            "implementation": "pass",
            "args_doc": "Arguments to be documented",
            "return_doc": "Return value",
            "raises_doc": "Possible exceptions",
            "init_params": "",
            "init_implementation": "pass",
            "methods": "pass",
            "attrs_doc": "Attributes",
            "imports": "import time",
            "exports": "'__all__'",
            "arrange_code": "# Arrange",
            "act_code": "# Act",
            "assert_code": "# Assert",
            "test_case": "basic",
            "test_description": "Basic test case",
            "fields": "field: str = Field(description='Example field')",
            "validators": "@validator('field')\ndef check_field(cls, v):\n    return v",
            "path": "/path",
            "method": "get",
            "response_model": "dict",
            "error_doc": "Error description",
        }

        if task.component_spec.api_spec:
            api = task.component_spec.api_spec
            params = []
            for param_name, param_spec in api.input_schema.get("properties", {}).items():
                param_type = param_spec.get("type", "Any")
                params.append(f"{param_name}: {param_type}")
            context["parameters"] = ", ".join(params)

            output_type = api.output_schema.get("type", "Any")
            context["return_type"] = output_type

        return context

    def _fill_template_manually(self, template: str, context: dict[str, Any]) -> str:
        import re

        result = template

        for key, value in context.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))

        result = re.sub(r"\{[^}]+\}", "# TODO: Implement", result)

        return result

    def _try_auto_fix(self, code: str, errors: list[str]) -> str | None:
        fixed_code = code

        for error in errors:
            if "Missing return type hint" in error:
                lines = code.split("\n")
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") and " -> " not in line:
                        indent = len(line) - len(line.lstrip())
                        if "(" in line and ")" in line:
                            fixed_line = line.rstrip() + " -> Any:\n"
                            lines[i] = fixed_line
                fixed_code = "\n".join(lines)

            elif "Missing docstring" in error:
                lines = code.split("\n")
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") or line.strip().startswith("class "):
                        indent = len(line) - len(line.lstrip())
                        docstring = (
                            " " * (indent + 4)
                            + '"""\n'
                            + " " * (indent + 4)
                            + "TODO: Add docstring.\n"
                            + " " * (indent + 4)
                            + '"""\n'
                        )
                        lines.insert(i + 1, docstring)
                        break
                fixed_code = "\n".join(lines)

        try:
            ast.parse(fixed_code)
            return fixed_code
        except SyntaxError:
            return None


def create_generator_for_tier(
    model_tier: Any, working_directory: Path | None = None
) -> AtomicCodeGenerator:
    from openlaoke.core.model_assessment.types import ModelTier

    tier = model_tier if isinstance(model_tier, ModelTier) else ModelTier.TIER_5_LIMITED
    pipeline = IntentBasedPipeline(tier, working_directory)
    return AtomicCodeGenerator(pipeline)
