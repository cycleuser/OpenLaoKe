"""Typed inbound/outbound message dataclasses for the message bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InboundMessage:
    """A user input entering the agent system.

    The same shape is used for all channels (CLI, WebSocket, MCP, sub-agent,
    scheduled cron job). This makes the agent loop a single async consumer.
    """

    text: str
    session_key: str
    sender_id: str = "user"
    channel: str = "cli"
    chat_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    queued_at: float = 0.0
    sender: str = "user"
    system_event: str | None = None
    pending_goal: str | None = None


@dataclass
class OutboundMessage:
    """A response emitted by the agent.

    Each subscriber (TUI renderer, WebSocket gateway, etc.) consumes the
    stream independently. ``final`` marks the end of a turn.
    """

    text: str
    session_key: str
    channel: str = "cli"
    chat_id: str = ""
    final: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False
    delta: bool = False
    reasoning: str = ""
    tool_activity: dict[str, Any] | None = None
