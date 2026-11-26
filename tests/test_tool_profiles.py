"""Tests for the tool profiles: which tools a host gets, and why.

The profiles are what the model is offered. Two things matter: the shell tools
must match the host (no PowerShell on a Mac without pwsh), and the headless
profile must keep its tool block small without losing the coding essentials.
"""

from __future__ import annotations

import pytest

from openlaoke.core.tool import ToolRegistry
from openlaoke.tools import register as register_module
from openlaoke.tools.register import (
    _has_bash,
    _has_powershell,
    register_all_tools,
    register_core_tools,
)

CORE = {
    "Read",
    "Write",
    "Edit",
    "Grep",
    "Glob",
    "ListDirectory",
    "ApplyPatch",
    "InvokeSkill",
}


@pytest.fixture()
def registry() -> ToolRegistry:
    return ToolRegistry()


def names(registry: ToolRegistry) -> set[str]:
    return {tool.name for tool in registry.get_all()}


# --------------------------------------------------------------------------- #
# Host detection
# --------------------------------------------------------------------------- #


def test_bash_is_always_available_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(register_module.platform, "system", lambda: "Darwin")
    assert _has_bash() is True


def test_bash_on_windows_needs_an_executable(monkeypatch) -> None:
    monkeypatch.setattr(register_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(register_module.shutil, "which", lambda name: None)
    assert _has_bash() is False

    monkeypatch.setattr(
        register_module.shutil, "which", lambda name: "/usr/bin/bash" if name == "bash" else None
    )
    assert _has_bash() is True


def test_powershell_is_always_available_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(register_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(register_module.shutil, "which", lambda name: None)
    assert _has_powershell() is True


def test_powershell_off_windows_needs_pwsh(monkeypatch) -> None:
    monkeypatch.setattr(register_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(register_module.shutil, "which", lambda name: None)
    assert _has_powershell() is False

    monkeypatch.setattr(
        register_module.shutil, "which", lambda name: "/opt/pwsh" if name == "pwsh" else None
    )
    assert _has_powershell() is True


# --------------------------------------------------------------------------- #
# Full profile
# --------------------------------------------------------------------------- #


def test_full_registration_includes_the_coding_tools(registry, monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)
    register_all_tools(registry)

    assert CORE <= names(registry)
    assert "Bash" in names(registry)
    assert "PowerShell" not in names(registry)


def test_full_registration_adds_powershell_when_it_exists(registry, monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: True)
    register_all_tools(registry)

    assert "PowerShell" in names(registry)


def test_full_registration_leaves_batch_and_browser_off_by_default(
    registry, monkeypatch
) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)

    class Config:
        enable_batch = False
        enable_browser = False

    monkeypatch.setattr("openlaoke.utils.config.load_config", lambda: Config())
    register_all_tools(registry)

    assert "Batch" not in names(registry)
    assert "Browser" not in names(registry)


def test_batch_is_registered_when_the_config_enables_it(registry, monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)

    class Config:
        enable_batch = True
        enable_browser = False

    monkeypatch.setattr("openlaoke.utils.config.load_config", lambda: Config())
    register_all_tools(registry)

    assert "Batch" in names(registry)


def test_browser_is_registered_only_when_selenium_is_installed(registry, monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)

    class Config:
        enable_batch = False
        enable_browser = True

    monkeypatch.setattr("openlaoke.utils.config.load_config", lambda: Config())
    monkeypatch.setattr("openlaoke.tools.browser_tool.selenium_available", lambda: False)
    register_all_tools(registry)
    assert "Browser" not in names(registry)

    monkeypatch.setattr("openlaoke.tools.browser_tool.selenium_available", lambda: True)
    fresh = ToolRegistry()
    register_all_tools(fresh)
    assert "Browser" in names(fresh)


def test_a_broken_config_still_registers_the_essential_tools(registry, monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)

    def boom():
        raise RuntimeError("config is corrupt")

    monkeypatch.setattr("openlaoke.utils.config.load_config", boom)
    register_all_tools(registry)

    assert CORE <= names(registry)
    assert "Batch" not in names(registry)


# --------------------------------------------------------------------------- #
# Core (headless) profile
# --------------------------------------------------------------------------- #


def test_core_profile_keeps_the_coding_tools_and_drops_the_rest(monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)
    registry = ToolRegistry()
    register_core_tools(registry)

    registered = names(registry)
    assert CORE <= registered
    assert "Bash" in registered
    for heavy in ("Panel", "Swarm", "Schedule", "Memory", "WebSearch", "Open", "Todo"):
        assert heavy not in registered


def test_core_profile_is_much_smaller_than_the_full_one(monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)

    class Config:
        enable_batch = False
        enable_browser = False

    monkeypatch.setattr("openlaoke.utils.config.load_config", lambda: Config())
    full = ToolRegistry()
    register_all_tools(full)
    core = ToolRegistry()
    register_core_tools(core)

    assert len(names(core)) < len(names(full))
    assert names(core) <= names(full)


def test_core_profile_schema_block_is_smaller_than_the_full_one(monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)

    class Config:
        enable_batch = False
        enable_browser = False

    monkeypatch.setattr("openlaoke.utils.config.load_config", lambda: Config())
    full = ToolRegistry()
    register_all_tools(full)
    core = ToolRegistry()
    register_core_tools(core)

    def prompt_bytes(registry: ToolRegistry) -> int:
        import json

        return len(json.dumps(registry.get_all_for_prompt()))

    # The whole point of the core profile: fewer prompt tokens per step.
    assert prompt_bytes(core) < prompt_bytes(full)


def test_core_profile_adds_powershell_when_it_exists(monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: True)
    registry = ToolRegistry()
    register_core_tools(registry)

    assert "PowerShell" in names(registry)


def test_registering_twice_is_idempotent(registry, monkeypatch) -> None:
    monkeypatch.setattr(register_module, "_has_powershell", lambda: False)
    register_all_tools(registry)
    first = names(registry)
    register_all_tools(registry)
    assert names(registry) == first
