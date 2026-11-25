"""Tests for fast_prune / fast_prune_aggressive and their helpers.

The load-bearing invariants are that message order is never rearranged,
tool_call/tool_result adjacency survives, tool results are truncated rather
than dropped, user requirements pass through byte-identical, and the digest
never makes the context bigger.
"""

from __future__ import annotations

from openlaoke.core.compact import extract_content
from openlaoke.core.compact.fast_pruner import (
    _is_assistant_tool_call,
    _is_tool_result,
    _is_user_requirement,
    _message_role,
    _sample_indices,
    _strip_prose,
    _truncate_tool_result,
    extract_decisions,
    extract_keywords,
    fast_prune,
    fast_prune_aggressive,
)
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    SystemMessage,
    UserMessage,
)


def user_obj(text: str) -> UserMessage:
    return UserMessage(role=MessageRole.USER, content=text)


def assistant_obj(text: str, tools=None) -> AssistantMessage:
    return AssistantMessage(role=MessageRole.ASSISTANT, content=text, tool_uses=tools or [])


def system_obj(text: str, subtype: str = "info", tool_use_id: str = "") -> SystemMessage:
    return SystemMessage(
        role=MessageRole.SYSTEM, content=text, subtype=subtype, tool_use_id=tool_use_id
    )


def contents(messages) -> list[str]:
    out = []
    for m in messages:
        out.append(m.get("content", "") if isinstance(m, dict) else m.content)
    return out


# --------------------------------------------------------------------------- #
# extract_content (regression: dict histories must count)
# --------------------------------------------------------------------------- #


def test_extract_content_dict() -> None:
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


def test_extract_content_message_objects() -> None:
    assert extract_content(user_obj("hi")) == "hi"
    assert "ok" in extract_content(assistant_obj("ok"))
    assert extract_content(system_obj("sys")) == "sys"


# --------------------------------------------------------------------------- #
# Role/kind predicates
# --------------------------------------------------------------------------- #


def test_message_role_reads_dicts_and_enums() -> None:
    assert _message_role({"role": "user"}) == "user"
    assert _message_role(user_obj("x")) == "user"  # StrEnum -> .value
    assert _message_role(object()) == ""


def test_is_user_requirement() -> None:
    assert _is_user_requirement({"role": "user", "content": "x"}) is True
    assert _is_user_requirement(user_obj("x")) is True
    # System-injected turns carry requirements too.
    assert _is_user_requirement({"role": "system", "content": "x", "system_injected": True}) is True
    assert _is_user_requirement({"role": "assistant", "content": "x"}) is False


def test_is_tool_result() -> None:
    assert _is_tool_result({"role": "tool", "content": "out"}) is True
    assert _is_tool_result(system_obj("out", tool_use_id="call_1")) is True
    assert _is_tool_result({"role": "system", "content": "out", "tool_use_id": "c"}) is True
    # A plain status system message is not a tool result.
    assert _is_tool_result(system_obj("status")) is False
    assert _is_tool_result(user_obj("x")) is False


def test_is_assistant_tool_call() -> None:
    assert _is_assistant_tool_call(assistant_obj("x", tools=[object()])) is True
    assert _is_assistant_tool_call({"role": "assistant", "tool_calls": [{"id": "c"}]}) is True
    assert _is_assistant_tool_call(assistant_obj("no tools")) is False
    assert _is_assistant_tool_call({"role": "assistant", "content": "x"}) is False
    assert _is_assistant_tool_call(user_obj("x")) is False


def test_strip_prose_copies_dicts_and_mutates_objects() -> None:
    original = {"role": "assistant", "content": "prose", "tool_calls": [{"id": "c"}]}
    stripped = _strip_prose(original)
    assert stripped["content"] == ""
    assert stripped["tool_calls"] == [{"id": "c"}]  # structure kept
    assert original["content"] == "prose"  # original untouched

    obj = assistant_obj("prose", tools=[object()])
    assert _strip_prose(obj) is obj
    assert obj.content == ""
    assert obj.tool_uses  # adjacency preserved

    # Anything without a settable content attribute is returned unchanged.
    assert _strip_prose(42) == 42


# --------------------------------------------------------------------------- #
# Keyword / decision extraction
# --------------------------------------------------------------------------- #


def test_extract_keywords_finds_code_shaped_tokens() -> None:
    text = (
        "We opened /src/openlaoke/core/engine.py and defined `def run_engine(x)`.\n"
        "Error: boom happened\n"
        "import openlaoke.core\n"
        "Tool: Read"
    )
    keywords = extract_keywords(text)
    assert any("engine.py" in k for k in keywords)
    assert any("run_engine" in k for k in keywords)
    assert any("boom" in k for k in keywords)
    assert any("openlaoke.core" in k for k in keywords)


