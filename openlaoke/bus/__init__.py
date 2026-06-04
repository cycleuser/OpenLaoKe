"""Async message and event buses.

The bus layer is the only place channels, agents, and the controller meet.
Two cooperating buses:

* :class:`MessageBus` decouples input channels from the agent loop. Each
  channel publishes :class:`InboundMessage`; the agent loop consumes them,
  processes them, and publishes :class:`OutboundMessage` results.

* :class:`EventBus` is the typed event stream that the controller emits
  to all interested observers (TUI, Web UI, telemetry, trace recorder).
  It is the single point through which the inner state of an agent turn
  is observed.
"""

from __future__ import annotations
