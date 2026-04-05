"""Convert programming intent to ComponentSpec for task decomposition.

This module bridges the gap between natural language understanding
and the fine-grained architecture decomposition system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlaoke.core.architecture.interfaces import (
    APISpec,
    ComponentSpec,
    ComponentType,
)
from openlaoke.core.intent_parser import (
    IntentType,
    ProgrammingIntent,
    TaskComplexity,
)
from openlaoke.core.model_assessment.types import ModelTier


@dataclass
class SpecGenerationResult:
    success: bool
    specs: list[ComponentSpec]
    errors: list[str]
    warnings: list[str]
    suggestions: list[str]


class IntentToSpecConverter:
    def __init__(self, model_tier: ModelTier = ModelTier.TIER_5_LIMITED) -> None:
        self.model_tier = model_tier
        self.max_lines_per_spec = self._get_max_lines_for_tier(model_tier)
        self.max_params_per_spec = self._get_max_params_for_tier(model_tier)

    def convert(self, intent: ProgrammingIntent) -> SpecGenerationResult:
        if intent.intent_type == IntentType.UNKNOWN:
            return SpecGenerationResult(
                success=False,
                specs=[],
                errors=["Cannot convert unknown intent to spec"],
                warnings=[],
                suggestions=["Please clarify what you want to create"],
            )

        specs = []

        if intent.intent_type == IntentType.WRITE_PROGRAM:
            specs = self._convert_program_intent(intent)
        elif intent.intent_type == IntentType.WRITE_FUNCTION:
            specs = self._convert_function_intent(intent)
        elif intent.intent_type == IntentType.WRITE_CLASS:
            specs = self._convert_class_intent(intent)
        elif intent.intent_type in [
            IntentType.DEBUG_CODE,
            IntentType.REFACTOR_CODE,
            IntentType.TEST_CODE,
        ]:
            specs = self._convert_modification_intent(intent)
        elif intent.intent_type in [
            IntentType.ANALYZE_CODE,
            IntentType.DOCUMENT_CODE,
        ]:
            specs = self._convert_analysis_intent(intent)

        errors = []
        warnings = []
        suggestions = []

        for spec in specs:
            if spec.api_spec is None:
                continue

            if len(spec.api_spec.input_schema.get("properties", {})) > self.max_params_per_spec:
                warnings.append(
                    f"Spec '{spec.name}' has too many parameters "
                    f"({len(spec.api_spec.input_schema.get('properties', {}))} > {self.max_params_per_spec}). "
                    f"Will be further decomposed."
                )

            if spec.complexity_score > self.max_lines_per_spec:
                warnings.append(
                    f"Spec '{spec.name}' complexity ({spec.complexity_score}) "
                    f"exceeds model limit ({self.max_lines_per_spec}). "
                    f"Will be decomposed into smaller tasks."
                )

        return SpecGenerationResult(
            success=len(specs) > 0,
            specs=specs,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _convert_program_intent(self, intent: ProgrammingIntent) -> list[ComponentSpec]:
        specs = []

        module_spec = self._create_module_spec(intent)

        main_component_spec = self._create_main_component_spec(intent)

        helper_specs = self._create_helper_specs(intent)

        specs.append(module_spec)
        specs.append(main_component_spec)
        specs.extend(helper_specs)

        test_spec = self._create_test_spec(intent, specs)
        specs.append(test_spec)

        return specs

    def _convert_function_intent(self, intent: ProgrammingIntent) -> list[ComponentSpec]:
        specs = []

        function_spec = self._create_function_spec(intent)

        helper_specs = self._create_helper_specs_for_function(intent, function_spec)

        specs.append(function_spec)
        specs.extend(helper_specs)

        test_spec = self._create_test_spec(intent, specs)
        specs.append(test_spec)

        return specs

    def _convert_class_intent(self, intent: ProgrammingIntent) -> list[ComponentSpec]:
        specs = []

        class_spec = self._create_class_spec(intent)

        method_specs = self._create_method_specs(intent, class_spec)

        specs.append(class_spec)
        specs.extend(method_specs)

        test_spec = self._create_test_spec(intent, specs)
        specs.append(test_spec)

        return specs

    def _convert_modification_intent(self, intent: ProgrammingIntent) -> list[ComponentSpec]:
        specs = []

        analysis_spec = self._create_analysis_spec(intent)

        modification_spec = self._create_modification_spec(intent)

        validation_spec = self._create_validation_spec(intent)

        specs.append(analysis_spec)
        specs.append(modification_spec)
        specs.append(validation_spec)

        return specs

    def _convert_analysis_intent(self, intent: ProgrammingIntent) -> list[ComponentSpec]:
        specs = []

        analysis_spec = self._create_analysis_spec(intent)

        report_spec = self._create_report_spec(intent)

        specs.append(analysis_spec)
        specs.append(report_spec)

        return specs

    def _create_module_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        module_name = intent.task_name.replace(" ", "_").replace("-", "_")

        return ComponentSpec(
            name=module_name,
            component_type=ComponentType.MODULE,
            api_spec=APISpec(
                name=module_name,
                description=f"Module for {intent.description}",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object", "properties": {}},
            ),
            test_requirements=["Module structure validation", "Import tests"],
            complexity_score=self._estimate_module_complexity(intent),
        )

    def _create_main_component_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        component_name = f"{intent.task_name.replace(' ', '_')}_main"

        input_schema = self._build_input_schema(intent)
        output_schema = self._build_output_schema(intent)

        component_type = self._determine_component_type(intent)

        complexity = self._estimate_component_complexity(intent)

        return ComponentSpec(
            name=component_name,
            component_type=component_type,
            api_spec=APISpec(
                name=component_name,
                description=f"Main {intent.task_name} component",
                input_schema=input_schema,
                output_schema=output_schema,
            ),
            test_requirements=[
                "Basic functionality test",
                "Edge case test",
                "Error handling test",
            ],
            complexity_score=complexity,
        )

    def _create_helper_specs(self, intent: ProgrammingIntent) -> list[ComponentSpec]:
        helper_specs = []

        for requirement in intent.requirements:
            if self._should_create_helper_for_requirement(requirement):
                helper_name = self._extract_helper_name_from_requirement(requirement)

                helper_spec = ComponentSpec(
                    name=helper_name,
                    component_type=ComponentType.FUNCTION,
                    api_spec=APISpec(
                        name=helper_name,
                        description=f"Helper function for {requirement}",
                        input_schema={"type": "object", "properties": {}},
                        output_schema={"type": "object", "properties": {}},
                    ),
                    test_requirements=["Helper test"],
                    complexity_score=3,
                )

                helper_specs.append(helper_spec)

        if intent.inputs:
            input_handler_spec = ComponentSpec(
                name="handle_input",
                component_type=ComponentType.FUNCTION,
                api_spec=APISpec(
                    name="handle_input",
                    description="Process and validate input",
                    input_schema=self._build_input_schema(intent),
                    output_schema={"type": "object", "properties": {}},
                ),
                test_requirements=["Input validation test"],
                complexity_score=2,
            )
            helper_specs.append(input_handler_spec)

        if intent.outputs:
            output_formatter_spec = ComponentSpec(
                name="format_output",
                component_type=ComponentType.FUNCTION,
                api_spec=APISpec(
                    name="format_output",
                    description="Format and prepare output",
                    input_schema={"type": "object", "properties": {}},
                    output_schema=self._build_output_schema(intent),
                ),
                test_requirements=["Output formatting test"],
                complexity_score=2,
            )
            helper_specs.append(output_formatter_spec)

        return helper_specs

    def _create_function_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        function_name = intent.task_name.replace(" ", "_").replace("-", "_")

        input_schema = self._build_input_schema(intent)
        output_schema = self._build_output_schema(intent)

        complexity = self._estimate_function_complexity(intent)

        return ComponentSpec(
            name=function_name,
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name=function_name,
                description=intent.description,
                input_schema=input_schema,
                output_schema=output_schema,
            ),
            test_requirements=[
                "Function correctness test",
                "Input validation test",
                "Output verification test",
            ],
            complexity_score=complexity,
        )

    def _create_helper_specs_for_function(
        self, intent: ProgrammingIntent, main_spec: ComponentSpec
    ) -> list[ComponentSpec]:
        helper_specs = []

        if main_spec.api_spec and len(main_spec.api_spec.input_schema.get("properties", {})) > 2:
            input_params = main_spec.api_spec.input_schema.get("properties", {})
            param_groups = self._split_params_into_groups(input_params)

            for i, group in enumerate(param_groups):
                helper_spec = ComponentSpec(
                    name=f"{main_spec.name}_validate_params_{i}",
                    component_type=ComponentType.FUNCTION,
                    api_spec=APISpec(
                        name=f"{main_spec.name}_validate_params_{i}",
                        description=f"Validate parameter group {i}",
                        input_schema={"type": "object", "properties": group},
                        output_schema={"type": "object", "properties": {}},
                    ),
                    test_requirements=["Validation test"],
                    complexity_score=2,
                    dependencies=[main_spec.name],
                )
                helper_specs.append(helper_spec)

        return helper_specs

    def _create_class_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        class_name = intent.task_name.replace(" ", "_").replace("-", "_").capitalize()

        complexity = self._estimate_class_complexity(intent)

        return ComponentSpec(
            name=class_name,
            component_type=ComponentType.CLASS,
            api_spec=APISpec(
                name=class_name,
                description=f"Class for {intent.description}",
                input_schema=self._build_input_schema(intent),
                output_schema=self._build_output_schema(intent),
            ),
            test_requirements=[
                "Class initialization test",
                "Method functionality test",
                "State management test",
            ],
            complexity_score=complexity,
        )

    def _create_method_specs(
        self, intent: ProgrammingIntent, class_spec: ComponentSpec
    ) -> list[ComponentSpec]:
        method_specs = []

        method_names = ["__init__", "process", "validate", "execute", "cleanup"]

        for method_name in method_names[: self.max_params_per_spec]:
            method_spec = ComponentSpec(
                name=f"{class_spec.name}_{method_name}",
                component_type=ComponentType.FUNCTION,
                api_spec=APISpec(
                    name=method_name,
                    description=f"{method_name} method for {class_spec.name}",
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object", "properties": {}},
                ),
                test_requirements=["Method test"],
                complexity_score=2,
                dependencies=[class_spec.name],
            )
            method_specs.append(method_spec)

        return method_specs

    def _create_test_spec(
        self, intent: ProgrammingIntent, component_specs: list[ComponentSpec]
    ) -> ComponentSpec:
        test_name = f"test_{intent.task_name.replace(' ', '_')}"

        return ComponentSpec(
            name=test_name,
            component_type=ComponentType.TEST,
            test_requirements=[],
            complexity_score=1,
            dependencies=[
                spec.name for spec in component_specs if spec.component_type != ComponentType.TEST
            ],
        )

    def _create_analysis_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        return ComponentSpec(
            name=f"analyze_{intent.task_name.replace(' ', '_')}",
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name="analyze",
                description=f"Analyze code for {intent.task_name}",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object", "properties": {"issues": {"type": "array"}}},
            ),
            test_requirements=["Analysis test"],
            complexity_score=3,
        )

    def _create_modification_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        return ComponentSpec(
            name=f"modify_{intent.task_name.replace(' ', '_')}",
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name="modify",
                description=f"Modify code for {intent.task_name}",
                input_schema={"type": "object", "properties": {}},
                output_schema={
                    "type": "object",
                    "properties": {"modified_code": {"type": "string"}},
                },
            ),
            test_requirements=["Modification test"],
            complexity_score=4,
        )

    def _create_validation_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        return ComponentSpec(
            name=f"validate_{intent.task_name.replace(' ', '_')}",
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name="validate",
                description=f"Validate modifications for {intent.task_name}",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object", "properties": {"is_valid": {"type": "boolean"}}},
            ),
            test_requirements=["Validation test"],
            complexity_score=2,
        )

    def _create_report_spec(self, intent: ProgrammingIntent) -> ComponentSpec:
        return ComponentSpec(
            name=f"report_{intent.task_name.replace(' ', '_')}",
            component_type=ComponentType.FUNCTION,
            api_spec=APISpec(
                name="report",
                description=f"Generate report for {intent.task_name}",
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object", "properties": {"report": {"type": "string"}}},
            ),
            test_requirements=["Report generation test"],
            complexity_score=2,
        )

    def _build_input_schema(self, intent: ProgrammingIntent) -> dict[str, Any]:
        properties = {}

        for input_item in intent.inputs[: self.max_params_per_spec]:
            input_name = input_item.replace(" ", "_").lower()
            properties[input_name] = {
                "type": self._infer_type_from_description(input_item),
                "description": input_item,
            }

        if not properties:
            properties["data"] = {
                "type": "any",
                "description": "Input data",
            }

        return {"type": "object", "properties": properties}

    def _build_output_schema(self, intent: ProgrammingIntent) -> dict[str, Any]:
        properties = {}

        for output_item in intent.outputs[: self.max_params_per_spec]:
            output_name = output_item.replace(" ", "_").lower()
            properties[output_name] = {
                "type": self._infer_type_from_description(output_item),
                "description": output_item,
            }

        if not properties:
            properties["result"] = {
                "type": "any",
                "description": "Result",
            }

        return {"type": "object", "properties": properties}

    def _infer_type_from_description(self, description: str) -> str:
        lower_desc = description.lower()

        if any(
            word in lower_desc for word in ["number", "int", "float", "count", "amount", "size"]
        ):
            return "number"

        if any(word in lower_desc for word in ["string", "text", "name", "path", "file", "url"]):
            return "string"

        if any(word in lower_desc for word in ["boolean", "bool", "flag", "enabled", "is"]):
            return "boolean"

        if any(word in lower_desc for word in ["list", "array", "items", "collection"]):
            return "array"

        if any(word in lower_desc for word in ["dict", "map", "object", "config"]):
            return "object"

        return "any"

    def _determine_component_type(self, intent: ProgrammingIntent) -> ComponentType:
        if intent.complexity == TaskComplexity.COMPLEX or intent.complexity == TaskComplexity.MODERATE:
            return ComponentType.CLASS
        else:
            return ComponentType.FUNCTION

    def _estimate_module_complexity(self, intent: ProgrammingIntent) -> int:
        base_complexity = 2

        base_complexity += len(intent.requirements)

        base_complexity += len(intent.inputs)

        base_complexity += len(intent.outputs)

        if intent.complexity == TaskComplexity.COMPLEX:
            base_complexity += 5
        elif intent.complexity == TaskComplexity.MODERATE:
            base_complexity += 3

        return min(base_complexity, self.max_lines_per_spec)

    def _estimate_component_complexity(self, intent: ProgrammingIntent) -> int:
        base_complexity = 5

        base_complexity += len(intent.requirements) * 2

        base_complexity += len(intent.inputs)

        base_complexity += len(intent.outputs)

        if intent.complexity == TaskComplexity.COMPLEX:
            base_complexity += 5
        elif intent.complexity == TaskComplexity.MODERATE:
            base_complexity += 3

        return min(base_complexity, self.max_lines_per_spec)

    def _estimate_function_complexity(self, intent: ProgrammingIntent) -> int:
        base_complexity = 4

        base_complexity += len(intent.requirements)

        if intent.complexity == TaskComplexity.COMPLEX:
            base_complexity += 3
        elif intent.complexity == TaskComplexity.MODERATE:
            base_complexity += 2

        return min(base_complexity, self.max_lines_per_spec)

    def _estimate_class_complexity(self, intent: ProgrammingIntent) -> int:
        base_complexity = 6

        base_complexity += len(intent.requirements) * 2

        base_complexity += len(intent.inputs)

        base_complexity += len(intent.outputs)

        if intent.complexity == TaskComplexity.COMPLEX:
            base_complexity += 5
        elif intent.complexity == TaskComplexity.MODERATE:
            base_complexity += 3

        return min(base_complexity, self.max_lines_per_spec)

    def _should_create_helper_for_requirement(self, requirement: str) -> bool:
        complex_keywords = [
            "validate",
            "check",
            "parse",
            "format",
            "convert",
            "calculate",
            "compute",
            "process",
            "handle",
            "manage",
        ]

        return any(keyword in requirement.lower() for keyword in complex_keywords)

    def _extract_helper_name_from_requirement(self, requirement: str) -> str:
        words = requirement.lower().split()

        if words[0] in ["validate", "check", "parse", "format", "convert", "calculate"]:
            return f"{words[0]}_{words[1] if len(words) > 1 else 'data'}"

        if "and" in requirement:
            return "handle_multiple"

        return "helper"

    def _split_params_into_groups(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        groups = []
        current_group = {}

        for param_name, param_spec in params.items():
            current_group[param_name] = param_spec

            if len(current_group) >= self.max_params_per_spec:
                groups.append(current_group)
                current_group = {}

        if current_group:
            groups.append(current_group)

        return groups

    def _get_max_lines_for_tier(self, tier: ModelTier) -> int:
        limits = {
            ModelTier.TIER_1_ADVANCED: 100,
            ModelTier.TIER_2_CAPABLE: 50,
            ModelTier.TIER_3_MODERATE: 30,
            ModelTier.TIER_4_BASIC: 20,
            ModelTier.TIER_5_LIMITED: 15,
        }
        return limits[tier]

    def _get_max_params_for_tier(self, tier: ModelTier) -> int:
        limits = {
            ModelTier.TIER_1_ADVANCED: 10,
            ModelTier.TIER_2_CAPABLE: 7,
            ModelTier.TIER_3_MODERATE: 5,
            ModelTier.TIER_4_BASIC: 4,
            ModelTier.TIER_5_LIMITED: 3,
        }
        return limits[tier]


def create_converter_for_model(model_tier: ModelTier) -> IntentToSpecConverter:
    return IntentToSpecConverter(model_tier)
