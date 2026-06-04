"""The Controller: the single async turn path.

The Controller owns:

* A :class:`~openlaoke.bus.queue.MessageBus` for inbound/outbound traffic
* An :class:`~openlaoke.bus.runtime_events.EventSink` for typed events
* A :class:`~openlaoke.agent.session.Session` per active session
* A :class:`~openlaoke.agent.subagent.SubagentManager` for nested runs
* A :class:`~openlaoke.permission.policy.Policy` and :class:`~openlaoke.permission.gate.Gate`
* A :class:`~openlaoke.snapshot.store.SnapshotStore` for code/conv rewind
* A :class:`~openlaoke.memory.dream.DreamConsolidator` for memory consolidation

The Controller does **not** import any frontend module.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TurnHandle:
    """Handle to a turn in flight."""

    session_id: str
    turn_id: str
    task: asyncio.Task
    started_at: float = field(default_factory=time.time)
    cancelled: bool = False


@dataclass
class SessionState:
    """Per-session state held by the Controller."""

    session_id: str
    session_key: str
    plan_mode: bool = False
    bypass: bool = False
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalTicket:
    """A pending approval the Controller is waiting on."""

    ticket_id: str
    tool_name: str
    tool_args: dict[str, Any]
    future: asyncio.Future[str]
    created_at: float = field(default_factory=time.time)
