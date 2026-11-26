"""Tests for the forgiving text tool-call parser.

This is the fallback path for small local models that emit tool calls as text
instead of provider-native tool_calls, so its job is to salvage what it can
from several formats and quietly drop what it cannot.
"""

from __future__ import annotations

import pytest

from openlaoke.core.tool_call_parser import (
    _convert_args_types,
    _fuzzy_match_tool_name,
    _levenshtein,
    _normalize_call_shape,
    _parse_kwargs,
    _parse_liquid_function_call,
    _safe_json_parse,
    extract_tool_calls,
)

# --------------------------------------------------------------------------- #
# extract_tool_calls: format detection and priority
# --------------------------------------------------------------------------- #


def test_empty_content_returns_no_calls() -> None:
    assert extract_tool_calls("") == []
    assert extract_tool_calls("", reasoning_content=None) == []


def test_plain_prose_without_calls() -> None:
    assert extract_tool_calls("I think the answer is 42.") == []


def test_hermes_format_single_call() -> None:
    content = '<tool_call>{"name": "Read", "arguments": {"file_path": "a.py"}}</tool_call>'
    calls = extract_tool_calls(content)
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    assert calls[0]["arguments"] == {"file_path": "a.py"}


def test_hermes_format_multiple_calls() -> None:
    content = (
        '<tool_call>{"name": "Read", "arguments": {"file_path": "a.py"}}</tool_call>\n'
        '<tool_call>{"name": "Grep", "arguments": {"pattern": "x"}}</tool_call>'
    )
    names = [call["name"] for call in extract_tool_calls(content)]
    assert names == ["Read", "Grep"]


def test_hermes_wins_over_later_formats() -> None:
    content = (
        '<tool_call>{"name": "Read", "arguments": {}}</tool_call>\n'
        '```json\n{"name": "Write", "arguments": {}}\n```'
    )
    assert [call["name"] for call in extract_tool_calls(content)] == ["Read"]


def test_liquid_marker_format() -> None:
    content = '<|tool_call_start|>[Read(file_path="a.py", limit=10)]<|tool_call_end|>'
    calls = extract_tool_calls(content)
    assert len(calls) == 1
    assert calls[0]["name"] == "Read"
    assert calls[0]["arguments"] == {"file_path": "a.py", "limit": 10}


def test_fenced_json_block() -> None:
    content = 'Sure.\n```json\n{"name": "Bash", "arguments": {"command": "ls"}}\n```\n'
    calls = extract_tool_calls(content)
    assert calls[0]["name"] == "Bash"
    assert calls[0]["arguments"] == {"command": "ls"}


def test_fenced_json_list_of_calls() -> None:
    content = '```json\n[{"name": "A", "arguments": {}}, {"name": "B", "arguments": {}}]\n```'
    assert [call["name"] for call in extract_tool_calls(content)] == ["A", "B"]


def test_tool_call_fence() -> None:
    content = '```tool_call\n{"name": "Glob", "arguments": {"pattern": "*.py"}}\n```'
    calls = extract_tool_calls(content)
    assert calls[0]["name"] == "Glob"


def test_bare_json_object_with_name() -> None:
    calls = extract_tool_calls('{"name": "Ls", "arguments": {"path": "."}}')
    assert calls[0]["name"] == "Ls"


def test_bare_json_array_returns_first_named_call() -> None:
    calls = extract_tool_calls('[{"name": "A", "arguments": {}}, {"name": "B", "arguments": {}}]')
    assert [call["name"] for call in calls] == ["A"]


def test_bare_json_without_name_is_ignored() -> None:
    assert extract_tool_calls('{"answer": 42}') == []
    assert extract_tool_calls('prefix {"answer": 42} then {"name": "X", "arguments": {}}') != []


def test_fenced_json_without_name_is_ignored() -> None:
    assert extract_tool_calls('```json\n{"answer": 42}\n```') == []


def test_malformed_json_degrades_to_no_calls() -> None:
    assert extract_tool_calls('<tool_call>{"name": "Read", "arguments": {</tool_call>') == []
    assert extract_tool_calls('```json\n{broken\n```') == []


def test_trailing_commas_are_repaired() -> None:
    content = '<tool_call>{"name": "Read", "arguments": {"a": 1,},}</tool_call>'
    calls = extract_tool_calls(content)
    assert calls[0]["arguments"] == {"a": 1}


def test_reasoning_content_is_used_when_content_is_empty() -> None:
    reasoning = '<tool_call>{"name": "Read", "arguments": {"file_path": "x"}}</tool_call>'
    calls = extract_tool_calls("", reasoning_content=reasoning)
    assert calls[0]["name"] == "Read"


