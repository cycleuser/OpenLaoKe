"""Workflow orchestrator for automated task coordination."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openlaoke.core.hyperauto.types import SubTask, SubTaskStatus, WorkflowContext

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class WorkflowPhase(StrEnum):
    """Phases of the workflow execution."""

    ANALYZE = "analyze"
    PLAN = "plan"
    INIT = "init"
    SEARCH = "search"
    CREATE = "create"
    IMPLEMENT = "implement"
    TEST = "test"
    REVIEW = "review"
    FINALIZE = "finalize"


class RecoveryStrategy(StrEnum):
    """Strategies for error recovery."""

    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    ROLLBACK = "rollback"
    ADAPT = "adapt"


@dataclass
class TaskTree:
    """Hierarchical representation of decomposed tasks."""

    root_task: str
    subtasks: list[SubTask] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    priority_order: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_task": self.root_task,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "dependencies": self.dependencies,
            "priority_order": self.priority_order,
        }


@dataclass
class DependencyEdge:
    """Edge in the dependency graph."""

    source: str
    target: str
    dependency_type: str = "hard"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyGraph:
    """Graph representing task dependencies."""

    nodes: list[str] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)
    adjacency: dict[str, list[str]] = field(default_factory=dict)
    reverse_adjacency: dict[str, list[str]] = field(default_factory=dict)

    def get_dependencies(self, task_id: str) -> list[str]:
        return self.reverse_adjacency.get(task_id, [])

    def get_dependents(self, task_id: str) -> list[str]:
        return self.adjacency.get(task_id, [])

    def topological_sort(self) -> list[str]:
        visited = set()
        stack: list[str] = []
        temp_marks = set()

        def visit(node: str) -> None:
            if node in temp_marks:
                raise ValueError(f"Circular dependency detected at {node}")
            if node not in visited:
                temp_marks.add(node)
                for dep in self.get_dependencies(node):
                    visit(dep)
                temp_marks.remove(node)
                visited.add(node)
                stack.append(node)

        for node in self.nodes:
            if node not in visited:
                visit(node)

        return stack

    def detect_cycles(self) -> list[list[str]]:
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str], visited: set[str]) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in self.adjacency.get(node, []):
                dfs(neighbor, path, visited)
            path.pop()

        visited: set[str] = set()
        for node in self.nodes:
            if node not in visited:
                dfs(node, [], visited)

        return cycles

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": [
                {"source": e.source, "target": e.target, "type": e.dependency_type}
                for e in self.edges
            ],
            "adjacency": self.adjacency,
            "reverse_adjacency": self.reverse_adjacency,
        }


@dataclass
class ExecutionStep:
    """Single step in the execution plan."""

    task_id: str
    phase: WorkflowPhase
    priority: int = 0
    parallel_group: int = 0
    estimated_duration: float = 0.0
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Complete execution plan for a workflow."""

    steps: list[ExecutionStep] = field(default_factory=list)
    parallel_groups: dict[int, list[str]] = field(default_factory=dict)
    total_estimated_duration: float = 0.0
    critical_path: list[str] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {
                    "task_id": s.task_id,
                    "phase": s.phase.value,
                    "priority": s.priority,
                    "parallel_group": s.parallel_group,
                    "estimated_duration": s.estimated_duration,
                    "dependencies": s.dependencies,
                }
                for s in self.steps
            ],
            "parallel_groups": self.parallel_groups,
            "total_estimated_duration": self.total_estimated_duration,
            "critical_path": self.critical_path,
            "checkpoints": self.checkpoints,
        }


