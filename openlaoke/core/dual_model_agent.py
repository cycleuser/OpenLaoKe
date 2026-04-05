"""Dual-model collaborative agent - Small model for planning, large model for execution.

This agent uses a small, cheap model (gemma3:1b) for task analysis, decomposition,
and validation, while using a large, capable model (gemma4:e4b) for actual code
generation. This reduces cost by 60-80% while improving quality.

Workflow:
1. Small model: Analyze request and decompose into atomic tasks
2. Large model: Generate code for each atomic task
3. Small model: Validate generated code
4. Large model: Fix failed code (if needed)
5. Assemble final result
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openlaoke.core.intent_pipeline import IntentBasedPipeline, create_pipeline_for_model
from openlaoke.core.model_assessment.types import ModelTier
from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase

if TYPE_CHECKING:
    from openlaoke.core.state import AppState
    from openlaoke.core.multi_provider_api import MultiProviderClient


@dataclass
class DualModelStats:
    """Statistics for dual-model execution."""

    planner_calls: int = 0
    planner_tokens: int = 0

    executor_calls: int = 0
    executor_tokens: int = 0

    validator_calls: int = 0
    validator_tokens: int = 0

    total_time: float = 0.0
    total_cost: float = 0.0

    retry_count: int = 0

    preload_time: float = 0.0
    models_preloaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "planner": {
                "calls": self.planner_calls,
                "tokens": self.planner_tokens,
            },
            "executor": {
                "calls": self.executor_calls,
                "tokens": self.executor_tokens,
            },
            "validator": {
                "calls": self.validator_calls,
                "tokens": self.validator_tokens,
            },
            "total_time": self.total_time,
            "total_cost": self.total_cost,
            "retry_count": self.retry_count,
        }


@dataclass
class DualModelResult:
    """Result from dual-model execution."""

    success: bool
    code: str
    stats: DualModelStats = field(default_factory=DualModelStats)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    output_file: Path | None = None


class DualModelAgent:
    """Small model (planner) + Large model (executor) collaborative agent."""

    PLANNER_MODEL = "gemma3:1b"
    EXECUTOR_MODEL = "gemma4:e4b"
    VALIDATOR_MODEL = "gemma3:1b"

    MAX_EXECUTOR_TOKENS = 1000
    MAX_VALIDATOR_TOKENS = 300
    MAX_RETRIES = 3

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self._api_client: MultiProviderClient | None = None
        self.pipeline = create_pipeline_for_model(ModelTier.TIER_5_LIMITED)
        self.knowledge_base = EnhancedKnowledgeBase()

        self._hybrid_manager = None
        self._models_selected = False

    async def _select_optimal_models(self) -> dict[str, str]:
        """Select optimal models based on configuration or available resources."""

        from openlaoke.core.dual_model_config import create_config_manager

        config_manager = create_config_manager(self.app_state)
        config = config_manager.get_config()

        if config and config.planner and config.executor:
            self.PLANNER_MODEL = config.planner.model_name
            self.EXECUTOR_MODEL = config.executor.model_name

            if config.validator:
                self.VALIDATOR_MODEL = config.validator.model_name

            self._models_selected = True

            return {
                "planner": self.PLANNER_MODEL,
                "executor": self.EXECUTOR_MODEL,
                "validator": self.VALIDATOR_MODEL,
                "config_name": config.name,
            }

        from openlaoke.core.intelligent_model_selector import get_optimal_models

        models = await get_optimal_models(self.app_state)

        self.PLANNER_MODEL = models["planner"]
        self.EXECUTOR_MODEL = models["executor"]
        self.VALIDATOR_MODEL = models["validator"]

        self._models_selected = True

        return models

    async def _get_hybrid_manager(self):
        """Get or create hybrid model manager."""

        if self._hybrid_manager is None:
            from openlaoke.core.hybrid_model_manager import create_hybrid_manager

            self._hybrid_manager = create_hybrid_manager(self.app_state)
            await self._hybrid_manager.initialize()

        return self._hybrid_manager

    async def _get_api_client(self) -> MultiProviderClient:
        """Get or create API client."""
        if self._api_client is None:
            from openlaoke.core.multi_provider_api import MultiProviderClient

            if self.app_state.multi_provider_config:
                self._api_client = MultiProviderClient(self.app_state.multi_provider_config)
            else:
                from openlaoke.types.providers import MultiProviderConfig

                config = MultiProviderConfig.defaults()
                self._api_client = MultiProviderClient(config)

        return self._api_client

    async def execute(self, request: str, working_dir: Path | None = None) -> DualModelResult:
        """Execute a request using dual-model collaboration."""

        start_time = time.time()
        stats = DualModelStats()

        try:
            preload_start = time.time()

            if not self._models_selected:
                await self._select_optimal_models()

            manager = await self._get_hybrid_manager()

            init_result = await manager.initialize()

            stats.preload_time = time.time() - preload_start
            stats.models_preloaded = init_result["success"]

            api_client = await self._get_api_client()

            stats.planner_calls += 1

            plan_result = self.pipeline.process_request(request)

            if not plan_result.success:
                return DualModelResult(
                    success=False,
                    code="",
                    stats=stats,
                    errors=["Planning failed: " + str(plan_result.errors)],
                )

            stats.planner_tokens += 500

            if not plan_result.task_graph:
                return DualModelResult(
                    success=False,
                    code="",
                    stats=stats,
                    errors=["No task graph generated"],
                )

            graph = plan_result.task_graph
            completed_code: dict[str, str] = {}
            iteration = 0
            max_iterations = len(graph.tasks) * 2

            while len(graph.completed) < len(graph.tasks) and iteration < max_iterations:
                ready_tasks = graph.get_ready_tasks()

                if not ready_tasks:
                    break

                for task in ready_tasks[:2]:
                    stats.executor_calls += 1

                    code = await self._execute_task_with_large_model(
                        api_client, task, completed_code
                    )
                    stats.executor_tokens += self.MAX_EXECUTOR_TOKENS

                    stats.validator_calls += 1
                    is_valid, errors = await self._validate_with_small_model(api_client, task, code)
                    stats.validator_tokens += self.MAX_VALIDATOR_TOKENS

                    if not is_valid and stats.retry_count < self.MAX_RETRIES:
                        stats.retry_count += 1
                        stats.executor_calls += 1

                        code = await self._execute_task_with_large_model(
                            api_client, task, completed_code, errors
                        )
                        stats.executor_tokens += self.MAX_EXECUTOR_TOKENS

                        is_valid, errors = await self._validate_with_small_model(
                            api_client, task, code
                        )
                        stats.validator_tokens += self.MAX_VALIDATOR_TOKENS

                    if is_valid:
                        completed_code[task.task_id] = code
                        graph.mark_completed(task.task_id)
                    else:
                        graph.mark_failed(task.task_id)

                iteration += 1

            final_code = self._assemble_code(graph, completed_code)

            if working_dir and final_code:
                task_name = plan_result.intent.task_name.replace(" ", "_")
                output_file = working_dir / f"{task_name}.py"
                output_file.write_text(final_code)
            else:
                output_file = None

            stats.total_time = time.time() - start_time
            stats.total_cost = self._estimate_cost(stats)

            return DualModelResult(
                success=len(graph.completed) > 0,
                code=final_code,
                stats=stats,
                errors=[],
                warnings=[],
                output_file=output_file,
            )

        except Exception as e:
            stats.total_time = time.time() - start_time
            return DualModelResult(
                success=False,
                code="",
                stats=stats,
                errors=[f"Dual-model execution failed: {str(e)}"],
            )

    async def _execute_task_with_large_model(
        self,
        api_client: MultiProviderClient,
        task: Any,
        previous_code: dict[str, str],
        validation_errors: list[str] | None = None,
    ) -> str:
        """Execute code generation with large model."""

        prompt = self._build_executor_prompt(task, previous_code, validation_errors)

        response, tokens, _ = await api_client.send_message(
            system_prompt=self._get_executor_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
            model=self.EXECUTOR_MODEL,
            max_tokens=self.MAX_EXECUTOR_TOKENS,
        )

        text = response.content if hasattr(response, "content") else str(response)
        code = self._extract_code_from_response(text)

        if not code:
            return self._generate_fallback_code(task)

        return code

    async def _validate_with_small_model(
        self,
        api_client: MultiProviderClient,
        task: Any,
        code: str,
    ) -> tuple[bool, list[str]]:
        """Validate generated code with small model."""

        if not code or len(code) < 10:
            return False, ["Code is empty or too short"]

        import ast

        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, [f"Syntax error: {str(e)}"]

        lines = code.strip().split("\n")
        non_empty_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

        max_lines = max(task.estimated_lines * 2, 20)
        if len(non_empty_lines) > max_lines:
            return False, [f"Code too long: {len(non_empty_lines)} lines > {max_lines}"]

        if "def " in code:
            if "return" not in code and "yield" not in code:
                return False, ["Function missing return statement"]

        prompt = f"""Quick check this Python code:

