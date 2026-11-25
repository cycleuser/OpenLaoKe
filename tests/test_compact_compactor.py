"""Tests for ContextCompactor: strategy wiring, dispatch, the full-compact
ladder, stats and budget helpers. Strategies are stubbed where the ladder
order matters, so no provider client is required.
"""

from __future__ import annotations

import pytest

from openlaoke.core.compact.compactor import (
    CompactConfig,
    CompactResult,
    CompactType,
    ContextCompactor,
)
from openlaoke.core.compact.strategies import StrategyResult
from openlaoke.core.compact.token_budget import TokenBudget
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    SystemMessage,
    TokenUsage,
    UserMessage,
)


def user(text: str) -> UserMessage:
    return UserMessage(role=MessageRole.USER, content=text)


def assistant(text: str) -> AssistantMessage:
    return AssistantMessage(role=MessageRole.ASSISTANT, content=text)


class StubStrategy:
    """Records calls and returns a canned StrategyResult."""

    def __init__(self, tokens_after: int, summary: str | None = None) -> None:
        self.tokens_after = tokens_after
        self.summary = summary
        self.calls: list[list] = []

    async def compact(self, messages, budget, summarizer=None):
        self.calls.append(list(messages))
        # Emit messages whose real token estimate matches tokens_after, so the
        # ladder gates and the subsequent auto_compact re-check agree.
        tail = [user("x" * (self.tokens_after * 4))] if self.tokens_after else []
        return StrategyResult(
            messages=tail,
            tokens_before=len(messages) * 100,
            tokens_after=self.tokens_after,
            messages_removed=max(0, len(messages) - len(tail)),
            messages_preserved=len(tail),
            summary=self.summary,
        )


# --------------------------------------------------------------------------- #
# CompactConfig / construction
# --------------------------------------------------------------------------- #


def test_config_builds_a_budget_with_its_thresholds() -> None:
    config = CompactConfig(trigger_threshold=0.5, keep_fraction=0.2)
    budget = config.get_token_budget(max_input=1000, max_output=100)
    assert budget.trigger_threshold == 0.5
    assert budget.keep_fraction == 0.2
    assert budget.max_input_tokens == 1000
    assert budget.max_output_tokens == 100


def test_config_budget_keeps_full_reserves_at_the_default_window() -> None:
    budget = CompactConfig().get_token_budget()
    assert budget.reserved_tokens == 10_000
    assert budget.tool_tokens == 5_000
    assert budget.get_available_tokens() == 185_000


def test_config_budget_scales_reserves_down_for_small_windows() -> None:
    # A 8k window with the fixed 10k + 5k reserves would leave zero available
    # tokens and a zero keep target, so compaction would erase the history.
    budget = CompactConfig().get_token_budget(max_input=8_192)
    assert budget.get_available_tokens() > 0
    assert budget.get_trigger_threshold() > 0
    assert budget.get_keep_tokens() > 0


def test_compactor_registers_the_four_strategies() -> None:
    compactor = ContextCompactor(CompactConfig())
    assert set(compactor.strategies) == {
        CompactType.AUTO,
        CompactType.REACTIVE,
        CompactType.SNIP,
        CompactType.MICRO,
    }


def test_no_summarizer_without_a_client() -> None:
    assert ContextCompactor(CompactConfig())._summarizer is None


@pytest.mark.parametrize("use_summarization", [True, False])
def test_summarizer_only_with_client_and_flag(use_summarization: bool) -> None:
    client = object()  # MessageSummarizer stores it; never called here
    compactor = ContextCompactor(CompactConfig(use_summarization=use_summarization), client=client)
    assert (compactor._summarizer is not None) is use_summarization


def test_budget_is_cached_unless_explicitly_set() -> None:
    compactor = ContextCompactor(CompactConfig())
    first = compactor.get_budget()
    assert compactor.get_budget() is first
    custom = TokenBudget(max_input_tokens=1234)
    compactor.set_budget(custom)
    assert compactor.get_budget() is custom


def test_estimate_tokens_handles_all_message_kinds() -> None:
    compactor = ContextCompactor(CompactConfig())
    messages = [user("a" * 400), assistant("b" * 400), SystemMessage(role=MessageRole.SYSTEM, content="c" * 400)]
    assert compactor.estimate_tokens(messages) == 300


# --------------------------------------------------------------------------- #
# should_compact / allocate_budget
# --------------------------------------------------------------------------- #


def test_should_compact_uses_the_overflow_threshold() -> None:
    compactor = ContextCompactor(CompactConfig(trigger_threshold=0.8))
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0)
    assert compactor.should_compact([user("x" * 1000)], budget) is False  # 250
    assert compactor.should_compact([user("x" * 4000)], budget) is True  # 1000


