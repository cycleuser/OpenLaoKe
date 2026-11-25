"""Tests for fast_prune / extract_content.

Regression focus: the interactive REPL keeps a provider-dict history, and
fast_prune must count and compact dict messages (a missing branch made it a
silent no-op for exactly the path that needs compaction most).
"""

from __future__ import annotations

from openlaoke.core.compact import extract_content
from openlaoke.core.compact.fast_pruner import fast_prune
from openlaoke.types.core_types import AssistantMessage, MessageRole, UserMessage


def test_extract_content_dict():
    assert extract_content({"role": "user", "content": "hello world"}) == "hello world"
    out = extract_content(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "Read", "arguments": "{}"}}],
        }
    )
    assert "Tool: Read" in out
    assert "{}" in out


def test_extract_content_message_objects():
    assert extract_content(UserMessage(role=MessageRole.USER, content="hi")) == "hi"
    am = AssistantMessage(role=MessageRole.ASSISTANT, content="ok")
    assert "ok" in extract_content(am)


def test_fast_prune_compacts_dict_history():
    msgs = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "word " * 300}
        for i in range(40)
    ]
    result = fast_prune(msgs, max_tokens=500)
    assert result.tokens_after < result.tokens_before
    assert len(result.messages) < len(msgs)


def test_fast_prune_under_budget_is_noop():
    msgs = [{"role": "user", "content": "short"}]
    result = fast_prune(msgs, max_tokens=8192)
    assert result.messages == msgs
    assert result.tokens_before == result.tokens_after


def test_fast_prune_keeps_last_user_requirement():
    msgs = [{"role": "assistant", "content": "filler " * 300} for _ in range(40)]
    msgs.append({"role": "user", "content": "FINAL REQUIREMENT"})
    msgs.append({"role": "assistant", "content": "answering"})
    result = fast_prune(msgs, max_tokens=500, keep_tail_tokens=200)
    joined = "\n".join(str(m.get("content", "")) for m in result.messages if isinstance(m, dict))
    assert "FINAL REQUIREMENT" in joined
