"""Tests for the compaction strategies (auto, reactive, snip, micro)."""

from __future__ import annotations

import pytest

from openlaoke.core.compact.strategies import (
    AutoCompactStrategy,
    MicroCompactStrategy,
    ReactiveCompactStrategy,
    SnipCompactStrategy,
    StrategyResult,
)
from openlaoke.core.compact.token_budget import TokenBudget
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    SystemMessage,
    UserMessage,
)


def user(text: str) -> UserMessage:
    return UserMessage(role=MessageRole.USER, content=text)


def assistant(text: str, tool_uses=None, stop_reason=None) -> AssistantMessage:
    return AssistantMessage(
        role=MessageRole.ASSISTANT,
        content=text,
        tool_uses=tool_uses or [],
        stop_reason=stop_reason,
    )


def system(text: str, subtype: str = "info") -> SystemMessage:
    return SystemMessage(role=MessageRole.SYSTEM, content=text, subtype=subtype)


# --------------------------------------------------------------------------- #
# StrategyResult / base helpers
# --------------------------------------------------------------------------- #


def test_compression_ratio_computed_from_tokens() -> None:
    result = StrategyResult(messages=[], tokens_before=1000, tokens_after=250, messages_removed=3, messages_preserved=1)
    assert result.compression_ratio == pytest.approx(0.75)


def test_compression_ratio_is_zero_without_before_tokens() -> None:
    result = StrategyResult(messages=[], tokens_before=0, tokens_after=0, messages_removed=0, messages_preserved=0)
    assert result.compression_ratio == 0.0


def test_estimate_tokens_is_four_chars_per_token() -> None:
    strategy = SnipCompactStrategy()
    assert strategy.estimate_tokens([user("a" * 400)]) == 100
    assert strategy.estimate_tokens([]) == 0


def test_importance_scores_recency_and_message_kind() -> None:
    strategy = SnipCompactStrategy()
    # Recency: last of 10 scores higher than first.
    assert strategy.get_message_importance(user("x"), 9, 10) > strategy.get_message_importance(user("x"), 0, 10)
    # Short user messages outrank long ones.
    short_user = strategy.get_message_importance(user("hi"), 5, 10)
    long_user = strategy.get_message_importance(user("y" * 600), 5, 10)
    assert short_user > long_user


def test_importance_rewards_tool_use_and_stop_reason() -> None:
    strategy = SnipCompactStrategy()
    plain = strategy.get_message_importance(assistant("done"), 5, 10)
    with_tools = strategy.get_message_importance(assistant("done", tool_uses=[object()]), 5, 10)
    tool_stop = strategy.get_message_importance(
        assistant("done", tool_uses=[object()], stop_reason="tool_use"), 5, 10
    )
    assert plain < with_tools < tool_stop


def test_importance_ranks_error_and_warning_system_messages_high() -> None:
    strategy = SnipCompactStrategy()
    plain_info = strategy.get_message_importance(system("ok"), 5, 10)
    compact = strategy.get_message_importance(system("sum", subtype="compact"), 5, 10)
    error = strategy.get_message_importance(system("bad", subtype="error"), 5, 10)
    warning = strategy.get_message_importance(system("careful", subtype="warning"), 5, 10)
    assert plain_info == compact < error == warning


def test_importance_is_clamped_to_one() -> None:
    strategy = SnipCompactStrategy()
    last_index = 99
    assert strategy.get_message_importance(user("hi"), last_index, 100) <= 1.0


# --------------------------------------------------------------------------- #
# AutoCompact
# --------------------------------------------------------------------------- #


def test_auto_should_apply_only_past_threshold() -> None:
    strategy = AutoCompactStrategy()
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, trigger_threshold=0.8)
    assert strategy.should_apply([user("x" * 100)], budget) is False  # 25 tokens
    assert strategy.should_apply([user("x" * 4000)], budget) is True  # 1000 tokens


@pytest.mark.asyncio
async def test_auto_is_a_noop_below_threshold() -> None:
    strategy = AutoCompactStrategy()
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, trigger_threshold=0.8)
    messages = [user("hi")]
    result = await strategy.compact(messages, budget)
    assert result.messages == messages
    assert result.messages_removed == 0
    assert result.messages_preserved == len(messages)
    assert result.tokens_after == result.tokens_before


