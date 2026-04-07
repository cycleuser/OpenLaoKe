"""Atomic code generator with real API calls for small models.

This version actually calls the model API to generate code,
instead of just filling templates with placeholders.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openlaoke.core.architecture.decomposer import AtomicTask, TaskGraph
from openlaoke.core.code_validator import CodeValidator
from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase
from openlaoke.core.intent_pipeline import IntentBasedPipeline

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class CodeGenerationResult:
    success: bool
    code: str
    task_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    test_passed: bool = False
    retry_needed: bool = False


class AtomicCodeGeneratorWithAPI:
    """Generate code by calling model API for each atomic task."""

    def __init__(
        self,
        pipeline: IntentBasedPipeline,
        app_state: AppState | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.app_state = app_state
        self.validator = CodeValidator()
        self.knowledge_base = EnhancedKnowledgeBase()
        self.completed_code: dict[str, str] = {}
        self.task_attempts: dict[str, int] = {}
        self.max_attempts_per_task = 3
        self._api_client = None

    async def _get_api_client(self):
        """Get or create API client."""
        if self._api_client is None:
            from openlaoke.core.multi_provider_api import MultiProviderClient

            if self.app_state and self.app_state.multi_provider_config:
                self._api_client = MultiProviderClient(self.app_state.multi_provider_config)
            else:
                from openlaoke.types.providers import MultiProviderConfig

                config = MultiProviderConfig.defaults()
                self._api_client = MultiProviderClient(config)

        return self._api_client

    async def generate_code_for_task_async(
        self, task: AtomicTask, previous_code: dict[str, str] | None = None
    ) -> CodeGenerationResult:
        """Generate code for a task by calling the model API."""
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

        try:
            code = await self._generate_with_api(task, previous_code)

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
        except Exception as e:
            return CodeGenerationResult(
                success=False,
                code="",
                task_id=task.task_id,
                errors=[f"API call failed: {str(e)}"],
                retry_needed=self.task_attempts[task.task_id] < self.max_attempts_per_task,
            )

    async def _generate_with_api(self, task: AtomicTask, previous_code: dict[str, str]) -> str:
        """Generate code by calling the model API."""
        api_client = await self._get_api_client()

        model = "gemma3:1b"
        if self.app_state and self.app_state.multi_provider_config:
            model = self.app_state.multi_provider_config.get_active_model()

        system_prompt = self._build_system_prompt(task)
        user_prompt = self._build_user_prompt(task, previous_code)

        messages = [{"role": "user", "content": user_prompt}]

        try:
            response_msg, token_usage, _ = await api_client.send_message(
                system_prompt=system_prompt,
                messages=messages,
                model=model,
                max_tokens=800,
            )

            if hasattr(response_msg, "content"):
                response_text = response_msg.content
            else:
                response_text = str(response_msg)

            code = self._extract_code_from_response(response_text)

            if not code:
                return self._generate_from_template(task)

            return code
        except Exception:
            return self._generate_from_template(task)

    def _build_system_prompt(self, task: AtomicTask) -> str:
        """Build system prompt for code generation."""
        tier_limits = self._get_tier_limits()

        prompt = f"""You are an expert Python code generator. Your task is to generate EXACTLY ONE small, atomic piece of code.

CRITICAL CONSTRAINTS:
- Maximum {tier_limits["max_lines"]} lines of code (excluding imports/docstrings)
- Maximum {tier_limits["max_params"]} parameters per function
- Maximum complexity score: {tier_limits["max_complexity"]}
- You MUST generate WORKING, COMPLETE code - NO placeholders like "pass" or "TODO"
- You MUST include proper imports at the top
- You MUST include a brief docstring
- Return ONLY the code, no explanations

Current task: {task.description}
Estimated lines: {task.estimated_lines}

