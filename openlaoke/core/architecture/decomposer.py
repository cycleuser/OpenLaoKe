"""Fine-grained task decomposition for small models.

Breaks down complex projects into atomic, function-level tasks
that even gemma3:1b can implement reliably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlaoke.core.architecture.interfaces import (
    APISpec,
    CodeTemplate,
    ComponentSpec,
    ComponentType,
    estimate_task_complexity,
    get_template_for_component,
    should_decompose_for_model,
)
from openlaoke.core.model_assessment.types import ModelTier


@dataclass
class AtomicTask:
    task_id: str
    description: str
    component_spec: ComponentSpec
    template: CodeTemplate
    dependencies: list[str] = field(default_factory=list)
    estimated_lines: int = 10
    test_required: bool = True
    validation_rules: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    parent_task_id: str | None = None


@dataclass
class TaskGraph:
    root_task_id: str
    tasks: dict[str, AtomicTask] = field(default_factory=dict)
    dependency_edges: dict[str, list[str]] = field(default_factory=dict)
    completed: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)

    def add_task(self, task: AtomicTask) -> None:
        self.tasks[task.task_id] = task
        if task.dependencies:
            self.dependency_edges[task.task_id] = task.dependencies

    def get_ready_tasks(self) -> list[AtomicTask]:
        ready = []
        for task_id, task in self.tasks.items():
            if task_id in self.completed or task_id in self.failed:
                continue

            deps_satisfied = all(dep_id in self.completed for dep_id in task.dependencies)
            if deps_satisfied:
                ready.append(task)
        return ready

    def mark_completed(self, task_id: str) -> None:
        self.completed.add(task_id)

    def mark_failed(self, task_id: str) -> None:
        self.failed.add(task_id)


class FineGrainedDecomposer:
    def __init__(self, model_tier: ModelTier):
        self.model_tier = model_tier
        self.max_lines_per_task = self._get_max_lines()
        self.max_params_per_function = self._get_max_params()
        self.max_complexity = self._get_max_complexity()

    def _get_max_lines(self) -> int:
        limits = {
            ModelTier.TIER_1_ADVANCED: 100,
            ModelTier.TIER_2_CAPABLE: 50,
            ModelTier.TIER_3_MODERATE: 30,
            ModelTier.TIER_4_BASIC: 20,
            ModelTier.TIER_5_LIMITED: 15,
        }
        return limits[self.model_tier]

    def _get_max_params(self) -> int:
        limits = {
            ModelTier.TIER_1_ADVANCED: 10,
            ModelTier.TIER_2_CAPABLE: 7,
            ModelTier.TIER_3_MODERATE: 5,
            ModelTier.TIER_4_BASIC: 4,
            ModelTier.TIER_5_LIMITED: 3,
        }
        return limits[self.model_tier]

    def _get_max_complexity(self) -> int:
        limits = {
            ModelTier.TIER_1_ADVANCED: 20,
            ModelTier.TIER_2_CAPABLE: 15,
            ModelTier.TIER_3_MODERATE: 10,
            ModelTier.TIER_4_BASIC: 7,
            ModelTier.TIER_5_LIMITED: 5,
        }
        return limits[self.model_tier]

    def decompose_function(self, spec: ComponentSpec) -> list[AtomicTask]:
        tasks = []

        if spec.api_spec:
            input_params = spec.api_spec.input_schema.get("properties", {})
            if len(input_params) > self.max_params_per_function:
                param_groups = self._group_parameters(input_params)
                for i, group in enumerate(param_groups):
                    group_spec = self._create_param_group_spec(spec, group, i)
                    task = self._create_atomic_task(group_spec, f"param_group_{i}")
                    tasks.append(task)

        main_task = self._create_atomic_task(spec, "main")
        if len(tasks) > 0:
            main_task.dependencies = [t.task_id for t in tasks]
            for t in tasks:
                t.parent_task_id = main_task.task_id
        tasks.append(main_task)

        if len(spec.test_requirements) > 0:
            test_task = self._create_test_task(spec, tasks[-1])
            test_task.dependencies = [main_task.task_id]
            tasks.append(test_task)

        return tasks

    def decompose_class(self, spec: ComponentSpec) -> list[AtomicTask]:
        tasks = []

        init_spec = ComponentSpec(
            name=f"{spec.name}__init__",
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name=f"{spec.name}_init",
                description=f"Initialize {spec.name}",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
            ),
            test_requirements=["basic test"],
            complexity_score=2,
        )
        init_task = self._create_atomic_task(init_spec, "init")
        tasks.append(init_task)

        method_specs = self._extract_methods_from_spec(spec)
        for method_spec in method_specs:
            method_tasks = self.decompose_function(method_spec)
            for task in method_tasks:
                task.dependencies.append(init_task.task_id)
            tasks.extend(method_tasks)

        class_task = self._create_atomic_task(spec, "class_definition")
        class_task.dependencies = [t.task_id for t in tasks]
        tasks.append(class_task)

        return tasks

    def decompose_module(self, spec: ComponentSpec) -> list[AtomicTask]:
        tasks = []

        imports_task = AtomicTask(
            task_id=f"{spec.name}_imports",
            description=f"Import statements for {spec.name}",
            component_spec=ComponentSpec(
                name=f"{spec.name}_imports",
                component_type=ComponentType.FUNCTION,
                complexity_score=1,
            ),
            template=CodeTemplate(
                name="imports",
                description="Import statements",
                template='"""Module-level imports."""\nfrom __future__ import annotations\n{imports}',
                required_imports=[],
            ),
            estimated_lines=5,
            test_required=False,
        )
        tasks.append(imports_task)

        component_specs = self._extract_components_from_module(spec)
        for comp_spec in component_specs:
            if comp_spec.component_type == ComponentType.FUNCTION:
                comp_tasks = self.decompose_function(comp_spec)
            elif comp_spec.component_type == ComponentType.CLASS:
                comp_tasks = self.decompose_class(comp_spec)
            else:
                comp_tasks = [self._create_atomic_task(comp_spec, "component")]

            for task in comp_tasks:
                task.dependencies.insert(0, imports_task.task_id)
            tasks.extend(comp_tasks)

        exports_task = AtomicTask(
            task_id=f"{spec.name}_exports",
            description=f"Module exports for {spec.name}",
            component_spec=ComponentSpec(
                name=f"{spec.name}_exports",
                component_type=ComponentType.FUNCTION,
                complexity_score=1,
            ),
            template=CodeTemplate(
                name="exports",
                description="Module exports",
                template="\n__all__ = [{exports}]",
                required_imports=[],
            ),
            estimated_lines=3,
            test_required=False,
            dependencies=[t.task_id for t in tasks if t.task_id != imports_task.task_id],
        )
        tasks.append(exports_task)

        return tasks

    def decompose_project(self, project_spec: dict[str, Any]) -> TaskGraph:
        graph = TaskGraph(root_task_id="project_root")

        modules = project_spec.get("modules", [])
        for module_spec_dict in modules:
            module_spec = ComponentSpec(
                name=module_spec_dict["name"],
                component_type=ComponentType.MODULE,
                dependencies=module_spec_dict.get("dependencies", []),
                complexity_score=module_spec_dict.get("complexity", 5),
            )

            module_tasks = self.decompose_module(module_spec)
            for task in module_tasks:
                graph.add_task(task)

        return graph

    def _create_atomic_task(self, spec: ComponentSpec, suffix: str = "") -> AtomicTask:
        task_id = f"{spec.name}_{suffix}" if suffix else spec.name

        template = get_template_for_component(spec.component_type)

        complexity = estimate_task_complexity(spec)
        if should_decompose_for_model(complexity, self.model_tier.value):
            estimated_lines = self.max_lines_per_task // 2
        else:
            estimated_lines = self.max_lines_per_task

        return AtomicTask(
            task_id=task_id,
            description=f"Implement {spec.name} ({spec.component_type.value})",
            component_spec=spec,
            template=template,
            estimated_lines=estimated_lines,
            test_required=True,
            validation_rules=template.validation_rules,
        )

    def _create_test_task(self, spec: ComponentSpec, parent_task: AtomicTask) -> AtomicTask:
        test_spec = ComponentSpec(
            name=f"test_{spec.name}",
            component_type=ComponentType.TEST,
            test_requirements=[],
            complexity_score=1,
        )

        return AtomicTask(
            task_id=f"test_{spec.name}",
            description=f"Test {spec.name}",
            component_spec=test_spec,
            template=get_template_for_component(ComponentType.TEST),
            estimated_lines=15,
            test_required=False,
            parent_task_id=parent_task.task_id,
        )

    def _group_parameters(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        groups = []
        current_group = {}

        for param_name, param_spec in params.items():
            current_group[param_name] = param_spec
            if len(current_group) >= self.max_params_per_function:
                groups.append(current_group)
                current_group = {}

        if current_group:
            groups.append(current_group)

        return groups

    def _create_param_group_spec(
        self, parent_spec: ComponentSpec, group: dict[str, Any], index: int
    ) -> ComponentSpec:
        return ComponentSpec(
            name=f"{parent_spec.name}_params_{index}",
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name=f"{parent_spec.name}_params_{index}",
                description=f"Parameter group {index} for {parent_spec.name}",
                input_schema={"type": "object", "properties": group},
                output_schema=parent_spec.api_spec.output_schema if parent_spec.api_spec else {},
            ),
            test_requirements=["basic test"],
            complexity_score=1,
        )

    def _extract_methods_from_spec(self, spec: ComponentSpec) -> list[ComponentSpec]:
        methods = []

        if spec.api_spec:
            methods.append(
                ComponentSpec(
                    name=f"{spec.name}_process",
                    component_type=ComponentType.FUNCTION,
                    api_spec=APISpec(
                        name=f"{spec.name}_process",
                        description=f"Process method for {spec.name}",
                        input_schema=spec.api_spec.input_schema,
                        output_schema=spec.api_spec.output_schema,
                    ),
                    test_requirements=["basic test"],
                    complexity_score=spec.complexity_score // 2,
                )
            )

        return methods

    def _extract_components_from_module(self, spec: ComponentSpec) -> list[ComponentSpec]:
        components = []

        components.append(
            ComponentSpec(
                name=f"{spec.name}_helper",
                component_type=ComponentType.FUNCTION,
                test_requirements=["basic test"],
                complexity_score=2,
            )
        )

        components.append(
            ComponentSpec(
                name=f"{spec.name}_main_class",
                component_type=ComponentType.CLASS,
                test_requirements=["basic test"],
                complexity_score=spec.complexity_score,
            )
        )

        return components


def create_decomposer_for_model(model_tier: ModelTier) -> FineGrainedDecomposer:
    return FineGrainedDecomposer(model_tier)