@dataclass
class RecoveryAction:
    """Action to recover from an error."""

    strategy: RecoveryStrategy
    retry_count: int = 0
    max_retries: int = 3
    alternative_task: str | None = None
    rollback_to: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressInfo:
    """Real-time progress information."""

    current_phase: WorkflowPhase = WorkflowPhase.ANALYZE
    current_task: str = ""
    completed_tasks: int = 0
    total_tasks: int = 0
    percentage: float = 0.0
    elapsed_time: float = 0.0
    estimated_remaining: float = 0.0
    active_tasks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_phase": self.current_phase.value,
            "current_task": self.current_task,
            "completed_tasks": self.completed_tasks,
            "total_tasks": self.total_tasks,
            "percentage": self.percentage,
            "elapsed_time": self.elapsed_time,
            "estimated_remaining": self.estimated_remaining,
            "active_tasks": self.active_tasks,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class ExecutionResult:
    """Result of executing a single task."""

    task_id: str
    success: bool
    output: Any = None
    error: str | None = None
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowResult:
    """Complete result of a workflow execution."""

    workflow_id: str
    success: bool
    task_tree: TaskTree
    execution_plan: ExecutionPlan
    execution_results: list[ExecutionResult] = field(default_factory=list)
    total_duration: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "success": self.success,
            "task_tree": self.task_tree.to_dict(),
            "execution_plan": self.execution_plan.to_dict(),
            "execution_results": [r.to_dict() for r in self.execution_results],
            "total_duration": self.total_duration,
            "error": self.error,
            "metadata": self.metadata,
        }