def test_nested_json_strings_do_not_break_bare_scanning() -> None:
    content = 'text {"a": "brace } inside string"} then {"name": "Read", "arguments": {}}'
    calls = extract_tool_calls(content)
    assert calls[0]["name"] == "Read"


def test_escaped_quotes_in_bare_json() -> None:
    content = '{"note": "say \\"hi\\"", "name": "Read", "arguments": {}}'
    calls = extract_tool_calls(content)
    assert calls[0]["name"] == "Read"


# --------------------------------------------------------------------------- #
# Call-shape normalisation
# --------------------------------------------------------------------------- #


def test_function_nesting_is_unwrapped() -> None:
    call = _normalize_call_shape(
        {"type": "function", "function": {"name": "Read", "arguments": {"a": 1}}}
    )
    assert call == {"name": "Read", "arguments": {"a": 1}}


def test_function_nesting_falls_back_to_outer_fields() -> None:
    call = _normalize_call_shape({"name": "Outer", "arguments": {"k": 1}, "function": {}})
    assert call["name"] == "Outer"
    assert call["arguments"] == {"k": 1}


def test_tool_and_args_aliases() -> None:
    call = _normalize_call_shape({"tool": "Grep", "args": {"pattern": "x"}})
    assert call["name"] == "Grep"
    assert call["arguments"] == {"pattern": "x"}


def test_arguments_as_json_string_are_parsed() -> None:
    call = _normalize_call_shape({"name": "Read", "arguments": '{"file_path": "a"}'})
    assert call["arguments"] == {"file_path": "a"}


def test_unparsable_arguments_become_an_empty_dict() -> None:
    call = _normalize_call_shape({"name": "Read", "arguments": "{oops"})
    assert call["arguments"] == {}
    call = _normalize_call_shape({"name": "Read", "arguments": 7})
    assert call["arguments"] == {}


def test_calls_without_a_name_are_dropped() -> None:
    assert extract_tool_calls('<tool_call>{"arguments": {"a": 1}}</tool_call>') == []


# --------------------------------------------------------------------------- #
# Fuzzy tool-name repair
# --------------------------------------------------------------------------- #


def test_levenshtein_base_cases_and_distance() -> None:
    assert _levenshtein("", "") == 0
    assert _levenshtein("abc", "") == 3
    assert _levenshtein("", "abc") == 3
    assert _levenshtein("read", "read") == 0
    assert _levenshtein("read", "red") == 1


def test_exact_and_case_insensitive_names_are_kept() -> None:
    assert _fuzzy_match_tool_name({"name": "Read"}, {"Read", "Grep"})["name"] == "Read"
    assert _fuzzy_match_tool_name({"name": "read"}, {"Read", "Grep"})["name"] == "Read"


def test_near_miss_names_are_repaired() -> None:
    # One extra letter: distance 1, well inside the budget for a 5-char name.
    assert _fuzzy_match_tool_name({"name": "Rread"}, {"Read", "Grep"})["name"] == "Read"


def test_short_names_need_a_proportionally_small_distance() -> None:
    # "Raed" is a transposition (distance 2) but the name is only 4 chars, so
    # the distance must stay below half the length: 2 < 2.0 is false.
    assert _fuzzy_match_tool_name({"name": "Raed"}, {"Read"})["name"] == "Raed"


def test_hopeless_names_are_left_alone() -> None:
    assert _fuzzy_match_tool_name({"name": "zzzzzzzz"}, {"Read"})["name"] == "zzzzzzzz"


def test_distant_names_are_not_force_fitted() -> None:
    # Distance 4 from every candidate, and the name is short: keep the original.
    assert _fuzzy_match_tool_name({"name": "wxyz"}, {"Read"})["name"] == "wxyz"


# --------------------------------------------------------------------------- #
# Argument type repair
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("false", False),
        ("null", None),
        ("none", None),
        ("42", 42),
        ("-7", -7),
        ("3.5", 3.5),
        ("-0.5", -0.5),
        ("already a string", "already a string"),
        ("", ""),
    ],
)
def test_convert_args_types(raw, expected) -> None:
    call = _convert_args_types({"name": "T", "arguments": {"k": raw}})
    assert call["arguments"]["k"] == expected
    assert isinstance(call["arguments"]["k"], type(expected))


def test_convert_args_types_keeps_non_strings() -> None:
    call = _convert_args_types({"name": "T", "arguments": {"n": 3, "flag": True, "lst": [1]}})
    assert call["arguments"] == {"n": 3, "flag": True, "lst": [1]}


def test_convert_args_types_ignores_non_dict_arguments() -> None:
    call = {"name": "T", "arguments": "not a dict"}
    assert _convert_args_types(call)["arguments"] == "not a dict"


