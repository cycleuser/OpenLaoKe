"""Tests for the small-local-model safeguards and repairs.

These are the mechanisms that keep a 1.7B model usable: schema-driven argument
coercion, schema sanitising for llama.cpp grammars, read-loop and repetition
detection, terminal-output compression, post-hoc tool-call validation, model
size estimation and the size-specific guidance.
"""

from __future__ import annotations

import pytest

from openlaoke.core.small_model_optimizations import (
    ReadLoopTracker,
    SmallModelGuard,
    TerminalOutputCompressor,
    ToolCallValidator,
    apply_structured_thinking_prefix,
    coerce_tool_args,
    estimate_model_size_from_name,
    get_small_model_guidance,
    sanitize_tool_schema,
)

# --------------------------------------------------------------------------- #
# coerce_tool_args
# --------------------------------------------------------------------------- #

SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "ratio": {"type": "number"},
        "verbose": {"type": "boolean"},
        "label": {"type": "string"},
        "items": {"type": "array"},
        "meta": {"type": "object"},
        "either": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
        "single": {"oneOf": [{"type": "boolean"}, {"type": "string"}]},
        "untyped": {},
    },
}


def test_coerce_without_a_schema_returns_the_input_untouched() -> None:
    args = {"count": "42"}
    assert coerce_tool_args(args, {}) == args
    assert coerce_tool_args(args, {"type": "object"}) == args


def test_coerce_keeps_unknown_keys() -> None:
    out = coerce_tool_args({"unknown": "x"}, SCHEMA)
    assert out == {"unknown": "x"}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("42", 42),
        ("42.9", 42),  # int(float(...))
        (" 7 ", 7),
        (3.9, 3),
        (5, 5),
        (True, True),  # bools are ints in Python but must not be reinterpreted
        ("not a number", "not a number"),
    ],
)
def test_coerce_integers(raw, expected) -> None:
    out = coerce_tool_args({"count": raw}, SCHEMA)
    assert out["count"] == expected
    assert isinstance(out["count"], type(expected))


@pytest.mark.parametrize(
    "raw,expected",
    [("1.5", 1.5), ("2", 2.0), (3, 3), (True, True), ("nope", "nope")],
)
def test_coerce_numbers(raw, expected) -> None:
    out = coerce_tool_args({"ratio": raw}, SCHEMA)
    assert out["ratio"] == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
        (0, False),
        (2, True),
    ],
)
def test_coerce_booleans(raw, expected) -> None:
    assert coerce_tool_args({"verbose": raw}, SCHEMA)["verbose"] is expected


def test_coerce_booleans_leaves_unrecognised_strings() -> None:
    assert coerce_tool_args({"verbose": "maybe"}, SCHEMA)["verbose"] == "maybe"


def test_coerce_strings_from_structures() -> None:
    assert coerce_tool_args({"label": 7}, SCHEMA)["label"] == "7"
    assert coerce_tool_args({"label": {"a": 1}}, SCHEMA)["label"] == '{"a": 1}'
    assert coerce_tool_args({"label": [1, 2]}, SCHEMA)["label"] == "[1, 2]"
    assert coerce_tool_args({"label": "already"}, SCHEMA)["label"] == "already"


def test_coerce_arrays_from_json_and_plain_strings() -> None:
    assert coerce_tool_args({"items": '["a", "b"]'}, SCHEMA)["items"] == ["a", "b"]
    assert coerce_tool_args({"items": "single"}, SCHEMA)["items"] == ["single"]
    assert coerce_tool_args({"items": [1]}, SCHEMA)["items"] == [1]
    assert coerce_tool_args({"items": 5}, SCHEMA)["items"] == 5


def test_coerce_objects_from_json() -> None:
    assert coerce_tool_args({"meta": '{"k": 1}'}, SCHEMA)["meta"] == {"k": 1}
    assert coerce_tool_args({"meta": "{bad"}, SCHEMA)["meta"] == "{bad"
    assert coerce_tool_args({"meta": {"k": 1}}, SCHEMA)["meta"] == {"k": 1}


def test_coerce_anyof_and_oneof_pick_the_first_non_null_type() -> None:
    assert coerce_tool_args({"either": "9"}, SCHEMA)["either"] == 9
    assert coerce_tool_args({"single": "true"}, SCHEMA)["single"] is True


def test_coerce_leaves_none_and_untyped_values_alone() -> None:
    out = coerce_tool_args({"count": None, "untyped": "42"}, SCHEMA)
    assert out["count"] is None
    assert out["untyped"] == "42"