class WorkflowOrchestrator:
    """Orchestrates automated workflow execution with intelligent coordination."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.context = WorkflowContext()
        self._progress = ProgressInfo()
        self._execution_lock = asyncio.Lock()
        self._task_results: dict[str, ExecutionResult] = {}
        self._start_time: float = 0.0

    def decompose_task(self, task: str) -> TaskTree:
        subtasks = self._analyze_and_decompose(task)
        dependencies = self._infer_dependencies(subtasks)
        priority_order = self._calculate_priority_order(subtasks, dependencies)

        return TaskTree(
            root_task=task,
            subtasks=subtasks,
            dependencies=dependencies,
            priority_order=priority_order,
        )

    def _analyze_and_decompose(self, task: str) -> list[SubTask]:
        keywords = task.lower().split()
        subtasks: list[SubTask] = []

        if any(kw in keywords for kw in ["create", "new", "build", "develop"]):
            subtasks.extend(self._create_development_subtasks(task))
        elif any(kw in keywords for kw in ["fix", "bug", "issue", "error"]):
            subtasks.extend(self._create_fix_subtasks(task))
        elif any(kw in keywords for kw in ["refactor", "improve", "optimize"]):
            subtasks.extend(self._create_refactor_subtasks(task))
        elif any(kw in keywords for kw in ["test", "verify", "validate"]):
            subtasks.extend(self._create_test_subtasks(task))
        elif any(kw in keywords for kw in ["analyze", "review", "check"]):
            subtasks.extend(self._create_analysis_subtasks(task))
        else:
            subtasks.extend(self._create_generic_subtasks(task))

        return subtasks

    def _create_development_subtasks(self, task: str) -> list[SubTask]:
        return [
            SubTask(
                name="analyze_requirements",
                description=f"Analyze requirements for: {task}",
                status=SubTaskStatus.PENDING,
                priority=10,
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="search_references",
                description="Search for similar implementations and references",
                status=SubTaskStatus.PENDING,
                priority=9,
                dependencies=["analyze_requirements"],
                metadata={"phase": WorkflowPhase.SEARCH.value},
            ),
            SubTask(
                name="design_architecture",
                description="Design architecture and structure",
                status=SubTaskStatus.PENDING,
                priority=8,
                dependencies=["search_references"],
                metadata={"phase": WorkflowPhase.PLAN.value},
            ),
            SubTask(
                name="create_structure",
                description="Create project structure and files",
                status=SubTaskStatus.PENDING,
                priority=7,
                dependencies=["design_architecture"],
                metadata={"phase": WorkflowPhase.CREATE.value},
            ),
            SubTask(
                name="implement_core",
                description="Implement core functionality",
                status=SubTaskStatus.PENDING,
                priority=6,
                dependencies=["create_structure"],
                metadata={"phase": WorkflowPhase.IMPLEMENT.value},
            ),
            SubTask(
                name="write_tests",
                description="Write tests for implemented features",
                status=SubTaskStatus.PENDING,
                priority=5,
                dependencies=["implement_core"],
                metadata={"phase": WorkflowPhase.TEST.value},
            ),
            SubTask(
                name="review_code",
                description="Review code quality and standards",
                status=SubTaskStatus.PENDING,
                priority=4,
                dependencies=["write_tests"],
                metadata={"phase": WorkflowPhase.REVIEW.value},
            ),
            SubTask(
                name="finalize",
                description="Finalize and clean up",
                status=SubTaskStatus.PENDING,
                priority=3,
                dependencies=["review_code"],
                metadata={"phase": WorkflowPhase.FINALIZE.value},
            ),
        ]

    def _create_fix_subtasks(self, task: str) -> list[SubTask]:
        return [
            SubTask(
                name="reproduce_issue",
                description=f"Reproduce the issue: {task}",
                status=SubTaskStatus.PENDING,
                priority=10,
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="identify_root_cause",
                description="Identify root cause of the issue",
                status=SubTaskStatus.PENDING,
                priority=9,
                dependencies=["reproduce_issue"],
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="search_similar_fixes",
                description="Search for similar fixes and solutions",
                status=SubTaskStatus.PENDING,
                priority=8,
                dependencies=["identify_root_cause"],
                metadata={"phase": WorkflowPhase.SEARCH.value},
            ),
            SubTask(
                name="implement_fix",
                description="Implement the fix",
                status=SubTaskStatus.PENDING,
                priority=7,
                dependencies=["search_similar_fixes"],
                metadata={"phase": WorkflowPhase.IMPLEMENT.value},
            ),
            SubTask(
                name="verify_fix",
                description="Verify the fix resolves the issue",
                status=SubTaskStatus.PENDING,
                priority=6,
                dependencies=["implement_fix"],
                metadata={"phase": WorkflowPhase.TEST.value},
            ),
            SubTask(
                name="review_fix",
                description="Review fix for side effects",
                status=SubTaskStatus.PENDING,
                priority=5,
                dependencies=["verify_fix"],
                metadata={"phase": WorkflowPhase.REVIEW.value},
            ),
        ]

    def _create_refactor_subtasks(self, task: str) -> list[SubTask]:
        return [
            SubTask(
                name="analyze_codebase",
                description=f"Analyze codebase structure for: {task}",
                status=SubTaskStatus.PENDING,
                priority=10,
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="identify_improvements",
                description="Identify improvement opportunities",
                status=SubTaskStatus.PENDING,
                priority=9,
                dependencies=["analyze_codebase"],
                metadata={"phase": WorkflowPhase.PLAN.value},
            ),
            SubTask(
                name="implement_refactor",
                description="Implement refactoring changes",
                status=SubTaskStatus.PENDING,
                priority=8,
                dependencies=["identify_improvements"],
                metadata={"phase": WorkflowPhase.IMPLEMENT.value},
            ),
            SubTask(
                name="verify_behavior",
                description="Verify behavior remains unchanged",
                status=SubTaskStatus.PENDING,
                priority=7,
                dependencies=["implement_refactor"],
                metadata={"phase": WorkflowPhase.TEST.value},
            ),
            SubTask(
                name="review_changes",
                description="Review refactoring changes",
                status=SubTaskStatus.PENDING,
                priority=6,
                dependencies=["verify_behavior"],
                metadata={"phase": WorkflowPhase.REVIEW.value},
            ),
        ]

    def _create_test_subtasks(self, task: str) -> list[SubTask]:
        return [
            SubTask(
                name="analyze_test_requirements",
                description=f"Analyze test requirements: {task}",
                status=SubTaskStatus.PENDING,
                priority=10,
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="create_test_plan",
                description="Create test plan and cases",
                status=SubTaskStatus.PENDING,
                priority=9,
                dependencies=["analyze_test_requirements"],
                metadata={"phase": WorkflowPhase.PLAN.value},
            ),
            SubTask(
                name="implement_tests",
                description="Implement test cases",
                status=SubTaskStatus.PENDING,
                priority=8,
                dependencies=["create_test_plan"],
                metadata={"phase": WorkflowPhase.CREATE.value},
            ),
            SubTask(
                name="run_tests",
                description="Run and validate tests",
                status=SubTaskStatus.PENDING,
                priority=7,
                dependencies=["implement_tests"],
                metadata={"phase": WorkflowPhase.TEST.value},
            ),
            SubTask(
                name="analyze_coverage",
                description="Analyze test coverage",
                status=SubTaskStatus.PENDING,
                priority=6,
                dependencies=["run_tests"],
                metadata={"phase": WorkflowPhase.REVIEW.value},
            ),
        ]

    def _create_analysis_subtasks(self, task: str) -> list[SubTask]:
        return [
            SubTask(
                name="gather_information",
                description=f"Gather information for: {task}",
                status=SubTaskStatus.PENDING,
                priority=10,
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="analyze_data",
                description="Analyze collected data",
                status=SubTaskStatus.PENDING,
                priority=9,
                dependencies=["gather_information"],
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="generate_report",
                description="Generate analysis report",
                status=SubTaskStatus.PENDING,
                priority=8,
                dependencies=["analyze_data"],
                metadata={"phase": WorkflowPhase.FINALIZE.value},
            ),
        ]

    def _create_generic_subtasks(self, task: str) -> list[SubTask]:
        return [
            SubTask(
                name="analyze_task",
                description=f"Analyze task requirements: {task}",
                status=SubTaskStatus.PENDING,
                priority=10,
                metadata={"phase": WorkflowPhase.ANALYZE.value},
            ),
            SubTask(
                name="plan_execution",
                description="Plan execution strategy",
                status=SubTaskStatus.PENDING,
                priority=9,
                dependencies=["analyze_task"],
                metadata={"phase": WorkflowPhase.PLAN.value},
            ),
            SubTask(
                name="execute_task",
                description="Execute planned actions",
                status=SubTaskStatus.PENDING,
                priority=8,
                dependencies=["plan_execution"],
                metadata={"phase": WorkflowPhase.IMPLEMENT.value},
            ),
            SubTask(
                name="verify_results",
                description="Verify execution results",
                status=SubTaskStatus.PENDING,
                priority=7,
                dependencies=["execute_task"],
                metadata={"phase": WorkflowPhase.TEST.value},
            ),
            SubTask(
                name="finalize_task",
                description="Finalize and clean up",
                status=SubTaskStatus.PENDING,
                priority=6,
                dependencies=["verify_results"],
                metadata={"phase": WorkflowPhase.FINALIZE.value},
            ),
        ]

    def _infer_dependencies(self, subtasks: list[SubTask]) -> dict[str, list[str]]:
        dependencies: dict[str, list[str]] = {}
        for task in subtasks:
            dependencies[task.id] = task.dependencies.copy()
        return dependencies

    def _calculate_priority_order(
        self, subtasks: list[SubTask], dependencies: dict[str, list[str]]
    ) -> list[str]:
        visited: set[str] = set()
        order: list[str] = []

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            visited.add(task_id)
            for dep_id in dependencies.get(task_id, []):
                visit(dep_id)
            order.append(task_id)

        for task in sorted(subtasks, key=lambda t: t.priority, reverse=True):
            visit(task.id)

        return order

    def analyze_dependencies(self, tasks: list[SubTask]) -> DependencyGraph:
        graph = DependencyGraph()

        for task in tasks:
            graph.nodes.append(task.id)
            graph.adjacency[task.id] = []
            graph.reverse_adjacency[task.id] = []

        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in graph.nodes:
                    graph.edges.append(
                        DependencyEdge(source=dep_id, target=task.id, dependency_type="hard")
                    )
                    graph.adjacency[dep_id].append(task.id)
                    graph.reverse_adjacency[task.id].append(dep_id)

        return graph

    def create_execution_plan(self, graph: DependencyGraph) -> ExecutionPlan:
        plan = ExecutionPlan()
        topo_order = graph.topological_sort()

        task_map = {task.id: task for task in self.context.sub_tasks}
        dependency_depths: dict[str, int] = {}

        for task_id in topo_order:
            deps = graph.get_dependencies(task_id)
            if deps:
                max_dep_depth = max(dependency_depths.get(dep, 0) for dep in deps)
                dependency_depths[task_id] = max_dep_depth + 1
            else:
                dependency_depths[task_id] = 0

        parallel_groups: dict[int, list[str]] = {}
        for task_id, depth in dependency_depths.items():
            if depth not in parallel_groups:
                parallel_groups[depth] = []
            parallel_groups[depth].append(task_id)

        for group_num in sorted(parallel_groups.keys()):
            group_tasks = parallel_groups[group_num]
            for task_id in group_tasks:
                task = task_map.get(task_id)
                if task:
                    phase = WorkflowPhase(task.metadata.get("phase", WorkflowPhase.IMPLEMENT.value))
                    plan.steps.append(
                        ExecutionStep(
                            task_id=task_id,
                            phase=phase,
                            priority=task.priority,
                            parallel_group=group_num,
                            dependencies=graph.get_dependencies(task_id),
                        )
                    )

        plan.parallel_groups = parallel_groups
        plan.total_estimated_duration = len(plan.steps) * 2.0
        plan.critical_path = self._find_critical_path(graph, dependency_depths)
        plan.checkpoints = self._identify_checkpoints(plan.steps)

        return plan

    def _find_critical_path(self, graph: DependencyGraph, depths: dict[str, int]) -> list[str]:
        if not depths:
            return []

        max_depth = max(depths.values())
        critical_path: list[str] = []

        current_depth = max_depth
        current_nodes = [n for n, d in depths.items() if d == current_depth]

        while current_depth >= 0 and current_nodes:
            node = current_nodes[0]
            critical_path.insert(0, node)
            current_depth -= 1
            current_nodes = [n for n, d in depths.items() if d == current_depth]

        return critical_path

    def _identify_checkpoints(self, steps: list[ExecutionStep]) -> list[str]:
        checkpoints: list[str] = []
        seen_phases: set[WorkflowPhase] = set()

        for step in steps:
            if step.phase not in seen_phases:
                seen_phases.add(step.phase)
                checkpoints.append(step.task_id)

        return checkpoints

    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        async with self._execution_lock:
            self._start_time = time.time()
            results: list[ExecutionResult] = []

            for group_num in sorted(plan.parallel_groups.keys()):
                task_ids = plan.parallel_groups[group_num]
                group_results = await self._execute_parallel_tasks(task_ids)
                results.extend(group_results)

                for result in group_results:
                    self._task_results[result.task_id] = result
                    if result.success:
                        self._progress.completed_tasks += 1
                    else:
                        self._progress.errors.append(
                            result.error or f"Task {result.task_id} failed"
                        )

                self._progress.percentage = (
                    self._progress.completed_tasks / max(len(plan.steps), 1)
                ) * 100

            success = all(r.success for r in results)
            return ExecutionResult(
                task_id="workflow_execution",
                success=success,
                output=[r.to_dict() for r in results],
                duration=time.time() - self._start_time,
            )

    async def _execute_parallel_tasks(self, task_ids: list[str]) -> list[ExecutionResult]:
        tasks = [self._execute_single_task(tid) for tid in task_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        execution_results: list[ExecutionResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                execution_results.append(
                    ExecutionResult(
                        task_id=task_ids[i],
                        success=False,
                        error=f"Exception during execution: {result}",
                    )
                )
            elif isinstance(result, ExecutionResult):
                execution_results.append(result)
            else:
                execution_results.append(
                    ExecutionResult(
                        task_id=task_ids[i],
                        success=False,
                        error=f"Unexpected result type: {type(result)}",
                    )
                )
        return execution_results

    async def _execute_single_task(self, task_id: str) -> ExecutionResult:
        task = next((t for t in self.context.sub_tasks if t.id == task_id), None)
        if not task:
            return ExecutionResult(
                task_id=task_id, success=False, error=f"Task {task_id} not found"
            )

        task.status = SubTaskStatus.RUNNING
        self._progress.current_task = task_id
        self._progress.active_tasks.append(task_id)

        start_time = time.time()
        try:
            result = await self._execute_task_action(task)
            task.status = SubTaskStatus.COMPLETED
            task.result = result

            return ExecutionResult(
                task_id=task_id,
                success=True,
                output=result,
                duration=time.time() - start_time,
            )
        except Exception as e:
            task.status = SubTaskStatus.FAILED
            task.error = str(e)

            recovery = self.handle_error(e, task)
            if (
                recovery.strategy == RecoveryStrategy.RETRY
                and recovery.retry_count < recovery.max_retries
            ):
                return await self._retry_task(task, recovery)

            return ExecutionResult(
                task_id=task_id,
                success=False,
                error=str(e),
                duration=time.time() - start_time,
            )
        finally:
            if task_id in self._progress.active_tasks:
                self._progress.active_tasks.remove(task_id)

    async def _execute_task_action(self, task: SubTask) -> Any:
        phase = WorkflowPhase(task.metadata.get("phase", WorkflowPhase.IMPLEMENT.value))
        self._progress.current_phase = phase

        await asyncio.sleep(0.1)

        return {"status": "completed", "task": task.name, "phase": phase.value}

    async def _retry_task(self, task: SubTask, recovery: RecoveryAction) -> ExecutionResult:
        task.status = SubTaskStatus.PENDING
        recovery.retry_count += 1

        return await self._execute_single_task(task.id)

    def track_progress(self) -> ProgressInfo:
        if self._start_time > 0:
            self._progress.elapsed_time = time.time() - self._start_time

        total = len(self.context.sub_tasks)
        if total > 0 and self._progress.completed_tasks > 0:
            avg_time_per_task = self._progress.elapsed_time / self._progress.completed_tasks
            remaining_tasks = total - self._progress.completed_tasks
            self._progress.estimated_remaining = avg_time_per_task * remaining_tasks

        self._progress.total_tasks = total

        return self._progress

    def handle_error(self, error: Exception, task: SubTask) -> RecoveryAction:
        error_msg = str(error)

        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                message=f"Timeout error, will retry: {error_msg}",
                max_retries=2,
            )
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                message=f"Network error, will retry: {error_msg}",
                max_retries=3,
            )
        elif "permission" in error_msg.lower() or "access denied" in error_msg.lower():
            return RecoveryAction(
                strategy=RecoveryStrategy.ABORT,
                message=f"Permission error: {error_msg}",
            )
        elif "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
            return RecoveryAction(
                strategy=RecoveryStrategy.ADAPT,
                message=f"Resource not found, will adapt: {error_msg}",
            )
        else:
            return RecoveryAction(
                strategy=RecoveryStrategy.SKIP,
                message=f"Unrecoverable error, skipping task: {error_msg}",
            )

    def validate_result(self, task: SubTask, result: Any) -> bool:
        if result is None:
            return False

        if isinstance(result, dict):
            if result.get("status") == "completed":
                return True
            if result.get("success") is True:
                return True
            if result.get("error"):
                return False

        if isinstance(result, str):
            return len(result) > 0 and "error" not in result.lower()

        if isinstance(result, (list, tuple)):
            return len(result) > 0

        return True

    async def run_full_workflow(self, task: str) -> WorkflowResult:
        workflow_id = uuid4().hex[:12]
        self.context = WorkflowContext(
            session_id=workflow_id,
            original_request=task,
            start_time=time.time(),
        )

        try:
            task_tree = self.decompose_task(task)
            self.context.sub_tasks = task_tree.subtasks

            graph = self.analyze_dependencies(task_tree.subtasks)
            cycles = graph.detect_cycles()
            if cycles:
                return WorkflowResult(
                    workflow_id=workflow_id,
                    success=False,
                    task_tree=task_tree,
                    execution_plan=ExecutionPlan(),
                    error=f"Circular dependencies detected: {cycles}",
                )

            plan = self.create_execution_plan(graph)
            exec_result = await self.execute_plan(plan)

            all_results = list(self._task_results.values())
            success = exec_result.success and all(
                self.validate_result(
                    next((t for t in task_tree.subtasks if t.id == r.task_id), SubTask()),
                    r.output,
                )
                for r in all_results
                if r.success
            )

            self.context.end_time = time.time()

            return WorkflowResult(
                workflow_id=workflow_id,
                success=success,
                task_tree=task_tree,
                execution_plan=plan,
                execution_results=all_results,
                total_duration=self.context.end_time - self.context.start_time,
                metadata={"context": self.context.to_dict()},
            )

        except Exception as e:
            self.context.end_time = time.time()
            return WorkflowResult(
                workflow_id=workflow_id,
                success=False,
                task_tree=TaskTree(root_task=task),
                execution_plan=ExecutionPlan(),
                error=str(e),
                total_duration=time.time() - self.context.start_time,
            )

    def get_context(self) -> WorkflowContext:
        return self.context

    def reset(self) -> None:
        self.context = WorkflowContext()
        self._progress = ProgressInfo()
        self._task_results.clear()
        self._start_time = 0.0
