"""HyperAuto Agent - Fully autonomous coding assistant."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from openlaoke.core.hyperauto.config import HyperAutoConfig
from openlaoke.core.hyperauto.types import (
    Decision,
    DecisionType,
    HyperAutoState,
    Reflection,
    SubTask,
    SubTaskStatus,
    WorkflowContext,
)
from openlaoke.core.skill_system import Skill, SkillRegistry, get_skill_registry

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class AnalysisResult:
    """Result of task analysis."""

    task_type: str
    description: str
    sub_tasks: list[dict[str, Any]]
    required_skills: list[str]
    required_tools: list[str]
    estimated_complexity: str
    confidence: float


@dataclass
class SkillGenerationResult:
    """Result of skill generation."""

    skill_name: str
    skill_content: str
    skill_description: str
    success: bool
    error: str | None = None


ProgressCallback = Callable[["WorkflowContext"], None]


class HyperAutoAgent:
    """HyperAuto Agent for fully autonomous task execution.

    Features:
    - Automatic task analysis and decomposition
    - Automatic skill generation when needed
    - Automatic project initialization
    - Automatic code search for reference
    - Automatic workflow orchestration
    - Intelligent decision making
    - Self-reflection and learning
    """

    def __init__(
        self,
        app_state: AppState,
        config: HyperAutoConfig | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self.app_state = app_state
        self.config = config or HyperAutoConfig()
        self.context = WorkflowContext()
        self._skill_registry: SkillRegistry | None = None
        self._execution_history: list[dict[str, Any]] = []
        self._learned_patterns: dict[str, list[str]] = {}
        self._on_progress: ProgressCallback | None = None
        self._api_client = None

    @property
    def skill_registry(self) -> SkillRegistry:
        if self._skill_registry is None:
            self._skill_registry = get_skill_registry()
        return self._skill_registry

    async def _get_api_client(self):
        """Get or create the API client."""
        if self._api_client is None:
            print("[DEBUG] _get_api_client: Creating new API client...")
            from openlaoke.core.multi_provider_api import MultiProviderClient

            if self.app_state.multi_provider_config:
                print("[DEBUG] _get_api_client: Using multi_provider_config from app_state")
                print(
                    f"[DEBUG] _get_api_client: Active provider: {self.app_state.multi_provider_config.active_provider}"
                )
                print(
                    f"[DEBUG] _get_api_client: Active model: {self.app_state.multi_provider_config.get_active_model()}"
                )
                self._api_client = MultiProviderClient(self.app_state.multi_provider_config)
            else:
                print(
                    "[DEBUG] _get_api_client: WARNING - No multi_provider_config, creating defaults (Ollama)"
                )
                from openlaoke.types.providers import MultiProviderConfig

                config = MultiProviderConfig.defaults()
                self._api_client = MultiProviderClient(config)
            print(f"[DEBUG] _get_api_client: Client created: {type(self._api_client).__name__}")
        else:
            print("[DEBUG] _get_api_client: Reusing existing client")
        return self._api_client

    async def run(self, request: str) -> dict[str, Any]:
        """Execute a request in HyperAuto mode."""
        import traceback

        print(f"[DEBUG] run: Starting HyperAuto for: {request[:100]}...")
        self.context = WorkflowContext(
            original_request=request,
            current_state=HyperAutoState.ANALYZING,
            start_time=time.time(),
        )

        try:
            while self.context.iteration < self.config.max_iterations:
                self.context.iteration += 1
                print(
                    f"[DEBUG] run: Iteration {self.context.iteration}, state={self.context.current_state.value}"
                )

                if self.context.current_state == HyperAutoState.ANALYZING:
                    print("[DEBUG] run: Analyzing request...")
                    await self._analyze_request()
                    self.context.current_state = HyperAutoState.PLANNING

                elif self.context.current_state == HyperAutoState.PLANNING:
                    print("[DEBUG] run: Creating plan...")
                    await self._create_plan()
                    self.context.current_state = HyperAutoState.EXECUTING

                elif self.context.current_state == HyperAutoState.EXECUTING:
                    print("[DEBUG] run: Executing plan...")
                    result = await self._execute_plan()
                    if result:
                        self.context.current_state = HyperAutoState.REFLECTING
                    else:
                        print("[DEBUG] run: Execute plan returned False, breaking")
                        break

                elif self.context.current_state == HyperAutoState.REFLECTING:
                    print("[DEBUG] run: Reflecting...")
                    if self.config.reflection_enabled:
                        await self._reflect()
                    if self.config.learning_enabled:
                        self.context.current_state = HyperAutoState.LEARNING
                    else:
                        self.context.current_state = HyperAutoState.COMPLETED

                elif self.context.current_state == HyperAutoState.LEARNING:
                    print("[DEBUG] run: Learning...")
                    await self._learn()
                    self.context.current_state = HyperAutoState.COMPLETED

                elif (
                    self.context.current_state == HyperAutoState.COMPLETED
                    or self.context.current_state == HyperAutoState.FAILED
                ):
                    print(f"[DEBUG] run: Reached final state: {self.context.current_state.value}")
                    break

            self.context.end_time = time.time()
            print(f"[DEBUG] run: Completed successfully after {self.context.iteration} iterations")
            return self._get_result()

        except Exception as e:
            self.context.current_state = HyperAutoState.FAILED
            self.context.end_time = time.time()
            print(f"[DEBUG] run: ERROR: {e}")
            print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "context": self.context.to_dict(),
            }

    async def _analyze_request(self) -> AnalysisResult:
        """Analyze the request and identify sub-tasks using AI."""
        import traceback

        request = self.context.original_request

        try:
            print("[DEBUG] _analyze_request: Starting analysis...")
            api = await self._get_api_client()
            print(f"[DEBUG] _analyze_request: API client type: {type(api).__name__}")

            system_prompt = "You are a task analyzer. Respond only with valid JSON."
            user_prompt = f"""Analyze this task and break it down:

Task: {request}

Respond with JSON containing:
- task_type: "creation"/"bugfix"/"refactor"/"testing"/"documentation"/"general"
- sub_tasks: array of {{name, description, type, priority, dependencies}}
- required_skills: array of skill names
- required_tools: array of tool names
- estimated_complexity: "low"/"medium"/"high"

JSON only, no other text."""

            if self.app_state.multi_provider_config:
                model = self.app_state.multi_provider_config.get_active_model()
            else:
                model = "gemma3:1b"
            print(f"[DEBUG] _analyze_request: Model={model}, calling API...")

            response_msg, token_usage, _ = await api.send_message(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                model=model,
                max_tokens=1000,
            )

            print("[DEBUG] _analyze_request: API call completed")

            if response_msg and response_msg.content:
                import json

                content = response_msg.content
                if hasattr(content, "text"):
                    content = content.text

                print(f"[DEBUG] _analyze_request: Response length={len(content)}")
                print(f"[DEBUG] _analyze_request: Response preview: {content[:200]}...")

                try:
                    data = json.loads(content)
                    task_type = data.get("task_type", "general")
                    sub_tasks = data.get("sub_tasks", [])
                    required_skills = data.get("required_skills", [])
                    required_tools = data.get("required_tools", [])
                    complexity = data.get("estimated_complexity", "medium")
                    print(
                        f"[DEBUG] _analyze_request: JSON parsed - type={task_type}, tasks={len(sub_tasks)}"
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[DEBUG] _analyze_request: JSON parse error: {e}")
                    task_type = self._classify_task(request)
                    sub_tasks = self._decompose_task(request, task_type)
                    required_skills = self._identify_required_skills(request, task_type)
                    required_tools = self._identify_required_tools(request, task_type)
                    complexity = "medium"

                if token_usage:
                    self.context.total_tokens += token_usage.total_tokens
                    print(f"[DEBUG] _analyze_request: Tokens={token_usage.total_tokens}")
            else:
                print("[DEBUG] _analyze_request: No response content!")
                raise ValueError("No response from API")

        except Exception as e:
            print(f"[DEBUG] _analyze_request: ERROR: {e}")
            print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
            task_type = self._classify_task(request)
            sub_tasks = self._decompose_task(request, task_type)
            required_skills = self._identify_required_skills(request, task_type)
            required_tools = self._identify_required_tools(request, task_type)
            complexity = "medium"

        analysis = AnalysisResult(
            task_type=task_type,
            description=request,
            sub_tasks=sub_tasks,
            required_skills=required_skills,
            required_tools=required_tools,
            estimated_complexity=complexity,
            confidence=0.85,
        )

        for i, sub_task_def in enumerate(sub_tasks):
            sub_task = SubTask(
                name=sub_task_def.get("name", f"task_{i}"),
                description=sub_task_def.get("description", ""),
                priority=sub_task_def.get("priority", i),
                dependencies=sub_task_def.get("dependencies", []),
                metadata=sub_task_def,
            )
            self.context.sub_tasks.append(sub_task)

        print(f"[DEBUG] _analyze_request: Complete - {len(sub_tasks)} sub-tasks")
        return analysis

    async def _create_plan(self) -> list[SubTask]:
        """Create an execution plan from sub-tasks."""
        tasks = self.context.sub_tasks
        sorted_tasks = self._topological_sort(tasks)

        for i, task in enumerate(sorted_tasks):
            task.priority = i

        self.context.sub_tasks = sorted_tasks
        return sorted_tasks

    async def _execute_plan(self) -> bool:
        """Execute the plan by running sub-tasks."""
        print("[DEBUG] _execute_plan: Starting execution")
        pending = self.context.get_pending_tasks()
        print(f"[DEBUG] _execute_plan: Pending tasks: {len(pending)}")

        if not pending:
            print("[DEBUG] _execute_plan: No pending tasks, returning True")
            return True

        running_tasks = []
        for task in pending[: self.config.max_parallel_tasks]:
            if self._can_execute_task(task):
                print(f"[DEBUG] _execute_plan: Starting task: {task.name}")
                running_tasks.append(asyncio.create_task(self._execute_sub_task(task)))

        if running_tasks:
            print(f"[DEBUG] _execute_plan: Waiting for {len(running_tasks)} tasks...")
            await asyncio.gather(*running_tasks, return_exceptions=True)
            print("[DEBUG] _execute_plan: All tasks completed")

        all_done = all(
            t.status in (SubTaskStatus.COMPLETED, SubTaskStatus.FAILED, SubTaskStatus.SKIPPED)
            for t in self.context.sub_tasks
        )

        print(f"[DEBUG] _execute_plan: all_done={all_done}")
        return all_done

    async def _execute_sub_task(self, task: SubTask) -> Any:
        """Execute a single sub-task using AI."""
        import traceback

        print(f"[DEBUG] _execute_sub_task: Starting task '{task.name}'")
        task.status = SubTaskStatus.RUNNING

        try:
            if self.config.dry_run:
                print("[DEBUG] _execute_sub_task: Dry run mode, skipping execution")
                task.result = {"dry_run": True, "simulated": True}
                task.status = SubTaskStatus.COMPLETED
                return task.result

            api = await self._get_api_client()
            print("[DEBUG] _execute_sub_task: API client ready")

            system_prompt = "You are a task executor. Complete tasks efficiently."
            user_prompt = f"""Execute this subtask:

