"""Small model optimizations for GGUF/local models (0.6B-8B).

Adapted from hermes-agent, learn-claude-code, and kwcode patterns.
Key optimizations:
1. Tool argument type coercion (fixes #1 small model failure mode)
2. JSON schema sanitization for llama.cpp compatibility
3. Read-loop prevention tracker
4. Terminal output compression (RTK-style)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def coerce_tool_args(args: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Coerce tool arguments to match their JSON Schema types.

    Small models frequently return numbers as strings ("42" instead of 42)
    and booleans as strings ("true" instead of true). This function compares
    each argument against the tool's JSON Schema and safely coerces types.

    Handles: int, float, bool, string, array, object, union types, null values.
    """
    if not schema or "properties" not in schema:
        return args

    properties = schema.get("properties", {})
    coerced = dict(args)

    for key, value in list(coerced.items()):
        if key not in properties:
            continue

        prop_schema = properties[key]
        prop_type = prop_schema.get("type")

        if prop_type is None and "anyOf" in prop_schema:
            prop_type = _infer_type_from_any_of(prop_schema["anyOf"])

        if prop_type is None and "oneOf" in prop_schema:
            prop_type = _infer_type_from_any_of(prop_schema["oneOf"])

        coerced[key] = _coerce_value(value, prop_type, prop_schema)

    return coerced


def _infer_type_from_any_of(any_of: list[dict[str, Any]]) -> str | None:
    for option in any_of:
        if option.get("type") and option.get("type") != "null":
            return option.get("type")
    return None


def _coerce_value(value: Any, expected_type: str | None, prop_schema: dict[str, Any]) -> Any:
    if value is None:
        return value

    if expected_type == "integer":
        return _coerce_to_int(value)
    elif expected_type == "number":
        return _coerce_to_number(value)
    elif expected_type == "boolean":
        return _coerce_to_bool(value)
    elif expected_type == "string":
        return _coerce_to_string(value)
    elif expected_type == "array":
        return _coerce_to_array(value, prop_schema)
    elif expected_type == "object":
        return _coerce_to_object(value, prop_schema)

    return value


