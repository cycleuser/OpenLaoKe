"""Tests for switchable harness modes (pi / jcode / opencode / balanced)."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openlaoke.core.harness_modes import (
    DEFAULT_MODE,
    engine_kwargs,
    get_mode,
    is_valid_mode,
    list_modes,
    mode_directives,
    normalize_mode,
)


def test_mode_catalog_is_complete() -> None:
    keys = {mode.key for mode in list_modes()}
    assert keys == {"balanced", "pi", "jcode", "opencode", "deep"}
    assert DEFAULT_MODE == "balanced"


def test_aliases_and_unknown_names() -> None:
    assert normalize_mode("fast") == "pi"
    assert normalize_mode("thorough") == "opencode"
    assert normalize_mode("robust") == "jcode"
    assert normalize_mode("max") == "deep"
    assert normalize_mode("high") == "deep"
    assert normalize_mode("default") == "balanced"
    assert normalize_mode("nonsense") == "balanced"
    assert normalize_mode(None) == "balanced"
    assert is_valid_mode("minimal")
    assert not is_valid_mode("nonsense")


def test_modes_are_meaningfully_different() -> None:
    pi = get_mode("pi")
    jcode = get_mode("jcode")
    opencode = get_mode("opencode")
    deep = get_mode("deep")
    balanced = get_mode("balanced")

    assert pi.max_steps < jcode.max_steps < balanced.max_steps < opencode.max_steps
    assert opencode.max_steps < deep.max_steps
    assert pi.reasoning_effort == "low"
    assert jcode.reasoning_effort == "low"
    assert opencode.reasoning_effort == "medium"
    assert deep.reasoning_effort == "high"
    assert pi.tools == "core"
    assert opencode.tools == "all"
    assert opencode.plan_first and not pi.plan_first
    assert deep.plan_first
    assert pi.verify == "light" and opencode.verify == "strict"


def test_engine_kwargs_follow_mode() -> None:
    pi = engine_kwargs(get_mode("pi"))
    jcode = engine_kwargs(get_mode("jcode"))
    assert pi["max_iterations"] == 25
    assert pi["max_repeat_calls"] == 2
    assert jcode["max_iterations"] == 35
    assert jcode["repair_tool_calls"] is True


def test_directives_name_the_mode_and_its_rules() -> None:
    pi_text = mode_directives("pi")
    opencode_text = mode_directives("opencode")
    assert "Harness mode: pi" in pi_text
    assert "Move fast" in pi_text
    assert "Harness mode: opencode" in opencode_text
    assert "AGENTS.md" in opencode_text
    assert pi_text != opencode_text


def test_cache_guard_injects_mode_directives() -> None:
    from openlaoke.core.cache_guard import CacheGuard

    state = SimpleNamespace(harness_mode="opencode")
    guard = CacheGuard(state)
    prompt = guard.system_prompt
    assert "Harness mode: opencode" in prompt
    assert "Harness mode: opencode" in guard.build()


def test_headless_prompt_injects_mode_directives() -> None:
    from openlaoke.core.system_prompt import build_system_prompt

    state = SimpleNamespace(
        harness_mode="pi",
        get_cwd=lambda: "/tmp",
        session_config=SimpleNamespace(system_prompt_suffix=""),
    )
    prompt = build_system_prompt(state, [])
    assert "Harness mode: pi" in prompt


@pytest.mark.asyncio
async def test_mode_command_switches_and_invalidates() -> None:
    from openlaoke.commands.base import CommandContext, ModeCommand

    class _Guard:
        def __init__(self) -> None:
            self.invalidated = False

        def invalidate(self) -> None:
            self.invalidated = True

    guard = _Guard()
    app_state = SimpleNamespace(
        harness_mode="balanced",
        max_steps=50,
        session_config=SimpleNamespace(reasoning_effort="low"),
        _cache_guard=guard,
    )
    config = SimpleNamespace(mode="balanced", reasoning_effort="low")

    with (
        patch("openlaoke.utils.config.load_config", return_value=config),
        patch("openlaoke.utils.config.save_config") as save,
    ):
        result = await ModeCommand().execute(CommandContext(app_state=app_state, args="thorough"))

    assert result.success
    assert "opencode" in result.message
    assert config.mode == "opencode"
    assert config.reasoning_effort == "medium"
    assert app_state.harness_mode == "opencode"
    assert app_state.max_steps == 60
    assert app_state.session_config.reasoning_effort == "medium"
    assert guard.invalidated
    save.assert_called_once()


@pytest.mark.asyncio
async def test_mode_command_rejects_unknown() -> None:
    from openlaoke.commands.base import CommandContext, ModeCommand

    app_state = SimpleNamespace(
        harness_mode="balanced",
        max_steps=50,
        session_config=SimpleNamespace(reasoning_effort="low"),
    )
    config = SimpleNamespace(mode="balanced", reasoning_effort="low")
    with (
        patch("openlaoke.utils.config.load_config", return_value=config),
        patch("openlaoke.utils.config.save_config"),
    ):
        result = await ModeCommand().execute(CommandContext(app_state=app_state, args="turbo"))
    assert not result.success
    assert "Unknown mode" in result.message
    assert app_state.harness_mode == "balanced"


@pytest.mark.asyncio
async def test_mode_command_lists_all_modes() -> None:
    from openlaoke.commands.base import CommandContext, ModeCommand

    app_state = SimpleNamespace(harness_mode="jcode")
    config = SimpleNamespace(mode="jcode", reasoning_effort="low")
    with patch("openlaoke.utils.config.load_config", return_value=config):
        result = await ModeCommand().execute(CommandContext(app_state=app_state, args=""))
    for key in ("balanced", "pi", "jcode", "opencode", "deep"):
        assert key in result.message


def test_mode_command_is_registered() -> None:
    from openlaoke.commands.registry import get_all_commands, get_command, register_all

    register_all()
    assert get_command("mode") is not None
    assert get_command("harness") is get_command("mode")
    assert any(cmd.name == "mode" for cmd in get_all_commands())
    assert inspect.iscoroutinefunction(get_command("mode").execute)


def test_cli_keeps_mode_value_out_of_the_prompt() -> None:
    from openlaoke.entrypoints.cli import split_argv

    flags, prompt = split_argv(["-c", "/tmp", "--mode", "pi", "--max-steps", "12", "write", "it"])

    assert flags == ["-c", "/tmp", "--mode", "pi", "--max-steps", "12"]
    assert prompt == ["write", "it"]


def test_non_interactive_honours_cli_max_steps() -> None:
    from openlaoke.entrypoints.cli import engine_kwargs_for

    mode = get_mode("balanced")
    assert engine_kwargs_for(SimpleNamespace(max_steps=12), mode)["max_iterations"] == 12
    assert (
        engine_kwargs_for(SimpleNamespace(max_steps=None), mode)["max_iterations"] == mode.max_steps
    )
    assert engine_kwargs_for(SimpleNamespace(max_steps=0), mode)["max_iterations"] == mode.max_steps
