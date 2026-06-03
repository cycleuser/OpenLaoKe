"""Early-stop detection for small model failure patterns.

Detects: repetition loops, patch spirals, greeting regression, read loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StopReason(StrEnum):
    REPETITION = "repetition"
    PATCH_SPIRAL = "patch_spiral"
    GREETING_REGRESSION = "greeting_regression"
    READ_LOOP = "read_loop"


@dataclass
class EarlyStopResult:
    should_stop: bool = False
    reason: StopReason | None = None
    message: str = ""


@dataclass
class EarlyStopDetector:
    max_consecutive_patch_failures: int = 4
    max_total_patch_attempts: int = 6
    read_loop_soft: int = 5
    read_loop_hard: int = 8
    _consecutive_reads: int = 0
    _consecutive_patch_failures: dict[str, int] = field(default_factory=dict)
    _total_patch_attempts: dict[str, int] = field(default_factory=dict)
    _last_output: str = ""

    def detect_repetition(
        self, output: str, window_sizes: tuple[int, ...] = (20, 40, 60, 80, 120)
    ) -> EarlyStopResult:
        if not output:
            return EarlyStopResult()
        tail = output[-200:] if len(output) > 200 else output
        for ws in window_sizes:
            if len(tail) < ws * 3:
                continue
            pattern = tail[-ws:]
            count = 0
            pos = len(tail) - ws
            while pos >= 0:
                if tail[pos : pos + ws] == pattern:
                    count += 1
                    pos -= ws
                else:
                    break
            if count >= 3:
                return EarlyStopResult(
                    should_stop=True,
                    reason=StopReason.REPETITION,
                    message="[SYSTEM] You are repeating the same output in a loop. STOP.",
                )
        self._last_output = output
        return EarlyStopResult()

    def detect_patch_spiral(self, tool_name: str, file_path: str, success: bool) -> EarlyStopResult:
        if tool_name not in ("Edit", "ApplyPatch"):
            return EarlyStopResult()
        self._total_patch_attempts[file_path] = self._total_patch_attempts.get(file_path, 0) + 1
        if not success:
            self._consecutive_patch_failures[file_path] = (
                self._consecutive_patch_failures.get(file_path, 0) + 1
            )
        else:
            self._consecutive_patch_failures[file_path] = 0
        cf = self._consecutive_patch_failures.get(file_path, 0)
        tp = self._total_patch_attempts.get(file_path, 0)
        if cf >= self.max_consecutive_patch_failures or tp >= self.max_total_patch_attempts:
            return EarlyStopResult(
                should_stop=True,
                reason=StopReason.PATCH_SPIRAL,
                message=(
                    "[SYSTEM] STOP using patch on this file. "
                    f"{cf} consecutive failures / {tp} total attempts. "
                    "Use read_file to see current state, then write_file to rewrite completely."
                ),
            )
        return EarlyStopResult()

    def detect_greeting_regression(self, output: str) -> EarlyStopResult:
        greeting_patterns = [
            r"(?i)\bhow can i help\b",
            r"(?i)\bwhat would you like\b",
            r"(?i)\bhow can i assist\b",
            r"(?i)\bwhat can i do for you\b",
            r"(?i)\bi'm here to help\b",
            r"(?i)\bfeel free to ask\b",
        ]
        import re

        for pattern in greeting_patterns:
            if re.search(pattern, output):
                return EarlyStopResult(
                    should_stop=True,
                    reason=StopReason.GREETING_REGRESSION,
                    message="[SYSTEM] You appear to have lost context. Continue where you left off.",
                )
        return EarlyStopResult()

    def detect_read_loop(self, tool_name: str) -> EarlyStopResult:
        if tool_name in ("Read", "ListDirectory", "Glob", "Grep"):
            self._consecutive_reads += 1
        else:
            self._consecutive_reads = 0
        if self._consecutive_reads >= self.read_loop_hard:
            return EarlyStopResult(
                should_stop=True,
                reason=StopReason.READ_LOOP,
                message=(
                    "[SYSTEM] STOP reading and START writing now. "
                    f"You've made {self._consecutive_reads} consecutive read calls. "
                    "You have enough context. Produce output."
                ),
            )
        if self._consecutive_reads >= self.read_loop_soft:
            return EarlyStopResult(
                should_stop=False,
                reason=StopReason.READ_LOOP,
                message="[SYSTEM] You likely have enough context. Consider writing your findings.",
            )
        return EarlyStopResult()

    def reset_read_count(self) -> None:
        self._consecutive_reads = 0

    def reset_all(self) -> None:
        self._consecutive_reads = 0
        self._consecutive_patch_failures.clear()
        self._total_patch_attempts.clear()
        self._last_output = ""