def _coerce_to_int(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        try:
            return int(float(value))
        except (ValueError, TypeError):
            pass
    if isinstance(value, float):
        return int(value)
    return value


def _coerce_to_number(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
    return value


def _coerce_to_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        if value.lower() in ("false", "0", "no", "off"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return value


def _coerce_to_string(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value)
    return str(value)


def _coerce_to_array(value: Any, prop_schema: dict[str, Any]) -> Any:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return [value]
    return value


def _coerce_to_object(value: Any, prop_schema: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return value


def sanitize_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Sanitize JSON Schema for llama.cpp's json-schema-to-grammar converter.

    llama.cpp rejects certain schema shapes that are valid in standard JSON Schema:
    - Bare "type": "object" with no properties
    - Missing "type" field
    - Extra fields like "title", "description" at root level
    - Nested schemas without proper type declarations
    """
    if not schema:
        return {"type": "object", "properties": {}}

    sanitized = dict(schema)

    if "type" not in sanitized:
        sanitized["type"] = "object"

    if sanitized.get("type") == "object" and "properties" not in sanitized:
        sanitized["properties"] = {}

    if "properties" in sanitized:
        new_props = {}
        for key, prop_schema in sanitized["properties"].items():
            if isinstance(prop_schema, dict):
                new_props[key] = sanitize_tool_schema(prop_schema)
            else:
                new_props[key] = {"type": "string"}
        sanitized["properties"] = new_props

    if "items" in sanitized and isinstance(sanitized["items"], dict):
        sanitized["items"] = sanitize_tool_schema(sanitized["items"])

    for key in ("$schema", "$id", "title", "additionalProperties"):
        sanitized.pop(key, None)

    return sanitized


@dataclass
class ReadLoopTracker:
    """Prevents small models from getting stuck in read-only loops.

    Resets consecutive-read counter when a non-read/search tool runs.
    If too many consecutive reads occur, injects a warning to prompt action.
    """

    consecutive_reads: int = 0
    max_consecutive_reads: int = 8
    read_tools: set[str] = field(
        default_factory=lambda: {
            "Read",
            "Glob",
            "Grep",
            "ListDirectory",
            "ToolSearch",
            "WebSearch",
            "WebFetch",
        }
    )
    last_tool: str = ""

    def notify_tool_call(self, tool_name: str) -> None:
        if tool_name in self.read_tools or tool_name.lower() in {
            t.lower() for t in self.read_tools
        }:
            self.consecutive_reads += 1
        else:
            self.consecutive_reads = 0
        self.last_tool = tool_name

    def should_warn(self) -> bool:
        return self.consecutive_reads >= self.max_consecutive_reads

    def get_warning_message(self) -> str:
        return (
            f"You have made {self.consecutive_reads} consecutive read/search calls without taking action. "
            "Please analyze the information you've gathered and proceed with the next step. "
            "If you need more information, explain what specific information you're looking for and why."
        )

    def reset(self) -> None:
        self.consecutive_reads = 0
        self.last_tool = ""


@dataclass
class TerminalOutputCompressor:
    """Compresses terminal/bash output to reduce token consumption.

    RTK-style compression: 60-90% token reduction on shell commands.
    """

    max_lines: int = 100
    max_chars: int = 8000
    preserve_head: int = 30
    preserve_tail: int = 20

    def compress(self, output: str) -> str:
        if not output:
            return output

        lines = output.split("\n")

        if len(lines) <= self.max_lines and len(output) <= self.max_chars:
            return output

        compressed_lines: list[str] = []
        removed_lines = 0

        for i, line in enumerate(lines):
            if i < self.preserve_head:
                compressed_lines.append(line)
            elif i >= len(lines) - self.preserve_tail:
                if removed_lines > 0:
                    compressed_lines.append(f"... ({removed_lines} lines omitted) ...")
                    removed_lines = 0
                compressed_lines.append(line)
            else:
                if len(line.strip()) > 0:
                    removed_lines += 1
                elif removed_lines > 0:
                    compressed_lines.append(f"... ({removed_lines} lines omitted) ...")
                    removed_lines = 0

        if removed_lines > 0:
            compressed_lines.append(f"... ({removed_lines} lines omitted) ...")

        result = "\n".join(compressed_lines)

        if len(result) > self.max_chars:
            result = result[: self.max_chars] + "\n... (output truncated) ..."

        return result

    def compress_error(self, error: str) -> str:
        lines = error.strip().split("\n")
        if len(lines) <= 20:
            return error

        error_lines: list[str] = []
        file_lines: list[str] = []

        for line in lines:
            is_error = any(
                kw in line.lower() for kw in ["error", "exception", "traceback", "failed", "fatal"]
            )
            is_error_type = ":" in line and any(
                kw in line.split(":")[0].strip() for kw in ["Error", "Exception"]
            )
            is_file = line.startswith("  File ")
            is_caret = line.strip().startswith("^")

            if is_error or is_error_type or is_caret:
                error_lines.append(line)
            elif is_file:
                file_lines.append(line)

        result: list[str] = []
        if error_lines:
            result.extend(error_lines[:10])
            if file_lines:
                result.append(f"... ({len(file_lines)} file entries omitted) ...")
                result.append(file_lines[-1])
            if len(error_lines) > 10:
                result.append(f"... ({len(error_lines) - 10} more errors omitted) ...")
                result.extend(error_lines[-3:])
        else:
            result = file_lines[:15] + file_lines[-5:]

        return "\n".join(result[:30])


def apply_structured_thinking_prefix(task_type: str) -> str:
    """Generate structured internal thinking prompt before coding output.

    Adapted from Viral_Writer's 11-dimension framework, applied to coding tasks.
    The model completes these dimensions internally before producing output.
    """
    if task_type in ("code", "edit", "refactor", "debug"):
        return (
            "Before writing code, think through:\n"
            "1. What is the core problem to solve?\n"
            "2. What files need to be modified and why?\n"
            "3. What is the simplest approach?\n"
            "4. What edge cases need handling?\n"
            "5. How to verify the solution works?\n"
            "Then proceed with the implementation.\n"
        )
    elif task_type in ("plan", "design", "architect"):
        return (
            "Before creating a plan, think through:\n"
            "1. What are the constraints and requirements?\n"
            "2. What are the trade-offs of different approaches?\n"
            "3. What is the minimum viable solution?\n"
            "4. What risks need mitigation?\n"
            "Then present the plan.\n"
        )
    elif task_type in ("test", "verify"):
        return (
            "Before writing tests, think through:\n"
            "1. What behavior needs verification?\n"
            "2. What are the happy path and edge cases?\n"
            "3. What assertions will catch regressions?\n"
            "4. How to make tests maintainable?\n"
            "Then write the tests.\n"
        )
    return ""


def estimate_model_size_from_name(model_name: str) -> str:
    """Estimate model size category from model name.

    Returns: 'tiny' (<3B), 'small' (3-10B), 'medium' (10-30B), 'large' (>30B)
    """
    model_lower = model_name.lower()

    known_mappings = {
        "qwen2.5-0.5b": "tiny",
        "qwen2.5-1.5b": "tiny",
        "qwen2.5-3b": "tiny",
        "qwen2.5-7b": "small",
        "qwen2.5-14b": "medium",
        "qwen2.5-32b": "large",
        "qwen2.5-72b": "large",
        "llama-3.2-1b": "tiny",
        "llama-3.2-3b": "small",
        "llama-3.1-8b": "medium",
        "llama-3.1-70b": "large",
        "llama-3.3-70b": "large",
        "gemma-2-2b": "tiny",
        "gemma-2-9b": "small",
        "gemma-2-27b": "medium",
        "deepseek-r1:1.5b": "tiny",
        "deepseek-r1:7b": "small",
        "deepseek-r1:8b": "small",
        "deepseek-r1:14b": "medium",
        "deepseek-r1:32b": "large",
        "deepseek-r1:70b": "large",
    }

    for key, size in known_mappings.items():
        if key in model_lower:
            return size

    size_patterns = [
        (r"0\.6b|0\.6\b|600m", "tiny"),
        (r"\b1b\b|1\.5b\b|\b2b\b|2\.5b\b|\b3b\b", "tiny"),
        (r"\b4b\b|\b5b\b|\b6b\b|\b7b\b|\b8b\b|\b9b\b", "small"),
        (r"\b10b\b|\b11b\b|\b12b\b|\b13b\b|\b14b\b|\b15b\b|\b16b\b|\b18b\b|\b20b\b", "medium"),
        (r"\b30b\b|\b32b\b|\b34b\b|\b40b\b|\b48b\b|\b60b\b|\b65b\b|\b70b\b|\b72b\b", "large"),
    ]

    for pattern, size in size_patterns:
        if re.search(pattern, model_lower):
            return size

    return "medium"


def get_small_model_guidance(model_size: str) -> str:
    """Return model-size-specific guidance for the system prompt."""
    if model_size == "tiny":
        return (
            "You are a small model. Keep responses concise. "
            "Focus on one file at a time. "
            "Use tools one at a time. "
            "Always read a file before editing it. "
            "Keep code changes minimal and targeted."
        )
    elif model_size == "small":
        return (
            "You are a medium-small model. "
            "Read files before editing. "
            "Focus on one task at a time. "
            "Keep responses focused and concise."
        )
    return ""