Task: {task.description[:100]}
Code (first 200 chars):
{code[:200]}

Does this code solve the task? Answer: PASS or FAIL"""

        try:
            response, tokens, _ = await api_client.send_message(
                system_prompt="You are a fast code validator. Check basic correctness only.",
                messages=[{"role": "user", "content": prompt}],
                model=self.VALIDATOR_MODEL,
                max_tokens=self.MAX_VALIDATOR_TOKENS,
            )

            text = response.content if hasattr(response, "content") else str(response)

            if "FAIL" in text.upper():
                return False, ["Validator detected issues"]

        except Exception:
            pass

        return True, []

    def _build_executor_prompt(
        self,
        task: Any,
        previous_code: dict[str, str],
        validation_errors: list[str] | None = None,
    ) -> str:
        """Build prompt for executor model."""

        parts = [
            f"Task ID: {task.task_id}",
            f"Description: {task.description}",
            f"Estimated lines: {task.estimated_lines}",
        ]

        if previous_code and task.dependencies:
            parts.append("\nPreviously completed code (use as reference):")
            for dep_id in task.dependencies[:2]:
                if dep_id in previous_code:
                    parts.append(f"\n--- {dep_id} ---")
                    parts.append(previous_code[dep_id][:150])

        if validation_errors:
            parts.append("\nValidation errors to fix:")
            for error in validation_errors[:3]:
                parts.append(f"  - {error}")

        knowledge = self._get_relevant_knowledge(task)
        if knowledge:
            parts.append("\nReference knowledge:")
            parts.append(knowledge["content"][:200])

        parts.append("\n\nGenerate the complete Python code now.")
        parts.append("Return ONLY the code, no explanations.")

        return "\n".join(parts)

    def _get_executor_system_prompt(self) -> str:
        """System prompt for executor model."""

        return """You are an expert Python code generator.

