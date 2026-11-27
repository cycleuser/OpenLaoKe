"""Tests for the hash-chained audit log and its out-of-band anchor."""

from __future__ import annotations

import json
import os
import stat

import pytest

from openlaoke.core.audit import (
    GENESIS_HASH,
    AuditCorruptionError,
    AuditLog,
    summarize_args,
)


def _log(tmp_path) -> AuditLog:
    return AuditLog(str(tmp_path / "audit"))


def test_entries_link_into_a_chain_and_verify(tmp_path):
    log = _log(tmp_path)

    first = log.append("tool.request", {"tool": "Bash", "args": {"command": "ls"}})
    second = log.append("tool.result", {"tool": "Bash", "bytes": 4})

    assert first.index == 1
    assert first.prev_hash == GENESIS_HASH
    assert second.index == 2
    assert second.prev_hash == first.hash
    assert second.hash != first.hash
    assert log.verify() is True
    assert [e.index for e in log.read()] == [1, 2]


def test_the_log_is_written_as_json_lines_with_owner_only_permissions(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Read"})

    lines = log.path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["action"] == "tool.request"
    assert stat.S_IMODE(os.stat(log.path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(log.head_path).st_mode) == 0o600


def test_editing_an_entry_is_detected(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash", "args": {"command": "ls"}})
    log.append("tool.result", {"tool": "Bash", "bytes": 4})

    rows = log.path.read_text().splitlines()
    tampered = json.loads(rows[0])
    tampered["data"]["args"]["command"] = "rm -rf /"
    log.path.write_text("\n".join([json.dumps(tampered), rows[1]]) + "\n")

    assert log.verify() is False
    with pytest.raises(AuditCorruptionError):
        log.append("tool.request", {"tool": "Read"})


def test_deleting_a_later_entry_is_detected(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash"})
    log.append("tool.result", {"tool": "Bash", "bytes": 4})

    rows = log.path.read_text().splitlines()
    log.path.write_text(rows[0] + "\n")

    # A prefix of a valid chain is itself a valid chain, so only the anchor
    # can notice this. Without it the deletion is silent.
    assert log.verify() is False


def test_deleting_the_whole_log_is_detected(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash"})
    log.path.unlink()

    assert log.verify() is False
    with pytest.raises(AuditCorruptionError):
        log.append("tool.request", {"tool": "Read"})


def test_a_missing_anchor_on_a_legacy_log_is_tolerated_once(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash"})
    log.head_path.unlink()

    # Readable, and the next append re-anchors the existing chain.
    assert log.verify() is True
    entry = log.append("tool.result", {"tool": "Bash", "bytes": 0})
    assert entry.index == 2
    assert log.head() == (2, entry.hash)


def test_an_unparseable_line_is_corruption_not_an_empty_log(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash"})
    log.path.write_text("not json\n")

    with pytest.raises(AuditCorruptionError):
        log.read()
    assert log.verify() is False


def test_a_symlinked_log_is_refused(tmp_path):
    log = _log(tmp_path)
    log.directory.mkdir(parents=True)
    target = tmp_path / "elsewhere.jsonl"
    target.write_text("")
    log.path.symlink_to(target)

    with pytest.raises(AuditCorruptionError):
        log.append("tool.request", {"tool": "Bash"})
    assert target.read_text() == ""


def test_append_reuses_the_cached_tip_only_while_the_file_is_untouched(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash"})
    assert log.append("tool.result", {"tool": "Bash"}).index == 2

    # An external append must be picked up rather than overwritten in place.
    other = AuditLog(str(tmp_path / "audit"))
    third = other.append("tool.request", {"tool": "Read"})
    assert third.index == 3
    assert log.append("tool.result", {"tool": "Read"}).index == 4
    assert log.verify() is True


def test_summarize_args_redacts_secrets_and_caps_long_values():
    summary = summarize_args(
        {
            "command": "curl -H 'x' https://example.test",
            "api_key": "sk-live-123",
            "GitHub_Token": "ghp_123",
            "body": "z" * 1000,
            "count": 3,
            "flag": True,
            "nested": {"a": 1},
        }
    )

    assert summary["command"] == "curl -H 'x' https://example.test"
    assert summary["api_key"] == "[redacted]"
    assert summary["GitHub_Token"] == "[redacted]"
    assert summary["body"].endswith("(1000 chars)")
    assert len(summary["body"]) < 500
    assert summary["count"] == 3
    assert summary["flag"] is True
    assert summary["nested"] == "<dict>"


def test_summarize_args_tolerates_non_dict_input():
    assert summarize_args(None) == {}
    assert summarize_args("nope") == {}


def test_recording_swallows_storage_failures(monkeypatch, tmp_path, caplog):
    from openlaoke.core import audit
    from openlaoke.core.state import AppState

    state = AppState(session_id="s", cwd=str(tmp_path))
    monkeypatch.setenv("OPENLAOKE_AUDIT_DIR", str(tmp_path / "audit"))

    def boom(self, action, data=None):
        raise AuditCorruptionError("chain is broken")

    monkeypatch.setattr(AuditLog, "append", boom)
    audit.record(state, "tool.request", tool="Bash")

    # A broken audit log must not take down a turn that ran fine.
    assert "Could not append to the audit log" in caplog.text


def test_the_audit_log_can_be_disabled(monkeypatch, tmp_path):
    from openlaoke.core import audit
    from openlaoke.core.state import AppState

    monkeypatch.setenv("OPENLAOKE_NO_AUDIT", "1")
    state = AppState(session_id="s", cwd=str(tmp_path))

    assert audit.get_audit(state) is None
    audit.record(state, "tool.request", tool="Bash")
    assert not (tmp_path / "audit").exists()


def test_status_text_reports_count_and_verification(tmp_path):
    log = _log(tmp_path)
    assert "empty" in log.status_text()

    log.append("tool.request", {"tool": "Bash", "args": {"command": "ls -la"}})
    text = log.status_text()

    assert "1 entries" in text
    assert "verified" in text
    assert "Bash" in text
    assert "ls -la" in text


def test_status_text_reports_a_corrupt_chain(tmp_path):
    log = _log(tmp_path)
    log.append("tool.request", {"tool": "Bash"})
    log.head_path.write_text('{"count": 9, "head": "' + "a" * 64 + '"}\n')

    assert "CORRUPT" in log.status_text()


def test_the_audit_command_shows_the_chain_and_reports_success(tmp_path, monkeypatch):
    import asyncio

    from openlaoke.commands.base import AuditCommand
    from openlaoke.core import audit
    from openlaoke.core.state import AppState

    monkeypatch.setenv("OPENLAOKE_AUDIT_DIR", str(tmp_path / "audit"))
    state = AppState(session_id="s", cwd=str(tmp_path))
    audit.record_tool_request(state, "Bash", {"command": "ls -la"}, "c1")
    audit.record_tool_result(
        state, "Bash", type("R", (), {"content": "ok", "is_error": False})(), "c1"
    )

    class Ctx:
        app_state = state
        args = "5"

    result = asyncio.run(AuditCommand().execute(Ctx()))

    assert result.success is True
    assert "2 entries" in result.message
    assert "tool.request" in result.message
    assert "ls -la" in result.message


def test_the_audit_command_rejects_a_bad_count_and_reports_corruption(tmp_path, monkeypatch):
    import asyncio

    from openlaoke.commands.base import AuditCommand
    from openlaoke.core import audit
    from openlaoke.core.state import AppState

    monkeypatch.setenv("OPENLAOKE_AUDIT_DIR", str(tmp_path / "audit"))
    state = AppState(session_id="s", cwd=str(tmp_path))
    audit.record(state, "tool.request", tool="Bash")

    class Ctx:
        app_state = state
        args = "nope"

    bad = asyncio.run(AuditCommand().execute(Ctx()))
    assert bad.success is False
    assert "Usage" in bad.message

    log = audit.get_audit(state)
    log.head_path.unlink()
    log.path.write_text("garbage\n")
    Ctx.args = ""
    corrupt = asyncio.run(AuditCommand().execute(Ctx()))
    assert corrupt.success is False


def test_the_audit_command_reports_when_logging_is_disabled(tmp_path, monkeypatch):
    import asyncio

    from openlaoke.commands.base import AuditCommand
    from openlaoke.core.state import AppState

    monkeypatch.setenv("OPENLAOKE_NO_AUDIT", "1")

    class Ctx:
        app_state = AppState(session_id="s", cwd=str(tmp_path))
        args = ""

    result = asyncio.run(AuditCommand().execute(Ctx()))

    assert result.success is False
    assert "disabled" in result.message


def test_execute_tool_records_request_and_result(tmp_path, monkeypatch):
    import asyncio

    from openlaoke.core import audit
    from openlaoke.core.engine import execute_tool
    from openlaoke.core.state import AppState
    from openlaoke.core.tool import Tool, ToolRegistry
    from openlaoke.types.core_types import ToolResultBlock, ToolUseBlock

    class Echo(Tool):
        name = "Echo"
        description = "echo"
        input_schema = {"type": "object", "properties": {"command": {"type": "string"}}}
        is_read_only = True

        async def call(self, ctx, **kwargs):
            return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="hi", is_error=False)

    monkeypatch.setenv("OPENLAOKE_AUDIT_DIR", str(tmp_path / "audit"))
    state = AppState(session_id="s", cwd=str(tmp_path))
    registry = ToolRegistry()
    registry.register(Echo())
    registry.freeze()

    asyncio.run(
        execute_tool(
            state,
            registry,
            ToolUseBlock(id="t1", name="Echo", input={"command": "ls"}),
        )
    )

    entries = audit.get_audit(state).read()
    assert [entry.action for entry in entries] == ["tool.request", "tool.result"]
    assert entries[0].data["args"] == {"command": "ls"}
    assert entries[1].data["bytes"] == 2
    assert entries[1].data["is_error"] is False


def test_a_policy_refusal_is_recorded_with_a_reason(tmp_path, monkeypatch):
    import asyncio

    from openlaoke.core import audit
    from openlaoke.core.engine import EnginePolicy, execute_tool
    from openlaoke.core.state import AppState
    from openlaoke.core.tool import Tool, ToolRegistry
    from openlaoke.types.core_types import ToolResultBlock, ToolUseBlock

    class Echo(Tool):
        name = "Echo"
        description = "echo"
        input_schema = {"type": "object", "properties": {}}

        async def call(self, ctx, **kwargs):  # pragma: no cover - never reached
            return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="", is_error=False)

    monkeypatch.setenv("OPENLAOKE_AUDIT_DIR", str(tmp_path / "audit"))
    state = AppState(session_id="s", cwd=str(tmp_path))
    registry = ToolRegistry()
    registry.register(Echo())
    registry.freeze()

    asyncio.run(
        execute_tool(
            state,
            registry,
            ToolUseBlock(id="t1", name="Echo", input={}),
            EnginePolicy(check_tool=lambda name, args: False),
        )
    )

    entries = audit.get_audit(state).read()
    assert [entry.action for entry in entries] == ["tool.denied"]
    assert entries[0].data["reason"] == "policy"
