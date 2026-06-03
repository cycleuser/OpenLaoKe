"""Adaptive model router - switches models based on failure rates.

When success rate drops below threshold, automatically promotes to a stronger model tier.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RouterStats:
    consecutive_failures: int = 0
    total_calls: int = 0
    total_failures: int = 0
    promoted_count: int = 0


@dataclass
class TierConfig:
    name: str
    model: str
    min_success_rate: float = 0.3
    min_calls_before_routing: int = 3


class AdaptiveRouter:
    """Auto-switches model tier based on failure rate.

    Tiers (increasing strength):
      fast -> default -> strong

    When failure rate exceeds threshold for current tier,
    automatically promotes to the next stronger tier.
    Demotions happen when the stronger tier's failure rate also
    exceeds threshold (falling back to original).
    """

    def __init__(
        self,
        fast_model: str = "gemma3:1b",
        default_model: str = "llama3.2",
        strong_model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._tiers: list[TierConfig] = [
            TierConfig(name="fast", model=fast_model, min_success_rate=0.3),
            TierConfig(name="default", model=default_model, min_success_rate=0.25),
            TierConfig(name="strong", model=strong_model, min_success_rate=0.2),
        ]
        self._current_tier: int = 0
        self._stats: defaultdict[str, RouterStats] = defaultdict(RouterStats)
        self._session_promotions: int = 0
        self._max_promotions: int = 5

    @property
    def current_model(self) -> str:
        return self._tiers[self._current_tier].model

    @property
    def current_tier_name(self) -> str:
        return self._tiers[self._current_tier].name

    def should_promote(self) -> bool:
        """Check if current model should be promoted based on failure rate."""
        tier = self._tiers[self._current_tier]
        stats = self._stats[tier.name]

        if stats.total_calls < tier.min_calls_before_routing:
            return False

        success_rate = (
            (stats.total_calls - stats.total_failures) / stats.total_calls
            if stats.total_calls > 0
            else 1.0
        )
        return success_rate < tier.min_success_rate

    def promote(self) -> str | None:
        """Promote to next stronger tier. Returns new model name or None if at max."""
        if self._current_tier >= len(self._tiers) - 1:
            return None
        if self._session_promotions >= self._max_promotions:
            return None

        self._current_tier += 1
        self._session_promotions += 1
        tier = self._tiers[self._current_tier]
        self._stats[tier.name].promoted_count += 1
        return tier.model

    def should_demote(self) -> bool:
        """Check if current tier should be demoted (stronger model also failing)."""
        if self._current_tier <= 0:
            return False

        tier = self._tiers[self._current_tier]
        stats = self._stats[tier.name]

        if stats.total_calls < tier.min_calls_before_routing:
            return False

        success_rate = (
            (stats.total_calls - stats.total_failures) / stats.total_calls
            if stats.total_calls > 0
            else 1.0
        )
        return success_rate < tier.min_success_rate and stats.total_failures >= 2

    def demote(self) -> str | None:
        """Demote to next weaker tier. Returns new model name."""
        if self._current_tier <= 0:
            return None
        self._current_tier -= 1
        return self._tiers[self._current_tier].model

    def record_success(self) -> None:
        """Record a successful call for the current tier."""
        tier = self._tiers[self._current_tier]
        self._stats[tier.name].total_calls += 1
        self._stats[tier.name].consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed call and check if promotion is needed."""
        tier = self._tiers[self._current_tier]
        self._stats[tier.name].total_calls += 1
        self._stats[tier.name].total_failures += 1
        self._stats[tier.name].consecutive_failures += 1

    def route(self) -> str:
        """Get current model, auto-promoting if needed."""
        if self.should_promote():
            promoted = self.promote()
            if promoted:
                return promoted
        return self.current_model

    def reset(self) -> None:
        """Reset to initial tier."""
        self._current_tier = 0
        self._session_promotions = 0

    def get_stats(self) -> dict[str, dict[str, object]]:
        return {
            name: {
                "calls": s.total_calls,
                "failures": s.total_failures,
                "promoted": s.promoted_count,
            }
            for name, s in self._stats.items()
        }
