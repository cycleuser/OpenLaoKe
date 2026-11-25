"""Tests for the token budget model used by context compaction."""

from __future__ import annotations

import pytest

from openlaoke.core.compact.token_budget import (
    Allocation,
    BudgetType,
    TokenBudget,
    TokenUsageTracker,
)
from openlaoke.types.core_types import TokenUsage

# --------------------------------------------------------------------------- #
# TokenBudget arithmetic
# --------------------------------------------------------------------------- #


def test_available_tokens_subtracts_reserved_and_tool_budgets() -> None:
    budget = TokenBudget(max_input_tokens=200_000, reserved_tokens=10_000, tool_tokens=5_000)
    assert budget.get_available_tokens() == 185_000


def test_available_tokens_adds_cache_reads() -> None:
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, cache_read_tokens=400)
    assert budget.get_available_tokens() == 1400


def test_available_tokens_never_goes_negative() -> None:
    budget = TokenBudget(max_input_tokens=100, reserved_tokens=1000, tool_tokens=1000)
    assert budget.get_available_tokens() == 0


def test_trigger_threshold_is_a_fraction_of_available() -> None:
    budget = TokenBudget(max_input_tokens=100_000, reserved_tokens=0, tool_tokens=0, trigger_threshold=0.8)
    assert budget.get_trigger_threshold() == 80_000


def test_keep_tokens_default_mode_scales_with_available() -> None:
    budget = TokenBudget(
        max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, keep_fraction=0.25
    )
    assert budget.get_keep_tokens() == 250


def test_keep_tokens_fraction_mode_scales_with_raw_window() -> None:
    budget = TokenBudget(
        max_input_tokens=1000,
        reserved_tokens=500,
        tool_tokens=0,
        keep_fraction=0.25,
        budget_type=BudgetType.FRACTION,
    )
    # 1000 * 0.25, not (1000-500) * 0.25
    assert budget.get_keep_tokens() == 250
    budget.keep_fraction = 0.5
    assert budget.get_keep_tokens() == 500


def test_check_overflow_is_inclusive_at_threshold() -> None:
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, trigger_threshold=0.8)
    assert budget.check_overflow(799) is False
    assert budget.check_overflow(800) is True  # exactly at threshold triggers
    assert budget.check_overflow(801) is True


def test_overflow_amount_only_when_past_available() -> None:
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0)
    assert budget.get_overflow_amount(1000) == 0
    assert budget.get_overflow_amount(1500) == 500


def test_target_tokens_never_exceeds_current() -> None:
    budget = TokenBudget(max_input_tokens=1000, reserved_tokens=0, tool_tokens=0, keep_fraction=0.5)
    assert budget.get_target_tokens(400) == 400  # keep 500 but only 400 exist
    assert budget.get_target_tokens(1000) == 500


def test_update_cache_tokens_records_both_counters() -> None:
    budget = TokenBudget()
    budget.update_cache_tokens(read=123, creation=45)
    assert budget.cache_read_tokens == 123
    assert budget.cache_creation_tokens == 45


# --------------------------------------------------------------------------- #
# allocate()
# --------------------------------------------------------------------------- #


def test_allocate_uses_reserved_minimums() -> None:
    budget = TokenBudget(max_input_tokens=10_000, reserved_tokens=1_000, tool_tokens=500)
    alloc = budget.allocate(system_tokens=200, tool_tokens=100, output_tokens=1000)
    assert alloc.total_available == 8_500
    # Reserved floors win over the smaller actuals.
    assert alloc.system_reserved == 1_000
    assert alloc.tools_reserved == 500
    assert alloc.messages_allocated == 7_000
    assert alloc.remaining == 0


def test_allocate_honours_larger_actuals() -> None:
    budget = TokenBudget(max_input_tokens=10_000, reserved_tokens=1_000, tool_tokens=500)
    alloc = budget.allocate(system_tokens=3_000, tool_tokens=2_000, output_tokens=10)
    assert alloc.system_reserved == 3_000
    assert alloc.tools_reserved == 2_000
    assert alloc.messages_allocated == 3_500
    assert alloc.output_allocated == 10


def test_allocate_caps_output_at_max_output_tokens() -> None:
    budget = TokenBudget(max_output_tokens=8192)
    alloc = budget.allocate(output_tokens=99_999)
    assert alloc.output_allocated == 8192


def test_allocate_clamps_message_allocation_at_zero() -> None:
    # Reserved floors alone exceed the available budget.
    budget = TokenBudget(max_input_tokens=1_000, reserved_tokens=8_000, tool_tokens=8_000)
    alloc = budget.allocate()
    assert alloc.total_available == 0
    assert alloc.messages_allocated == 0
    # An over-committed budget reports no spare room, not a negative amount.
    assert alloc.remaining == 0


def test_allocate_reports_cache_available() -> None:
    budget = TokenBudget(cache_read_tokens=321)
    assert budget.allocate().cache_available == 321


def test_allocation_within_budget() -> None:
    assert Allocation(remaining=100).is_within_budget(100) is True
    assert Allocation(remaining=100).is_within_budget(101) is False


# --------------------------------------------------------------------------- #
# TokenUsageTracker
# --------------------------------------------------------------------------- #


def test_tracker_accumulates_and_peaks() -> None:
    tracker = TokenUsageTracker()
    tracker.track_usage(TokenUsage(input_tokens=100, output_tokens=20), timestamp=1.0)
    tracker.track_usage(TokenUsage(input_tokens=50, output_tokens=60), timestamp=2.0)
    assert tracker.total_input == 150
    assert tracker.total_output == 80
    assert tracker.peak_input == 100
    assert tracker.peak_output == 60
    assert tracker.get_total_tokens() == 230
    assert tracker.get_average_input() == pytest.approx(75.0)
    assert tracker.get_average_output() == pytest.approx(40.0)


def test_tracker_stamps_history_with_current_time_by_default() -> None:
    tracker = TokenUsageTracker()
    tracker.track_usage(TokenUsage(input_tokens=1, output_tokens=2))
    assert len(tracker.history) == 1
    ts, tin, tout = tracker.history[0]
    assert ts > 0
    assert (tin, tout) == (1, 2)


def test_tracker_averages_are_zero_without_history() -> None:
    tracker = TokenUsageTracker()
    assert tracker.get_average_input() == 0.0
    assert tracker.get_average_output() == 0.0
    assert tracker.get_total_tokens() == 0


def test_tracker_reset_clears_everything() -> None:
    tracker = TokenUsageTracker()
    tracker.track_usage(TokenUsage(input_tokens=10, output_tokens=10), timestamp=1.0)
    tracker.reset()
    assert tracker.total_input == 0
    assert tracker.total_output == 0
    assert tracker.peak_input == 0
    assert tracker.peak_output == 0
    assert tracker.history == []
