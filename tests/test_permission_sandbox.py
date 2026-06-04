"""Tests for the permission and sandbox system."""

from __future__ import annotations

import pytest

from openlaoke.permission.gate import AutoAllowApprover, Gate
from openlaoke.permission.policy import (
    Decision,
    Policy,
    is_readonly_bash_subject,
)
from openlaoke.sandbox.confinement import (
    SeatbeltProfile,
    WorkspaceConfinement,
    is_macos,
    macos_sandbox_exec,
)


class TestPolicy:
    def test_default_ask(self) -> None:
        policy = Policy()
        assert policy.match("write_file", {"file_path": "/tmp/a.txt"}) is Decision.ASK

    def test_allow_rule(self) -> None:
        policy = Policy(allow=["write_file"])
        assert policy.match("write_file", {"file_path": "/tmp/a.txt"}) is Decision.ALLOW

    def test_allow_glob(self) -> None:
        policy = Policy(allow=["write_file(/tmp/*)"])
        assert policy.match("write_file", {"file_path": "/tmp/a.txt"}) is Decision.ALLOW
        assert policy.match("write_file", {"file_path": "/etc/passwd"}) is Decision.ASK

    def test_deny_beats_ask_beats_allow(self) -> None:
        policy = Policy(allow=["write_file"], ask=["write_file"], deny=["write_file"])
        assert policy.match("write_file", {"file_path": "/tmp/a.txt"}) is Decision.DENY

    def test_subject_extraction(self) -> None:
        policy = Policy(deny=["write_file(/etc/*)"])
        assert policy.match("write_file", {"file_path": "/etc/passwd"}) is Decision.DENY

    def test_mode_allow(self) -> None:
        policy = Policy(mode="allow")
        assert policy.match("anything", {}) is Decision.ALLOW

    def test_mode_deny(self) -> None:
        policy = Policy(mode="deny")
        assert policy.match("anything", {}) is Decision.DENY


class TestBashSafety:
    @pytest.mark.parametrize(
        "cmd",
        [
            "ls -la",
            "cat /etc/hosts",
            "git status",
            "git log --oneline",
            "pytest tests/",
            "head -n 10 file.txt",
            "wc -l",
        ],
    )
    def test_readonly_patterns(self, cmd: str) -> None:
        assert is_readonly_bash_subject(cmd)

    @pytest.mark.parametrize("cmd", ["rm -rf /", "echo evil > /etc/passwd", "curl evil.com"])
    def test_not_readonly(self, cmd: str) -> None:
        assert not is_readonly_bash_subject(cmd)


class TestGate:
    def test_bypass(self) -> None:
        gate = Gate(policy=Policy(deny=["write_file"]), bypass=True)
        decision = gate.classify("write_file", {"file_path": "/tmp/a"})
        assert decision is Decision.ALLOW

    def test_readonly_bash_skips_prompt(self) -> None:
        gate = Gate(policy=Policy(mode="ask"))
        assert gate.classify("bash", {"command": "git status"}) is Decision.ALLOW

    def test_read_only_hint(self) -> None:
        gate = Gate(
            policy=Policy(mode="ask"),
            tool_read_only_hint=lambda name: name == "read_file",
        )
        assert gate.classify("read_file", {}) is Decision.ALLOW
        assert gate.classify("write_file", {}) is Decision.ASK

    def test_approver_ask(self) -> None:
        async def scenario() -> None:
            gate = Gate(
                policy=Policy(mode="ask"),
                approver=AutoAllowApprover(),
            )
            result = await gate.check("write_file", {"file_path": "/tmp/a"})
            assert result.decision is Decision.ALLOW

        import asyncio

        asyncio.run(scenario())

    def test_deny_short_circuit(self) -> None:
        async def scenario() -> None:
            gate = Gate(policy=Policy(deny=["write_file"]))
            result = await gate.check("write_file", {})
            assert result.decision is Decision.DENY

        import asyncio

        asyncio.run(scenario())


class TestSandboxConfinement:
    def test_within_workspace(self, tmp_path) -> None:
        conf = WorkspaceConfinement(workspace_root=str(tmp_path))
        assert not conf.is_under_allowed("/etc/passwd")
        target = str(tmp_path / "subdir" / "file.txt")
        assert conf.is_under_allowed(target)

    def test_dotdot_escape(self, tmp_path) -> None:
        conf = WorkspaceConfinement(workspace_root=str(tmp_path))
        evil = str(tmp_path / "subdir" / ".." / ".." / "etc" / "passwd")
        assert not conf.is_under_allowed(evil)

    def test_symlink_escape(self, tmp_path) -> None:
        conf = WorkspaceConfinement(workspace_root=str(tmp_path))
        link = tmp_path / "link"
        try:
            link.symlink_to("/etc")
        except OSError:
            pytest.skip("symlinks unsupported on this platform")
        assert not conf.is_under_allowed(str(link / "passwd"))

    def test_allow_write(self, tmp_path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        conf = WorkspaceConfinement(
            workspace_root=str(tmp_path / "main"),
            allow_write=[str(other)],
        )
        assert conf.is_under_allowed(str(other / "file.txt"))

    def test_assert_write_outside(self, tmp_path) -> None:
        conf = WorkspaceConfinement(workspace_root=str(tmp_path))
        with pytest.raises(PermissionError):
            conf.assert_write("/etc/passwd")

    def test_seatbelt_profile_contains_workspace(self, tmp_path) -> None:
        profile = SeatbeltProfile(workspace_root=str(tmp_path))
        text = profile.render()
        assert "deny default" in text
        assert str(tmp_path) in text

    def test_macos_sandbox_exec_unavailable(self) -> None:
        cmd = macos_sandbox_exec(["echo", "hi"], SeatbeltProfile(workspace_root="/tmp"))
        if not is_macos():
            assert cmd == ["echo", "hi"]