def test_coerce_only_walks_the_properties_it_knows() -> None:
    out = coerce_tool_args({"count": "3", "extra": "4"}, SCHEMA)
    assert out["extra"] == "4"


# --------------------------------------------------------------------------- #
# sanitize_tool_schema
# --------------------------------------------------------------------------- #


def test_sanitize_empty_schema_yields_a_minimal_object() -> None:
    assert sanitize_tool_schema({}) == {"type": "object", "properties": {}}


def test_sanitize_adds_type_and_properties() -> None:
    assert sanitize_tool_schema({"description": "x"}) == {
        "type": "object",
        "properties": {},
        "description": "x",
    }


def test_sanitize_recurses_into_properties_and_items() -> None:
    schema = {
        "type": "object",
        "properties": {
            "nested": {"type": "object", "properties": {"deep": {"type": "string"}}},
            "list": {"type": "array", "items": {"type": "object"}},
            "weird": "not a schema",
        },
    }
    out = sanitize_tool_schema(schema)
    assert out["properties"]["nested"]["properties"]["deep"] == {"type": "string"}
    assert out["properties"]["list"]["items"] == {"type": "object", "properties": {}}
    # Non-dict property schemas are replaced with a plain string type.
    assert out["properties"]["weird"] == {"type": "string"}


def test_sanitize_drops_root_keys_llama_cpp_rejects() -> None:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "x",
        "title": "T",
        "additionalProperties": False,
        "type": "object",
        "properties": {},
    }
    out = sanitize_tool_schema(schema)
    for key in ("$schema", "$id", "title", "additionalProperties"):
        assert key not in out


def test_sanitize_does_not_mutate_the_input() -> None:
    schema = {"type": "object", "title": "keep me"}
    sanitize_tool_schema(schema)
    assert schema["title"] == "keep me"


# --------------------------------------------------------------------------- #
# ReadLoopTracker
# --------------------------------------------------------------------------- #


def test_read_tools_are_counted_case_insensitively() -> None:
    tracker = ReadLoopTracker(max_consecutive_reads=3)
    tracker.notify_tool_call("Read")
    tracker.notify_tool_call("grep")
    assert tracker.consecutive_reads == 2
    assert tracker.should_warn() is False
    tracker.notify_tool_call("Glob")
    assert tracker.should_warn() is True


def test_non_read_tools_reset_the_streak() -> None:
    tracker = ReadLoopTracker(max_consecutive_reads=2)
    tracker.notify_tool_call("Read")
    tracker.notify_tool_call("Read")
    assert tracker.should_warn() is True
    tracker.notify_tool_call("Write")
    assert tracker.consecutive_reads == 0
    assert tracker.should_warn() is False
    assert tracker.last_tool == "Write"


def test_read_loop_warning_message_names_the_count() -> None:
    tracker = ReadLoopTracker(max_consecutive_reads=2)
    tracker.notify_tool_call("Read")
    tracker.notify_tool_call("Read")
    message = tracker.get_warning_message()
    assert "2 consecutive read/search calls" in message
    assert "proceed with the next step" in message


def test_read_loop_reset() -> None:
    tracker = ReadLoopTracker(max_consecutive_reads=1)
    tracker.notify_tool_call("Read")
    tracker.reset()
    assert tracker.consecutive_reads == 0
    assert tracker.last_tool == ""
    assert tracker.should_warn() is False


# --------------------------------------------------------------------------- #
# TerminalOutputCompressor
# --------------------------------------------------------------------------- #


def test_empty_output_is_returned_as_is() -> None:
    assert TerminalOutputCompressor().compress("") == ""


def test_short_output_is_returned_unchanged() -> None:
    text = "line\n" * 10
    assert TerminalOutputCompressor().compress(text) == text


def test_long_output_keeps_head_and_tail_with_a_gap_marker() -> None:
    lines = [f"line {i}" for i in range(200)]
    compressed = TerminalOutputCompressor(max_lines=100).compress("\n".join(lines))
    parts = compressed.split("\n")
    assert parts[0] == "line 0"
    assert "line 199" in compressed
    assert any("lines omitted" in part for part in parts)
    assert len(parts) < 200


def test_blank_lines_do_not_count_as_removed() -> None:
    lines = ["head"] * 30 + [""] * 5 + ["middle"] * 20 + [""] * 5 + ["tail"] * 20
    compressed = TerminalOutputCompressor(max_lines=10, max_chars=10_000).compress("\n".join(lines))
    # Only the 20 non-blank middle lines are reported as omitted.
    assert "(20 lines omitted)" in compressed
    assert compressed.startswith("head")
    assert compressed.endswith("tail")


