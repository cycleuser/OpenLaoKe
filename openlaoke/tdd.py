"""TDD state machine.

Five phases: idle -> red -> red.confirmed -> green -> refactor -> done.

In ``loop`` mode, a list of requirements is auto-advanced. The TDD
phase gate blocks writes that violate the current phase:

* In ``red`` you may only write a test.
* In ``green`` you may only edit the production file under test.
* In ``refactor`` writes are allowed to either.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class TDDPhase(StrEnum):
    IDLE = "idle"
    RED = "red"
    RED_CONFIRMED = "red.confirmed"
    GREEN = "green"
    REFACTOR = "refactor"
    DONE = "done"


@dataclass
class TDDState:
    """A single TDD cycle state."""

    cycle_id: str
    phase: TDDPhase = TDDPhase.IDLE
    test_path: str = ""
    impl_path: str = ""
    started_at: float = field(default_factory=time.time)
    last_test_run: dict[str, Any] = field(default_factory=dict)
    last_impl_run: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class TDDLoop:
    """Manages an auto-advancing requirements loop.

    ``requirements`` is a list of human-readable assertions. The loop
    walks them in order; for each, it runs a full Red -> Green ->
    Refactor cycle.
    """

    requirements: list[str] = field(default_factory=list)
    cycles: list[TDDState] = field(default_factory=list)
    current: int = 0
    finished: bool = False

    def is_writer_allowed(self, file_path: str) -> bool:
        cycle = self.current_cycle()
        if cycle is None or cycle.phase in (TDDPhase.IDLE, TDDPhase.DONE):
            return True
        if cycle.phase == TDDPhase.RED:
            return not (cycle.impl_path and file_path == cycle.impl_path)
        if cycle.phase == TDDPhase.GREEN:
            return not (cycle.test_path and file_path == cycle.test_path)
        return True
        return True

    def advance(self) -> None:
        if self.current < len(self.cycles) - 1:
            self.current += 1
        else:
            self.finished = True

    def current_cycle(self) -> TDDState | None:
        if 0 <= self.current < len(self.cycles):
            return self.cycles[self.current]
        return None

    def describe(self) -> str:
        cycle = self.current_cycle()
        if cycle is None:
            return "TDD idle"
        if not self.requirements:
            return f"TDD: {cycle.phase.value}"
        idx = min(self.current, len(self.requirements) - 1)
        req = self.requirements[idx]
        return f"TDD: {cycle.phase.value} (req {idx + 1}/{len(self.requirements)}: {req})"


def init_requirements(
    state: TDDState, requirements: list[str], test_path: str, impl_path: str
) -> TDDState:
    """Initialize a :class:`TDDLoop` with the given requirements."""
    state.cycle_id = state.cycle_id or f"tdd_{int(time.time())}"
    state.phase = TDDPhase.RED
    state.test_path = test_path
    state.impl_path = impl_path
    return state
