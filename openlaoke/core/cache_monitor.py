"""Prompt-cache monitor.

Providers charge differently for a cache read, a cache write and a fresh
prompt, and the thing that decides which one you get is not the amount of text
but whether the *prefix* is byte-identical to the previous request.  A harness
that quietly reorders the system prompt, re-serialises tool schemas every turn,
or rewrites an early message therefore pays full price on every turn without
anything in the UI looking wrong.

This module watches both halves of that: it fingerprints the request prefix so
a change is visible before the bill arrives, and it reads the provider's own
cache counters back so the estimate can be checked against reality.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def _get(source: Any, *names: str) -> int:
    """Read an int from an object or dict, trying each name in turn."""
    for name in names:
        value = source.get(name) if isinstance(source, dict) else getattr(source, name, None)
        if value:
            return int(value)
    return 0


@dataclass
class CacheReading:
    """What one provider response said about the cache."""

    turn: int
    input_tokens: int
    cache_read: int
    cache_write: int
    prefix_changed: bool

    @property
    def hit_rate(self) -> float:
        """Share of the prompt that came from cache, 0..1."""
        if self.input_tokens <= 0:
            return 0.0
        return self.cache_read / self.input_tokens

    @property
    def warm(self) -> bool:
        return self.cache_read > 0 and not self.prefix_changed


@dataclass
class CacheMonitor:
    """Track cache hit rate and prefix stability across turns."""

    readings: list[CacheReading] = field(default_factory=list)
    max_readings: int = 200
    _last_fingerprint: str = ""
    _turn: int = 0
    _cold_streak: int = 0
    _saved_tokens: int = 0
    _pending_change: bool = False

    def fingerprint(
        self,
        model: str,
        system_prompt: str,
        tool_names: list[str],
        messages: list[dict[str, Any]],
    ) -> str:
        """Hash the cacheable prefix: model, system prompt, tools, older messages.

        The newest message is excluded on purpose.  It differs on every turn by
        definition, so including it would report "cold" every single time and
        the metric would say nothing.
        """
        stable = messages[:-1] if messages else []
        payload = json.dumps(
            {"model": model, "system": system_prompt, "tools": tool_names, "history": stable},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def note_request(
        self,
        model: str,
        system_prompt: str,
        tool_names: list[str],
        messages: list[dict[str, Any]],
    ) -> bool:
        """Record a request; return True when the prefix changed since last time."""
        self._turn += 1
        prefix_hash = self.fingerprint(model, system_prompt, tool_names, messages)
        changed = bool(self._last_fingerprint) and prefix_hash != self._last_fingerprint
        self._last_fingerprint = prefix_hash
        self._pending_change = changed
        return changed

    def observe(self, usage: Any, model: str = "") -> CacheReading | None:
        """Fold a provider usage block into the history."""
        if usage is None:
            return None
        if isinstance(usage, dict):
            details = usage.get("prompt_tokens_details")
        else:
            details = getattr(usage, "prompt_tokens_details", None)
        cache_read = _get(usage, "cache_read_input_tokens", "cache_read_tokens")
        if not cache_read and details is not None:
            cache_read = _get(details, "cached_tokens")
        cache_write = _get(usage, "cache_creation_input_tokens", "cache_write_tokens")
        input_tokens = _get(usage, "input_tokens", "prompt_tokens")
        reading = CacheReading(
            turn=self._turn,
            input_tokens=input_tokens,
            cache_read=cache_read,
            cache_write=cache_write,
            prefix_changed=self._pending_change,
        )
        self._pending_change = False
        self._saved_tokens += cache_read
        if cache_read:
            self._cold_streak = 0
        else:
            self._cold_streak += 1
        self.readings.append(reading)
        del self.readings[: -self.max_readings]
        return reading

    @property
    def cold_streak(self) -> int:
        return self._cold_streak

    @property
    def saved_tokens(self) -> int:
        return self._saved_tokens

    def last(self) -> CacheReading | None:
        return self.readings[-1] if self.readings else None

    def avg_hit_rate(self, window: int = 20) -> float:
        recent = self.readings[-window:]
        if not recent:
            return 0.0
        return sum(reading.hit_rate for reading in recent) / len(recent)

    def render(self) -> str:
        """Human-readable report for ``/cache``."""
        if not self.readings:
            return (
                "No provider cache data yet: this provider either does not report cache "
                "counters or no request has completed in this session."
            )
        last = self.readings[-1]
        lines = [
            f"Last request: {last.input_tokens:,} input tokens, "
            f"{last.cache_read:,} read from cache ({last.hit_rate:.0%}), "
            f"{last.cache_write:,} written to cache",
            f"Average hit rate (last {min(20, len(self.readings))} turns): {self.avg_hit_rate():.0%}",
            f"Tokens served from cache this session: {self.saved_tokens:,}",
        ]
        if last.prefix_changed:
            lines.append(
                "The request prefix changed since the previous turn, so the provider had to "
                "re-read it. Check what rewrote the system prompt, the tool schemas, or an "
                "early message."
            )
        if self._cold_streak >= 3:
            lines.append(
                f"{self._cold_streak} consecutive turns without a cache read. If the provider "
                "supports prompt caching, the prefix is being rebuilt every turn."
            )
        return "\n".join(lines)