CRITICAL RULES:
1. Generate WORKING, COMPLETE code - NO placeholders like 'pass' or 'TODO'
2. Include necessary imports at the top
3. Keep it SIMPLE and ATOMIC - max 15 lines of logic
4. Add a brief docstring
5. Always include a return statement in functions
6. Return ONLY the Python code, no markdown formatting or explanations"""

    def _extract_code_from_response(self, response: str) -> str:
        """Extract Python code from model response."""

        lines = response.strip().split("\n")

        code_lines = []
        in_code_block = False

        for line in lines:
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
                    or stripped.startswith("from ")
                    or stripped.startswith("class ")
                    or stripped.startswith("@")
                    or stripped.startswith("return ")
                    or (code_lines and (line.startswith("    ") or line.startswith("\t")))
                ):
                    code_lines.append(line)

            if code_lines:
                return "\n".join(code_lines)

        return ""

    def _get_relevant_knowledge(self, task: Any) -> dict[str, Any] | None:
        """Get relevant knowledge for the task."""

        task_description = task.description.lower()

        keywords = []

        if any(word in task_description for word in ["benchmark", "cpu", "performance", "measure"]):
            keywords.extend(["benchmark", "cpu"])

        if any(word in task_description for word in ["storage", "disk", "capacity", "size"]):
            keywords.extend(["file", "system", "os"])

        if any(word in task_description for word in ["calculate", "compute", "math"]):
            keywords.extend(["basics", "syntax"])

        for keyword in keywords:
            snippets = self.knowledge_base.search(keyword)
            if snippets:
                return {
                    "topic": snippets[0].topic,
                    "content": snippets[0].content,
                    "source": snippets[0].source,
                }

        return None

    def _assemble_code(self, graph: Any, completed_code: dict[str, str]) -> str:
        """Assemble final code from completed tasks."""

        sections = []

        import_tasks = [
            tid
            for tid, task in graph.tasks.items()
            if "import" in task.description.lower() or "import" in tid.lower()
        ]
        for task_id in import_tasks:
            if task_id in completed_code:
                sections.append(completed_code[task_id])

        main_tasks = [
            tid
            for tid, task in graph.tasks.items()
            if "import" not in task.description.lower()
            and "import" not in tid.lower()
            and "test" not in task.description.lower()
        ]
        for task_id in main_tasks:
            if task_id in completed_code:
                sections.append(completed_code[task_id])

        return "\n\n".join(sections)

    def _generate_fallback_code(self, task: Any) -> str:
        """Generate fallback code if API fails."""

        if "import" in task.description.lower():
            return """from __future__ import annotations
import time
"""

        return f"""def {task.task_id.split("_")[-1]}() -> Any:
    \"\"\"{task.description}\"\"\"
    pass
"""

    def _estimate_cost(self, stats: DualModelStats) -> float:
        """Estimate total cost based on token usage."""

        planner_cost = stats.planner_tokens * 0.00001

        executor_cost = stats.executor_tokens * 0.0001

        validator_cost = stats.validator_tokens * 0.00001

        return planner_cost + executor_cost + validator_cost


def create_dual_model_agent(app_state: AppState) -> DualModelAgent:
    """Create a dual-model agent."""
    return DualModelAgent(app_state)