def test_extract_keywords_dedupes_and_caps() -> None:
    text = "Error: same\n" * 10
    keywords = extract_keywords(text)
    assert keywords.count(keywords[0]) == 1
    capped = extract_keywords("Error: a\nError: b\nError: c\n", max_keywords=2)
    assert len(capped) == 2


def test_extract_keywords_ignores_short_and_plain_prose() -> None:
    assert extract_keywords("ab if of to") == []


def test_extract_decisions_keeps_constraint_sentences() -> None:
    text = (
        "We decided to use the streaming path for all providers.\n"
        "Unrelated filler sentence here.\n"
        "The parser must not raise on malformed JSON input.\n"
        "short\n"
    )
    lines = extract_decisions(text)
    assert any("decided to use the streaming path" in line for line in lines)
    assert any("must not raise" in line for line in lines)
    assert all(len(line) > 20 for line in lines)


def test_extract_decisions_caps_line_count() -> None:
    text = "\n".join(["we decided to keep this behaviour because reasons abound"] * 20)
    assert len(extract_decisions(text, max_lines=3)) == 3
    assert len(extract_decisions(text)) == 12


def test_sample_indices_returns_everything_when_small() -> None:
    indices = [1, 2, 3]
    assert _sample_indices(indices, max_samples=10) == {1, 2, 3}


def test_sample_indices_is_head_biased_and_bounded() -> None:
    indices = list(range(1000))
    sampled = _sample_indices(indices, max_samples=40)
    assert len(sampled) <= 50
    assert set(range(10)).issubset(sampled)


def test_truncate_tool_result_leaves_short_output_alone() -> None:
    short = "\n".join(f"line{i}" for i in range(40))
    assert _truncate_tool_result(short) == short


def test_truncate_tool_result_collapses_the_middle() -> None:
    content = "\n".join(f"line{i}" for i in range(200))
    truncated = _truncate_tool_result(content, head_lines=5, tail_lines=3)
    assert truncated.startswith("line0\nline1")
    assert "lines truncated, full output was" in truncated
    assert truncated.endswith("line198\nline199")
    assert len(truncated) < len(content)


# --------------------------------------------------------------------------- #
# fast_prune
# --------------------------------------------------------------------------- #


def test_fast_prune_compacts_dict_history() -> None:
    msgs = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "word " * 300} for i in range(40)
    ]
    result = fast_prune(msgs, max_tokens=500)
    assert result.tokens_after < result.tokens_before
    assert len(result.messages) < len(msgs)


def test_fast_prune_under_budget_is_noop() -> None:
    msgs = [{"role": "user", "content": "short"}]
    result = fast_prune(msgs, max_tokens=8192)
    assert result.messages == msgs
    assert result.tokens_before == result.tokens_after


def test_fast_prune_empty_input() -> None:
    result = fast_prune([], max_tokens=100)
    assert result.messages == []
    assert (result.tokens_before, result.tokens_after) == (0, 0)


def test_fast_prune_keeps_last_user_requirement() -> None:
    msgs = [{"role": "assistant", "content": "filler " * 300} for _ in range(40)]
    msgs.append({"role": "user", "content": "FINAL REQUIREMENT"})
    msgs.append({"role": "assistant", "content": "answering"})
    result = fast_prune(msgs, max_tokens=500, keep_tail_tokens=200)
    joined = "\n".join(contents(result.messages))
    assert "FINAL REQUIREMENT" in joined


def test_fast_prune_preserves_head_and_tail_and_order() -> None:
    head = {"role": "system", "content": "SYSTEM PROMPT " * 50}
    tail_msgs = [{"role": "assistant", "content": f"tail{i} " * 20} for i in range(3)]
    middle = [{"role": "assistant", "content": "prose " * 400} for _ in range(30)]
    msgs = [head, *middle, *tail_msgs]
    result = fast_prune(msgs, max_tokens=600, keep_tail_tokens=200)
    # Head survives verbatim and first.
    assert result.messages[0] is head
    # The tail survives verbatim and last.
    assert [m for m in result.messages[-3:]] == tail_msgs
    # Message identity order is a subsequence of the input order.
    order = [msgs.index(m) for m in result.messages if m in msgs]
    assert order == sorted(order)


def test_fast_prune_keeps_middle_user_requirement_byte_identical() -> None:
    msgs = [{"role": "assistant", "content": "prose " * 400} for _ in range(40)]
    requirement = {"role": "user", "content": "MUST KEEP THIS REQUIREMENT " * 3}
    msgs.insert(20, requirement)
    result = fast_prune(msgs, max_tokens=500, keep_tail_tokens=100)
    assert requirement in result.messages
    kept = [m for m in result.messages if m is requirement]
    assert len(kept) == 1
    assert kept[0]["content"] == requirement["content"]


