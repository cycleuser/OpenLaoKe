"""Token budget management for context compaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.types.core_types import TokenUsage


class BudgetType(StrEnum):
    """Types of token budget specifications."""

    FIXED = "fixed"
    FRACTION = "fraction"
    DYNAMIC = "dynamic"


@dataclass
class Allocation:
    """Token allocation result."""

    total_available: int = 0
    system_reserved: int = 0
    tools_reserved: int = 0
    cache_available: int = 0
    messages_allocated: int = 0
    output_allocated: int = 0
    remaining: int = 0

    def is_within_budget(self, tokens: int) -> bool:
        return tokens <= self.remaining


@dataclass
class TokenBudget:
    """Token budget management for context window."""

    max_input_tokens: int = 200000
    max_output_tokens: int = 8192
    reserved_tokens: int = 10000
    tool_tokens: int = 5000
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    budget_type: BudgetType = BudgetType.FIXED
    trigger_threshold: float = 0.80
    keep_fraction: float = 0.30

    def get_available_tokens(self) -> int:
        total_reserved = self.reserved_tokens + self.tool_tokens
        available = self.max_input_tokens - total_reserved
        if self.cache_read_tokens > 0:
            available += self.cache_read_tokens
        return max(0, available)

    def get_trigger_threshold(self) -> int:
        available = self.get_available_tokens()
        return int(available * self.trigger_threshold)

    def get_keep_tokens(self) -> int:
        if self.budget_type == BudgetType.FRACTION:
            return int(self.max_input_tokens * self.keep_fraction)
        return int(self.get_available_tokens() * self.keep_fraction)

    def allocate(
        self,
        system_tokens: int = 0,
        tool_tokens: int = 0,
        output_tokens: int = 0,
    ) -> Allocation:
        total_available = self.get_available_tokens()
        system_reserved = max(system_tokens, self.reserved_tokens)
        tools_reserved = max(tool_tokens, self.tool_tokens)
        output_allocated = min(output_tokens, self.max_output_tokens)

        remaining_for_messages = total_available - system_reserved - tools_reserved
        messages_allocated = min(remaining_for_messages, total_available - output_allocated)

        return Allocation(
            total_available=total_available,
            system_reserved=system_reserved,
            tools_reserved=tools_reserved,
            cache_available=self.cache_read_tokens,
            messages_allocated=messages_allocated,
            output_allocated=output_allocated,
            remaining=total_available - system_reserved - tools_reserved - messages_allocated,
        )

    def check_overflow(self, current_tokens: int) -> bool:
        threshold = self.get_trigger_threshold()
        return current_tokens >= threshold

    def get_overflow_amount(self, current_tokens: int) -> int:
        available = self.get_available_tokens()
        if current_tokens <= available:
            return 0
        return current_tokens - available

    def get_target_tokens(self, current_tokens: int) -> int:
        keep_tokens = self.get_keep_tokens()
        return min(keep_tokens, current_tokens)

    def update_cache_tokens(self, read: int, creation: int) -> None:
        self.cache_read_tokens = read
        self.cache_creation_tokens = creation


@dataclass
class TokenUsageTracker:
    """Track token usage over time."""

    total_input: int = 0
    total_output: int = 0
    peak_input: int = 0
    peak_output: int = 0
    history: list[tuple[float, int, int]] = field(default_factory=list)

    def track_usage(self, usage: TokenUsage, timestamp: float = 0.0) -> None:
        from time import time

        ts = timestamp or time()
        self.total_input += usage.input_tokens
        self.total_output += usage.output_tokens
        self.peak_input = max(self.peak_input, usage.input_tokens)
        self.peak_output = max(self.peak_output, usage.output_tokens)
        self.history.append((ts, usage.input_tokens, usage.output_tokens))

    def get_average_input(self) -> float:
        if not self.history:
            return 0.0
        return sum(h[1] for h in self.history) / len(self.history)

    def get_average_output(self) -> float:
        if not self.history:
            return 0.0
        return sum(h[2] for h in self.history) / len(self.history)

    def get_total_tokens(self) -> int:
        return self.total_input + self.total_output

    def reset(self) -> None:
        self.total_input = 0
        self.total_output = 0
        self.peak_input = 0
        self.peak_output = 0
        self.history.clear()
