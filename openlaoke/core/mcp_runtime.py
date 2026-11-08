"""Bridge MCP servers into the local tool registry.

Each server tool becomes a normal local tool, so the model sees one flat list
and the permission layer, the result ledger and the intent field all keep
working without knowing MCP exists.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from openlaoke.core.mcp_client import MCPError, MCPServerConfig, MCPStdioClient, MCPToolSpec
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

logger = logging.getLogger(__name__)

_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def tool_name(server: str, name: str) -> str:
    """Stable, model-friendly name: ``mcp__server__tool``."""
    return f"mcp__{_SAFE.sub('_', server)}__{_SAFE.sub('_', name)}"


class MCPTool(Tool):
    """A tool served by an MCP server."""

    def __init__(self, client: MCPStdioClient, spec: MCPToolSpec) -> None:
        self.client = client
        self.spec = spec
        self.name = tool_name(client.config.name, spec.name)
        self.description = f"[{client.config.name}] {spec.description or spec.name}"
        self.is_read_only = False
        self.is_destructive = False
        self.is_concurrency_safe = False
        # MCP servers provide their own JSON Schema; the base class accepts a
        # dict and adds the shared intent fields to it.
        self.input_schema = spec.input_schema or {"type": "object", "properties": {}}

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        arguments = {key: value for key, value in kwargs.items() if key not in _LOCAL_FIELDS}
        try:
            text, is_error = await self.client.call_tool(self.spec.name, arguments)
        except MCPError as exc:
            return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=str(exc), is_error=True)
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id, content=text or "(no output)", is_error=is_error
        )


_LOCAL_FIELDS = {"intent", "accept_large_output"}


class MCPRuntime:
    """Owns the server processes and the tools they expose."""

    def __init__(self) -> None:
        self.clients: dict[str, MCPStdioClient] = {}
        self.failures: dict[str, str] = {}

    async def start(self, servers: dict[str, Any], registry: ToolRegistry) -> list[str]:
        """Start every configured server and register its tools.

        Returns the names of the tools that were added. A server that fails is
        recorded in ``failures`` and skipped.
        """
        added: list[str] = []
        for name, raw in servers.items():
            if not isinstance(raw, dict):
                self.failures[name] = "configuration must be an object"
                continue
            if raw.get("disabled"):
                continue
            config = MCPServerConfig.from_dict(str(name), raw)
            client = MCPStdioClient(config)
            try:
                await client.start()
                specs = await client.list_tools()
            except (MCPError, OSError, TimeoutError) as exc:
                self.failures[name] = str(exc)
                logger.warning("mcp server %s failed to start: %s", name, exc)
                await client.stop()
                continue

            self.clients[name] = client
            for spec in specs:
                registry.register(MCPTool(client, spec))
                added.append(tool_name(name, spec.name))
        return added

    async def stop(self) -> None:
        for client in list(self.clients.values()):
            await client.stop()
        self.clients.clear()

    def summary(self) -> str:
        if not self.clients and not self.failures:
            return "No MCP servers configured."
        lines = []
        for name, client in self.clients.items():
            lines.append(f"{name}: running ({client.config.command})")
        for name, reason in self.failures.items():
            lines.append(f"{name}: failed - {reason}")
        return "\n".join(lines)