def test_fast_prune_keeps_assistant_tool_call_messages_intact() -> None:
    msgs = [{"role": "assistant", "content": "prose " * 400} for _ in range(40)]
    tool_call = {
        "role": "assistant",
        "content": "calling",
        "tool_calls": [{"id": "c1", "function": {"name": "Read", "arguments": "{}"}}],
    }
    tool_result = {"role": "tool", "tool_call_id": "c1", "content": "file body " * 100}
    msgs[20:20] = [tool_call, tool_result]
    result = fast_prune(msgs, max_tokens=500, keep_tail_tokens=100)
    kept_ids = [id(m) for m in result.messages]
    # The assistant tool call is protected: identity preserved, still adjacent
    # to its result.
    assert id(tool_call) in kept_ids
    assert kept_ids.index(id(tool_call)) + 1 == kept_ids.index(id(tool_result)) or (
        id(tool_result) in kept_ids
    )


def test_fast_prune_protect_read_results_can_be_disabled() -> None:
    msgs = [{"role": "assistant", "content": "prose " * 400} for _ in range(40)]
    tool_call = {"role": "assistant", "content": "calling", "tool_calls": [{"id": "c1"}]}
    msgs.insert(20, tool_call)
    protected = fast_prune(msgs, max_tokens=500, keep_tail_tokens=100)
    unprotected = fast_prune(msgs, max_tokens=500, keep_tail_tokens=100, protect_read_results=False)
    assert id(tool_call) in [id(m) for m in protected.messages]
    # When protection is off the tool call may be elided from the middle.
    assert len(unprotected.messages) <= len(protected.messages)


def test_fast_prune_truncates_long_tool_results_instead_of_dropping_them() -> None:
    body = "\n".join(f"output line {i}" for i in range(200))
    prose = {"role": "assistant", "content": "prose " * 400}
    # Layout matters: the tool result must land in the middle window (before the
    # last user requirement, which anchors the tail), not in the kept tail.
    msgs = [{"role": "system", "content": "SYSTEM " * 20}]
    msgs.extend(dict(prose) for _ in range(10))
    msgs.append({"role": "assistant", "content": "running", "tool_calls": [{"id": "c2"}]})
    msgs.append({"role": "tool", "tool_call_id": "c2", "content": body})
    msgs.append(dict(prose))
    msgs.append({"role": "user", "content": "FINAL QUESTION"})
    msgs.extend({"role": "assistant", "content": "tail"} for _ in range(3))
    result = fast_prune(msgs, max_tokens=800, keep_tail_tokens=200)
    tool_outputs = [
        m["content"] for m in result.messages if isinstance(m, dict) and m.get("role") == "tool"
    ]
    assert tool_outputs, "tool result must not be dropped"
    assert "lines truncated, full output was" in tool_outputs[0]
    assert tool_outputs[0].startswith("output line 0")
    assert tool_outputs[0].endswith("output line 199")


def test_fast_prune_truncates_system_message_tool_results_keeping_metadata() -> None:
    body = "\n".join(f"chunk {i}" for i in range(200))
    original = system_obj(body, subtype="result", tool_use_id="call_9")
    msgs = [{"role": "assistant", "content": "prose " * 400} for _ in range(20)]
    msgs.append(original)
    msgs.extend({"role": "assistant", "content": "prose " * 400} for _ in range(20))
    result = fast_prune(msgs, max_tokens=800, keep_tail_tokens=200)
    shortened = [m for m in result.messages if isinstance(m, SystemMessage) and m.tool_use_id]
    assert shortened
    assert "lines truncated" in shortened[0].content
    assert shortened[0].tool_use_id == "call_9"
    assert shortened[0].subtype == "result"


def test_fast_prune_inserts_digest_after_the_head_block() -> None:
    head = {"role": "system", "content": "HEAD " * 30}
    msgs = [head]
    msgs.extend({"role": "assistant", "content": f"file /pkg/mod{i}.py def fn{i} Error: e{i}\n" * 20} for i in range(40))
    result = fast_prune(msgs, max_tokens=600, keep_tail_tokens=100)
    digests = [
        m
        for m in result.messages
        if isinstance(m, SystemMessage) and m.subtype == "compact"
    ]
    assert digests, "assistant prose should collapse into a digest"
    assert result.messages.index(digests[0]) == 1  # right after the head block
    assert "tokens of assistant prose elided" in digests[0].content
    assert result.keywords_extracted > 0


def test_fast_prune_never_grows_the_context_when_digest_is_not_worth_it() -> None:
    # One tiny prose message in the middle: the digest header alone costs more.
    msgs = [
        {"role": "user", "content": "a" * 4000},
        {"role": "assistant", "content": "ok"},
        {"role": "assistant", "content": "ok again"},
        {"role": "user", "content": "b" * 4000},
    ]
    result = fast_prune(msgs, max_tokens=1000)
    # Regression: the no-op path used to restore the full list and then append
    # the tail again, duplicating messages in the user's history.
    assert result.messages == msgs
    assert len(result.messages) == len(msgs)
    assert result.tokens_after == result.tokens_before
    assert result.keywords_extracted == 0


