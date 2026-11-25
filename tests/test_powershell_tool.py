"""Tests for the PowerShell tool: command construction, output shaping and
every error branch. subprocess is monkeypatched; nothing is executed.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from openlaoke.tools import powershell_tool as mod
from openlaoke.tools.powershell_tool import PowerShellTool

from .conftest import ctx_for_dir


@pytest.fixture()
def tool() -> PowerShellTool:
    return PowerShellTool()


@pytest.fixture()
def ctx(tmp_path):
    return ctx_for_dir(str(tmp_path))


def fake_run(returncode=0, stdout="", stderr=""):
    calls: list[dict] = []

    def _run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


@pytest.mark.asyncio
async def test_empty_command_is_rejected_without_spawning(tool, ctx, monkeypatch) -> None:
    run = fake_run()
    monkeypatch.setattr(mod.subprocess, "run", run)
    result = await tool.call(ctx, command="   ")
    assert result.is_error is True
    assert "Empty command" in result.content
    assert run.calls == []


@pytest.mark.asyncio
async def test_success_returns_stdout(tool, ctx, monkeypatch) -> None:
    run = fake_run(stdout="hello\n")
    monkeypatch.setattr(mod.subprocess, "run", run)
    result = await tool.call(ctx, command="Write-Output hello")
    assert result.is_error is False
    assert result.content == "hello\n"
    # asyncio.to_thread forwards the argv list as the single positional arg.
    argv = run.calls[0]["args"][0]
    assert "-Command" in argv
    assert "Write-Output hello" in argv
    assert run.calls[0]["kwargs"]["cwd"] == ctx.app_state.get_cwd()


@pytest.mark.asyncio
async def test_silent_success_has_explanatory_content(tool, ctx, monkeypatch) -> None:
    monkeypatch.setattr(mod.subprocess, "run", fake_run(stdout="", stderr=""))
    result = await tool.call(ctx, command="New-Item -ItemType Directory foo")
    assert result.is_error is False
    assert result.content == "(command completed successfully with no output)"


@pytest.mark.asyncio
async def test_stderr_is_appended_even_on_success(tool, ctx, monkeypatch) -> None:
    monkeypatch.setattr(mod.subprocess, "run", fake_run(stdout="out", stderr="warn"))
    result = await tool.call(ctx, command="cmd")
    assert "out" in result.content
    assert "Stderr:\nwarn" in result.content


@pytest.mark.asyncio
async def test_nonzero_exit_is_an_error_with_code_and_output(tool, ctx, monkeypatch) -> None:
    monkeypatch.setattr(mod.subprocess, "run", fake_run(returncode=2, stdout="partial", stderr="boom"))
    result = await tool.call(ctx, command="bad")
    assert result.is_error is True
    assert "exited with code 2" in result.content
    assert "partial" in result.content
    assert "boom" in result.content


@pytest.mark.asyncio
async def test_missing_pwsh_on_unix_explains_install(tool, ctx, monkeypatch) -> None:
    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(mod.subprocess, "run", raise_not_found)
    monkeypatch.setattr(mod.platform, "system", lambda: "Darwin")
    result = await tool.call(ctx, command="Get-Date")
    assert result.is_error is True
    assert "pwsh" in result.content
    assert "brew install powershell" in result.content


@pytest.mark.asyncio
async def test_missing_powershell_on_windows_uses_windows_wording(tool, ctx, monkeypatch) -> None:
    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(mod.subprocess, "run", raise_not_found)
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    result = await tool.call(ctx, command="Get-Date")
    assert result.is_error is True
    assert result.content == "Error: PowerShell not found"


@pytest.mark.asyncio
async def test_timeout_reports_the_limit_used(tool, ctx, monkeypatch) -> None:
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pwsh", timeout=kwargs.get("timeout"))

    monkeypatch.setattr(mod.subprocess, "run", raise_timeout)
    result = await tool.call(ctx, command="Start-Sleep 100", timeout=7.5)
    assert result.is_error is True
    assert "timed out after 7.5 seconds" in result.content


@pytest.mark.asyncio
async def test_default_timeout_is_sixty_seconds(tool, ctx, monkeypatch) -> None:
    run = fake_run(stdout="ok")
    monkeypatch.setattr(mod.subprocess, "run", run)
    await tool.call(ctx, command="cmd")
    assert run.calls[0]["kwargs"]["timeout"] == 60.0


@pytest.mark.asyncio
async def test_unexpected_exception_is_wrapped(tool, ctx, monkeypatch) -> None:
    def raise_weird(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(mod.subprocess, "run", raise_weird)
    result = await tool.call(ctx, command="cmd")
    assert result.is_error is True
    assert "Error executing PowerShell command: kaboom" in result.content


@pytest.mark.parametrize(
    "system,expected",
    [("Windows", "powershell"), ("Darwin", "pwsh"), ("Linux", "pwsh")],
)
def test_executable_selection(tool, monkeypatch, system: str, expected: str) -> None:
    monkeypatch.setattr(mod.platform, "system", lambda: system)
    assert tool._get_powershell_cmd() == expected


def test_register_adds_tool() -> None:
    from openlaoke.core.tool import ToolRegistry

    registry = ToolRegistry()
    mod.register(registry)
    registered = registry.get("PowerShell")
    assert registered is not None
    assert isinstance(registered, PowerShellTool)


def test_tool_flags_declare_destructive_policy(tool) -> None:
    assert tool.is_read_only is False
    assert tool.is_destructive is True
    assert tool.requires_approval is True
    assert tool.is_concurrency_safe is False
