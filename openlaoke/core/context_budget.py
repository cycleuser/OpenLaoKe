"""Token estimation and the per-session context budget.

Estimation is a fallback: whenever a provider reports real usage we prefer it.
The estimator is CJK aware because ``len(text) // 4`` undercounts Chinese by
roughly a factor of two to three, which lets oversized turns through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_UNKNOWN_WINDOW = 8192
_MIN_PRUNE_BUDGET = 2048

_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x3000, 0x30FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7A3),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFF65),
    (0x20000, 0x2A6DF),
)


def _is_cjk(codepoint: int) -> bool:
    return any(low <= codepoint <= high for low, high in _CJK_RANGES)


def estimate_text_tokens(text: str) -> int:
    """Estimate tokens for one string; CJK characters count as one token each."""
    if not text:
        return 0
    cjk = sum(1 for char in text if _is_cjk(ord(char)))
    ascii_like = len(text) - cjk
    return max(1, cjk + (ascii_like + 3) // 4)


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            parts.append(_block_to_text(block))
        return "\n".join(parts)
    if isinstance(content, dict):
        return _block_to_text(content)
    return str(content)


def _block_to_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        text = block.get("text")
        if isinstance(text, str):
            extra = block.get("input") or block.get("content") or ""
            return f"{text}{_content_to_text(extra)}"
        return _content_to_text(block.get("content"))
    text = getattr(block, "text", None)
    if isinstance(text, str):
        return text
    return _content_to_text(getattr(block, "content", None))


def estimate_message_tokens(message: Any) -> int:
    """Estimate one message, dict or typed, including tool call payloads."""
    total = 4
    if isinstance(message, dict):
        total += estimate_text_tokens(_content_to_text(message.get("content")))
        for call in message.get("tool_calls") or []:
            total += estimate_text_tokens(str(call))
    else:
        total += estimate_text_tokens(_content_to_text(getattr(message, "content", None)))
        total += estimate_text_tokens(str(getattr(message, "tool_calls", "") or ""))
    return total


def estimate_messages_tokens(messages: list[Any]) -> int:
    return sum(estimate_message_tokens(message) for message in messages)


def cap_tokens(session_cap: int | None, global_cap: int | None) -> int | None:
    """Session cap wins over the global one; zero or negative means no cap."""
    for candidate in (session_cap, global_cap):
        if isinstance(candidate, int) and candidate > 0:
            return candidate
    return None


@dataclass(frozen=True)
class ContextBudget:
    """What a session may spend, and what it has spent."""

    model_window: int | None
    cap: int | None
    fallback_window: bool = False
    used_tokens: int = 0
    source: str = "estimate"

    @property
    def effective_budget(self) -> int:
        window = self.model_window
        if window is None or window <= 0:
            window = DEFAULT_UNKNOWN_WINDOW
        if self.cap and self.cap > 0:
            return min(window, self.cap)
        return window

    @property
    def remaining(self) -> int:
        return max(0, self.effective_budget - self.used_tokens)

    @property
    def used_ratio(self) -> float:
        budget = self.effective_budget
        return self.used_tokens / budget if budget else 0.0

    @property
    def window_label(self) -> str:
        if self.model_window and self.model_window > 0:
            return f"{self.model_window:,}"
        return f"{DEFAULT_UNKNOWN_WINDOW:,} (unknown)"

    def prune_targets(self) -> tuple[int, int]:
        """Return ``(ctx_budget, keep_tail)`` for the fast pruner."""
        ctx_budget = max(_MIN_PRUNE_BUDGET, int(self.effective_budget * 0.8))
        keep_tail = max(_MIN_PRUNE_BUDGET, ctx_budget // 3)
        return ctx_budget, keep_tail

    def render(self) -> str:
        lines = [
            f"Model window : {self.window_label}",
            f"Session cap  : {f'{self.cap:,}' if self.cap else 'none'}",
            f"Effective    : {self.effective_budget:,} tokens",
            f"In use       : {self.used_tokens:,} ({self.used_ratio:.0%})",
            f"Estimate via : {self.source}",
        ]
        if self.fallback_window:
            lines.append("Note         : window unknown, using a conservative default")
        return "\n".join(lines)


def resolve_budget(
    *,
    model_window: int | None,
    session_cap: int | None = None,
    global_cap: int | None = None,
    used_tokens: int = 0,
    source: str = "estimate",
) -> ContextBudget:
    """Build the budget; the cap may raise or lower the global default but never
    exceeds the model window."""
    return ContextBudget(
        model_window=model_window,
        cap=cap_tokens(session_cap, global_cap),
        fallback_window=not (model_window and model_window > 0),
        used_tokens=used_tokens,
        source=source,
    )
