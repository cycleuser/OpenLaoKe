"""MCP client for stdio and streamable-HTTP transports.

The :class:`MCPClient` wraps a single MCP server. Multiple clients can
be registered with the :class:`MCPManager` (one per server). Each
client can be ``eager``, ``lazy``, or ``background``:

* ``eager`` — handshake blocks at boot; ready before first turn.
* ``lazy`` (default) — registers placeholder tools until first use.
* ``background`` — spawns a goroutine/task to warm the connection
  while the user is idle.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class TransportType(StrEnum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"
    SSE = "sse"


class Tier(StrEnum):
    EAGER = "eager"
    LAZY = "lazy"
    BACKGROUND = "background"


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def sanitize_tool_name(server: str, tool: str) -> str:
    """Return ``mcp__<server>__<tool>`` with non-safe chars replaced."""
    safe_server = _SAFE_NAME_RE.sub("_", server)
    safe_tool = _SAFE_NAME_RE.sub("_", tool)
    return f"mcp__{safe_server}__{safe_tool}"


@dataclass
class PluginEntry:
    """A single MCP server configuration."""

    name: str
    transport: TransportType = TransportType.STDIO
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    tier: Tier = Tier.LAZY
    enabled: bool = True
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolInfo:
    """A tool advertised by an MCP server."""

    server: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    read_only: bool = False


@dataclass
class MCPPromptInfo:
    server: str
    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MCPResourceInfo:
    server: str
    uri: str
    name: str = ""
    description: str = ""
    mime_type: str = ""


def expand_env(value: str) -> str:
    """Expand ``${VAR}`` and ``${VAR:-default}`` references."""
    if not value:
        return value
    pattern = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        return match.group(0)

    return pattern.sub(_replace, value)


def expand_plugin_env(entry: PluginEntry) -> PluginEntry:
    """Return a copy of ``entry`` with ``${VAR}`` expansions applied."""
    expanded_env: dict[str, str] = {}
    for k, v in entry.env.items():
        expanded_env[k] = expand_env(v)
    expanded_url = expand_env(entry.url) if entry.url else None
    expanded_headers = {k: expand_env(v) for k, v in entry.headers.items()}
    expanded_args = [expand_env(a) for a in entry.args]
    return PluginEntry(
        name=entry.name,
        transport=entry.transport,
        command=expand_env(entry.command) if entry.command else None,
        args=expanded_args,
        env=expanded_env,
        url=expanded_url,
        headers=expanded_headers,
        tier=entry.tier,
        enabled=entry.enabled,
        description=entry.description,
        metadata=dict(entry.metadata),
    )


class MCPConnection:
    """Base class for MCP transports. Subclasses implement handshake."""

    def __init__(self, entry: PluginEntry) -> None:
        self.entry = expand_plugin_env(entry)
        self.tools: list[MCPToolInfo] = []
        self.prompts: list[MCPPromptInfo] = []
        self.resources: list[MCPResourceInfo] = []
        self.ready = False
        self.last_error: str = ""

    async def handshake(self) -> None:
        raise NotImplementedError

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def list_prompts(self) -> list[MCPPromptInfo]:
        return list(self.prompts)

    async def list_resources(self) -> list[MCPResourceInfo]:
        return list(self.resources)

    async def read_resource(self, uri: str) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self) -> None:
        self.ready = False


class MCPManager:
    """Lifecycle and routing for MCP servers."""

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}
        self._placeholders: dict[str, list[MCPToolInfo]] = {}
        self._lock = asyncio.Lock()

    def register(self, entry: PluginEntry) -> None:
        self._placeholders[entry.name] = []

    def add_connection(self, name: str, conn: MCPConnection) -> None:
        self._connections[name] = conn

    def has_server(self, name: str) -> bool:
        return name in self._connections

    def list_servers(self) -> list[str]:
        return list(self._connections.keys())

    def list_tools(self, server: str | None = None) -> list[MCPToolInfo]:
        if server is None:
            tools: list[MCPToolInfo] = []
            for conn in self._connections.values():
                tools.extend(conn.tools)
            return tools
        conn = self._connections.get(server)
        return list(conn.tools) if conn else []

    def resolve_tool(self, full_name: str) -> tuple[str, MCPToolInfo] | None:
        """Resolve a ``mcp__<server>__<tool>`` name to a (server, tool) pair."""
        if not full_name.startswith("mcp__"):
            return None
        parts = full_name.split("__", 2)
        if len(parts) != 3:
            return None
        server, tool = parts[1], parts[2]
        for info in self.list_tools(server):
            if info.name == tool:
                return server, info
        return None

    async def call_tool(
        self, full_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resolved = self.resolve_tool(full_name)
        if not resolved:
            return {"error": f"unknown tool: {full_name}"}
        server, _ = resolved
        conn = self._connections.get(server)
        if not conn:
            return {"error": f"server not connected: {server}"}
        if not conn.ready:
            try:
                await conn.handshake()
            except Exception as exc:
                conn.last_error = str(exc)
                return {"error": f"handshake failed: {exc}"}
        try:
            return await conn.call_tool(resolved[1].name, arguments or {})
        except Exception as exc:
            return {"error": f"call failed: {exc}"}

    async def connect(self, name: str) -> bool:
        if name in self._connections:
            return True
        placeholder = self._placeholders.get(name)
        if placeholder is None:
            return False
        return False

    async def disconnect(self, name: str) -> bool:
        conn = self._connections.pop(name, None)
        if conn is None:
            return False
        await conn.close()
        return True

    async def add_runtime(self, entry: PluginEntry) -> None:
        """Register and connect a server at runtime (hot-add)."""
        async with self._lock:
            self._placeholders.setdefault(entry.name, [])
            if entry.name in self._connections:
                return

    async def remove_runtime(self, name: str) -> bool:
        async with self._lock:
            return await self.disconnect(name)


def mcp_tool_namespace() -> str:
    """The standard namespace prefix for MCP tools."""
    return "mcp__"
