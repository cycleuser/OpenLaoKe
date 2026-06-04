"""WebSocket channel.

Connects to a local WebSocket gateway (or any WS server) and forwards
inbound/outbound traffic. Supports streaming and live file-edit events.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from openlaoke.bus.events import InboundMessage, OutboundMessage
from openlaoke.channels.base import BaseChannel, ChannelConfig

logger = logging.getLogger(__name__)

CHANNEL_NAME = "websocket"
CHANNEL_CLASS = None  # set below


class WebSocketChannel(BaseChannel):
    """A WebSocket channel for the WebUI gateway."""

    name = "websocket"
    supports_streaming = True
    supports_reasoning = True

    def __init__(self, config: ChannelConfig, bus: Any) -> None:
        super().__init__(config, bus)
        self._ws: Any = None
        self._listener_task: asyncio.Task | None = None
        self._buffers: dict[str, str] = {}

    async def start(self) -> None:
        url = self.config.extra.get("url", "ws://127.0.0.1:3000/ws")
        try:
            import websockets
        except ImportError:
            logger.warning("websockets package not installed; WS channel disabled")
            return
        self._ws = await websockets.connect(url)
        self._listener_task = asyncio.create_task(self._listener())

    async def stop(self) -> None:
        self._stopped = True
        if self._listener_task is not None:
            self._listener_task.cancel()
            self._listener_task = None
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

    async def _listener(self) -> None:
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                try:
                    payload = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                kind = payload.get("type", "user")
                if kind != "user":
                    continue
                text = payload.get("text", "")
                if not text:
                    continue
                msg = InboundMessage(
                    text=text,
                    session_key="ws",
                    sender_id=str(payload.get("sender_id", "user")),
                    channel="websocket",
                    chat_id=str(payload.get("chat_id", "default")),
                    metadata=dict(payload.get("metadata") or {}),
                )
                await self.bus.publish_inbound(msg)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("WS listener error: %s", exc)

    async def send(self, message: OutboundMessage) -> None:
        if self._ws is None:
            return
        await self._ws.send(
            json.dumps(
                {
                    "type": "message",
                    "session_key": message.session_key,
                    "chat_id": message.chat_id,
                    "text": message.text,
                    "final": message.final,
                    "is_error": message.is_error,
                }
            )
        )

    async def send_delta(
        self,
        chat_id: str,
        delta: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "delta", "chat_id": chat_id, "delta": delta}))

    async def send_reasoning_delta(self, chat_id: str, delta: str) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "reasoning", "chat_id": chat_id, "delta": delta}))


CHANNEL_CLASS = WebSocketChannel
