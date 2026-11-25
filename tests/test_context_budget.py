"""Tests for the session context budget (phase P2)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from openlaoke.commands.base import CommandContext, CommandResult, ContextCommand, _parse_amount
from openlaoke.core.context_budget import (
    ContextBudget,
    _block_to_text,
    _content_to_text,
    cap_tokens,
    estimate_message_tokens,
    estimate_messages_tokens,
    estimate_text_tokens,
    resolve_budget,
)

_ASCII = "hello world this is a plain english sentence " * 20
_CJK = "这段中文用于校验估算器按字符计数的行为" * 60


def test_cjk_text_counts_more_tokens_than_ascii_of_same_length() -> None:
    cjk = _CJK[: len(_ASCII)]
    assert len(cjk) == len(_ASCII)
    assert estimate_text_tokens(cjk) > estimate_text_tokens(_ASCII) * 2


def test_ascii_estimate_close_to_chars_over_four() -> None:
    rough = len(_ASCII) // 4
    assert abs(estimate_text_tokens(_ASCII) - rough) <= rough * 0.25


def test_estimate_messages_handles_dict_tool_calls() -> None:
    messages = [
        {"role": "user", "content": "fix it"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": "Read", "args": {"file_path": "a.py"}}],
        },
    ]
    assert estimate_messages_tokens(messages) > estimate_text_tokens("fix it")


def test_cap_tokens_prefers_session_and_ignores_zero() -> None:
    assert cap_tokens(4000, 8000) == 4000
    assert cap_tokens(None, 8000) == 8000
    assert cap_tokens(0, 8000) == 8000
    assert cap_tokens(None, 0) is None


def test_effective_budget_is_min_of_window_and_cap() -> None:
    assert resolve_budget(model_window=200000, session_cap=64000).effective_budget == 64000
    assert resolve_budget(model_window=8192, session_cap=64000).effective_budget == 8192
    assert resolve_budget(model_window=None).effective_budget == 8192


def test_budget_usage_and_prune_targets() -> None:
    budget = resolve_budget(model_window=32000, session_cap=16000, used_tokens=4000)
    assert budget.remaining == 12000
    assert abs(budget.used_ratio - 0.25) < 1e-9
    ctx_budget, keep_tail = budget.prune_targets()
    assert ctx_budget == int(16000 * 0.8)
    assert keep_tail == ctx_budget // 3
    assert "16,000" in budget.render()


def test_prune_targets_have_a_floor() -> None:
    budget = ContextBudget(model_window=1000, cap=None)
    ctx_budget, keep_tail = budget.prune_targets()
    assert ctx_budget >= 2048 and keep_tail >= 2048


def _ctx(state: SimpleNamespace, args: str = "") -> CommandContext:
    return CommandContext(app_state=state, args=args)


def _state() -> SimpleNamespace:
    return SimpleNamespace(
        compact_state={"model_window": 32768, "used_tokens": 8000},
        context_cap=None,
        session_config=SimpleNamespace(model="qwen2.5-coder:7b"),
        set_context_cap=lambda tokens: None,
    )


def test_context_command_reports_window_and_usage() -> None:
    result: CommandResult = asyncio.run(ContextCommand().execute(_ctx(_state())))
    assert result.success
    assert "32,768" in result.message
    assert "8,000" in result.message


def test_context_command_sets_and_clears_session_cap() -> None:
    recorded: list[int | None] = []
    state = _state()
    state.set_context_cap = recorded.append  # type: ignore[assignment]

    asyncio.run(ContextCommand().execute(_ctx(state, "16k")))
    asyncio.run(ContextCommand().execute(_ctx(state, "clear")))
    assert recorded == [16384, None]


def test_context_command_rejects_nonsense_and_tiny_caps() -> None:
    bad = asyncio.run(ContextCommand().execute(_ctx(_state(), "banana")))
    assert not bad.success

    tiny = asyncio.run(ContextCommand().execute(_ctx(_state(), "512")))
    assert not tiny.success


def test_parse_amount_accepts_suffixes() -> None:
    assert _parse_amount("8k") == 8192
    assert _parse_amount("1M") == 1048576
    assert _parse_amount("12000") == 12000


# --------------------------------------------------------------------------- #
# Content normalisation (provider payloads arrive in several shapes)
# --------------------------------------------------------------------------- #


def test_empty_and_none_text_estimate_to_zero() -> None:
    assert estimate_text_tokens("") == 0
    assert _content_to_text(None) == ""


def test_content_string_and_list_of_blocks() -> None:
    assert _content_to_text("plain") == "plain"
    assert _content_to_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a\nb"
    assert _content_to_text(["x", "y"]) == "x\ny"


def test_content_dict_and_non_string_payloads() -> None:
    assert _content_to_text({"text": "hello", "input": "ARGS"}) == "helloARGS"
    assert _content_to_text({"content": "inner"}) == "inner"
    assert _content_to_text({"text": "only text"}) == "only text"
    assert _content_to_text(123) == "123"


def test_block_to_text_understands_objects_with_text_attribute() -> None:
    block = SimpleNamespace(text="obj text")
    assert _block_to_text(block) == "obj text"
    # Falls back to the content attribute when there is no text.
    assert _block_to_text(SimpleNamespace(content="obj content")) == "obj content"
    assert _block_to_text(SimpleNamespace()) == ""


def test_estimate_message_tokens_counts_typed_tool_calls() -> None:
    typed = SimpleNamespace(content="ok", tool_calls=[{"name": "Read"}])
    assert estimate_message_tokens(typed) > estimate_message_tokens(SimpleNamespace(content="ok", tool_calls=None))


def test_estimate_message_tokens_includes_per_message_overhead() -> None:
    assert estimate_message_tokens({"role": "user", "content": ""}) == 4
    assert estimate_message_tokens({"role": "user", "content": "abcd"}) == 5


def test_used_ratio_is_zero_for_a_degenerate_budget() -> None:
    budget = ContextBudget(model_window=0, cap=None, used_tokens=100)
    assert budget.effective_budget == 8192  # falls back to the default window
    assert budget.used_ratio == 100 / 8192
    empty = ContextBudget(model_window=None, cap=None)
    assert empty.used_ratio == 0.0


def test_render_reports_fallback_window_note() -> None:
    rendered = resolve_budget(model_window=None).render()
    assert "unknown" in rendered
    assert "conservative default" in rendered
    assert "Session cap  : none" in rendered

    capped = resolve_budget(model_window=32000, session_cap=8000, used_tokens=2000).render()
    assert "8,000" in capped
    assert "(25%)" in capped
    assert "conservative default" not in capped
