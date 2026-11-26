"""Recover tool calls that arrive as text from local model runtimes."""

from __future__ import annotations

from openlaoke.core.text_tool_calls import parse_text_tool_calls


def test_parses_qwen_xml_tool_call() -> None:
    text = (
        "I will read the file.\n"
        "<tool_call>\n"
        "<function=Read>\n"
        "<parameter=file_path>\n"
        "sales.csv\n"
        "</parameter>\n"
        "<parameter=limit>\n"
        "10\n"
        "</parameter>\n"
        "</function>\n"
        "</tool_call>"
    )
    clean, calls = parse_text_tool_calls(text)
    assert clean == "I will read the file."
    assert len(calls) == 1
    assert calls[0].name == "Read"
    assert calls[0].input == {"file_path": "sales.csv", "limit": 10}


def test_parses_json_tool_call() -> None:
    text = (
        '<tool_call>{"name": "Bash", "arguments": '
        '{"command": "python analyze.py", "intent": "run"}}</tool_call>'
    )
    clean, calls = parse_text_tool_calls(text)
    assert clean == ""
    assert calls[0].name == "Bash"
    assert calls[0].input["command"] == "python analyze.py"


def test_parses_bare_function_block() -> None:
    text = "<function=Glob>\n<parameter=pattern>\n**/*.py\n</parameter>\n</function>"
    clean, calls = parse_text_tool_calls(text)
    assert clean == ""
    assert calls[0].name == "Glob"
    assert calls[0].input == {"pattern": "**/*.py"}


def test_parses_multiple_calls() -> None:
    text = (
        "<tool_call><function=Read><parameter=file_path>a.py</parameter></function></tool_call>"
        "<tool_call><function=Read><parameter=file_path>b.py</parameter></function></tool_call>"
    )
    clean, calls = parse_text_tool_calls(text)
    assert clean == ""
    assert [call.input["file_path"] for call in calls] == ["a.py", "b.py"]


def test_coerces_booleans_and_json_values() -> None:
    text = (
        "<tool_call><function=Write><parameter=path>x.txt</parameter>"
        "<parameter=accept_large_output>true</parameter>"
        '<parameter=meta>{"a": 1}</parameter></function></tool_call>'
    )
    _, calls = parse_text_tool_calls(text)
    assert calls[0].input == {
        "path": "x.txt",
        "accept_large_output": True,
        "meta": {"a": 1},
    }


def test_plain_text_is_untouched() -> None:
    text = "The answer is 42. No tools here."
    clean, calls = parse_text_tool_calls(text)
    assert clean == text
    assert calls == []


def test_parses_arg_key_arg_value_tool_call() -> None:
    """GLM / Spark emit Name<arg_key>..</arg_key><arg_value>..</arg_value>."""
    text = (
        "<tool_call>Bash<arg_key>command</arg_key>"
        "<arg_value>curl -sS -L -o page.html https://example.com</arg_value>"
        "<arg_key>intent</arg_key><arg_value>download the page</arg_value></tool_call>"
    )
    clean, calls = parse_text_tool_calls(text)
    assert clean == ""
    assert len(calls) == 1
    assert calls[0].name == "Bash"
    assert calls[0].input["command"] == "curl -sS -L -o page.html https://example.com"
    assert calls[0].input["intent"] == "download the page"


def test_parses_arg_key_call_without_closing_tag() -> None:
    text = "<tool_call>Write<arg_key>file_path</arg_key><arg_value>a.py</arg_value>"
    _, calls = parse_text_tool_calls(text)
    assert calls and calls[0].name == "Write"
    assert calls[0].input == {"file_path": "a.py"}


def test_arg_key_needs_both_key_and_value() -> None:
    texts = [
        "<tool_call>Bash<arg_key>command</arg_key></tool_call>",
        "<tool_call>I will now download the page.</tool_call>",
    ]
    for text in texts:
        _, calls = parse_text_tool_calls(text)
        assert calls == []


def test_repl_and_engine_share_one_parser() -> None:
    """The REPL path must not keep a private copy of the dialects."""
    from openlaoke.core.repl import REPL

    text = "<tool_call>Bash<arg_key>command</arg_key><arg_value>ls -l</arg_value></tool_call>"
    calls = REPL._parse_inline_tool_calls(text)
    assert calls and calls[0].name == "Bash"
    assert calls[0].input == {"command": "ls -l"}


# --------------------------------------------------------------------------- #
# rejected payloads: every dialect must refuse what it cannot parse
# --------------------------------------------------------------------------- #
def test_json_payload_with_a_bad_value_is_rejected() -> None:
    # Not JSON at all -> no call, text untouched.
    text = "<tool_call>{not json}</tool_call>"
    cleaned, calls = parse_text_tool_calls(text)

    assert calls == []
    assert cleaned == text


