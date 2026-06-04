"""Channel base class and registration helpers.

A :class:`BaseChannel` subclass is responsible for:

* Connecting to its transport (readline, websocket, polling, etc.)
* Publishing inbound messages to the :class:`MessageBus`
* Consuming outbound messages and rendering them on its transport
* Optional streaming (``send_delta``) for live typing
* Optional reasoning-channel output

Channels are discovered by the :class:`ChannelManager` via
``pkgutil``-style enumeration. The manager also serves the bundled
WebUI static files.
"""

from __future__ import annotations

import abc
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from openlaoke.bus.events import OutboundMessage
from openlaoke.bus.queue import MessageBus

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Per-channel configuration."""

    name: str
    enabled: bool = True
    allow_from: list[str] = field(default_factory=lambda: ["*"])
    pairing_required: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class BaseChannel(abc.ABC):
    """A single channel adapter."""

    name: str = "base"
    supports_streaming: bool = False
    supports_reasoning: bool = False

    def __init__(
        self,
        config: ChannelConfig,
        bus: MessageBus,
    ) -> None:
        self.config = config
        self.bus = bus
        self._stopped = False

    @abc.abstractmethod
    async def start(self) -> None:
        """Open the transport. Should not block forever."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """Close the transport and release resources."""

    @abc.abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        """Render an outbound message to the user."""

    async def send_delta(
        self,
        chat_id: str,
        delta: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:  # noqa: B027
        """Streaming override. Default: append to a per-chat buffer."""

    async def send_reasoning_delta(
        self,
        chat_id: str,
        delta: str,
    ) -> None:  # noqa: B027
        """Reasoning-channel streaming override (default no-op)."""

    async def send_reasoning_end(self, chat_id: str) -> None:  # noqa: B027
        """End-of-reasoning marker (default no-op)."""

    async def send_file_edit_events(
        self,
        chat_id: str,
        events: list[dict[str, Any]],
    ) -> None:  # noqa: B027
        """Optional live file-edit events (default no-op)."""

    def is_allowed(self, sender_id: str) -> bool:
        if not self.config.allow_from:
            return False
        if "*" in self.config.allow_from:
            return True
        return sender_id in self.config.allow_from

    async def run_consumer(
        self,
        session_key: str,
        on_message: Any,
    ) -> None:
        """Default inbound loop: pull from bus and call on_message."""
        while not self._stopped:
            msg = await self.bus.consume_inbound(session_key)
            try:
                if asyncio.iscoroutinefunction(on_message):
                    await on_message(msg)
                else:
                    on_message(msg)
            except Exception as exc:
                logger.exception("Channel %s consumer error: %s", self.name, exc)
            finally:
                await self.bus.release_session(session_key)
