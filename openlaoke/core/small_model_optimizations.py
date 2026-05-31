"""Small model optimizations for GGUF/local models (0.6B-8B).

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


@dataclass
class SmallModelGuard:
    """Runtime guard for small model behavior during task execution.

    Tracks and enforces limits on:
    - Total tool calls per task
    - Consecutive same-tool calls (loop detection)
    - Repeated identical responses (stuck detection)
    - Tool call format quality (parse failures -> corrective hints)
    """

    model_size: str = "small"
    total_tool_calls: int = field(default=0)
    max_tool_calls: int = field(default=0)
    last_tool_name: str = ""
    same_tool_streak: int = 0
    max_same_tool_streak: int = 0
    consecutive_parse_failures: int = 0
    max_parse_failures: int = 4
    last_response_hash: str = ""
    response_repeat_count: int = 0
    max_response_repeats: int = 3
    task_tool_calls: int = 0
    max_task_tool_calls: int = 0

    def __post_init__(self) -> None:
        limits = {"tiny": (12, 4, 15), "small": (20, 6, 25), "medium": (30, 8, 40), "large": (50, 12, 60)}
        toks, streak, task = limits.get(self.model_size, (20, 6, 25))
        self.max_tool_calls = toks
        self.max_same_tool_streak = streak
        self.max_task_tool_calls = task

    def check_before_api_call(self) -> str | None:
        if self.task_tool_calls >= self.max_task_tool_calls:
            return (
                f"Maximum tool calls ({self.max_task_tool_calls}) reached for this task. "
                "Summarize what you've done and stop using tools."
            )
        return None

    def check_after_api_call(self, content: str, tool_count: int) -> str | None:
        content_hash = str(hash((content or "").strip()[:200]))
        if content_hash == self.last_response_hash:
            self.response_repeat_count += 1
            if self.response_repeat_count >= self.max_response_repeats:
                return (
                    "You have repeated the same response. The task is not progressing. "
                    "Either take a different approach with tools, or state that you cannot complete the task."
                )
        else:
            self.last_response_hash = content_hash
            self.response_repeat_count = 0

        if not content or not content.strip():
            return "Your response was empty. Provide text or use tools."

        if len(content.strip()) < 3 and tool_count == 0:
            return (
                "Your response was too short and used no tools. "
                "Either provide a proper text response or use tools."
            )

        return None

    def notify_tool_call(self, tool_name: str) -> str | None:
        self.total_tool_calls += 1
        self.task_tool_calls += 1

        if tool_name == self.last_tool_name:
            self.same_tool_streak += 1
            if self.same_tool_streak >= self.max_same_tool_streak:
                return (
                    f"You have called '{tool_name}' {self.same_tool_streak} times in a row. "
                    "Try a different tool or summarize your findings."
                )
        else:
            self.last_tool_name = tool_name
            self.same_tool_streak = 1

        if self.total_tool_calls >= self.max_tool_calls:
            return (
                f"Tool call limit ({self.max_tool_calls}) reached for this iteration. "
                "Respond with text only."
            )

        return None

    def notify_parse_failure(self, raw_content: str) -> str:
        self.consecutive_parse_failures += 1
        snippet = raw_content[:150].replace("\n", " ")
        base = (
            f"Your tool call format was incorrect. "
            f'Use EXACTLY: <tool_call> <function=ToolName> <parameter=param> value </tool_call>\n'
            f"Your output was: {snippet}\n"
        )
        if self.consecutive_parse_failures >= self.max_parse_failures:
            base += (
                "You have failed to format tool calls correctly multiple times. "
                "Stop using tools and explain what you want to do in plain text."
            )
        return base

    def notify_parse_success(self) -> None:
        self.consecutive_parse_failures = 0

    def reset_task(self) -> None:
        self.task_tool_calls = 0
        self.last_tool_name = ""
        self.same_tool_streak = 0
        self.consecutive_parse_failures = 0
        self.last_response_hash = ""
        self.response_repeat_count = 0


@dataclass
class ToolCallValidator:
    """Post-hoc validation and correction of small model tool calls.

    Inspired by Needle's grammar-constrained decoding, but operating
    post-generation since we can't control GGUF model logits.
    """

    known_names: list[str] = field(default_factory=list)
    name_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)

    _param_aliases: dict[str, str] = field(default_factory=lambda: {
        "file": "file_path", "path": "file_path", "filename": "file_path",
        "filepath": "file_path", "dest": "file_path", "target": "file_path",
        "cmd": "command", "shell": "command", "run": "command", "exec": "command",
        "code": "content", "text": "content", "body": "content", "data": "content",
        "source": "content", "val": "content",
        "pattern": "pattern", "glob": "pattern", "regex": "pattern",
        "query": "query", "search": "query", "find": "query",
        "old": "old_string", "old_text": "old_string", "before": "old_string",
        "new": "new_string", "new_text": "new_string", "after": "new_string",
        "seconds": "seconds", "duration": "seconds", "time": "seconds",
        "url": "url", "link": "url", "address": "url",
    })

    def set_tools(self, tool_registry: Any) -> None:
        from openlaoke.core.tool import Tool

        tools: list[Tool] = tool_registry.get_all()
        self.known_names = [t.name for t in tools]
        for t in tools:
            schema = t.get_input_schema()
            if schema and "properties" in schema:
                self.name_schemas[t.name] = schema

    def _fuzzy_name(self, name: str) -> str | None:
        name_lower = name.lower().strip()
        for known in self.known_names:
            if known.lower() == name_lower:
                return known
        for known in self.known_names:
            if known.lower().startswith(name_lower[:3]) and len(name_lower) >= 3:
                return known
        return None

    def _correct_params(self, tool_name: str, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        hints: list[str] = []
        schema = self.name_schemas.get(tool_name, {})
        schema_props = schema.get("properties", {})
        schema_required = schema.get("required", [])

        new_params: dict[str, Any] = {}
        mapped_keys: set[str] = set()

        for key, val in params.items():
            key_lower = key.lower().strip()
            if key_lower in schema_props:
                new_params[key_lower] = val
                mapped_keys.add(key_lower)
            elif key_lower in self._param_aliases:
                canonical = self._param_aliases[key_lower]
                new_params[canonical] = val
                mapped_keys.add(canonical)
                hints.append(f"Corrected parameter '{key}' to '{canonical}'")
            else:
                new_params[key] = val
                hints.append(f"Unknown parameter '{key}' for {tool_name}")

        for req in schema_required:
            if req not in mapped_keys and req not in new_params:
                hints.append(f"MISSING required parameter '{req}' for {tool_name}")

        return new_params, hints

    def validate(self, tool_name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
        corrected_name = self._fuzzy_name(tool_name) or tool_name
        name_hint = None
        if corrected_name != tool_name:
            name_hint = f"Corrected tool name '{tool_name}' to '{corrected_name}'"

        corrected_params, param_hints = self._correct_params(corrected_name, params)

        hint = None
        parts = []
        if name_hint:
            parts.append(name_hint)
        if param_hints:
            parts.append("; ".join(param_hints))
        if parts:
            hint = ". ".join(parts)

        return corrected_name, corrected_params, hint


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
        "qwen3.5-0.8b": "tiny",
        "qwen3.5-1.7b": "tiny",
        "qwen3.5-4b": "small",
        "qwen3.5-8b": "small",
        "qwen3.5-14b": "medium",
        "qwen3.5-32b": "large",
        "qwen3-0.6b": "tiny",
        "qwen3-1.7b": "tiny",
        "qwen3-4b": "small",
        "qwen3-8b": "small",
        "llama-4-scout": "medium",
        "llama-4-maverick": "large",
        "llama-3.2-1b": "tiny",
        "llama-3.2-3b": "small",
        "llama-3.1-8b": "medium",
        "llama-3.3-70b": "large",
        "gemma-3-1b": "tiny",
        "gemma-3-4b": "small",
        "gemma-3-12b": "medium",
        "gemma-3-27b": "large",
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
        (r"0\.[5-9]b\b|0\.[5-9]\b|600m|500m|700m|800m", "tiny"),
        (r"\b1b\b|1\.[0-9]b\b|\b2b\b|2\.[0-9]b\b|\b3b\b", "tiny"),
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
            "You are a tiny 0.8B model. Work ONE step at a time.\n"
            "RULES:\n"
            "1. For questions: answer directly in 1-3 sentences. NO tools.\n"
            "2. For tasks: use ONE tool per response. Output DONE on its own line when finished.\n"
            "3. Tool format: 'Write file_path=x content=...' or 'Bash command=...'\n"
            "4. Read a file BEFORE editing it.\n"
            "5. Keep responses under 150 words.\n"
            "6. If you fail 3 times, explain the problem in text and output DONE.\n"
            "NEVER chain tools. NEVER describe what you'll do - just DO it."
        )
    elif model_size == "small":
        return (
            "You are a small model. "
            "Answer simple questions directly without tools. "
            "Read files before editing. "
            "Focus on one task at a time. "
            "Keep responses focused and concise."
        )
    return ""
