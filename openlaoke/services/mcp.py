"""MCP (Model Context Protocol) service for external tool servers."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"
    url: str = ""


@dataclass
class MCPServerConnection:
    """State of an MCP server connection."""
    config: MCPServerConfig
    connected: bool = False
    tools: list[dict[str, Any]] = field(default_factory=list)
    process: asyncio.subprocess.Process | None = None
    error: str | None = None


class MCPService:
    """Manages MCP server connections and tool discovery."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.servers: dict[str, MCPServerConnection] = {}
        self._config_path = os.path.expanduser("~/.openlaoke/mcp_servers.json")

    async def load_config(self) -> None:
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path) as f:
                    data = json.load(f)
                for name, cfg in data.get("mcpServers", {}).items():
                    self.servers[name] = MCPServerConnection(
                        config=MCPServerConfig(
                            name=name,
                            command=cfg.get("command", ""),
                            args=cfg.get("args", []),
                            env=cfg.get("env", {}),
                            transport=cfg.get("transport", "stdio"),
                            url=cfg.get("url", ""),
                        )
                    )
            except Exception:
                pass

    async def connect_server(self, name: str) -> MCPServerConnection | None:
        conn = self.servers.get(name)
        if not conn:
            return None

        try:
            env = os.environ.copy()
            env.update(conn.config.env)

            conn.process = await asyncio.create_subprocess_exec(
                conn.config.command,
                *conn.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            conn.connected = True

            await self._discover_tools(conn)

        except Exception as e:
            conn.error = str(e)
            conn.connected = False

        return conn

    async def _discover_tools(self, conn: MCPServerConnection) -> None:
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }
            conn.process.stdin.write((json.dumps(request) + "\n").encode())
            await conn.process.stdin.drain()

            response_line = await asyncio.wait_for(
                conn.process.stdout.readline(), timeout=10.0
            )
            response = json.loads(response_line.decode())

            for tool_def in response.get("result", {}).get("tools", []):
                conn.tools.append(tool_def)
                self._register_mcp_tool(conn, tool_def)

        except Exception:
            pass

    def _register_mcp_tool(self, conn: MCPServerConnection, tool_def: dict[str, Any]) -> None:
        name = tool_def.get("name", "")
        description = tool_def.get("description", "")
        schema = tool_def.get("inputSchema", {})

        class MCPToolWrapper(Tool):
            def __init__(self, mcp_name: str, server_conn: MCPServerConnection):
                self.name = f"mcp_{mcp_name}_{name}"
                self.description = f"[MCP: {mcp_name}] {description}"
                self.input_schema = schema
                self._mcp_name = mcp_name
                self._server = server_conn

            async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
                try:
                    request = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": kwargs},
                    }
                    self._server.process.stdin.write(
                        (json.dumps(request) + "\n").encode()
                    )
                    await self._server.process.stdin.drain()

                    response_line = await asyncio.wait_for(
                        self._server.process.stdout.readline(), timeout=30.0
                    )
                    response = json.loads(response_line.decode())

                    content = response.get("result", {}).get("content", [])
                    text = "\n".join(
                        c.get("text", "") for c in content if isinstance(c, dict)
                    )
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=text or "(no output)",
                    )
                except Exception as e:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content=f"MCP tool error: {e}",
                        is_error=True,
                    )

        self.registry.register(MCPToolWrapper(name, conn))

    async def disconnect_all(self) -> None:
        for conn in self.servers.values():
            if conn.process and conn.process.returncode is None:
                conn.process.kill()
                await conn.process.wait()
            conn.connected = False

    def get_server_status(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "connected": conn.connected,
                "tools": len(conn.tools),
                "error": conn.error,
            }
            for name, conn in self.servers.items()
        ]
