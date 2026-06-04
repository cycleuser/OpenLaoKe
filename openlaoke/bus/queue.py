"""Async message bus decoupling channels from the agent loop.

Multiple channels (CLI, WebSocket, MCP, cron, sub-agents) can publish
:class:`InboundMessage` to the bus. The agent loop pulls one at a time
and publishes :class:`OutboundMessage` back.

Per-session serial dispatch means messages for one session are processed
in order. Cross-session dispatch is concurrent.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from openlaoke.bus.events import InboundMessage, OutboundMessage


@dataclass
class _SessionChannel:
    inbound: asyncio.Queue[InboundMessage] = field(default_factory=asyncio.Queue)
    outbound: asyncio.Queue[OutboundMessage] = field(default_factory=asyncio.Queue)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending_turn: asyncio.Queue[InboundMessage] = field(default_factory=asyncio.Queue)
    has_active_consumer: bool = False


class MessageBus:
    """Fan-in / fan-out message bus keyed by session."""

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionChannel] = {}
        self._global_limit: asyncio.Semaphore | None = None
        self._closed = False

    def set_max_concurrent(self, n: int) -> None:
        """Bound the total number of concurrent session workers."""
        self._global_limit = asyncio.Semaphore(max(1, n))

    def _channel(self, session_key: str) -> _SessionChannel:
        if session_key not in self._sessions:
            self._sessions[session_key] = _SessionChannel()
        return self._sessions[session_key]

    async def publish_inbound(self, message: InboundMessage) -> None:
        """Push a message for the agent to consume.

        If the message targets a session that is currently being processed,
        the message is enqueued in ``pending_turn`` so that follow-ups ride
        onto the active turn rather than spawning a competing one.
        """
        if not message.queued_at:
            message.queued_at = time.time()
        ch = self._channel(message.session_key)
        if ch.has_active_consumer:
            await ch.pending_turn.put(message)
        else:
            await ch.inbound.put(message)

    async def consume_inbound(self, session_key: str) -> InboundMessage:
        """Block until a message arrives for this session.

        After the consumer finishes a turn, it must call
        :meth:`release_session` to flush any pending follow-ups.
        """
        ch = self._channel(session_key)
        ch.has_active_consumer = True
        if self._global_limit is not None:
            await self._global_limit.acquire()
        return await ch.inbound.get()

    async def release_session(self, session_key: str) -> None:
        """Mark session as idle and drain pending turn-tails into the main queue."""
        ch = self._channel(session_key)
        ch.has_active_consumer = False
        while not ch.pending_turn.empty():
            msg = ch.pending_turn.get_nowait()
            await ch.inbound.put(msg)
        if self._global_limit is not None:
            self._global_limit.release()

    async def publish_outbound(self, message: OutboundMessage) -> None:
        ch = self._channel(message.session_key)
        await ch.outbound.put(message)

    async def consume_outbound(self, session_key: str) -> OutboundMessage:
        return await self._channel(session_key).outbound.get()

    def stream_outbound(self, session_key: str) -> AsyncIterator[OutboundMessage]:
        async def _gen() -> AsyncIterator[OutboundMessage]:
            while True:
                yield await self.consume_outbound(session_key)

        return _gen()

    def acquire_session_lock(self, session_key: str) -> asyncio.Lock:
        """Per-session serial lock — messages for the same session run serially."""
        return self._channel(session_key).lock

    def known_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    async def shutdown(self) -> None:
        self._closed = True
        for ch in self._sessions.values():
            while not ch.inbound.empty():
                ch.inbound.get_nowait()
            while not ch.outbound.empty():
                ch.outbound.get_nowait()
            while not ch.pending_turn.empty():
                ch.pending_turn.get_nowait()


def new_session_key(prefix: str = "session") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