def test_compression_truncates_by_characters_as_a_last_resort() -> None:
    text = "\n".join(["x" * 200] * 100)
    compressed = TerminalOutputCompressor(max_lines=10, max_chars=500).compress(text)
    assert len(compressed) <= 500 + len("\n... (output truncated) ...")
    assert compressed.endswith("... (output truncated) ...")


def test_error_compression_leaves_short_tracebacks_alone() -> None:
    error = "\n".join(f"line {i}" for i in range(5))
    assert TerminalOutputCompressor().compress_error(error) == error


def test_error_compression_keeps_the_error_lines_and_last_frame() -> None:
    lines = ["Traceback (most recent call last):"]
    lines += [f'  File "/pkg/mod{i}.py", line {i}, in fn{i}' for i in range(30)]
    lines.append("ValueError: something broke")
    compressed = TerminalOutputCompressor().compress_error("\n".join(lines))
    assert "ValueError: something broke" in compressed
    assert "file entries omitted" in compressed
    assert len(compressed.split("\n")) <= 30


def test_error_compression_caps_a_long_error_list() -> None:
    lines = [f"RuntimeError: failure number {i}" for i in range(40)]
    compressed = TerminalOutputCompressor().compress_error("\n".join(lines))
    # The first ten errors, an omission marker, then the last few.
    assert "failure number 0" in compressed
    assert "more errors omitted" in compressed
    assert "failure number 39" in compressed
    assert "failure number 20" not in compressed


def test_error_compression_without_error_keywords_falls_back_to_file_lines() -> None:
    lines = [f'  File "/x/{i}.py", line 1' for i in range(40)]
    compressed = TerminalOutputCompressor().compress_error("\n".join(lines))
    assert compressed.count("File") == 20  # first 15 + last 5


# --------------------------------------------------------------------------- #
# SmallModelGuard
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "size,expected",
    [("tiny", (12, 4, 15)), ("small", (20, 6, 25)), ("medium", (30, 8, 40)), ("large", (50, 12, 60))],
)
def test_guard_limits_follow_the_model_size(size: str, expected) -> None:
    guard = SmallModelGuard(model_size=size)
    assert (guard.max_tool_calls, guard.max_same_tool_streak, guard.max_task_tool_calls) == expected


def test_guard_unknown_size_uses_the_small_defaults() -> None:
    guard = SmallModelGuard(model_size="enormous")
    assert guard.max_task_tool_calls == 25


def test_guard_blocks_once_the_task_budget_is_spent() -> None:
    guard = SmallModelGuard(model_size="tiny")
    assert guard.check_before_api_call() is None
    guard.task_tool_calls = 15
    message = guard.check_before_api_call()
    assert message is not None
    assert "Maximum tool calls (15)" in message


def test_guard_detects_repeated_responses() -> None:
    guard = SmallModelGuard(max_response_repeats=2)
    assert guard.check_after_api_call("same answer", 0) is None
    assert guard.check_after_api_call("same answer", 0) is None
    repeated = guard.check_after_api_call("same answer", 0)
    assert repeated is not None
    assert "repeated the same response" in repeated


def test_guard_forgets_the_streak_on_a_new_response() -> None:
    guard = SmallModelGuard(max_response_repeats=2)
    guard.check_after_api_call("one", 0)
    assert guard.check_after_api_call("two", 0) is None
    assert guard.response_repeat_count == 0


def test_guard_flags_empty_and_tiny_responses() -> None:
    guard = SmallModelGuard()
    assert "empty" in guard.check_after_api_call("", 0)
    assert "empty" in guard.check_after_api_call("   ", 0)
    short = guard.check_after_api_call("ok", 0)
    assert short is not None and "too short" in short
    # The same short text is fine when a tool was used.
    assert guard.check_after_api_call("ok", 1) is None


def test_guard_warns_on_a_same_tool_streak() -> None:
    guard = SmallModelGuard(model_size="tiny")  # streak limit 4
    for _ in range(3):
        assert guard.notify_tool_call("Read") is None
    warning = guard.notify_tool_call("Read")
    assert warning is not None
    assert "called 'Read' 4 times in a row" in warning


def test_guard_resets_the_streak_when_the_tool_changes() -> None:
    guard = SmallModelGuard(model_size="tiny")
    guard.notify_tool_call("Read")
    guard.notify_tool_call("Read")
    guard.notify_tool_call("Grep")
    assert guard.same_tool_streak == 1


def test_guard_warns_at_the_iteration_tool_limit() -> None:
    guard = SmallModelGuard(model_size="tiny")  # max_tool_calls 12
    warning = None
    # Alternate tools so the same-tool streak warning does not fire first.
    for i in range(12):
        warning = guard.notify_tool_call("Bash" if i % 2 == 0 else "Read")
    assert warning is not None
    assert "Tool call limit (12) reached" in warning
    assert guard.total_tool_calls == 12
    assert guard.task_tool_calls == 12


