"""Channel system.

A *channel* is any source of inbound messages (CLI, WebSocket, MCP,
scheduled cron) and any sink for outbound messages. Channels are
self-contained and transport-agnostic; the Controller does not know
which channel produced a message.
"""

from __future__ import annotations