@pytest.mark.asyncio
async def test_auto_trims_by_importance_without_summarizer() -> None:
    strategy = AutoCompactStrategy()
    # 10 messages x 1000 chars = 250 tokens each, 2500 total; keep ~25%.
    budget = TokenBudget(
        max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, trigger_threshold=0.5, keep_fraction=0.25
    )
    messages = [user(f"message {i} " + "x" * 990) for i in range(10)]
    result = await strategy.compact(messages, budget)
    assert result.tokens_before == 2500
    assert 0 < result.messages_preserved < len(messages)
    assert result.messages_removed == len(messages) - len(result.messages)
    assert result.tokens_after < result.tokens_before
    # Preserved messages keep their original relative order.
    positions = [messages.index(m) for m in result.messages]
    assert positions == sorted(positions)


@pytest.mark.asyncio
async def test_auto_keeps_recent_messages_when_trimming() -> None:
    strategy = AutoCompactStrategy()
    budget = TokenBudget(
        max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, trigger_threshold=0.5, keep_fraction=0.25
    )
    messages = [user(f"m{i} " + "x" * 996) for i in range(10)]
    result = await strategy.compact(messages, budget)
    # The newest message has the highest recency score, so it survives.
    assert messages[-1] in result.messages


@pytest.mark.asyncio
async def test_auto_handles_empty_message_list() -> None:
    strategy = AutoCompactStrategy()
    budget = TokenBudget(max_input_tokens=10, reserved_tokens=0, tool_tokens=0)
    result = await strategy.compact([], budget)
    assert result.messages == []
    assert result.messages_removed == 0


class FakeSummarizer:
    """Stands in for MessageSummarizer in the summary compaction path."""

    def __init__(self, summary: str = "the summary", preserve: list | None = None) -> None:
        self.summary = summary
        self.preserve = preserve or []

    async def summarize_with_preserve(self, messages):
        return type("R", (), {"summary": self.summary, "original_tokens": 1, "summary_tokens": 1})()

    def create_summary_message(self, summary: str) -> SystemMessage:
        return system(f"[Context Summary]\n{summary}", subtype="compact")

    def split_messages(self, messages):
        to_summarize = [m for m in messages if m not in self.preserve]
        return to_summarize, list(self.preserve)


@pytest.mark.asyncio
async def test_auto_uses_summarizer_when_available() -> None:
    strategy = AutoCompactStrategy()
    budget = TokenBudget(max_input_tokens=100, reserved_tokens=0, tool_tokens=0)
    messages = [user("x" * 800) for _ in range(4)]
    preserved = [messages[-1]]
    result = await strategy.compact(messages, budget, summarizer=FakeSummarizer(preserve=preserved))
    assert result.summary == "the summary"
    assert result.messages[0].content.startswith("[Context Summary]")
    assert result.messages[0].subtype == "compact"
    assert result.messages[1:] == preserved
    assert result.messages_removed == len(messages) - len(preserved)
    assert result.messages_preserved == len(preserved)
    assert result.tokens_after < result.tokens_before


# --------------------------------------------------------------------------- #
# ReactiveCompact
# --------------------------------------------------------------------------- #


def test_reactive_always_applies() -> None:
    assert ReactiveCompactStrategy().should_apply([], TokenBudget()) is True


@pytest.mark.asyncio
async def test_reactive_leaves_short_content_and_non_system_messages_alone() -> None:
    strategy = ReactiveCompactStrategy(max_tool_result_tokens=10)
    messages = [user("short"), assistant("short"), system("short")]
    result = await strategy.compact(messages, TokenBudget())
    assert result.messages == messages
    assert result.messages_removed == 0
    assert result.tokens_after == result.tokens_before


@pytest.mark.asyncio
async def test_reactive_truncates_long_line_oriented_output() -> None:
    strategy = ReactiveCompactStrategy(max_tool_result_tokens=1)  # 4-char budget
    lines = [f"line-{i}" for i in range(150)]
    messages = [system("\n".join(lines))]
    result = await strategy.compact(messages, TokenBudget())
    content = result.messages[0].content
    assert content.startswith("line-0\nline-1")
    assert "truncated 80 lines" in content  # 150 - (50 head + 20 tail)
    assert content.endswith("line-149")
    assert result.messages_removed == 0  # same message count, content shortened
    assert result.tokens_after < result.tokens_before


