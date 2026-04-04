"""MCP (Model Context Protocol) service with multi-transport support."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class TransportType(StrEnum):
    """MCP transport types."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    WS = "ws"


class ConnectionState(StrEnum):
    """MCP connection states."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    NEEDS_AUTH = "needs_auth"
    NEEDS_CLIENT_REGISTRATION = "needs_client_registration"
    DISABLED = "disabled"


@dataclass
class OAuthConfig:
    """OAuth configuration for MCP servers."""

    client_id: str | None = None
    client_secret: str | None = None
    scope: str | None = None
    redirect_uri: str = "http://127.0.0.1:19876/mcp/oauth/callback"


@dataclass
class OAuthTokens:
    """OAuth tokens storage."""

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    scope: str | None = None


@dataclass
class OAuthState:
    """OAuth state for authentication flow."""

    code_verifier: str | None = None
    state: str | None = None
    tokens: OAuthTokens | None = None


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""

    name: str
    transport: TransportType = TransportType.STDIO
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    oauth: OAuthConfig | bool | None = None
    enabled: bool = True
    timeout: int = 30000


@dataclass
class MCPServerConnection:
    """State of an MCP server connection."""

    config: MCPServerConfig
    state: ConnectionState = ConnectionState.DISCONNECTED
    tools: list[dict[str, Any]] = field(default_factory=list)
    process: asyncio.subprocess.Process | None = None
    error: str | None = None
    oauth_state: OAuthState | None = None
    _http_client: httpx.AsyncClient | None = None
    _ws_connection: Any = None
    _sse_response: httpx.Response | None = None
    _request_id: int = 0


class MCPService:
    """Manages MCP server connections with multi-transport support."""

    OAUTH_CALLBACK_PORT = 19876
    OAUTH_CALLBACK_PATH = "/mcp/oauth/callback"

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.servers: dict[str, MCPServerConnection] = {}
        self._config_path = os.path.expanduser("~/.openlaoke/mcp_servers.json")
        self._auth_path = os.path.expanduser("~/.openlaoke/mcp_auth.json")
        self._oauth_transports: dict[str, MCPServerConnection] = {}

    async def load_config(self) -> None:
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path) as f:
                    data = json.load(f)
                for name, cfg in data.get("mcpServers", {}).items():
                    oauth_cfg: OAuthConfig | bool | None = None
                    if "oauth" in cfg:
                        oauth_data = cfg["oauth"]
                        if oauth_data is False:
                            oauth_cfg = False
                        elif isinstance(oauth_data, dict):
                            oauth_cfg = OAuthConfig(
                                client_id=oauth_data.get("clientId"),
                                client_secret=oauth_data.get("clientSecret"),
                                scope=oauth_data.get("scope"),
                            )

                    transport_str = cfg.get("transport", "stdio")
                    try:
                        transport = TransportType(transport_str)
                    except ValueError:
                        transport = TransportType.STDIO

                    self.servers[name] = MCPServerConnection(
                        config=MCPServerConfig(
                            name=name,
                            transport=transport,
                            command=cfg.get("command", ""),
                            args=cfg.get("args", []),
                            env=cfg.get("env", {}),
                            url=cfg.get("url", ""),
                            headers=cfg.get("headers", {}),
                            oauth=oauth_cfg,
                            enabled=cfg.get("enabled", True),
                            timeout=cfg.get("timeout", 30000),
                        )
                    )
            except Exception:
                pass

        await self._load_auth_state()

    async def _load_auth_state(self) -> None:
        if os.path.exists(self._auth_path):
            try:
                with open(self._auth_path) as f:
                    data = json.load(f)
                for name, state_data in data.items():
                    if name in self.servers:
                        conn = self.servers[name]
                        if "tokens" in state_data:
                            tokens = OAuthTokens(
                                access_token=state_data["tokens"]["accessToken"],
                                refresh_token=state_data["tokens"].get("refreshToken"),
                                expires_at=state_data["tokens"].get("expiresAt"),
                                scope=state_data["tokens"].get("scope"),
                            )
                            conn.oauth_state = OAuthState(
                                code_verifier=state_data.get("codeVerifier"),
                                state=state_data.get("oauthState"),
                                tokens=tokens,
                            )
            except Exception:
                pass

    async def _save_auth_state(self) -> None:
        data: dict[str, dict[str, Any]] = {}
        for name, conn in self.servers.items():
            if conn.oauth_state:
                state_data: dict[str, Any] = {}
                if conn.oauth_state.tokens:
                    state_data["tokens"] = {
                        "accessToken": conn.oauth_state.tokens.access_token,
                        "refreshToken": conn.oauth_state.tokens.refresh_token,
                        "expiresAt": conn.oauth_state.tokens.expires_at,
                        "scope": conn.oauth_state.tokens.scope,
                    }
                if conn.oauth_state.code_verifier:
                    state_data["codeVerifier"] = conn.oauth_state.code_verifier
                if conn.oauth_state.state:
                    state_data["oauthState"] = conn.oauth_state.state
                data[name] = state_data

        os.makedirs(os.path.dirname(self._auth_path), exist_ok=True)
        with open(self._auth_path, "w") as f:
            json.dump(data, f, indent=2)

    async def connect_server(self, name: str) -> MCPServerConnection | None:
        conn = self.servers.get(name)
        if not conn:
            return None

        if not conn.config.enabled:
            conn.state = ConnectionState.DISABLED
            return conn

        try:
            if conn.config.transport == TransportType.STDIO:
                await self._connect_stdio(conn)
            elif conn.config.transport == TransportType.SSE:
                await self._connect_sse(conn)
            elif conn.config.transport == TransportType.HTTP:
                await self._connect_http(conn)
            elif conn.config.transport == TransportType.WS:
                await self._connect_ws(conn)

            if conn.state == ConnectionState.CONNECTED:
                await self._discover_tools(conn)

        except Exception as e:
            conn.error = str(e)
            conn.state = ConnectionState.FAILED

        return conn

    async def _connect_stdio(self, conn: MCPServerConnection) -> None:
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
        conn.state = ConnectionState.CONNECTED

    async def _connect_sse(self, conn: MCPServerConnection) -> None:
        headers = self._build_headers(conn)
        client = httpx.AsyncClient(timeout=conn.config.timeout / 1000)

        try:
            response = await client.get(
                conn.config.url,
                headers=headers,
            )
            response.raise_for_status()
            conn._http_client = client
            conn._sse_response = response
            conn.state = ConnectionState.CONNECTED
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                conn.state = ConnectionState.NEEDS_AUTH
                self._oauth_transports[conn.config.name] = conn
            else:
                raise

    async def _connect_http(self, conn: MCPServerConnection) -> None:
        client = httpx.AsyncClient(timeout=conn.config.timeout / 1000)
        conn._http_client = client

        try:
            await self._http_request(conn, "initialize", {"protocolVersion": "2024-11-05"})
            conn.state = ConnectionState.CONNECTED
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                conn.state = ConnectionState.NEEDS_AUTH
                self._oauth_transports[conn.config.name] = conn
            else:
                raise

    async def _connect_ws(self, conn: MCPServerConnection) -> None:
        import websockets

        headers = self._build_headers(conn)
        extra_headers = [(k, v) for k, v in headers.items()]

        try:
            ws = await websockets.connect(
                conn.config.url,
                additional_headers=extra_headers,
                ping_interval=20,
                ping_timeout=conn.config.timeout / 1000,
            )
            conn._ws_connection = ws
            await self._ws_request(conn, "initialize", {"protocolVersion": "2024-11-05"})
            conn.state = ConnectionState.CONNECTED
        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "Unauthorized" in error_str:
                conn.state = ConnectionState.NEEDS_AUTH
                self._oauth_transports[conn.config.name] = conn
            else:
                raise

    def _build_headers(self, conn: MCPServerConnection) -> dict[str, str]:
        headers = dict(conn.config.headers)
        if conn.oauth_state and conn.oauth_state.tokens:
            headers["Authorization"] = f"Bearer {conn.oauth_state.tokens.access_token}"
        return headers

    async def _http_request(
        self, conn: MCPServerConnection, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if not conn._http_client:
            raise ValueError("HTTP client not initialized")
        conn._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": conn._request_id,
            "method": method,
            "params": params,
        }

        response = await conn._http_client.post(
            conn.config.url,
            json=request,
            headers=self._build_headers(conn),
        )
        response.raise_for_status()
        return dict(response.json())

    async def _ws_request(
        self, conn: MCPServerConnection, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if not conn._ws_connection:
            raise ValueError("WebSocket connection not initialized")
        conn._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": conn._request_id,
            "method": method,
            "params": params,
        }

        await conn._ws_connection.send(json.dumps(request))
        response_str = await conn._ws_connection.recv()
        return dict(json.loads(response_str))

    async def _stdio_request(
        self, conn: MCPServerConnection, method: str, params: dict[str, Any], timeout: float = 30.0
    ) -> dict[str, Any]:
        if not conn.process or not conn.process.stdin or not conn.process.stdout:
            raise ValueError("Process not initialized")
        conn._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": conn._request_id,
            "method": method,
            "params": params,
        }

        conn.process.stdin.write((json.dumps(request) + "\n").encode())
        await conn.process.stdin.drain()

        response_line = await asyncio.wait_for(conn.process.stdout.readline(), timeout=timeout)
        return dict(json.loads(response_line.decode()))

    async def _discover_tools(self, conn: MCPServerConnection) -> None:
        try:
            response = await self._send_request(conn, "tools/list", {})

            for tool_def in response.get("result", {}).get("tools", []):
                conn.tools.append(tool_def)
                self._register_mcp_tool(conn, tool_def)

        except Exception:
            pass

    async def _send_request(
        self, conn: MCPServerConnection, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if conn.config.transport == TransportType.STDIO:
            return await self._stdio_request(conn, method, params)
        elif conn.config.transport == TransportType.HTTP:
            return await self._http_request(conn, method, params)
        elif conn.config.transport == TransportType.WS:
            return await self._ws_request(conn, method, params)
        elif conn.config.transport == TransportType.SSE:
            return await self._http_request(conn, method, params)
        raise ValueError(f"Unsupported transport: {conn.config.transport}")

    def _register_mcp_tool(self, conn: MCPServerConnection, tool_def: dict[str, Any]) -> None:
        name = tool_def.get("name", "")
        description = tool_def.get("description", "")
        schema = tool_def.get("inputSchema", {})

        class MCPToolWrapper(Tool):
            def __init__(
                self,
                mcp_service: MCPService,
                mcp_name: str,
                server_conn: MCPServerConnection,
                tool_name: str,
                tool_desc: str,
                tool_schema: dict[str, Any],
            ):
                self.name = f"mcp_{mcp_name}_{tool_name}"
                self.description = f"[MCP: {mcp_name}] {tool_desc}"
                self.input_schema = tool_schema
                self._mcp_service = mcp_service
                self._mcp_name = mcp_name
                self._server = server_conn
                self._tool_name = tool_name

            async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
                try:
                    response = await self._mcp_service._send_request(
                        self._server,
                        "tools/call",
                        {"name": self._tool_name, "arguments": kwargs},
                    )

                    content = response.get("result", {}).get("content", [])
                    text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
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

        self.registry.register(MCPToolWrapper(self, name, conn, name, description, schema))

    async def start_oauth_flow(self, name: str) -> tuple[str, str]:
        conn = self.servers.get(name)
        if not conn:
            raise ValueError(f"MCP server {name} not found")

        if conn.config.oauth is False:
            raise ValueError(f"OAuth disabled for {name}")

        code_verifier = secrets.token_urlsafe(32)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )

        state = secrets.token_urlsafe(32)

        if conn.oauth_state is None:
            conn.oauth_state = OAuthState()
        conn.oauth_state.code_verifier = code_verifier
        conn.oauth_state.state = state

        oauth_config = (
            conn.config.oauth if isinstance(conn.config.oauth, OAuthConfig) else OAuthConfig()
        )

        auth_url_params = {
            "response_type": "code",
            "client_id": oauth_config.client_id or "",
            "redirect_uri": oauth_config.redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }

        if oauth_config.scope:
            auth_url_params["scope"] = oauth_config.scope

        base_url = conn.config.url
        auth_base = base_url.split("/mcp")[0] if "/mcp" in base_url else base_url.rstrip("/")

        authorization_url = f"{auth_base}/authorize?{urllib.parse.urlencode(auth_url_params)}"

        await self._save_auth_state()
        return authorization_url, state

    async def finish_oauth_flow(self, name: str, authorization_code: str) -> ConnectionState:
        conn = self._oauth_transports.get(name) or self.servers.get(name)
        if not conn:
            raise ValueError(f"MCP server {name} not found")

        if not conn.oauth_state or not conn.oauth_state.code_verifier:
            raise ValueError(f"No pending OAuth flow for {name}")

        oauth_config = (
            conn.config.oauth if isinstance(conn.config.oauth, OAuthConfig) else OAuthConfig()
        )

        token_url_params = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": oauth_config.redirect_uri,
            "code_verifier": conn.oauth_state.code_verifier,
        }

        if oauth_config.client_id:
            token_url_params["client_id"] = oauth_config.client_id
        if oauth_config.client_secret:
            token_url_params["client_secret"] = oauth_config.client_secret

        base_url = conn.config.url
        token_base = base_url.split("/mcp")[0] if "/mcp" in base_url else base_url.rstrip("/")

        token_url = f"{token_base}/token"

        client = httpx.AsyncClient()
        try:
            response = await client.post(
                token_url,
                data=token_url_params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

            tokens = OAuthTokens(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                expires_at=(token_data.get("expires_in") if token_data.get("expires_in") else None),
                scope=token_data.get("scope"),
            )

            conn.oauth_state.tokens = tokens
            conn.oauth_state.code_verifier = None
            conn.oauth_state.state = None

            await self._save_auth_state()

            del self._oauth_transports[name]

            result = await self.connect_server(name)
            return result.state if result else ConnectionState.FAILED

        finally:
            await client.aclose()

    async def remove_auth(self, name: str) -> None:
        conn = self.servers.get(name)
        if not conn:
            return

        conn.oauth_state = None
        if name in self._oauth_transports:
            del self._oauth_transports[name]

        await self._save_auth_state()

    def supports_oauth(self, name: str) -> bool:
        conn = self.servers.get(name)
        if not conn:
            return False

        if conn.config.transport == TransportType.STDIO:
            return False

        return conn.config.oauth is not False

    def has_stored_tokens(self, name: str) -> bool:
        conn = self.servers.get(name)
        if not conn or not conn.oauth_state:
            return False
        return conn.oauth_state.tokens is not None

    async def disconnect_all(self) -> None:
        for conn in self.servers.values():
            await self._disconnect_connection(conn)

    async def _disconnect_connection(self, conn: MCPServerConnection) -> None:
        if conn.process and conn.process.returncode is None:
            conn.process.kill()
            await conn.process.wait()

        if conn._http_client:
            await conn._http_client.aclose()
            conn._http_client = None

        if conn._ws_connection:
            await conn._ws_connection.close()
            conn._ws_connection = None

        conn.state = ConnectionState.DISCONNECTED

    def get_server_status(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "state": conn.state.value,
                "transport": conn.config.transport.value,
                "tools": len(conn.tools),
                "error": conn.error,
                "has_auth": self.has_stored_tokens(name),
            }
            for name, conn in self.servers.items()
        ]