def test_guard_parse_failure_hint_includes_the_snippet_and_escalates() -> None:
    guard = SmallModelGuard(max_parse_failures=2)
    first = guard.notify_parse_failure("bad <call>\nnext line")
    assert "Your tool call format was incorrect" in first
    assert "<tool_call> <function=ToolName>" in first
    assert "bad <call> next line" in first  # newlines flattened
    assert "multiple times" not in first

    second = guard.notify_parse_failure("again")
    assert "multiple times" in second
    assert guard.consecutive_parse_failures == 2


def test_guard_parse_success_clears_the_failure_count() -> None:
    guard = SmallModelGuard()
    guard.notify_parse_failure("x")
    guard.notify_parse_success()
    assert guard.consecutive_parse_failures == 0


def test_guard_reset_task_clears_per_task_state() -> None:
    guard = SmallModelGuard()
    guard.notify_tool_call("Read")
    guard.notify_parse_failure("x")
    guard.check_after_api_call("answer", 0)

    guard.reset_task()

    assert guard.task_tool_calls == 0
    assert guard.same_tool_streak == 0
    assert guard.consecutive_parse_failures == 0
    assert guard.last_response_hash == ""
    assert guard.response_repeat_count == 0
    # Session-wide counters survive a task reset.
    assert guard.total_tool_calls == 1


# --------------------------------------------------------------------------- #
# ToolCallValidator
# --------------------------------------------------------------------------- #


class FakeTool:
    def __init__(self, name: str, schema: dict | None = None):
        self.name = name
        self._schema = schema or {}

    def get_input_schema(self) -> dict:
        return self._schema


class FakeRegistry:
    def __init__(self, tools: list[FakeTool]):
        self._tools = tools

    def get_all(self) -> list[FakeTool]:
        return self._tools


