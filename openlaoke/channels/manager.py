"""Channel manager: discovery, retry policy, lifecycle."""

from __future__ import annotations

import asyncio
import logging
import pkgutil
from collections.abc import Iterable
from dataclasses import dataclass

from openlaoke.bus.queue import MessageBus
from openlaoke.channels.base import BaseChannel, ChannelConfig

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (1.0, 2.0, 4.0)


@dataclass
class ManagedChannel:
    """A channel + its retry state."""

    channel: BaseChannel
    retry_attempts: int = 0
    last_error: str = ""


class ChannelManager:
    """Discovers, instantiates, and supervises channel adapters.

    Discovery is via :func:`pkgutil.iter_modules`-style import of any
    module under ``openlaoke.channels`` that exposes a
    :func:`register` function returning a :class:`BaseChannel` subclass.
    """

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._channels: dict[str, ManagedChannel] = {}
        self._configs: dict[str, ChannelConfig] = {}
        self._closed = False

    def configure(self, configs: Iterable[ChannelConfig]) -> None:
        for cfg in configs:
            self._configs[cfg.name] = cfg

    def register_channel(
        self,
        name: str,
        channel_cls: type[BaseChannel],
        config: ChannelConfig | None = None,
    ) -> None:
        cfg = config or self._configs.get(name) or ChannelConfig(name=name)
        instance = channel_cls(cfg, self.bus)
        self._channels[name] = ManagedChannel(channel=instance)

    async def start_all(self) -> None:
        for name, managed in list(self._channels.items()):
            if not managed.channel.config.enabled:
                continue
            await self._start_with_retry(name, managed)

    async def stop_all(self) -> None:
        self._closed = True
        for managed in self._channels.values():
            try:
                await managed.channel.stop()
            except Exception as exc:
                logger.warning("Error stopping channel: %s", exc)

    async def _start_with_retry(self, name: str, managed: ManagedChannel) -> None:
        for attempt, delay in enumerate((*_RETRY_DELAYS, _RETRY_DELAYS[-1])):
            try:
                await managed.channel.start()
                managed.retry_attempts = 0
                return
            except Exception as exc:
                managed.retry_attempts = attempt + 1
                managed.last_error = str(exc)
                logger.warning(
                    "Channel %s start failed (attempt %d): %s",
                    name,
                    attempt + 1,
                    exc,
                )
                if self._closed:
                    return
                await asyncio.sleep(delay)

    def get(self, name: str) -> BaseChannel | None:
        managed = self._channels.get(name)
        return managed.channel if managed else None

    def list_channels(self) -> list[str]:
        return list(self._channels.keys())


def discover_builtin_channels() -> dict[str, type[BaseChannel]]:
    """Return a dict ``{name: class}`` of built-in channels."""
    import openlaoke.channels as pkg

    found: dict[str, type[BaseChannel]] = {}
    for _finder, name, _is_pkg in pkgutil.iter_modules(pkg.__path__):
        if name.startswith("_") or name in {"base", "manager"}:
            continue
        try:
            module = __import__(f"openlaoke.channels.{name}", fromlist=["*"])
        except ImportError as exc:
            logger.debug("Skipped channel %s: %s", name, exc)
            continue
        cls = getattr(module, "CHANNEL_CLASS", None)
        if cls is not None and isinstance(cls, type) and issubclass(cls, BaseChannel):
            found[getattr(module, "CHANNEL_NAME", name)] = cls
    return found