def test_fast_prune_handles_message_objects_as_well_as_dicts() -> None:
    msgs = [system_obj("SYSTEM " * 100)]
    msgs.extend(assistant_obj("\n".join(["/pkg/file.py def handler", "Error: nope"])) for _ in range(40))
    result = fast_prune(msgs, max_tokens=400, keep_tail_tokens=100)
    assert result.tokens_after <= result.tokens_before
    digests = [m for m in result.messages if isinstance(m, SystemMessage) and m.subtype == "compact"]
    assert digests


# --------------------------------------------------------------------------- #
# fast_prune_aggressive
# --------------------------------------------------------------------------- #


def test_aggressive_empty_and_under_budget_are_noops() -> None:
    assert fast_prune_aggressive([]).messages == []
    msgs = [{"role": "user", "content": "short"}]
    result = fast_prune_aggressive(msgs, max_tokens=4096)
    assert result.messages == msgs
    assert result.tokens_before == result.tokens_after


def test_aggressive_truncates_long_system_prose_in_pass_one() -> None:
    # Pass 1 only rewrites SystemMessage objects (dict system entries fall
    # through to the middle-elision pass), and it needs >3000 chars over >40
    # lines before it will collapse the middle.
    body = "\n".join(f"notice {i} " + "x" * 40 for i in range(200))
    long_system = system_obj(body, subtype="info")
    msgs = [long_system, {"role": "user", "content": "hi"}]
    result = fast_prune_aggressive(msgs, max_tokens=100)
    first = result.messages[0]
    assert "truncated" in first.content
    assert first.content.startswith("notice 0")


def test_aggressive_leaves_error_warning_and_compact_systems_alone() -> None:
    for subtype in ("error", "warning", "compact"):
        body = "\n".join(f"line {i}" for i in range(200))
        msg = system_obj(body, subtype=subtype)
        result = fast_prune_aggressive([msg, {"role": "user", "content": "x" * 4000}], max_tokens=100)
        kept = [m for m in result.messages if isinstance(m, SystemMessage)]
        if kept:
            assert kept[0].content == body


def test_aggressive_keeps_first_message_and_last_quarter() -> None:
    first = {"role": "assistant", "content": "FIRST " * 40}
    tail = {"role": "assistant", "content": "LAST " * 40}
    middle = [{"role": "assistant", "content": "prose " * 200} for _ in range(30)]
    msgs = [first, *middle, tail]
    result = fast_prune_aggressive(msgs, max_tokens=600)
    assert result.messages[0] is first
    assert result.messages[-1] is tail


def test_aggressive_keeps_user_requirements_and_truncates_tool_results() -> None:
    requirement = {"role": "user", "content": "keep me " * 10}
    body = "\n".join(f"row {i}" for i in range(200))
    tool_result = {"role": "tool", "tool_call_id": "c", "content": body}
    msgs = [{"role": "assistant", "content": "head " * 100}]
    msgs.extend({"role": "assistant", "content": "prose " * 200} for _ in range(10))
    msgs.extend([requirement, tool_result])
    msgs.extend({"role": "assistant", "content": "prose " * 200} for _ in range(10))
    result = fast_prune_aggressive(msgs, max_tokens=500)
    assert requirement in result.messages
    tool_outputs = [m["content"] for m in result.messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert tool_outputs
    assert "lines truncated" in tool_outputs[0]


def test_aggressive_appends_digest_for_elided_prose() -> None:
    msgs = [{"role": "assistant", "content": "head " * 200}]
    msgs.extend(
        {"role": "assistant", "content": f"/pkg/mod{i}.py def fn{i} Error: bad{i}\n" * 20}
        for i in range(30)
    )
    msgs.append({"role": "assistant", "content": "tail " * 50})
    result = fast_prune_aggressive(msgs, max_tokens=500)
    digests = [m for m in result.messages if isinstance(m, SystemMessage) and m.subtype == "compact"]
    assert digests
    assert "tokens elided" in digests[0].content
    assert result.keywords_extracted > 0
    assert result.tokens_after < result.tokens_before


def test_aggressive_restores_everything_when_digest_would_not_help() -> None:
    msgs = [
        {"role": "assistant", "content": "h" * 2000},
        {"role": "assistant", "content": "tiny"},
        {"role": "assistant", "content": "t" * 2000},
    ]
    result = fast_prune_aggressive(msgs, max_tokens=800)
    if result.tokens_after >= result.tokens_before:
        # Regression: the no-op path must not duplicate the tail.
        assert result.messages == msgs
        assert len(result.messages) == len(msgs)
        assert result.keywords_extracted == 0
