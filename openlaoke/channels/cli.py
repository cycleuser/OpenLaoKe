"""Built-in CLI channel.

Reads user input from stdin in a non-blocking loop and publishes
inbound messages. Output is printed to stdout with optional streaming.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from openlaoke.bus.events import InboundMessage, OutboundMessage
from openlaoke.channels.base import BaseChannel, ChannelConfig

logger = logging.getLogger(__name__)

CHANNEL_NAME = "cli"
CHANNEL_CLASS = None  # set below


class CLIChannel(BaseChannel):
    """A simple stdin/stdout channel."""

    name = "cli"
    supports_streaming = True
    supports_reasoning = True

    def __init__(self, config: ChannelConfig, bus: Any) -> None:
        super().__init__(config, bus)
        self._input_task: asyncio.Task | None = None
        self._buffer: dict[str, str] = {}

    async def start(self) -> None:
        self._input_task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        self._stopped = True
        if self._input_task is not None:
            self._input_task.cancel()
            self._input_task = None

    async def _read_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while not self._stopped:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except Exception as exc:
                logger.debug("stdin read failed: %s", exc)
                break
            if not line:
                await asyncio.sleep(0.05)
                continue
            text = line.rstrip("\n")
            if not text.strip():
                continue
            msg = InboundMessage(
                text=text,
                session_key="cli",
                sender_id="user",
                channel="cli",
                chat_id="cli",
            )
            await self.bus.publish_inbound(msg)

    async def send(self, message: OutboundMessage) -> None:
        sys.stdout.write((message.text or "") + "\n")
        sys.stdout.flush()

    async def send_delta(
        self,
        chat_id: str,
        delta: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        sys.stdout.write(delta)
        sys.stdout.flush()
        self._buffer[chat_id] = self._buffer.get(chat_id, "") + delta

    async def send_reasoning_delta(self, chat_id: str, delta: str) -> None:
        sys.stdout.write(f"[reasoning] {delta}")
        sys.stdout.flush()

    async def send_reasoning_end(self, chat_id: str) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()


CHANNEL_CLASS = CLIChannel
