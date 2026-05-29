"""Quality monitor catching structural failure modes.

Catches: empty turns, blank tool names, hallucinated tool names, exact-repeat calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class QualityCheckResult:
    has_issue: bool = False
    message: str = ""


@dataclass
class QualityMonitor:
    max_consecutive_corrections: int = 2
    _correction_count: int = 0
    _last_tool_calls: list[tuple[str, str]] = field(default_factory=list)
    _enabled: bool = True

    def check(
        self, content: str, tool_calls: list[dict], known_tools: set[str]
    ) -> QualityCheckResult:
        if not self._enabled:
            return QualityCheckResult()
        if self._correction_count >= self.max_consecutive_corrections:
            return QualityCheckResult()

        r = self._check_empty(content, tool_calls)
        if r.has_issue:
            return r

        r = self._check_blank_tool_name(tool_calls)
        if r.has_issue:
            return r

        r = self._check_hallucinated_tool(tool_calls, known_tools)
        if r.has_issue:
            return r

        r = self._check_repeated_call(tool_calls)
        if r.has_issue:
            return r

        self._correction_count = 0
        return QualityCheckResult()

    def _check_empty(self, content: str, tool_calls: list[dict]) -> QualityCheckResult:
        if not content.strip() and not tool_calls:
            self._correction_count += 1
            return QualityCheckResult(
                has_issue=True,
                message="[QUALITY-MONITOR] Empty response detected. You must either produce output or call a tool.",
            )
        return QualityCheckResult()

    def _check_blank_tool_name(self, tool_calls: list[dict]) -> QualityCheckResult:
        for call in tool_calls:
            name = str(call.get("name", ""))
            if name == "":
                self._correction_count += 1
                return QualityCheckResult(
                    has_issue=True,
                    message=(
                        "[QUALITY-MONITOR] Tool call with empty name detected. "
                        "Available tools: " + _format_tool_suggestion(call, set())
                    ),
                )
        return QualityCheckResult()

    def _check_hallucinated_tool(
        self, tool_calls: list[dict], known_tools: set[str]
    ) -> QualityCheckResult:
        for call in tool_calls:
            name = str(call.get("name", ""))
            if name and name not in known_tools:
                suggestion = _format_tool_suggestion(call, known_tools)
                self._correction_count += 1
                return QualityCheckResult(
                    has_issue=True,
                    message=(
                        f"[QUALITY-MONITOR] Unknown tool '{name}'. "
                        f"Did you mean one of: {suggestion}?"
                    ),
                )
        return QualityCheckResult()

    def _check_repeated_call(self, tool_calls: list[dict]) -> QualityCheckResult:
        current = [
            (c.get("name", ""), json.dumps(c.get("arguments", {}), sort_keys=True))
            for c in tool_calls
        ]
        if self._last_tool_calls and current == self._last_tool_calls:
            self._correction_count += 1
            self._last_tool_calls = current
            return QualityCheckResult(
                has_issue=True,
                message="[QUALITY-MONITOR] You just called the same tools with the same arguments. Take a different approach.",
            )
        self._last_tool_calls = current
        return QualityCheckResult()

    def reset(self) -> None:
        self._correction_count = 0
        self._last_tool_calls.clear()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value


def _format_tool_suggestion(call: dict, known_tools: set[str]) -> str:
    """Return comma-separated list of closest tool name matches."""
    name = str(call.get("name", ""))
    if not known_tools:
        return "use tool_search to discover tools"
    scored = []
    for known in known_tools:
        dist = _levenshtein(name.lower(), known.lower())
        scored.append((dist, known))
    scored.sort()
    return ", ".join(t for _, t in scored[:5])


def _levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[n]