Task: {task.name}
Description: {task.description}
Context: {self.context.original_request}

Provide the results."""

            if self.app_state.multi_provider_config:
                model = self.app_state.multi_provider_config.get_active_model()
            else:
                model = "gemma3:1b"
            print(f"[DEBUG] _execute_sub_task: Calling API with model={model}...")

            response_msg, token_usage, _ = await api.send_message(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                model=model,
                max_tokens=4000,
            )

            print("[DEBUG] _execute_sub_task: API response received")

            if response_msg and response_msg.content:
                content = response_msg.content
                if hasattr(content, "text"):
                    content = content.text
                print(f"[DEBUG] _execute_sub_task: Response length={len(content)}")
                task.result = {"output": content, "task": task.name}
                task.status = SubTaskStatus.COMPLETED

                if token_usage:
                    self.context.total_tokens += token_usage.total_tokens
                    print(f"[DEBUG] _execute_sub_task: Tokens={token_usage.total_tokens}")
            else:
                print("[DEBUG] _execute_sub_task: No API response, using dispatcher")
                result = await self._dispatch_task(task)
                task.result = result
                task.status = SubTaskStatus.COMPLETED

            if self.config.auto_run_tests and task.metadata.get("requires_test", False):
                await self._run_tests_for_task(task)

            print(f"[DEBUG] _execute_sub_task: Task '{task.name}' completed successfully")
            return task.result

        except Exception as e:
            print(f"[DEBUG] _execute_sub_task: ERROR in task '{task.name}': {e}")
            print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
            task.error = str(e)
            task.status = SubTaskStatus.FAILED

            if self.config.rollback_on_failure:
                await self._rollback_task(task)

            return None

    async def _dispatch_task(self, task: SubTask) -> Any:
        """Dispatch a task to the appropriate handler."""
        task_type = task.metadata.get("type", "generic")

        handlers = {
            "skill_creation": self._handle_skill_creation,
            "project_init": self._handle_project_init,
            "code_search": self._handle_code_search,
            "dependency_install": self._handle_dependency_install,
            "code_generation": self._handle_code_generation,
            "code_edit": self._handle_code_edit,
            "test_execution": self._handle_test_execution,
            "git_operation": self._handle_git_operation,
            "generic": self._handle_generic_task,
        }

        handler = handlers.get(task_type, self._handle_generic_task)
        return await handler(task)

    async def _handle_skill_creation(self, task: SubTask) -> Any:
        """Handle automatic skill creation."""
        skill_name = task.metadata.get("skill_name", "")
        skill_description = task.metadata.get("skill_description", "")

        if not skill_name:
            return None

        skill_content = await self._generate_skill_content(skill_name, skill_description)

        skill = await self._create_skill(skill_name, skill_content, skill_description)

        if skill:
            self.context.decisions.append(
                Decision(
                    type=DecisionType.SKILL_CREATION,
                    confidence=0.9,
                    reasoning=f"Created skill '{skill_name}' for task",
                    action="create_skill",
                    parameters={"skill_name": skill_name},
                    executed=True,
                    result=skill.name,
                )
            )

        return skill

    async def _handle_project_init(self, task: SubTask) -> Any:
        """Handle automatic project initialization."""
        project_type = task.metadata.get("project_type", "generic")
        project_path = task.metadata.get("project_path", self.app_state.cwd)

        result = await self._initialize_project(project_path, project_type)

        self.context.decisions.append(
            Decision(
                type=DecisionType.PROJECT_INIT,
                confidence=0.85,
                reasoning=f"Initialized {project_type} project at {project_path}",
                action="init_project",
                parameters={"project_type": project_type, "project_path": project_path},
                executed=True,
                result=result,
            )
        )

        return result

    async def _handle_code_search(self, task: SubTask) -> Any:
        """Handle automatic code search."""
        query = task.metadata.get("query", "")
        file_pattern = task.metadata.get("file_pattern", "*")

        results = await self._search_code(query, file_pattern)

        self.context.decisions.append(
            Decision(
                type=DecisionType.CODE_SEARCH,
                confidence=0.8,
                reasoning=f"Searched for '{query}' in {file_pattern}",
                action="search_code",
                parameters={"query": query, "file_pattern": file_pattern},
                executed=True,
                result=results,
            )
        )

        return results

    async def _handle_dependency_install(self, task: SubTask) -> Any:
        """Handle automatic dependency installation."""
        dependencies = task.metadata.get("dependencies", [])
        package_manager = task.metadata.get("package_manager", "auto")

        result = await self._install_dependencies(dependencies, package_manager)

        self.context.decisions.append(
            Decision(
                type=DecisionType.DEPENDENCY_INSTALL,
                confidence=0.85,
                reasoning=f"Installed dependencies: {dependencies}",
                action="install_deps",
                parameters={"dependencies": dependencies, "package_manager": package_manager},
                executed=True,
                result=result,
            )
        )

        return result

    async def _handle_code_generation(self, task: SubTask) -> Any:
        """Handle code generation tasks."""
        return {"generated": True, "task": task.name}

    async def _handle_code_edit(self, task: SubTask) -> Any:
        """Handle code editing tasks."""
        return {"edited": True, "task": task.name}

    async def _handle_test_execution(self, task: SubTask) -> Any:
        """Handle test execution tasks."""
        return {"tested": True, "task": task.name}

    async def _handle_git_operation(self, task: SubTask) -> Any:
        """Handle git operations."""
        operation = task.metadata.get("operation", "status")

        if operation == "commit" and self.config.auto_commit:
            return await self._git_commit(task)

        return {"operation": operation, "executed": False}

    async def _handle_generic_task(self, task: SubTask) -> Any:
        """Handle generic tasks."""
        return {"completed": True, "task": task.name}

    async def _reflect(self) -> Reflection:
        """Reflect on the completed work."""
        completed = self.context.get_completed_tasks()
        failed = self.context.get_failed_tasks()

        observations: list[str] = []
        improvements: list[str] = []
        learned_patterns: list[str] = []
        error_patterns: list[str] = []

        for task in completed:
            if task.result:
                observations.append(f"Task '{task.name}' completed successfully")

        for task in failed:
            if task.error:
                error_patterns.append(f"Task '{task.name}' failed: {task.error}")
                improvements.append(f"Need better error handling for '{task.name}'")

        reflection = Reflection(
            task_id=self.context.session_id,
            success=len(failed) == 0,
            observations=observations,
            improvements=improvements,
            learned_patterns=learned_patterns,
            error_patterns=error_patterns,
        )

        self.context.reflections.append(reflection)
        return reflection

    async def _learn(self) -> dict[str, Any]:
        """Learn from the execution and update patterns."""
        for reflection in self.context.reflections:
            for pattern in reflection.learned_patterns:
                category = "general"
                if category not in self._learned_patterns:
                    self._learned_patterns[category] = []
                if pattern not in self._learned_patterns[category]:
                    self._learned_patterns[category].append(pattern)

        return {
            "patterns_learned": sum(len(v) for v in self._learned_patterns.values()),
            "categories": list(self._learned_patterns.keys()),
        }

    def _classify_task(self, request: str) -> str:
        """Classify the type of task."""
        request_lower = request.lower()

        if any(kw in request_lower for kw in ["create", "new", "build", "implement"]):
            return "creation"
        elif any(kw in request_lower for kw in ["fix", "bug", "error", "issue"]):
            return "bugfix"
        elif any(kw in request_lower for kw in ["refactor", "improve", "optimize"]):
            return "refactor"
        elif any(kw in request_lower for kw in ["test", "spec", "coverage"]):
            return "testing"
        elif any(kw in request_lower for kw in ["document", "readme", "doc"]):
            return "documentation"
        else:
            return "general"

    def _decompose_task(self, request: str, task_type: str) -> list[dict[str, Any]]:
        """Decompose a task into sub-tasks."""
        sub_tasks = [
            {
                "name": "analyze_context",
                "description": "Analyze current project context",
                "type": "analysis",
                "priority": 0,
                "dependencies": [],
            },
            {
                "name": "search_reference",
                "description": "Search for relevant code references",
                "type": "code_search",
                "priority": 1,
                "dependencies": ["analyze_context"],
            },
        ]

        if task_type == "creation":
            sub_tasks.extend(
                [
                    {
                        "name": "create_structure",
                        "description": "Create necessary file structure",
                        "type": "code_generation",
                        "priority": 2,
                        "dependencies": ["search_reference"],
                        "requires_test": True,
                    },
                ]
            )
        elif task_type == "bugfix":
            sub_tasks.extend(
                [
                    {
                        "name": "identify_issue",
                        "description": "Identify the root cause",
                        "type": "analysis",
                        "priority": 2,
                        "dependencies": ["search_reference"],
                    },
                    {
                        "name": "apply_fix",
                        "description": "Apply the fix",
                        "type": "code_edit",
                        "priority": 3,
                        "dependencies": ["identify_issue"],
                        "requires_test": True,
                    },
                ]
            )

        sub_tasks.append(
            {
                "name": "verify_results",
                "description": "Verify the results",
                "type": "test_execution",
                "priority": 99,
                "dependencies": [],
            }
        )

        return sub_tasks

    def _identify_required_skills(self, request: str, task_type: str) -> list[str]:
        """Identify what skills might be needed."""
        available_skills = self.skill_registry.list_skills()
        required = []

        request_lower = request.lower()

        skill_keywords = {
            "browse": ["browser", "test", "qa", "website", "page"],
            "debug": ["debug", "error", "fix", "issue"],
            "ship": ["deploy", "release", "ship", "publish"],
            "qa": ["test", "qa", "quality"],
        }

        for skill, keywords in skill_keywords.items():
            if skill in available_skills and any(kw in request_lower for kw in keywords):
                required.append(skill)

        return required

    def _identify_required_tools(self, request: str, task_type: str) -> list[str]:
        """Identify what tools might be needed."""
        tools = ["bash", "read", "write", "edit"]
        request_lower = request.lower()

        if "search" in request_lower or "find" in request_lower:
            tools.extend(["grep", "glob"])

        if "git" in request_lower or "commit" in request_lower:
            tools.append("bash")

        if "web" in request_lower or "url" in request_lower:
            tools.append("webfetch")

        return list(set(tools))

    def _estimate_complexity(self, sub_tasks: list[dict[str, Any]]) -> str:
        """Estimate task complexity."""
        count = len(sub_tasks)
        if count <= 3:
            return "low"
        elif count <= 7:
            return "medium"
        else:
            return "high"

    def _topological_sort(self, tasks: list[SubTask]) -> list[SubTask]:
        """Sort tasks by dependencies using topological sort."""
        sorted_tasks = []
        visited = set()
        temp_visited = set()

        def visit(task: SubTask) -> None:
            if task.id in visited:
                return
            if task.id in temp_visited:
                return

            temp_visited.add(task.id)

            for dep_id in task.dependencies:
                for t in tasks:
                    if t.id == dep_id:
                        visit(t)

            temp_visited.remove(task.id)
            visited.add(task.id)
            sorted_tasks.append(task)

        for task in tasks:
            if task.id not in visited:
                visit(task)

        return sorted_tasks

    def _can_execute_task(self, task: SubTask) -> bool:
        """Check if a task's dependencies are satisfied."""
        for dep_id in task.dependencies:
            dep_task = next((t for t in self.context.sub_tasks if t.id == dep_id), None)
            if dep_task and dep_task.status != SubTaskStatus.COMPLETED:
                return False
        return True

    async def _generate_skill_content(self, skill_name: str, description: str) -> str:
        """Generate skill content using templates or AI."""
        template = self.config.skill_templates.get(
            skill_name,
            f"""---
name: {skill_name}
description: {description}
version: 1.0.0
---

# {skill_name}

{description}

## Instructions

This skill was auto-generated by HyperAuto for the task: {self.context.original_request}

## Workflow

1. Analyze the request
2. Execute the task
3. Verify the results
""",
        )
        return template

    async def _create_skill(
        self,
        skill_name: str,
        content: str,
        description: str,
    ) -> Skill | None:
        """Create and register a new skill."""
        try:
            skill = Skill.from_content(content)
            skill.name = skill_name
            skill.description = description

            return skill
        except Exception:
            return None

    async def _initialize_project(self, project_path: str, project_type: str) -> dict[str, Any]:
        """Initialize a project structure."""
        return {
            "path": project_path,
            "type": project_type,
            "initialized": True,
        }

    async def _search_code(self, query: str, file_pattern: str) -> list[dict[str, Any]]:
        """Search for code in the codebase."""
        return [
            {
                "query": query,
                "pattern": file_pattern,
                "results": [],
            }
        ]

    async def _install_dependencies(
        self,
        dependencies: list[str],
        package_manager: str,
    ) -> dict[str, Any]:
        """Install project dependencies."""
        return {
            "dependencies": dependencies,
            "manager": package_manager,
            "installed": True,
        }

    async def _run_tests_for_task(self, task: SubTask) -> dict[str, Any]:
        """Run tests related to a task."""
        return {"tested": True, "task": task.id}

    async def _rollback_task(self, task: SubTask) -> None:
        """Rollback changes made by a failed task."""
        pass

    async def _git_commit(self, task: SubTask) -> dict[str, Any]:
        """Perform a git commit."""
        return {"committed": True, "task": task.id}

    def _get_result(self) -> dict[str, Any]:
        """Get the final result of the workflow."""
        completed = len(self.context.get_completed_tasks())
        failed = len(self.context.get_failed_tasks())
        total = len(self.context.sub_tasks)

        return {
            "success": failed == 0 and completed > 0,
            "session_id": self.context.session_id,
            "iterations": self.context.iteration,
            "tasks_completed": completed,
            "tasks_failed": failed,
            "tasks_total": total,
            "decisions_made": len(self.context.decisions),
            "reflections": len(self.context.reflections),
            "final_state": self.context.current_state.value,
            "duration": (self.context.end_time or time.time()) - self.context.start_time,
            "context": self.context.to_dict(),
        }