READ_SCHEMA = {
    "type": "object",
    "properties": {"file_path": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["file_path"],
}


@pytest.fixture()
def validator() -> ToolCallValidator:
    v = ToolCallValidator()
    v.set_tools(
        FakeRegistry(
            [
                FakeTool("Read", READ_SCHEMA),
                FakeTool("Write", {"type": "object", "properties": {"file_path": {}, "content": {}}}),
                FakeTool("Bash", {"type": "object", "properties": {"command": {}}, "required": ["command"]}),
            ]
        )
    )
    return v


def test_set_tools_records_names_and_schemas(validator) -> None:
    assert validator.known_names == ["Read", "Write", "Bash"]
    assert validator.name_schemas["Read"] == READ_SCHEMA
    assert "Bash" in validator.name_schemas


def test_validate_accepts_a_correct_call(validator) -> None:
    name, params, hint = validator.validate("Read", {"file_path": "a.py"})
    assert name == "Read"
    assert params == {"file_path": "a.py"}
    assert hint is None


def test_validate_fixes_the_tool_name_case(validator) -> None:
    name, _, hint = validator.validate("read", {"file_path": "a.py"})
    assert name == "Read"
    assert hint is not None and "Corrected tool name 'read' to 'Read'" in hint


def test_validate_prefix_matches_unknown_tool_names(validator) -> None:
    name, _, _ = validator.validate("writ", {})
    assert name == "Write"


def test_validate_leaves_a_hopeless_name(validator) -> None:
    name, _, hint = validator.validate("zzz", {})
    assert name == "zzz"
    assert hint is None


def test_validate_maps_parameter_aliases(validator) -> None:
    _, params, hint = validator.validate("Read", {"path": "a.py", "count": 3})
    assert params["file_path"] == "a.py"
    assert "Corrected parameter 'path' to 'file_path'" in hint
    # Unknown params are kept but reported.
    assert params["count"] == {"count": 3}.get("count")
    assert "Unknown parameter 'count' for Read" in hint


def test_validate_lowercases_keys_that_already_match(validator) -> None:
    _, params, hint = validator.validate("Read", {"File_Path": "a.py"})
    assert params == {"file_path": "a.py"}
    assert hint is None


def test_validate_reports_missing_required_parameters(validator) -> None:
    _, _, hint = validator.validate("Bash", {"cmd": "ls"})
    assert "Corrected parameter 'cmd' to 'command'" in hint
    # The alias satisfies the required list, so nothing is reported missing.
    assert "MISSING" not in hint

    _, _, missing = validator.validate("Read", {})
    assert "MISSING required parameter 'file_path' for Read" in missing


def test_validate_combines_name_and_parameter_hints(validator) -> None:
    _, _, hint = validator.validate("read", {"bogus": 1})
    assert hint is not None
    assert hint.startswith("Corrected tool name")
    assert "Unknown parameter 'bogus'" in hint
    assert "MISSING required parameter" in hint


def test_validator_without_schemas_keeps_arguments_but_notes_them(validator) -> None:
    validator.set_tools(FakeRegistry([FakeTool("Plain")]))
    name, params, hint = validator.validate("Plain", {"anything": 1})
    assert name == "Plain"
    # With no schema, nothing can match, so the argument is kept and reported.
    assert params == {"anything": 1}
    assert hint == "Unknown parameter 'anything' for Plain"


# --------------------------------------------------------------------------- #
# Thinking prefix, size estimation and guidance
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("task_type", ["code", "edit", "refactor", "debug"])
def test_thinking_prefix_for_implementation_tasks(task_type: str) -> None:
    prefix = apply_structured_thinking_prefix(task_type)
    assert "Before writing code" in prefix
    assert "simplest approach" in prefix


@pytest.mark.parametrize("task_type", ["plan", "design", "architect"])
def test_thinking_prefix_for_planning_tasks(task_type: str) -> None:
    assert "Before creating a plan" in apply_structured_thinking_prefix(task_type)


@pytest.mark.parametrize("task_type", ["test", "verify"])
def test_thinking_prefix_for_testing_tasks(task_type: str) -> None:
    assert "Before writing tests" in apply_structured_thinking_prefix(task_type)


def test_thinking_prefix_is_empty_for_other_tasks() -> None:
    assert apply_structured_thinking_prefix("chat") == ""
    assert apply_structured_thinking_prefix("") == ""


@pytest.mark.parametrize(
    "name,expected",
    [
        ("qwen3-0.6b", "tiny"),
        ("Qwen3.5-1.7B-Instruct", "tiny"),
        ("llama-3.2-3b-instruct", "small"),
        ("gemma-3-12b-it", "medium"),
        ("llama-3.3-70b-versatile", "large"),
        ("deepseek-r1:32b", "large"),
        ("mistral-7b", "small"),
        ("some-4b-model", "small"),
        ("some-13b-model", "medium"),
        ("someone-0.5b", "tiny"),
        ("totally-unknown-model", "medium"),
    ],
)
def test_estimate_model_size_from_name(name: str, expected: str) -> None:
    assert estimate_model_size_from_name(name) == expected


def test_estimate_uses_parameter_count_patterns() -> None:
    assert estimate_model_size_from_name("custom-800m") == "tiny"
    assert estimate_model_size_from_name("mixtral-48b") == "large"


def test_guidance_for_tiny_models_is_stepwise() -> None:
    guidance = get_small_model_guidance("tiny")
    assert "ONE step at a time" in guidance
    assert "use ONE tool per response" in guidance
    assert "NEVER chain tools" in guidance


def test_guidance_for_small_models_is_shorter() -> None:
    guidance = get_small_model_guidance("small")
    assert "Answer simple questions directly" in guidance


def test_no_guidance_for_larger_models() -> None:
    assert get_small_model_guidance("medium") == ""
    assert get_small_model_guidance("large") == ""


# --------------------------------------------------------------------------- #
# Remaining degenerate paths
# --------------------------------------------------------------------------- #


def test_anyof_without_any_typed_option_yields_no_expected_type() -> None:
    schema = {"type": "object", "properties": {"x": {"anyOf": [{"type": "null"}, {}]}}}
    # No concrete type can be inferred, so the value passes through untouched.
    assert coerce_tool_args({"x": "42"}, schema)["x"] == "42"


def test_bool_coercion_passes_non_scalars_through() -> None:
    schema = {"type": "object", "properties": {"flag": {"type": "boolean"}}}
    assert coerce_tool_args({"flag": [1]}, schema)["flag"] == [1]


def test_trailing_omissions_are_marked_at_the_end() -> None:
    # A long middle with no tail lines left to flush the counter.
    lines = ["head"] * 5 + ["noise"] * 50
    compressed = TerminalOutputCompressor(
        max_lines=10, preserve_head=5, preserve_tail=0, max_chars=100_000
    ).compress("\n".join(lines))
    assert compressed.endswith("... (50 lines omitted) ...")


def test_bool_coercion_keeps_a_real_bool() -> None:
    assert coerce_tool_args({"verbose": True}, SCHEMA)["verbose"] is True
    assert coerce_tool_args({"verbose": False}, SCHEMA)["verbose"] is False
