"""Result ledger: what the model has already been shown.

Small windows are mostly wasted on repeated content, so before a tool result
enters the transcript this layer checks two things: has this exact body already
been sent, and is this body big enough that the model should decide whether to
pay for it.  A withheld body stays here, addressable by a pointer the model can
ask to reopen, so nothing is lost, only deferred.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from openlaoke.core.context_budget import estimate_text_tokens

LARGE_RESULT_TOKENS = 1500
HEAD_TOKENS = 300
TAIL_TOKENS = 200

INTENT_FIELD = "intent"
ACCEPT_FIELD = "accept_large_output"
INTENT_DESCRIPTION = "Short label shown in the UI: why this call is being made."
ACCEPT_DESCRIPTION = (
    "Re-run accepting the stated token cost of a withheld result. "
    "Set true only after reading the cost shown in the previous result."
)


@dataclass
class LedgerEntry:
    index: int
    tool: str
    tokens: int
    body: str
    intent: str = ""


@dataclass
class LedgerStats:
    calls: int = 0
    duplicate_calls: int = 0
    withheld_calls: int = 0
    tokens_saved: int = 0
    bodies: int = 0

    def render(self) -> str:
        return (
            f"calls={self.calls} duplicates={self.duplicate_calls} "
            f"withheld={self.withheld_calls} tokens_saved={self.tokens_saved:,} "
            f"bodies_held={self.bodies}"
        )


@dataclass
class ResultLedger:
    """Per-session record of tool output already delivered to the model."""

    large_threshold: int = LARGE_RESULT_TOKENS
    head_tokens: int = HEAD_TOKENS
    tail_tokens: int = TAIL_TOKENS
    _by_digest: dict[str, LedgerEntry] = field(default_factory=dict)
    _order: list[LedgerEntry] = field(default_factory=list)
    stats: LedgerStats = field(default_factory=LedgerStats)

    def guard(self, tool: str, tool_input: dict, content: str) -> str:
        """Return the body to actually send, or a pointer/summary in its place."""
        if not content or tool_input.get("is_error"):
            return content
        self.stats.calls += 1

        digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        tokens = estimate_text_tokens(content)
        accepted = bool(tool_input.get(ACCEPT_FIELD))
        seen = self._by_digest.get(digest)

        if seen is not None:
            self.stats.duplicate_calls += 1
            if not accepted:
                self.stats.tokens_saved += tokens
                return (
                    f"[Identical to result #{seen.index} from {seen.tool} "
                    f"({tokens:,} tokens elided). Repeat the call with "
                    f"{ACCEPT_FIELD}=true only if it is really needed again.]"
                )
            return content

        entry = LedgerEntry(
            index=len(self._order) + 1,
            tool=tool,
            tokens=tokens,
            body=content,
            intent=str(tool_input.get(INTENT_FIELD) or ""),
        )
        self._order.append(entry)
        self._by_digest[digest] = entry
        self.stats.bodies = len(self._order)

        if tokens > self.large_threshold and not accepted:
            self.stats.withheld_calls += 1
            self.stats.tokens_saved += tokens - self._digest_cost(content)
            return self._withhold(entry, tokens)
        return content

    def _withhold(self, entry: LedgerEntry, tokens: int) -> str:
        digest_body = self.digest_body(entry.body)
        return (
            f"[Result #{entry.index} from {entry.tool} is {tokens:,} tokens, above the "
            f"{self.large_threshold:,} token budget, so only its edges are shown. "
            f"Repeat the same call with {ACCEPT_FIELD}=true to spend the full "
            f"{tokens:,} tokens on it.]\n\n{digest_body}"
        )

    def digest_body(self, body: str) -> str:
        """Keep a head and a tail slice, dropping the middle."""
        head_chars = self.head_tokens * 4
        tail_chars = self.tail_tokens * 4
        if len(body) <= head_chars + tail_chars:
            return body
        dropped = len(body) - head_chars - tail_chars
        return f"{body[:head_chars]}\n\n... [{dropped:,} characters omitted] ...\n\n{body[-tail_chars:]}"

    def _digest_cost(self, body: str) -> int:
        return estimate_text_tokens(self.digest_body(body))

    def reopen(self, index: int) -> str | None:
        if 1 <= index <= len(self._order):
            return self._order[index - 1].body
        return None

    def recent(self, count: int = 5) -> list[LedgerEntry]:
        return self._order[-count:]

    def reset(self) -> None:
        self._by_digest.clear()
        self._order.clear()
        self.stats = LedgerStats()
