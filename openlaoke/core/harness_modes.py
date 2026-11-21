"""Switchable harness modes inspired by pi, Jcode, and OpenCode.

The reference agents differ less in raw model quality than in harness policy:
how much they plan, how hard they think, how many steps they allow, how much
context they send, and how they verify. OpenLaoKe keeps one engine and exposes
those choices as named modes, so users can pick the temperament that fits the
task instead of living with one fixed personality.

Every mode is a plain frozen dataclass. Nothing here performs I/O, so it is
safe to import from the CLI, the REPL, and the prompt builder.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessMode:
    """One named bundle of harness behaviour."""

    key: str
    label: str
    summary: str
    reasoning_effort: str
    max_steps: int
    tools: str
    repair_tool_calls: bool
    max_repeat_calls: int
    parallel_readonly: bool
    verify: str
    plan_first: bool
    directives: tuple[str, ...]

    @property
    def all_tools(self) -> bool:
        return self.tools == "all"


PI = HarnessMode(
    key="pi",
    label="pi",
    summary="Fast and minimal: act now, keep context small, stop early.",
    reasoning_effort="low",
    max_steps=25,
    tools="core",
    repair_tool_calls=True,
    max_repeat_calls=2,
    parallel_readonly=True,
    verify="light",
    plan_first=False,
    directives=(
        "Move fast. Pick the smallest sufficient action and execute it; do not "
        "narrate a plan for single-step work.",
        "Keep context small: read only what the task needs, and prefer one "
        "targeted edit over a broad refactor.",
        "When the change is obvious, verify with the cheapest useful check and stop.",
    ),
)

JCODE = HarnessMode(
    key="jcode",
    label="jcode",
    summary="Reliability first: repair bad calls, guard loops, verify once, stop.",
    reasoning_effort="low",
    max_steps=35,
    tools="core",
    repair_tool_calls=True,
    max_repeat_calls=3,
    parallel_readonly=True,
    verify="once",
    plan_first=False,
    directives=(
        "Act first and inspect only what you need; stop as soon as the task is verifiably done.",
        "Batch independent reads in one turn. Never repeat an identical tool call; "
        "change the arguments or the approach.",
        "Use tool evidence, not speculation. If a call fails, read the error and adapt.",
    ),
)

OPENCODE = HarnessMode(
    key="opencode",
    label="opencode",
    summary="Thorough: read conventions, plan multi-file work, verify strictly.",
    reasoning_effort="medium",
    max_steps=60,
    tools="all",
    repair_tool_calls=True,
    max_repeat_calls=4,
    parallel_readonly=True,
    verify="strict",
    plan_first=True,
    directives=(
        "Start by reading AGENTS.md, README, and nearby config so the change "
        "matches the project's conventions.",
        "For multi-file or ambiguous work, state a short plan (2-4 bullets) before "
        "editing, then execute it.",
        "Preserve existing patterns and public interfaces; prefer the project's "
        "idioms over new abstractions.",
        "Verify with the project's real test, lint, or build command. Fix failures "
        "before declaring the task done.",
    ),
)

BALANCED = HarnessMode(
    key="balanced",
    label="balanced",
    summary="Default blend: Jcode's reliability, pi's brevity, OpenCode's conventions.",
    reasoning_effort="low",
    max_steps=50,
    tools="core",
    repair_tool_calls=True,
    max_repeat_calls=3,
    parallel_readonly=True,
    verify="once",
    plan_first=False,
    directives=(
        "Follow project conventions when they exist; otherwise choose the simplest "
        "correct approach.",
        "Inspect, make the smallest change, verify once, and stop.",
    ),
)

MODES: dict[str, HarnessMode] = {mode.key: mode for mode in (BALANCED, PI, JCODE, OPENCODE)}

DEFAULT_MODE = BALANCED.key

ALIASES: dict[str, str] = {
    "default": DEFAULT_MODE,
    "auto": DEFAULT_MODE,
    "blend": DEFAULT_MODE,
    "fast": "pi",
    "minimal": "pi",
    "reliable": "jcode",
    "robust": "jcode",
    "strict": "opencode",
    "thorough": "opencode",
}


def normalize_mode(name: str | None) -> str:
    """Return a canonical mode key, or the default for unknown/empty input."""
    key = (name or "").strip().lower()
    key = ALIASES.get(key, key)
    return key if key in MODES else DEFAULT_MODE


def is_valid_mode(name: str | None) -> bool:
    key = (name or "").strip().lower()
    return ALIASES.get(key, key) in MODES


def get_mode(name: str | None = None) -> HarnessMode:
    """Resolve a mode name (aliases allowed). Never raises."""
    return MODES[normalize_mode(name)]


def list_modes() -> list[HarnessMode]:
    return list(MODES.values())


def mode_directives(name: str | None) -> str:
    """System-prompt block for a mode. Empty string is never returned."""
    mode = get_mode(name)
    lines = [f"## Harness mode: {mode.label}", f"{mode.summary}"]
    lines.extend(f"- {line}" for line in mode.directives)
    return "\n".join(lines)


def engine_kwargs(mode: HarnessMode) -> dict[str, object]:
    """EnginePolicy knobs for a mode, shared by every loop entry point."""
    return {
        "max_iterations": mode.max_steps,
        "repair_tool_calls": mode.repair_tool_calls,
        "max_repeat_calls": mode.max_repeat_calls,
        "parallel_readonly": mode.parallel_readonly,
    }
