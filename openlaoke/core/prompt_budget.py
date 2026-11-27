"""Assemble a system prompt from named blocks under a token budget.

The failure this prevents is subtle. When a prompt has to shrink, the obvious
implementation walks the parts and stops when it runs out of room. Whatever
happens to be first therefore survives, and whatever is last is dropped, which
means a long "Current Context" block can push out the rules that keep the agent
honest. Nothing errors; the agent just quietly stops following its constraints.

So blocks carry a tier:

* ``required`` blocks are always kept, in order. If they alone exceed the
  budget the assembly reports ``over_budget`` and the caller decides; it never
  silently drops a safety rule to make room for a nice-to-have.
* ``optional`` blocks fill the remaining space in priority order. A block that
  does not fit is skipped and the loop continues, so one oversized appendix does
  not evict every smaller one after it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openlaoke.core.context_budget import estimate_text_tokens

REQUIRED = "required"
OPTIONAL = "optional"


@dataclass(frozen=True)
class PromptBlock:
    name: str
    text: str
    tier: str = OPTIONAL
    separator: str = "\n\n"

    @property
    def required(self) -> bool:
        return self.tier == REQUIRED


@dataclass
class AssemblyReport:
    """What fit, what did not, and whether the budget was respected."""

    used_tokens: int = 0
    budget: int | None = None
    included: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    over_budget: bool = False

    @property
    def dropped_required(self) -> bool:
        """True only if a required block was dropped, which assembly never does."""
        return False

    def render(self) -> str:
        budget = f"{self.budget:,}" if self.budget else "none"
        lines = [f"Included: {', '.join(self.included) or '(none)'}"]
        if self.dropped:
            lines.append(f"Dropped (optional, out of budget): {', '.join(self.dropped)}")
        lines.append(f"Tokens: {self.used_tokens:,} / {budget}")
        if self.over_budget:
            lines.append("WARNING: required blocks alone exceed the budget")
        return "\n".join(lines)


def assemble(
    blocks: list[PromptBlock],
    *,
    max_tokens: int | None = None,
    report: AssemblyReport | None = None,
) -> tuple[str, AssemblyReport]:
    """Join blocks under ``max_tokens``, keeping every required one.

    ``max_tokens=None`` means "no budget": everything is included and the report
    still says what was used.
    """
    report = report or AssemblyReport(budget=max_tokens)
    parts: list[str] = []
    used = 0

    for block in blocks:
        if not block.text:
            continue
        separator = block.separator if parts else ""
        cost = estimate_text_tokens(block.text) + estimate_text_tokens(separator)
        if max_tokens is not None and not block.required and used + cost > max_tokens:
            report.dropped.append(block.name)
            continue
        parts.append(separator + block.text)
        used += cost
        report.included.append(block.name)

    report.used_tokens = used
    if max_tokens is not None and used > max_tokens:
        report.over_budget = True
    return "".join(parts), report


def budget_for_window(
    window: int | None, *, fraction: float = 0.25, floor: int = 512
) -> int | None:
    """A prompt allowance for a model window, or ``None`` when the window is unknown."""
    if not window or window <= 0:
        return None
    return max(floor, int(window * fraction))