Generate a complete, working implementation now."""

        return prompt

    def _build_user_prompt(self, task: AtomicTask, previous_code: dict[str, str]) -> str:
        """Build user prompt with task details and context."""
        prompt_parts = [f"Task: {task.task_id}", f"Description: {task.description}"]

        if task.component_spec:
            spec = task.component_spec
            prompt_parts.append(f"Component type: {spec.component_type}")
            prompt_parts.append(f"Component name: {spec.name}")

            if spec.api_spec:
                prompt_parts.append(f"API spec: {spec.api_spec}")

        if previous_code and task.dependencies:
            prompt_parts.append("\nPreviously completed code (use as reference):")
            for dep_id in task.dependencies:
                if dep_id in previous_code:
                    prompt_parts.append(f"\n--- {dep_id} ---")
                    prompt_parts.append(previous_code[dep_id][:200])

        knowledge = self._get_relevant_knowledge(task)
        if knowledge:
            prompt_parts.append("\nReference knowledge (use similar patterns):")
            prompt_parts.append(knowledge["content"][:300])

        prompt_parts.append(
            "\nGenerate the complete code now. Return ONLY code, no markdown formatting."
        )

        return "\n".join(prompt_parts)

    def _get_tier_limits(self) -> dict[str, int]:
        """Get limits based on model tier."""
        from openlaoke.core.model_assessment.types import ModelTier

        tier = self.pipeline.model_tier

        if tier == ModelTier.TIER_5_LIMITED:
            return {
                "max_lines": 15,
                "max_params": 3,
                "max_complexity": 5,
            }
        elif tier == ModelTier.TIER_4_BASIC:
            return {
                "max_lines": 30,
                "max_params": 5,
                "max_complexity": 8,
            }
        else:
            return {
                "max_lines": 100,
                "max_params": 10,
                "max_complexity": 20,
            }

    def _extract_code_from_response(self, response: str) -> str:
        """Extract Python code from model response."""
        lines = response.strip().split("\n")

        code_lines = []
        in_code_block = False

        for _, line in enumerate(lines):
            if line.strip().startswith("```python"):
                in_code_block = True
                continue
            elif line.strip() == "```" and in_code_block:
                in_code_block = False
                continue
            elif in_code_block:
                code_lines.append(line)

        if code_lines:
            return "\n".join(code_lines)

        if "def " in response or "import " in response:
            code_lines = []
            for line in lines:
                stripped = line.strip()
                if (
                    stripped.startswith("def ")
                    or stripped.startswith("import ")
                    or stripped.startswith("class ")
                    or stripped.startswith("from ")
                    or stripped.startswith("@")
                    or stripped.startswith("return ")
                    or stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                    or ":" in stripped
                    or (code_lines and (line.startswith("    ") or line.startswith("\t")))
                ):
                    code_lines.append(line)

            if code_lines:
                return "\n".join(code_lines)

        return ""

    def _generate_from_template(self, task: AtomicTask) -> str:
        """Fallback: generate code from template."""
        template = task.template.template
        context = self._build_context(task)

        try:
            code = template.format(**context)
        except KeyError:
            code = self._fill_template_manually(template, context)

        code = code.strip()
        if not code.endswith("\n"):
            code += "\n"

        return code

    def _get_relevant_knowledge(self, task: AtomicTask) -> dict[str, Any] | None:
        """Get relevant knowledge snippets."""
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

        if any(word in task_description for word in ["storage", "disk", "capacity", "size"]):
            keywords.extend(["file", "system", "os"])

        for keyword in keywords:
            snippets = self.knowledge_base.search(keyword)
            if snippets:
                return {
                    "topic": snippets[0].topic,
                    "content": snippets[0].content,
                    "source": snippets[0].source,
                    "tags": snippets[0].tags,
                }

        return None

    def assemble_final_code(self, task_graph: TaskGraph, completed_code: dict[str, str]) -> str:
        """Assemble final code from completed tasks."""
        code_sections = []

        import_tasks = [
            tid
            for tid, task in task_graph.tasks.items()
            if "import" in task.description.lower() or "import" in task.task_id.lower()
        ]
        for task_id in import_tasks:
            if task_id in completed_code:
                code_sections.append(completed_code[task_id])

        main_tasks = [
            tid
            for tid, task in task_graph.tasks.items()
            if "import" not in task.description.lower()
            and "import" not in task.task_id.lower()
            and "test" not in task.description.lower()
            and "test" not in task.task_id.lower()
        ]
        for task_id in main_tasks:
            if task_id in completed_code:
                code_sections.append(completed_code[task_id])

        return "\n\n".join(code_sections)

    def _build_context(self, task: AtomicTask) -> dict[str, Any]:
        """Build template context."""
        context = {
            "function_name": task.component_spec.name if task.component_spec else "func",
            "class_name": task.component_spec.name if task.component_spec else "Class",
            "parameters": "",
            "return_type": "Any",
            "return_value": "result",
            "docstring": task.description,
            "implementation": "pass",
            "args_doc": "Arguments to be documented",
            "return_doc": "Return value",
            "raises_doc": "Possible exceptions",
            "imports": "import time",
        }

        if task.component_spec and task.component_spec.api_spec:
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
        """Fill template manually."""
        import re

        result = template
        for key, value in context.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))

        result = re.sub(r"\{[^}]+\}", "", result)

        return result

    def _try_auto_fix(self, code: str, errors: list[str]) -> str | None:
        """Try to auto-fix common issues."""
        fixed_code = code

        for error in errors:
            if "Missing return type hint" in error:
                lines = code.split("\n")
                for i, line in enumerate(lines):
                    if line.strip().startswith("def ") and " -> " not in line:
                        len(line) - len(line.lstrip())
                        if "(" in line and ")" in line:
                            fixed_line = line.rstrip() + " -> Any:\n"
                            lines[i] = fixed_line
                fixed_code = "\n".join(lines)

        try:
            ast.parse(fixed_code)
            return fixed_code
        except SyntaxError:
            return None


def create_generator_with_api(
    model_tier: Any,
    working_directory: Path | None = None,
    app_state: AppState | None = None,
) -> AtomicCodeGeneratorWithAPI:
    """Create generator with API support."""
    from openlaoke.core.model_assessment.types import ModelTier

    tier = model_tier if isinstance(model_tier, ModelTier) else ModelTier.TIER_5_LIMITED
    pipeline = IntentBasedPipeline(tier, working_directory)
    return AtomicCodeGeneratorWithAPI(pipeline, app_state)
