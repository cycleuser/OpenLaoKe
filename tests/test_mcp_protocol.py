"""Protocol-level tests for the MCP stdio client, with a fake process.

``test_mcp.py`` runs a real server subprocess end to end. This file covers the
failure branches that a well-behaved server never reaches: a dead pipe, a
timeout, a stale response id, a non-JSON line, an oversized message and the
shutdown paths. The process object is faked so those branches are deterministic.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from openlaoke.core.mcp_client import (
    MAX_MESSAGE_BYTES,
    MCPError,
    MCPServerConfig,
    MCPStdioClient,
)


class FakeStdin:
    def __init__(self) -> None:
        self.written: list[str] = []
        self.closed = False
        self._closing = False

    def write(self, data: bytes) -> None:
        self.written.append(data.decode())

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True
        self._closing = True

    def is_closing(self) -> bool:
        return self._closing


HANG = object()


class FakeStdout:
    def __init__(self, lines: list[Any]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        item = self._lines.pop(0)
        if item is HANG:
            await asyncio.sleep(10)  # a server that accepts input and never answers
            return b""
        if isinstance(item, BaseException):
            raise item
        return item if isinstance(item, bytes) else item.encode()


class FakeProc:
    def __init__(self, *, lines: list[Any] | None = None, returncode: int | None = None) -> None:
        self.stdin = FakeStdin()
        self.stdout = FakeStdout(lines or [])
        self.returncode = returncode
        self.terminated = False
        self.killed = False
        self._hang = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        if self._hang:
            await asyncio.sleep(10)
        return self.returncode or 0


def make_client(
    *, lines: list[Any] | None = None, timeout: float = 1.0
) -> tuple[MCPStdioClient, FakeProc]:
    client = MCPStdioClient(MCPServerConfig(name="fake", command="x", timeout=timeout))
    proc = FakeProc(lines=lines)
    client.proc = proc  # type: ignore[assignment]
    return client, proc


def response(request_id: int, result: Any) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\n"


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #


def test_sending_without_a_process_is_an_error() -> None:
    client = MCPStdioClient(MCPServerConfig(name="fake", command="x"))

    with pytest.raises(MCPError, match="is not running"):
        run(client._send({"id": 1}))


def test_a_notification_has_no_id() -> None:
    client, proc = make_client()

    run(client._notify("notifications/initialized", {}))

    payload = json.loads(proc.stdin.written[0])
    assert "id" not in payload
    assert payload["method"] == "notifications/initialized"


# --------------------------------------------------------------------------- #
# Request handling
# --------------------------------------------------------------------------- #


def test_a_request_returns_its_result() -> None:
    client, proc = make_client(lines=[response(1, {"tools": []})])

    assert run(client._request("tools/list", {})) == {"tools": []}
    assert json.loads(proc.stdin.written[0])["id"] == 1


def test_a_hung_server_times_out_as_an_mcp_error() -> None:
    """A stuck read used to escape as a bare TimeoutError, which /mcp tools did not catch."""
    client, _proc = make_client(lines=[HANG], timeout=0.01)

    with pytest.raises(MCPError, match="timed out after 0.01s"):
        run(client._request("tools/list", {}))


def test_an_expired_deadline_is_reported_before_reading() -> None:
    client, proc = make_client(lines=[response(1, {})], timeout=0.0)

    with pytest.raises(MCPError, match="timed out"):
        run(client._request("tools/list", {}))

    assert proc.stdin.written  # the request was still sent


def test_a_tool_call_surfaces_a_hang_as_an_error_result() -> None:
    from openlaoke.core.mcp_client import MCPToolSpec
    from openlaoke.core.mcp_runtime import MCPTool
    from openlaoke.core.tool import ToolContext

    client, _proc = make_client(lines=[HANG], timeout=0.01)
    tool = MCPTool(client, MCPToolSpec(name="slow", description="", input_schema={}))

    result = run(
        tool.call(ToolContext(tool_use_id="t1", app_state=SimpleNamespace(get_cwd=lambda: ".")))
    )

    assert result.is_error is True
    assert "timed out" in result.content


def test_a_closed_connection_is_reported() -> None:
    client, _proc = make_client(lines=[], timeout=5.0)

    with pytest.raises(MCPError, match="connection closed"):
        run(client._request("tools/list", {}))


def test_non_json_noise_is_ignored() -> None:
    client, _proc = make_client(lines=["starting up...\n", response(1, {"ok": True})])

    assert run(client._request("tools/list", {})) == {"ok": True}


def test_a_stale_response_is_ignored() -> None:
    client, _proc = make_client(lines=[response(99, {"stale": True}), response(1, {"fresh": True})])

    assert run(client._request("tools/list", {})) == {"fresh": True}


def test_an_error_response_becomes_an_mcp_error() -> None:
    error = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "no"}})
    client, _proc = make_client(lines=[error + "\n"])

    with pytest.raises(MCPError, match=r"no \(code -32601\)"):
        run(client._request("tools/call", {}))


def test_an_error_response_without_fields_still_reports() -> None:
    client, _proc = make_client(lines=[json.dumps({"id": 1, "error": None}) + "\n"])

    with pytest.raises(MCPError, match=r"error \(code \?\)"):
        run(client._request("tools/call", {}))


def test_an_oversized_message_is_refused() -> None:
    huge = b"x" * (MAX_MESSAGE_BYTES + 10)
    client, _proc = make_client(lines=[huge])

    with pytest.raises(MCPError, match="larger than"):
        run(client._read_line())


def test_an_incomplete_read_is_treated_as_closed() -> None:
    client, _proc = make_client(lines=[asyncio.IncompleteReadError(b"partial", 10)])

    assert run(client._read_line()) is None


def test_reading_without_a_process_returns_none() -> None:
    client = MCPStdioClient(MCPServerConfig(name="fake", command="x"))

    assert run(client._read_line()) is None


# --------------------------------------------------------------------------- #
# Payload shapes
# --------------------------------------------------------------------------- #


def test_tool_specs_skip_malformed_entries_and_accept_both_schema_keys() -> None:
    payload = {
        "tools": [
            {"name": "good", "description": "d", "inputSchema": {"type": "object"}},
            {"name": "snake", "input_schema": {"type": "object", "properties": {}}},
            {"description": "no name"},
            "not a dict",
            {"name": "weird", "inputSchema": "not a dict"},
        ]
    }
    client, _proc = make_client(lines=[response(1, payload)])

    specs = run(client.list_tools())

    assert [spec.name for spec in specs] == ["good", "snake", "weird"]
    assert specs[0].input_schema == {"type": "object"}
    assert specs[1].input_schema["properties"] == {}
    assert specs[2].input_schema == {}
    assert specs[0].description == "d"


def test_a_non_dict_tools_result_yields_no_specs() -> None:
    client, _proc = make_client(lines=[response(1, ["nope"])])

    assert run(client.list_tools()) == []


def test_tool_output_joins_text_blocks() -> None:
    payload = {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
    client, _proc = make_client(lines=[response(1, payload)])

    assert run(client.call_tool("t", {})) == ("a\nb", False)


def test_resource_text_is_included() -> None:
    payload = {"content": [{"type": "resource", "resource": {"text": "from a file"}}]}
    client, _proc = make_client(lines=[response(1, payload)])

    assert run(client.call_tool("t", {})) == ("from a file", False)


def test_empty_content_falls_back_to_the_raw_payload() -> None:
    payload = {"content": [], "isError": True}
    client, _proc = make_client(lines=[response(1, payload)])

    text, is_error = run(client.call_tool("t", {}))

    assert json.loads(text)["isError"] is True
    assert is_error is True


def test_a_non_dict_call_result_is_returned_as_text() -> None:
    client, _proc = make_client(lines=[response(1, "plain string")])

    assert run(client.call_tool("t", {})) == ("plain string", False)


# --------------------------------------------------------------------------- #
# Shutdown
# --------------------------------------------------------------------------- #


def test_stop_is_a_no_op_without_a_process() -> None:
    client = MCPStdioClient(MCPServerConfig(name="fake", command="x"))

    run(client.stop())

    assert client.proc is None


def test_stop_closes_stdin_and_terminates() -> None:
    client, proc = make_client()

    run(client.stop())

    assert proc.stdin.closed is True
    assert proc.terminated is True
    assert client.proc is None


def test_stop_leaves_a_finished_process_alone() -> None:
    client, proc = make_client()
    proc.returncode = 0

    run(client.stop())

    assert proc.terminated is False
    assert proc.stdin.closed is True


def test_stop_kills_a_process_that_ignores_terminate(monkeypatch) -> None:
    client, proc = make_client()
    proc._hang = True

    client.config.timeout = 0.01
    original = proc.terminate

    def terminate_and_hang() -> None:
        original()
        proc.returncode = None  # pretend it did not exit

    proc.terminate = terminate_and_hang  # type: ignore[method-assign]

    async def fast_wait_for(coro, timeout):
        coro.close()
        raise TimeoutError

    monkeypatch.setattr("openlaoke.core.mcp_client.asyncio.wait_for", fast_wait_for)

    run(client.stop())

    assert proc.killed is True


def test_start_without_a_command_is_refused() -> None:
    client = MCPStdioClient(MCPServerConfig(name="fake", command=""))

    with pytest.raises(MCPError, match="has no command"):
        run(client.start())


def test_server_config_from_dict_fills_defaults() -> None:
    config = MCPServerConfig.from_dict(
        "docs",
        {"command": "  npx  ", "args": ["-y", 3], "env": {"TOKEN": 7}, "cwd": "/tmp", "timeout": 5},
    )

    assert config.name == "docs"
    assert config.command == "npx"
    assert config.args == ["-y", "3"]
    assert config.env == {"TOKEN": "7"}
    assert config.cwd == "/tmp"
    assert config.timeout == 5.0


def test_server_config_from_dict_uses_the_default_timeout() -> None:
    config = MCPServerConfig.from_dict("x", {})

    assert config.command == ""
    assert config.timeout == 20.0
