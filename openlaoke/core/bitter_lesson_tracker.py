"""Self-reflection and correction mechanism based on The Bitter Lesson.

The Bitter Lesson (Rich Sutton, 2019):
"Methods that leverage computation and learning scale better than methods
that rely on human-engineered knowledge."

This module implements a self-correcting system that:
1. Tracks what works and what doesn't across different model sizes
2. Learns from session outcomes empirically
3. Auto-adjusts strategies based on real results, not assumptions
4. Avoids over-engineering - favors simple, scalable approaches
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StrategyOutcome:
    """Records the outcome of using a specific strategy."""

    strategy_name: str
    model_size: str
    success: bool
    duration_ms: float = 0.0
    tokens_used: int = 0
    error_type: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class Lesson:
    """A learned lesson from accumulated outcomes."""

    strategy_name: str
    model_size: str
    success_rate: float = 0.0
    total_attempts: int = 0
    avg_duration_ms: float = 0.0
    avg_tokens_used: int = 0
    common_errors: dict[str, int] = field(default_factory=dict)
    recommendation: str = ""
    last_updated: float = field(default_factory=time.time)


class BitterLessonTracker:
    """Tracks strategy outcomes and auto-corrects based on empirical evidence.

    Core principles (from The Bitter Lesson):
    1. Don't over-engineer - let data decide what works
    2. Computation > hand-crafted rules
    3. General methods > domain-specific hacks
    4. Learning from experience > human-designed knowledge

    This tracker:
    - Records every strategy's outcome (success/failure, tokens, time)
    - Computes success rates per model size
    - Auto-disables strategies with <30% success rate
    - Recommends simpler alternatives when complex ones fail
    - Persists lessons across sessions
    """

    def __init__(self, data_dir: str | None = None) -> None:
        self.outcomes: list[StrategyOutcome] = []
        self.lessons: dict[str, Lesson] = {}
        self.disabled_strategies: set[str] = set()
        self._data_dir = Path(data_dir) if data_dir else Path.home() / ".openlaoke" / "lessons"
        self._load_lessons()

    def record_outcome(
        self,
        strategy_name: str,
        model_size: str,
        success: bool,
        duration_ms: float = 0.0,
        tokens_used: int = 0,
        error_type: str = "",
    ) -> None:
        """Record the outcome of using a strategy."""
        outcome = StrategyOutcome(
            strategy_name=strategy_name,
            model_size=model_size,
            success=success,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            error_type=error_type,
        )
        self.outcomes.append(outcome)
        self._update_lessons(strategy_name, model_size)

        if self._should_disable_strategy(strategy_name, model_size):
            self.disabled_strategies.add(f"{strategy_name}:{model_size}")

    def is_strategy_disabled(self, strategy_name: str, model_size: str) -> bool:
        return f"{strategy_name}:{model_size}" in self.disabled_strategies

    def get_recommendation(self, strategy_name: str, model_size: str) -> str:
        key = f"{strategy_name}:{model_size}"
        lesson = self.lessons.get(key)
        if lesson:
            return lesson.recommendation
        return ""

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get aggregated statistics across all strategies."""
        stats: dict[str, Any] = {}
        for key, lesson in self.lessons.items():
            stats[key] = {
                "success_rate": lesson.success_rate,
                "total_attempts": lesson.total_attempts,
                "avg_duration_ms": lesson.avg_duration_ms,
                "avg_tokens_used": lesson.avg_tokens_used,
                "recommendation": lesson.recommendation,
                "disabled": key in self.disabled_strategies,
            }
        return stats

    def get_bitter_lessons_summary(self) -> str:
        """Generate a summary of lessons learned, in the spirit of The Bitter Lesson."""
        if not self.lessons:
            return "No lessons learned yet. Keep using the system to gather data."

        lines = ["=== Bitter Lesson Tracker ===", ""]

        sorted_lessons = sorted(
            self.lessons.values(),
            key=lambda lesson: lesson.total_attempts,
            reverse=True,
        )

        for lesson in sorted_lessons:
            status = (
                "DISABLED"
                if f"{lesson.strategy_name}:{lesson.model_size}" in self.disabled_strategies
                else "active"
            )
            lines.append(
                f"[{status}] {lesson.strategy_name} ({lesson.model_size}): "
                f"{lesson.success_rate:.0%} success rate ({lesson.total_attempts} attempts)"
            )
            if lesson.recommendation:
                lines.append(f"  -> {lesson.recommendation}")

        lines.append("")
        lines.append(
            "Bitter Lesson Principle: Let computation and learning decide, not human assumptions."
        )

        return "\n".join(lines)

    def _update_lessons(self, strategy_name: str, model_size: str) -> None:
        key = f"{strategy_name}:{model_size}"
        relevant = [
            o
            for o in self.outcomes
            if o.strategy_name == strategy_name and o.model_size == model_size
        ]

        if not relevant:
            return

        total = len(relevant)
        successes = sum(1 for o in relevant if o.success)
        success_rate = successes / total if total > 0 else 0.0

        avg_duration = sum(o.duration_ms for o in relevant) / total if total > 0 else 0.0
        avg_tokens = sum(o.tokens_used for o in relevant) / total if total > 0 else 0

        error_counts: dict[str, int] = {}
        for o in relevant:
            if o.error_type:
                error_counts[o.error_type] = error_counts.get(o.error_type, 0) + 1

        recommendation = self._generate_recommendation(
            strategy_name, model_size, success_rate, total, error_counts
        )

        self.lessons[key] = Lesson(
            strategy_name=strategy_name,
            model_size=model_size,
            success_rate=success_rate,
            total_attempts=total,
            avg_duration_ms=avg_duration,
            avg_tokens_used=int(avg_tokens),
            common_errors=error_counts,
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self,
        strategy_name: str,
        model_size: str,
        success_rate: float,
        total_attempts: int,
        error_counts: dict[str, int],
    ) -> str:
        if total_attempts < 3:
            return "Need more data to form a recommendation."

        if success_rate < 0.3:
            return f"This strategy fails {1 - success_rate:.0%} of the time. Consider a simpler approach or disable for {model_size} models."
        elif success_rate < 0.6:
            return f"Moderate success rate. Try simplifying the approach or reducing scope for {model_size} models."
        elif success_rate >= 0.9 and total_attempts >= 10:
            return f"Highly reliable for {model_size} models. Consider making this the default."
        else:
            return f"Working adequately ({success_rate:.0%} success). Monitor for regressions."

    def _should_disable_strategy(self, strategy_name: str, model_size: str) -> bool:
        key = f"{strategy_name}:{model_size}"
        lesson = self.lessons.get(key)
        if not lesson:
            return False
        return lesson.total_attempts >= 10 and lesson.success_rate < 0.3

    def _load_lessons(self) -> None:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            lessons_file = self._data_dir / "lessons.json"
            if lessons_file.exists():
                data = json.loads(lessons_file.read_text())
                for key, lesson_data in data.get("lessons", {}).items():
                    self.lessons[key] = Lesson(
                        strategy_name=lesson_data["strategy_name"],
                        model_size=lesson_data["model_size"],
                        success_rate=lesson_data.get("success_rate", 0.0),
                        total_attempts=lesson_data.get("total_attempts", 0),
                        avg_duration_ms=lesson_data.get("avg_duration_ms", 0.0),
                        avg_tokens_used=lesson_data.get("avg_tokens_used", 0),
                        common_errors=lesson_data.get("common_errors", {}),
                        recommendation=lesson_data.get("recommendation", ""),
                        last_updated=lesson_data.get("last_updated", time.time()),
                    )
                self.disabled_strategies = set(data.get("disabled_strategies", []))
        except Exception:
            pass

    def save(self) -> None:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "lessons": {
                    key: {
                        "strategy_name": lesson.strategy_name,
                        "model_size": lesson.model_size,
                        "success_rate": lesson.success_rate,
                        "total_attempts": lesson.total_attempts,
                        "avg_duration_ms": lesson.avg_duration_ms,
                        "avg_tokens_used": lesson.avg_tokens_used,
                        "common_errors": lesson.common_errors,
                        "recommendation": lesson.recommendation,
                        "last_updated": lesson.last_updated,
                    }
                    for key, lesson in self.lessons.items()
                },
                "disabled_strategies": list(self.disabled_strategies),
            }
            (self._data_dir / "lessons.json").write_text(json.dumps(data, indent=2))
        except Exception:
            pass
