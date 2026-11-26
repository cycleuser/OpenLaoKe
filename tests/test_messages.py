"""Tests for enforce_role_alternation: the conversation shape providers require.

Every request goes through it, so the cases that matter are the ones a real
session produces: a trimmed history starting with an assistant turn, a retried
turn leaving two user messages in a row, several tool results that must stay
separate, and content that is already a list of blocks.
"""

from __future__ import annotations

from typing import Any

from openlaoke.core.messages import enforce_role_alternation


def test_empty_conversation_is_returned_as_is() -> None:
    assert enforce_role_alternation([]) == []


def test_an_already_valid_conversation_is_unchanged_in_content() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert enforce_role_alternation(messages) == messages


def test_the_input_list_is_not_mutated() -> None:
    messages = [
        {"role": "user", "content": "one"},
        {"role": "user", "content": "two"},
    ]
    enforce_role_alternation(messages)
    assert [m["content"] for m in messages] == ["one", "two"]


def test_adjacent_user_turns_are_merged() -> None:
    result = enforce_role_alternation(
        [
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "ok"},
        ]
    )

    assert [m["role"] for m in result] == ["user", "assistant"]
    assert result[0]["content"] == "first\nsecond"


def test_adjacent_assistant_turns_are_merged() -> None:
    result = enforce_role_alternation(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "part one"},
            {"role": "assistant", "content": "part two"},
        ]
    )

    assert [m["role"] for m in result] == ["user", "assistant"]
    assert result[1]["content"] == "part one\npart two"


def test_tool_messages_are_never_merged() -> None:
    result = enforce_role_alternation(
        [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "function": {"name": "Read", "arguments": "{}"}},
                    {"id": "c2", "function": {"name": "Read", "arguments": "{}"}},
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "one"},
            {"role": "tool", "tool_call_id": "c2", "content": "two"},
        ]
    )

    assert [m["role"] for m in result] == ["user", "assistant", "tool", "tool"]
    assert [m["tool_call_id"] for m in result[2:]] == ["c1", "c2"]


def test_a_leading_assistant_turn_is_dropped() -> None:
    result = enforce_role_alternation(
        [
            {"role": "assistant", "content": "orphan"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    )

    assert [m["content"] for m in result] == ["hi", "hello"]


def test_a_leading_tool_message_is_dropped() -> None:
    result = enforce_role_alternation(
        [
            {"role": "tool", "tool_call_id": "c1", "content": "orphan"},
            {"role": "user", "content": "hi"},
        ]
    )

    assert result == [{"role": "user", "content": "hi"}]


def test_a_conversation_with_nothing_but_assistant_turns_becomes_empty() -> None:
    assert enforce_role_alternation([{"role": "assistant", "content": "x"}]) == []


def test_a_leading_system_turn_is_kept() -> None:
    result = enforce_role_alternation(
        [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
        ]
    )
    assert [m["role"] for m in result] == ["system", "user"]


def test_merging_string_and_block_content_produces_blocks() -> None:
    blocks: list[dict[str, Any]] = [{"type": "text", "text": "block text"}]
    result = enforce_role_alternation(
        [
            {"role": "user", "content": blocks},
            {"role": "user", "content": "plain"},
            {"role": "assistant", "content": "ok"},
        ]
    )

    assert result[0]["content"] == [
        {"type": "text", "text": "block text"},
        {"type": "text", "text": "plain"},
    ]


def test_merging_blocks_with_blocks_concatenates_them() -> None:
    first = [{"type": "text", "text": "a"}]
    second = [{"type": "text", "text": "b", "cache_control": {"type": "ephemeral"}}]
    result = enforce_role_alternation(
        [
            {"role": "user", "content": first},
            {"role": "user", "content": second},
            {"role": "assistant", "content": "ok"},
        ]
    )

    assert result[0]["content"] == [
        {"type": "text", "text": "a"},
        {"type": "text", "text": "b", "cache_control": {"type": "ephemeral"}},
    ]


def test_merging_keeps_extra_keys_from_the_first_message() -> None:
    result = enforce_role_alternation(
        [
            {"role": "user", "content": "a", "system_injected": False},
            {"role": "user", "content": "b"},
            {"role": "assistant", "content": "ok"},
        ]
    )
    assert result[0]["system_injected"] is False


def test_missing_content_is_treated_as_empty() -> None:
    result = enforce_role_alternation(
        [
            {"role": "user"},
            {"role": "user", "content": "tail"},
            {"role": "assistant", "content": "ok"},
        ]
    )
    assert result[0]["content"].endswith("tail")


def test_an_alternating_long_conversation_is_preserved() -> None:
    messages: list[dict[str, Any]] = [{"role": "user", "content": "start"}]
    for i in range(6):
        messages.append({"role": "assistant", "content": f"a{i}"})
        messages.append({"role": "user", "content": f"u{i}"})

    result = enforce_role_alternation(messages)

    assert result == messages
