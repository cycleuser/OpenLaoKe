"""Standard API interfaces and templates for small model development.

This module defines consistent interfaces that small models can implement
piece by piece, ensuring perfect assembly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class ComponentType(StrEnum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    API_ENDPOINT = "api_endpoint"
    DATA_MODEL = "data_model"
    TEST = "test"


class TaskSize(StrEnum):
    ATOMIC = "atomic"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass
class CodeTemplate:
    name: str
    description: str
    template: str
    required_imports: list[str] = field(default_factory=list)
    required_dependencies: list[str] = field(default_factory=list)
    validation_rules: list[str] = field(default_factory=list)
    example_usage: str = ""
    docstring_template: str = ""


@dataclass
class APISpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    error_codes: dict[str, str] = field(default_factory=dict)
    version: str = "1.0.0"
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ComponentSpec:
    name: str
    component_type: ComponentType
    api_spec: APISpec | None = None
    dependencies: list[str] = field(default_factory=list)
    implements: list[str] = field(default_factory=list)
    test_requirements: list[str] = field(default_factory=list)
    complexity_score: int = 1


@runtime_checkable
class Validatable(Protocol):
    def validate(self) -> tuple[bool, list[str]]: ...


@runtime_checkable
class Testable(Protocol):
    def get_test_cases(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class Assemblable(Protocol):
    def get_dependencies(self) -> list[str]: ...

    def get_exports(self) -> list[str]: ...


STANDARD_TEMPLATES: dict[str, CodeTemplate] = {
    "function_basic": CodeTemplate(
        name="function_basic",
        description="Basic function with type hints and docstring",
        template='''def {function_name}({parameters}) -> {return_type}:
    """
    {docstring}

    Args:
        {args_doc}

    Returns:
        {return_doc}

    Raises:
        {raises_doc}
    """
    {implementation}
    return {return_value}''',
        required_imports=["from __future__ import annotations"],
        validation_rules=[
            "Must have complete type hints",
            "Must have docstring with Args, Returns, Raises sections",
            "Must have at least one test case",
        ],
        docstring_template="Brief description of what the function does.\n\nDetailed explanation if needed.",
    ),
    "class_basic": CodeTemplate(
        name="class_basic",
        description="Basic class with init and methods",
        template='''class {class_name}:
    """
    {docstring}

    Attributes:
        {attrs_doc}
    """

    def __init__(self, {init_params}):
        """Initialize {class_name}."""
        {init_implementation}

    {methods}''',
        required_imports=[
            "from __future__ import annotations",
            "from dataclasses import dataclass",
        ],
        validation_rules=[
            "Must have __init__ method",
            "All public methods must have type hints",
            "Must have class-level docstring",
        ],
    ),
    "api_endpoint": CodeTemplate(
        name="api_endpoint",
        description="FastAPI endpoint with validation",
        template='''@router.{method}("/{path}", response_model={response_model})
async def {function_name}({parameters}) -> {return_type}:
    """
    {docstring}

    Args:
        {args_doc}

    Returns:
        {return_doc}

    Raises:
        HTTPException: {error_doc}
    """
    {implementation}
    return {return_value}''',
        required_imports=[
            "from fastapi import APIRouter, HTTPException",
            "from pydantic import BaseModel",
        ],
        required_dependencies=["fastapi>=0.100.0", "pydantic>=2.0.0"],
        validation_rules=[
            "Must have response_model",
            "Must handle errors with HTTPException",
            "Must have async def for I/O operations",
        ],
    ),
    "data_model": CodeTemplate(
        name="data_model",
        description="Pydantic data model with validation",
        template='''class {class_name}(BaseModel):
    """
    {docstring}
    """
    {fields}

    {validators}''',
        required_imports=["from pydantic import BaseModel, Field, validator"],
        validation_rules=[
            "Must inherit from BaseModel",
            "All fields must have Field() with description",
            "Complex validations must use @validator",
        ],
    ),
    "test_function": CodeTemplate(
        name="test_function",
        description="Pytest test function",
        template='''def test_{function_name}_{test_case}():
    """Test {test_description}."""
    # Arrange
    {arrange_code}

    # Act
    {act_code}

    # Assert
    {assert_code}''',
        required_imports=["import pytest"],
        validation_rules=[
            "Must follow AAA pattern (Arrange-Act-Assert)",
            "Must have descriptive test name",
            "Must test one thing only",
        ],
    ),
}


STANDARD_API_SPECS: dict[str, APISpec] = {
    "tool_call": APISpec(
        name="tool_call",
        description="Standard tool call interface",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tool name"},
                "arguments": {"type": "object", "description": "Tool arguments"},
            },
            "required": ["name", "arguments"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "result": {"type": "any"},
                "error": {"type": "string"},
            },
            "required": ["success"],
        },
        error_codes={
            "TOOL_NOT_FOUND": "Requested tool does not exist",
            "INVALID_ARGS": "Arguments do not match tool schema",
            "EXECUTION_ERROR": "Tool execution failed",
        },
        examples=[
            {
                "input": {"name": "read", "arguments": {"file_path": "/tmp/test.txt"}},
                "output": {"success": True, "result": "file content", "error": None},
            }
        ],
    ),
    "state_update": APISpec(
        name="state_update",
        description="Standard state update interface",
        input_schema={
            "type": "object",
            "properties": {
                "state_key": {"type": "string"},
                "value": {"type": "any"},
                "metadata": {"type": "object"},
            },
            "required": ["state_key", "value"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "previous_value": {"type": "any"},
                "timestamp": {"type": "number"},
            },
            "required": ["success", "timestamp"],
        },
    ),
    "component_assembly": APISpec(
        name="component_assembly",
        description="Component assembly interface",
        input_schema={
            "type": "object",
            "properties": {
                "components": {"type": "array", "items": {"type": "object"}},
                "assembly_order": {"type": "array", "items": {"type": "string"}},
                "validation_level": {"type": "string", "enum": ["basic", "strict", "exhaustive"]},
            },
            "required": ["components"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "assembled_code": {"type": "string"},
                "errors": {"type": "array", "items": {"type": "string"}},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["success"],
        },
    ),
}


def get_template_for_component(component_type: ComponentType) -> CodeTemplate:
    template_map = {
        ComponentType.FUNCTION: STANDARD_TEMPLATES["function_basic"],
        ComponentType.CLASS: STANDARD_TEMPLATES["class_basic"],
        ComponentType.API_ENDPOINT: STANDARD_TEMPLATES["api_endpoint"],
        ComponentType.DATA_MODEL: STANDARD_TEMPLATES["data_model"],
        ComponentType.TEST: STANDARD_TEMPLATES["test_function"],
    }
    return template_map.get(component_type, STANDARD_TEMPLATES["function_basic"])


def estimate_task_complexity(spec: ComponentSpec) -> TaskSize:
    score = spec.complexity_score

    if len(spec.dependencies) > 5:
        score += 2
    if len(spec.test_requirements) > 5:
        score += 1
    if spec.api_spec and len(spec.api_spec.input_schema.get("properties", {})) > 5:
        score += 2

    if score <= 2:
        return TaskSize.ATOMIC
    elif score <= 4:
        return TaskSize.SMALL
    elif score <= 6:
        return TaskSize.MEDIUM
    else:
        return TaskSize.LARGE


def should_decompose_for_model(task_size: TaskSize, model_tier: str) -> bool:
    if model_tier == "tier_5_limited":
        return task_size in [TaskSize.MEDIUM, TaskSize.LARGE]
    elif model_tier == "tier_4_basic":
        return task_size == TaskSize.LARGE
    else:
        return False