def test_a_json_list_payload_is_rejected() -> None:
    text = '<tool_call>[{"name": "Read"}]</tool_call>'

    assert parse_text_tool_calls(text)[1] == []


def test_a_json_payload_without_a_name_is_rejected() -> None:
    text = '<tool_call>{"arguments": {"file_path": "a"}}</tool_call>'

    assert parse_text_tool_calls(text)[1] == []


def test_json_arguments_may_arrive_as_a_string_or_as_a_function_object() -> None:
    as_string, calls = parse_text_tool_calls(
        '<tool_call>{"name": "Read", "arguments": "{\\"file_path\\": \\"a\\"}"}</tool_call>'
    )
    nested, nested_calls = parse_text_tool_calls(
        '<tool_call>{"function": {"name": "Read", "arguments": {"file_path": "b"}}}</tool_call>'
    )

    assert calls[0].input == {"file_path": "a"}
    assert nested_calls[0].name == "Read"
    assert nested_calls[0].input == {"file_path": "b"}
    assert as_string == "" and nested == ""


def test_json_arguments_that_are_not_json_become_empty_input() -> None:
    _, calls = parse_text_tool_calls('<tool_call>{"name": "Read", "arguments": "{oops"}</tool_call>')

    assert calls[0].name == "Read"
    assert calls[0].input == {}


def test_non_dict_arguments_are_dropped() -> None:
    _, calls = parse_text_tool_calls('<tool_call>{"name": "Read", "arguments": "just text"}</tool_call>')

    assert calls[0].input == {}


def test_a_bare_function_block_is_parsed_without_the_wrapper() -> None:
    text = 'Reading now.\n<function=Read><parameter=file_path>a.py</parameter></function>'

    cleaned, calls = parse_text_tool_calls(text)

    assert calls[0].name == "Read"
    assert calls[0].input == {"file_path": "a.py"}
    assert "function=" not in cleaned


def test_an_arg_key_block_without_values_is_rejected() -> None:
    text = "<tool_call>Read<arg_key>file_path</arg_key></tool_call>"

    assert parse_text_tool_calls(text)[1] == []


def test_an_arg_key_block_with_mismatched_pairs_is_rejected() -> None:
    text = "<tool_call>Read<arg_key>a</arg_key><arg_value>1</arg_value><arg_key>b</arg_key></tool_call>"

    assert parse_text_tool_calls(text)[1] == []


def test_an_arg_key_block_without_a_name_is_rejected() -> None:
    text = "<tool_call><arg_key>a</arg_key><arg_value>1</arg_value></tool_call>"

    assert parse_text_tool_calls(text)[1] == []


def test_an_arg_key_block_with_only_blank_keys_is_rejected() -> None:
    text = "<tool_call>Read<arg_key>  </arg_key><arg_value>1</arg_value></tool_call>"

    assert parse_text_tool_calls(text)[1] == []


def test_an_unterminated_block_with_json_is_left_alone() -> None:
    # The last-resort path only understands the arg_key dialect.
    text = 'call it: <tool_call>{"name": "Read", "arguments": {"file_path": "a"}}'

    assert parse_text_tool_calls(text)[1] == []


def test_multiple_blocks_are_all_removed_from_the_visible_text() -> None:
    text = (
        "first\n<tool_call><function=Read><parameter=file_path>a</parameter></function></tool_call>\n"
        "second\n<tool_call><function=Glob><parameter=pattern>*.py</parameter></function></tool_call>\n"
        "done"
    )

    cleaned, calls = parse_text_tool_calls(text)

    assert [call.name for call in calls] == ["Read", "Glob"]
    assert "tool_call" not in cleaned
    assert cleaned.startswith("first")
    assert cleaned.endswith("done")


def test_parameter_values_are_coerced_by_shape() -> None:
    text = (
        "<tool_call><function=Write>"
        "<parameter=file_path>a.txt</parameter>"
        "<parameter=flag>false</parameter>"
        "<parameter=empty>none</parameter>"
        "<parameter=obj>{\"a\": 1}</parameter>"
        "<parameter=broken>{oops</parameter>"
        "<parameter=ratio>0.5</parameter>"
        "</function></tool_call>"
    )

    _, calls = parse_text_tool_calls(text)

    assert calls[0].input == {
        "file_path": "a.txt",
        "flag": False,
        "empty": None,
        "obj": {"a": 1},
        "broken": "{oops",
        "ratio": 0.5,
    }


def test_an_argtag_body_without_a_name_is_rejected() -> None:
    from openlaoke.core.text_tool_calls import _parse_argtag_block

    assert _parse_argtag_block("<arg_key>a</arg_key><arg_value>1</arg_value>") == []