def test_should_compact_defaults_to_the_cached_budget() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(TokenBudget(max_input_tokens=10, reserved_tokens=0, tool_tokens=0))
    assert compactor.should_compact([user("y" * 100)]) is True


def test_allocate_budget_reserves_a_tenth_of_current_tokens() -> None:
    compactor = ContextCompactor(CompactConfig())
    budget = TokenBudget(max_input_tokens=10_000, reserved_tokens=100, tool_tokens=100)
    alloc = compactor.allocate_budget([user("z" * 4000)], budget)  # 1000 tokens -> 100 system
    assert alloc.system_reserved == 100  # max(1000 // 10, 100)
    assert alloc.total_available == 9_800


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_compact_dispatches_to_the_configured_default() -> None:
    compactor = ContextCompactor(CompactConfig(default_type=CompactType.SNIP))
    stub = StubStrategy(tokens_after=50, summary=None)
    compactor.strategies[CompactType.SNIP] = stub
    result = await compactor.compact([user("a"), user("b")])
    assert len(stub.calls) == 1
    assert result.compact_type == CompactType.SNIP
    assert result.messages_preserved == 1
    assert result.messages_removed == 1


@pytest.mark.asyncio
async def test_compact_honours_an_explicit_type() -> None:
    compactor = ContextCompactor(CompactConfig(default_type=CompactType.SNIP))
    snip, micro = StubStrategy(tokens_after=10), StubStrategy(tokens_after=20)
    compactor.strategies[CompactType.SNIP] = snip
    compactor.strategies[CompactType.MICRO] = micro
    result = await compactor.compact([user("a")], compact_type=CompactType.MICRO)
    assert len(snip.calls) == 0
    assert result.compact_type == CompactType.MICRO


@pytest.mark.asyncio
async def test_compact_falls_back_to_auto_for_unknown_type() -> None:
    compactor = ContextCompactor(CompactConfig())
    auto = StubStrategy(tokens_after=10)
    compactor.strategies[CompactType.AUTO] = auto
    # "bogus" is not a registered strategy key.
    result = await compactor.compact([user("a")], compact_type="bogus")  # type: ignore[arg-type]
    assert len(auto.calls) == 1
    assert result.compact_type == "bogus"


@pytest.mark.asyncio
async def test_compact_result_carries_allocation_and_summary() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.strategies[CompactType.AUTO] = StubStrategy(tokens_after=5, summary="brief")
    result = await compactor.compact([user("a")])
    assert result.summary == "brief"
    assert result.allocation is not None
    assert result.tokens_after == 5


def test_compact_result_compression_ratio_and_payload() -> None:
    result = CompactResult(
        messages=[user("a")],
        tokens_before=400,
        tokens_after=100,
        messages_removed=3,
        messages_preserved=1,
        compact_type=CompactType.AUTO,
        summary="s",
    )
    assert result.compression_ratio == pytest.approx(0.75)
    payload = result.to_dict()
    assert payload["compact_type"] == "auto"
    assert payload["compression_ratio"] == pytest.approx(0.75)
    assert payload["summary"] == "s"


def test_compact_result_zero_ratio_without_before_tokens() -> None:
    result = CompactResult(
        messages=[], tokens_before=0, tokens_after=0, messages_removed=0, messages_preserved=0,
        compact_type=CompactType.AUTO,
    )
    assert result.compression_ratio == 0.0


# --------------------------------------------------------------------------- #
# Convenience wrappers
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_auto_compact_is_a_noop_below_threshold() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(TokenBudget(max_input_tokens=100_000, reserved_tokens=0, tool_tokens=0))
    messages = [user("small")]
    result = await compactor.auto_compact(messages)
    assert result.messages == messages
    assert result.messages_removed == 0
    assert result.tokens_before == result.tokens_after
    assert result.compact_type == CompactType.AUTO


@pytest.mark.asyncio
async def test_auto_compact_compacts_when_over_threshold() -> None:
    compactor = ContextCompactor(CompactConfig(trigger_threshold=0.5))
    compactor.set_budget(TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, keep_fraction=0.1))
    messages = [user(f"m{i} " + "x" * 996) for i in range(10)]
    result = await compactor.auto_compact(messages)
    assert result.messages_removed > 0
    assert result.tokens_after < result.tokens_before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrapper,compact_type",
    [
        ("reactive_compact", CompactType.REACTIVE),
        ("snip_compact", CompactType.SNIP),
        ("micro_compact", CompactType.MICRO),
    ],
)
async def test_wrappers_use_their_own_strategy(wrapper: str, compact_type: CompactType) -> None:
    compactor = ContextCompactor(CompactConfig())
    stub = StubStrategy(tokens_after=1)
    compactor.strategies[compact_type] = stub
    result = await getattr(compactor, wrapper)([user("a")])
    assert len(stub.calls) == 1
    assert result.compact_type == compact_type


