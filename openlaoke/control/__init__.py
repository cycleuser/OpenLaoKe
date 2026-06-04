"""Transport-agnostic controller.

The Controller is the single async turn path. Frontends (TUI, WebUI,
HTTP gateway) submit high-level commands and observe the typed event
stream. The Controller never imports a frontend module.

The state machine for one turn::

    RESTORE -> COMPACT -> COMMAND -> BUILD -> RUN -> SAVE -> RESPOND -> DONE

Each phase is implemented as a guarded coroutine that emits events.
"""

from __future__ import annotations

from openlaoke.control.controller import ApprovalTicket, SessionState, TurnHandle
from openlaoke.control.orchestrator import AgentLoopConfig, Orchestrator, TurnResult
from openlaoke.control.phase import RunResult, TurnPhase, can_transition

__all__ = [
    "AgentLoopConfig",
    "ApprovalTicket",
    "Orchestrator",
    "RunResult",
    "SessionState",
    "TurnHandle",
    "TurnPhase",
    "TurnResult",
    "can_transition",
]