@pytest.mark.asyncio
async def test_reactive_truncates_wide_single_line_output_by_chars() -> None:
    strategy = ReactiveCompactStrategy(max_tool_result_tokens=10)  # 40-char budget
    messages = [system("x" * 500)]
    result = await strategy.compact(messages, TokenBudget())
    content = result.messages[0].content
    assert content.startswith("x" * 40)
    assert content.endswith("\n... [truncated] ...")


@pytest.mark.asyncio
async def test_reactive_preserves_message_metadata_on_truncation() -> None:
    strategy = ReactiveCompactStrategy(max_tool_result_tokens=1)
    original = SystemMessage(
        role=MessageRole.SYSTEM,
        content="z" * 500,
        subtype="result",
        tool_use_id="call_7",
        timestamp=42.0,
    )
    result = await strategy.compact([original], TokenBudget())
    shortened = result.messages[0]
    assert shortened.subtype == "result"
    assert shortened.timestamp == 42.0


# --------------------------------------------------------------------------- #
# SnipCompact
# --------------------------------------------------------------------------- #


def test_snip_applies_only_above_keep_recent() -> None:
    strategy = SnipCompactStrategy(keep_recent=3)
    assert strategy.should_apply([user("a")] * 3, TokenBudget()) is False
    assert strategy.should_apply([user("a")] * 4, TokenBudget()) is True


@pytest.mark.asyncio
async def test_snip_keeps_only_the_tail() -> None:
    strategy = SnipCompactStrategy(keep_recent=3)
    messages = [user(f"m{i}") for i in range(6)]
    result = await strategy.compact(messages, TokenBudget())
    assert result.messages == messages[-3:]
    assert result.messages_removed == 3
    assert result.messages_preserved == 3


@pytest.mark.asyncio
async def test_snip_is_a_noop_at_or_below_keep_recent() -> None:
    strategy = SnipCompactStrategy(keep_recent=5)
    messages = [user(f"m{i}") for i in range(3)]
    result = await strategy.compact(messages, TokenBudget())
    assert result.messages == messages
    assert result.messages_removed == 0
    assert result.messages_preserved == 3


# --------------------------------------------------------------------------- #
# MicroCompact
# --------------------------------------------------------------------------- #


def test_micro_applies_only_past_half_the_available_budget() -> None:
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0)
    strategy = MicroCompactStrategy()
    assert strategy.should_apply([user("x" * 100)], budget) is False  # 25 of 500
    assert strategy.should_apply([user("x" * 2400)], budget) is True  # 600 of 500


@pytest.mark.asyncio
async def test_micro_drops_exact_duplicate_system_messages() -> None:
    strategy = MicroCompactStrategy()
    messages = [
        system("duplicate output", subtype="result"),
        user("question"),
        system("duplicate output", subtype="result"),
    ]
    result = await strategy.compact(messages, TokenBudget())
    assert len(result.messages) == 2
    assert result.messages_removed == 1
    assert result.messages == [messages[0], messages[1]]


@pytest.mark.asyncio
async def test_micro_keeps_duplicates_of_different_subtype_or_role() -> None:
    strategy = MicroCompactStrategy()
    messages = [
        system("same text", subtype="result"),
        system("same text", subtype="error"),
        user("same text"),
        user("same text"),
    ]
    result = await strategy.compact(messages, TokenBudget())
    assert len(result.messages) == 4
    assert result.messages_removed == 0


@pytest.mark.asyncio
async def test_micro_leaves_single_message_alone() -> None:
    strategy = MicroCompactStrategy()
    messages = [system("only")]
    result = await strategy.compact(messages, TokenBudget())
    assert result.messages == messages
    assert result.messages_removed == 0


@pytest.mark.asyncio
async def test_micro_handles_empty_input() -> None:
    result = await MicroCompactStrategy().compact([], TokenBudget())
    assert result.messages == []
    assert result.tokens_before == 0
    assert result.tokens_after == 0