def test_known_tools_drive_both_repairs() -> None:
    content = '<tool_call>{"name": "read", "arguments": {"limit": "5"}}</tool_call>'
    calls = extract_tool_calls(content, known_tools={"Read"})
    assert calls[0]["name"] == "Read"
    assert calls[0]["arguments"] == {"limit": 5}


def test_unknown_tools_are_not_repaired_without_a_tool_set() -> None:
    content = '<tool_call>{"name": "read", "arguments": {"limit": "5"}}</tool_call>'
    calls = extract_tool_calls(content)
    assert calls[0]["name"] == "read"
    assert calls[0]["arguments"] == {"limit": "5"}


# --------------------------------------------------------------------------- #
# Liquid kwargs parser
# --------------------------------------------------------------------------- #


def test_liquid_call_without_arguments() -> None:
    assert _parse_liquid_function_call("Ls()") == {"name": "Ls", "arguments": {}}


def test_liquid_call_is_not_a_function_shape() -> None:
    assert _parse_liquid_function_call("just text") is None
    assert _parse_liquid_function_call("[not a call]") is None


def test_liquid_brackets_are_optional() -> None:
    assert _parse_liquid_function_call('Read(file_path="a")') == {
        "name": "Read",
        "arguments": {"file_path": "a"},
    }
    assert _parse_liquid_function_call('[Read(file_path="a")]') == {
        "name": "Read",
        "arguments": {"file_path": "a"},
    }


def test_kwargs_parsing_mixed_types() -> None:
    args = _parse_kwargs('a=1, b="two", c=true, d=None, e=1.5')
    assert args == {"a": 1, "b": "two", "c": True, "d": None, "e": 1.5}


def test_kwargs_parsing_escapes() -> None:
    args = _parse_kwargs(r'a="line\nnext\tcol \"quoted\"", b="back\\slash"')
    assert args["a"] == 'line\nnext\tcol "quoted"'
    assert args["b"] == "back\\slash"


def test_kwargs_parsing_nested_brackets() -> None:
    args = _parse_kwargs('a=[1, 2], b={"k": "v"}')
    # Bracketed values are captured as their inner text, not decoded.
    assert args["a"] == "1, 2"
    assert args["b"] == '"k": "v"'


def test_kwargs_stops_on_a_missing_assignment() -> None:
    assert _parse_kwargs("a=1, garbage") == {"a": 1}


def test_kwargs_handles_empty_input() -> None:
    assert _parse_kwargs("") == {}
    assert _parse_kwargs("   ") == {}


# --------------------------------------------------------------------------- #
# JSON repair helper
# --------------------------------------------------------------------------- #


def test_safe_json_parse_repairs_trailing_commas_only() -> None:
    assert _safe_json_parse('{"a": 1,}') == {"a": 1}
    assert _safe_json_parse("[1, 2, ]") == [1, 2]
    assert _safe_json_parse("not json") is None


# --------------------------------------------------------------------------- #
# Degenerate input guards
# --------------------------------------------------------------------------- #


def test_kwargs_stops_when_a_value_is_missing() -> None:
    # "a=" with nothing after it: no value to consume.
    assert _parse_kwargs("a=") == {}
    # A value that is only a separator becomes an empty string.
    assert _parse_kwargs("a= ,") == {"a": ""}


def test_kwargs_stops_on_an_empty_key() -> None:
    assert _parse_kwargs('= "x"') == {}


def test_string_escapes_for_carriage_return_backslash_and_unknown() -> None:
    args = _parse_kwargs(r'a="x\ry", b="p\\q", c="bad\zend"')
    assert args["a"] == "x\ry"
    assert args["b"] == "p\\q"
    # Unknown escapes are preserved verbatim rather than dropped.
    assert args["c"] == "bad\\zend"


def test_unterminated_string_runs_to_the_end() -> None:
    args = _parse_kwargs('a="never closed')
    assert args["a"] == "never closed"


def test_bracketed_value_runs_to_the_end_when_unbalanced() -> None:
    # Best effort: the closing bracket is missing, so the captured slice stops
    # one character short of the end.
    args = _parse_kwargs("a=[1, 2")
    assert args["a"] == "1,"


def test_bare_json_scan_handles_unterminated_objects() -> None:
    # A truncated object is skipped, and scanning continues to the next one.
    content = '{"broken": "unterminated and then {"name": "Read", "arguments": {}}'
    calls = extract_tool_calls(content)
    assert [call["name"] for call in calls] == ["Read"]


def test_bare_json_scan_with_trailing_escape() -> None:
    assert extract_tool_calls('{"a": "ends with escape \\') == []
