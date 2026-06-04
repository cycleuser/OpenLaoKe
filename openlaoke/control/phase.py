"""State machine for the agent loop."""

from __future__ import annotations

from enum import StrEnum


class TurnPhase(StrEnum):
    RESTORE = "restore"
    COMPACT = "compact"
    COMMAND = "command"
    BUILD = "build"
    RUN = "run"
    SAVE = "save"
    RESPOND = "respond"
    DONE = "done"


class RunResult(StrEnum):
    OK = "ok"
    COMPACTED = "compacted"
    INTERRUPTED = "interrupted"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


PHASE_TRANSITIONS: dict[TurnPhase, list[TurnPhase]] = {
    TurnPhase.RESTORE: [TurnPhase.COMPACT, TurnPhase.COMMAND],
    TurnPhase.COMPACT: [TurnPhase.COMMAND],
    TurnPhase.COMMAND: [TurnPhase.BUILD, TurnPhase.DONE],
    TurnPhase.BUILD: [TurnPhase.RUN, TurnPhase.DONE],
    TurnPhase.RUN: [TurnPhase.SAVE, TurnPhase.DONE],
    TurnPhase.SAVE: [TurnPhase.RESPOND],
    TurnPhase.RESPOND: [TurnPhase.DONE],
    TurnPhase.DONE: [],
}


def can_transition(current: TurnPhase, target: TurnPhase) -> bool:
    return target in PHASE_TRANSITIONS.get(current, [])
