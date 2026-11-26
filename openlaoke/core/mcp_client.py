"""Minimal MCP client over stdio.

Speaks JSON-RPC 2.0 with newline-delimited framing, which is what the Model
Context Protocol specifies for stdio transports. Only the parts a tool host
needs are implemented: ``initialize``, ``tools/list`` and ``tools/call``.
Resources, prompts and sampling are not exposed because nothing here consumes
them yet.

A server that fails to start, crashes, or does not answer within the timeout is
reported and skipped: one bad entry in the config must not stop the session from
starting.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "openlaoke"
CLIENT_VERSION = "0.1"
DEFAULT_TIMEOUT = 20.0
MAX_MESSAGE_BYTES = 4_000_000


class MCPError(RuntimeError):
    """A protocol-level failure: bad handshake, error response, timeout."""


@dataclass
class MCPToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> MCPServerConfig:
        return cls(
            name=name,
            command=str(data.get("command") or "").strip(),
            args=[str(item) for item in (data.get("args") or [])],
            env={str(key): str(value) for key, value in (data.get("env") or {}).items()},
            cwd=str(data.get("cwd") or ""),
            timeout=float(data.get("timeout") or DEFAULT_TIMEOUT),
        )


class MCPStdioClient:
    """One MCP server process."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.proc: asyncio.subprocess.Process | None = None
        self._next_id = 0
        self._lock = asyncio.Lock()
        self.server_info: dict[str, Any] = {}

    async def start(self) -> None:
        if not self.config.command:
            raise MCPError(f"server '{self.config.name}' has no command")

        env = os.environ.copy()
        env.update(self.config.env)
        self.proc = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=self.config.cwd or None,
            env=env,
        )
        result = await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        self.server_info = result.get("serverInfo", {}) if isinstance(result, dict) else {}
        await self._notify("notifications/initialized", {})

    async def list_tools(self) -> list[MCPToolSpec]:
        result = await self._request("tools/list", {})
        raw = result.get("tools") if isinstance(result, dict) else None
        specs: list[MCPToolSpec] = []
        for item in raw or []:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            schema = item.get("inputSchema") or item.get("input_schema") or {}
            specs.append(
                MCPToolSpec(
                    name=str(item["name"]),
                    description=str(item.get("description") or ""),
                    input_schema=schema if isinstance(schema, dict) else {},
                )
            )
        return specs

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """Return ``(text, is_error)`` for one tool call."""
        result = await self._request("tools/call", {"name": name, "arguments": arguments})
        if not isinstance(result, dict):
            return str(result), False

        chunks: list[str] = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
            elif isinstance(item, dict) and item.get("type") == "resource":
                resource = item.get("resource") or {}
                if isinstance(resource, dict) and resource.get("text"):
                    chunks.append(str(resource["text"]))
        text = "\n".join(chunk for chunk in chunks if chunk)
        if not text:
            text = json.dumps(result, ensure_ascii=False)[:4000]
        return text, bool(result.get("isError"))

    async def stop(self) -> None:
        if self.proc is None:
            return
        proc, self.proc = self.proc, None
        if proc.stdin and not proc.stdin.is_closing():
            proc.stdin.close()
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except TimeoutError:
                proc.kill()
                with contextlib.suppress(Exception):
                    await proc.wait()

    # ── protocol ────────────────────────────────────────────────────────

    async def _send(self, payload: dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise MCPError(f"server '{self.config.name}' is not running")
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        self.proc.stdin.write(line.encode("utf-8"))
        await self.proc.stdin.drain()

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        async with self._lock:
            self._next_id += 1
            request_id = self._next_id
            await self._send(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            deadline = asyncio.get_running_loop().time() + self.config.timeout
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise MCPError(f"{self.config.name}: '{method}' timed out")
                try:
                    line = await asyncio.wait_for(self._read_line(), timeout=remaining)
                except TimeoutError as exc:
                    # A server that hangs must look like any other protocol
                    # failure: callers catch MCPError, and an escaping
                    # TimeoutError turned a stuck server into a broken turn.
                    raise MCPError(
                        f"{self.config.name}: '{method}' timed out after "
                        f"{self.config.timeout:g}s"
                    ) from exc
                if line is None:
                    raise MCPError(f"{self.config.name}: connection closed during '{method}'")
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("mcp %s: ignoring non-JSON line", self.config.name)
                    continue
                if message.get("id") != request_id:
                    # Notifications and stale responses are not ours to handle.
                    continue
                if "error" in message:
                    error = message["error"] or {}
                    raise MCPError(
                        f"{self.config.name}: {error.get('message', 'error')} "
                        f"(code {error.get('code', '?')})"
                    )
                return message.get("result", {})

    async def _read_line(self) -> str | None:
        if self.proc is None or self.proc.stdout is None:
            return None
        try:
            raw = await self.proc.stdout.readline()
        except (asyncio.IncompleteReadError, ValueError):
            return None
        if not raw:
            return None
        if len(raw) > MAX_MESSAGE_BYTES:
            raise MCPError(f"{self.config.name}: response larger than {MAX_MESSAGE_BYTES} bytes")
        return raw.decode("utf-8", errors="replace").strip()