@pytest.mark.asyncio
async def test_full_compact_stops_after_micro_when_it_is_enough() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(TokenBudget(max_input_tokens=10_000, reserved_tokens=0, tool_tokens=0))
    micro, snip, auto = StubStrategy(10), StubStrategy(10), StubStrategy(10)
    compactor.strategies.update(
        {CompactType.MICRO: micro, CompactType.SNIP: snip, CompactType.AUTO: auto}
    )
    result = await compactor.full_compact([user("a")])
    assert result.compact_type == CompactType.MICRO
    assert (len(micro.calls), len(snip.calls), len(auto.calls)) == (1, 0, 0)


@pytest.mark.asyncio
async def test_full_compact_escalates_to_snip_then_auto() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(TokenBudget(max_input_tokens=100, reserved_tokens=0, tool_tokens=0))
    micro = StubStrategy(500)  # still over the 100-token budget
    snip = StubStrategy(400)  # still over
    auto = StubStrategy(50)  # fits
    compactor.strategies.update(
        {CompactType.MICRO: micro, CompactType.SNIP: snip, CompactType.AUTO: auto}
    )
    result = await compactor.full_compact([user("a")])
    assert result.compact_type == CompactType.AUTO
    assert (len(micro.calls), len(snip.calls), len(auto.calls)) == (1, 1, 1)


@pytest.mark.asyncio
async def test_full_compact_stops_at_snip_when_it_fits() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(TokenBudget(max_input_tokens=100, reserved_tokens=0, tool_tokens=0))
    micro, snip, auto = StubStrategy(500), StubStrategy(50), StubStrategy(10)
    compactor.strategies.update(
        {CompactType.MICRO: micro, CompactType.SNIP: snip, CompactType.AUTO: auto}
    )
    result = await compactor.full_compact([user("a")])
    assert result.compact_type == CompactType.SNIP
    assert len(auto.calls) == 0


# --------------------------------------------------------------------------- #
# Stats and budget bookkeeping
# --------------------------------------------------------------------------- #


def test_compaction_stats_reports_overflow_state() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(
        TokenBudget(
            max_input_tokens=1000,
            reserved_tokens=0,
            tool_tokens=0,
            trigger_threshold=0.5,
        )
    )
    stats = compactor.get_compaction_stats([user("x" * 4000)])  # 1000 tokens
    assert stats["current_tokens"] == 1000
    assert stats["available_tokens"] == 1000
    assert stats["threshold_tokens"] == 500
    assert stats["message_count"] == 1
    assert stats["overflow"] is True
    assert stats["overflow_amount"] == 0
    assert stats["recommended_action"] == "auto"


def test_compaction_stats_without_overflow_recommends_nothing() -> None:
    compactor = ContextCompactor(CompactConfig())
    stats = compactor.get_compaction_stats([user("tiny")])
    assert stats["overflow"] is False
    assert stats["recommended_action"] == "none"


@pytest.mark.parametrize(
    "current,threshold,available,expected",
    [
        (50, 100, 200, "none"),  # at/below threshold
        (120, 100, 200, "micro"),  # just past threshold
        (150, 100, 400, "snip"),  # past 1.2x threshold but below 0.8 available
        (400, 100, 400, "auto"),  # near the hard limit
    ],
)
def test_recommended_action_ladder(current: int, threshold: int, available: int, expected: str) -> None:
    compactor = ContextCompactor(CompactConfig())
    assert compactor._get_recommended_action(current, threshold, available) == expected


def test_track_usage_updates_budget_cache_counters() -> None:
    compactor = ContextCompactor(CompactConfig())
    budget = TokenBudget()
    compactor.set_budget(budget)
    compactor.track_usage(TokenUsage(input_tokens=0, output_tokens=0, cache_read_tokens=900, cache_creation_tokens=30))
    assert budget.cache_read_tokens == 900
    assert budget.cache_creation_tokens == 30


def test_can_add_message_checks_projected_tokens() -> None:
    compactor = ContextCompactor(CompactConfig())
    compactor.set_budget(TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0))
    assert compactor.can_add_message([], user("a" * 3996)) is True  # 999 < 1000
    assert compactor.can_add_message([], user("a" * 4000)) is False  # 1000 is not < 1000
    assert compactor.can_add_message([user("b" * 3600)], user("c" * 400)) is False  # 900+100
