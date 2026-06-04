"""Three-tier command router.

Tier 1: ``priority`` — handled without lock. Reserved for
always-on, never-blocking commands like ``/stop``, ``/restart``,
``/status``.

Tier 2: ``exact`` — exact match on the command name (``/new``,
``/help``, ``/dream``).

Tier 3: ``prefix`` — longest-prefix-first. Used for ``/model preset``,
``/goal foo``, ``/history 5``.

Custom commands (markdown files in ``.openlaoke/commands/``) become
``/git:commit`` etc. via subdirs.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """The result of running a slash command."""

    success: bool = True
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""


CommandHandler = Callable[[str, dict[str, Any]], Awaitable[CommandResult]]


@dataclass
class CommandSpec:
    name: str
    handler: CommandHandler
    description: str = ""
    aliases: tuple[str, ...] = ()
    tier: str = "exact"


class CommandRouter:
    """Three-tier dispatch with longest-prefix-first for tier 3."""

    def __init__(self) -> None:
        self._priority: list[CommandSpec] = []
        self._exact: dict[str, CommandSpec] = {}
        self._prefix: list[CommandSpec] = []

    def register(self, spec: CommandSpec) -> None:
        if spec.tier == "priority":
            self._priority.append(spec)
            for alias in (spec.name, *spec.aliases):
                self._exact.pop(alias, None)
                self._prefix = [s for s in self._prefix if s.name != alias]
            self._priority.append(spec)
            return
        if spec.tier == "exact":
            for alias in (spec.name, *spec.aliases):
                self._exact[alias] = spec
            return
        if spec.tier == "prefix":
            self._prefix.append(spec)
            self._prefix.sort(key=lambda s: len(s.name), reverse=True)
            return
        raise ValueError(f"unknown tier: {spec.tier}")

    def unregister(self, name: str) -> bool:
        if any(s.name == name for s in self._priority):
            self._priority = [s for s in self._priority if s.name != name]
            return True
        if name in self._exact:
            spec = self._exact.pop(name)
            for alias in (spec.name, *spec.aliases):
                self._exact.pop(alias, None)
            return True
        before = len(self._prefix)
        self._prefix = [s for s in self._prefix if s.name != name]
        return len(self._prefix) < before

    def lookup(self, command: str) -> CommandSpec | None:
        name = command.lstrip("/").lower()
        for spec in self._priority:
            if name in (spec.name.lower(), *(a.lower() for a in spec.aliases)):
                return spec
        if name in self._exact:
            return self._exact[name]
        for spec in self._prefix:
            if name.startswith(spec.name.lower()):
                return spec
        return None

    async def dispatch(
        self,
        command: str,
        args: dict[str, Any] | None = None,
    ) -> CommandResult:
        spec = self.lookup(command)
        if spec is None:
            return CommandResult(success=False, error=f"unknown command: {command}")
        try:
            return await spec.handler(command, args or {})
        except Exception as exc:
            logger.exception("Command %s failed", command)
            return CommandResult(success=False, error=str(exc))

    def list_commands(self) -> list[str]:
        names: set[str] = set()
        for spec in self._priority:
            names.add(spec.name)
        for spec in self._exact.values():
            names.add(spec.name)
        for spec in self._prefix:
            names.add(spec.name)
        return sorted(names)


def make_router() -> CommandRouter:
    """Default command router pre-loaded with built-ins."""
    router = CommandRouter()

    async def stop(_cmd: str, _args: dict[str, Any]) -> CommandResult:
        return CommandResult(text="stopped")

    async def status(_cmd: str, _args: dict[str, Any]) -> CommandResult:
        return CommandResult(text="ok")

    async def help_cmd(_cmd: str, _args: dict[str, Any]) -> CommandResult:
        return CommandResult(text="commands: /stop /status /help /new /dream /goal /history /model")

    async def new_session(_cmd: str, _args: dict[str, Any]) -> CommandResult:
        return CommandResult(text="new session")

    async def dream(_cmd: str, _args: dict[str, Any]) -> CommandResult:
        return CommandResult(text="dream: memory consolidation")

    async def goal(_cmd: str, args: dict[str, Any]) -> CommandResult:
        return CommandResult(text=f"goal registered: {args.get('text', '')}")

    async def history(_cmd: str, _args: dict[str, Any]) -> CommandResult:
        return CommandResult(text="history")

    async def model(_cmd: str, args: dict[str, Any]) -> CommandResult:
        return CommandResult(text=f"model switched: {args.get('preset', 'default')}")

    router.register(CommandSpec(name="stop", handler=stop, tier="priority", aliases=()))
    router.register(CommandSpec(name="status", handler=status, tier="priority", aliases=()))
    router.register(CommandSpec(name="help", handler=help_cmd, tier="exact", aliases=("?",)))
    router.register(CommandSpec(name="new", handler=new_session, tier="exact", aliases=()))
    router.register(CommandSpec(name="dream", handler=dream, tier="exact", aliases=()))
    router.register(CommandSpec(name="goal", handler=goal, tier="prefix", aliases=()))
    router.register(CommandSpec(name="history", handler=history, tier="prefix", aliases=()))
    router.register(CommandSpec(name="model", handler=model, tier="prefix", aliases=()))
    return router
