"""Tests for the CLI entry point: argument splitting, overrides and the three run modes.

``main()`` is driven by setting ``sys.argv`` and replacing the pieces that would
open a terminal, a network client or the config wizard. The run modes themselves
get their collaborators replaced the same way.
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

import pytest

import openlaoke.entrypoints.cli as cli
from openlaoke.types.providers import ProviderConfig, ProviderType
from openlaoke.utils.config import AppConfig


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".openlaoke").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    # A developer machine may export a real key; the wizard's own env detection
    # would then quietly reconfigure the config these tests build by hand.
    from openlaoke.core.provider_presets import PRESETS

    for preset in PRESETS:
        if preset.env_var:
            monkeypatch.delenv(preset.env_var, raising=False)
    yield home


@pytest.fixture()
def launched(monkeypatch):
    """Record which run mode main() picked instead of starting one."""
    calls: dict[str, Any] = {}

    async def interactive(app_state, config):
        calls["mode"] = "interactive"
        calls["app_state"] = app_state
        calls["config"] = config

    async def headless(prompt, app_state, config):
        calls["mode"] = "headless"
        calls["prompt"] = prompt
        calls["app_state"] = app_state

    async def bot(prompt, app_state, config, bot, room):
        calls["mode"] = "bot"
        calls["prompt"] = prompt
        calls["bot"] = bot
        calls["room"] = room

    monkeypatch.setattr(cli, "_run_interactive", interactive)
    monkeypatch.setattr(cli, "_run_non_interactive", headless)
    monkeypatch.setattr(cli, "_run_bot_prompt", bot)
    return calls


def ready_config() -> AppConfig:
    """A config that passes the first-run check, so the wizard is skipped."""
    config = AppConfig()
    config.first_run = False
    config.providers.active_provider = "openai"
    config.providers.active_model = "gpt-4o"
    config.providers.providers["openai"].api_key = "sk-x"
    return config


def bare_config() -> AppConfig:
    """A first run on a machine with no provider at all (a container, a CI box)."""
    config = AppConfig()
    config.first_run = True
    config.providers.providers.clear()
    config.providers.active_provider = ""
    config.providers.active_model = ""
    return config


def run_main(monkeypatch, argv: list[str], config: AppConfig | None = None) -> None:
    monkeypatch.setattr(sys, "argv", ["openlaoke", *argv])
    monkeypatch.setattr(cli, "load_config", lambda: config or ready_config())
    cli.main()


# --------------------------------------------------------------------------- #
# split_argv
# --------------------------------------------------------------------------- #


def test_value_flags_keep_their_value_out_of_the_prompt() -> None:
    flags, prompt = cli.split_argv(["-m", "gpt-4o", "fix", "the", "build"])

    assert flags == ["-m", "gpt-4o"]
    assert prompt == ["fix", "the", "build"]


def test_a_dangling_value_flag_does_not_crash() -> None:
    flags, prompt = cli.split_argv(["--model"])

    assert flags == ["--model"]
    assert prompt == []


def test_everything_after_an_unknown_flag_stays_in_the_prompt() -> None:
    _flags, prompt = cli.split_argv(["--why", "explain"])

    assert prompt == ["explain"]


# --------------------------------------------------------------------------- #
# main(): early exits
# --------------------------------------------------------------------------- #


def test_version_prints_and_exits(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["openlaoke", "--version"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 0
    assert "OpenLaoKe" in capsys.readouterr().out


def test_show_config_prints_and_returns(monkeypatch) -> None:
    shown: list[Any] = []
    monkeypatch.setattr(cli, "show_current_config", lambda config: shown.append(config))

    run_main(monkeypatch, ["--show-config"])

    assert len(shown) == 1


def test_config_flag_runs_the_wizard_and_stops(monkeypatch) -> None:
    saved: list[Any] = []
    monkeypatch.setattr(cli, "run_config_wizard", lambda config: config)
    monkeypatch.setattr(cli, "save_config", lambda config: saved.append(config))

    run_main(monkeypatch, ["--config"])

    assert len(saved) == 1


def test_first_run_runs_the_wizard_then_continues(monkeypatch, launched) -> None:
    config = bare_config()
    saved: list[Any] = []

    def wizard(current):
        current.first_run = False
        return current

    monkeypatch.setattr(cli, "run_config_wizard", wizard)
    monkeypatch.setattr(cli, "save_config", lambda cfg: saved.append(cfg))
    monkeypatch.setattr(cli, "_interactive_terminal", lambda: True)

    run_main(monkeypatch, [], config)

    assert saved and saved[0].first_run is False
    assert launched["mode"] == "interactive"


def test_no_terminal_and_no_key_exits_cleanly(monkeypatch, capsys) -> None:
    """A pipe is not a person: say so instead of dying on EOFError."""
    config = bare_config()
    monkeypatch.setattr(cli, "_interactive_terminal", lambda: False)
    started: list[str] = []
    monkeypatch.setattr(cli, "_run_interactive", lambda *a: started.append("ran"))

    with pytest.raises(SystemExit) as exited:
        run_main(monkeypatch, [], config)

    assert exited.value.code == 1
    out = capsys.readouterr().out
    assert "no terminal to ask in" in out
    assert "--config" in out
    assert not started, "it must not try to start a session without a provider"


def test_a_key_in_the_environment_is_enough(monkeypatch, launched) -> None:
    """The client already reads these variables; do not demand a wizard answer."""
    config = bare_config()
    monkeypatch.setattr(cli, "_interactive_terminal", lambda: False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    saved: list[Any] = []
    monkeypatch.setattr(cli, "save_config", lambda cfg: saved.append(cfg))

    run_main(monkeypatch, [], config)

    assert launched["mode"] == "interactive"
    assert launched["config"].providers.active_provider == "anthropic"
    assert saved, "the choice is remembered for the next run"


def test_eof_at_a_wizard_prompt_is_not_a_crash(monkeypatch, capsys) -> None:
    config = bare_config()
    monkeypatch.setattr(cli, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(cli, "run_config_wizard", lambda current: (_ for _ in ()).throw(EOFError()))

    with pytest.raises(SystemExit) as exited:
        run_main(monkeypatch, [], config)

    assert exited.value.code == 1
    assert "Configuration cancelled" in capsys.readouterr().out


def test_an_unknown_provider_is_reported(monkeypatch, capsys) -> None:
    run_main(monkeypatch, ["--provider", "ghost"])

    assert "Unknown provider: ghost" in capsys.readouterr().out


def test_an_unknown_mode_is_reported(monkeypatch, capsys) -> None:
    run_main(monkeypatch, ["--mode", "turbo"])

    assert "Unknown mode: turbo" in capsys.readouterr().out


def test_bot_mode_without_a_prompt_exits_with_two(monkeypatch, capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run_main(monkeypatch, ["--bot", "helper"])

    assert excinfo.value.code == 2
    assert "needs a prompt" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# main(): overrides land on the state
# --------------------------------------------------------------------------- #


def test_model_and_key_overrides_reach_the_config(monkeypatch, launched) -> None:
    config = ready_config()

    run_main(monkeypatch, ["--model", "gpt-4o-mini", "--api-key", "sk-new"], config)

    assert config.providers.active_model == "gpt-4o-mini"
    assert config.providers.providers["openai"].api_key == "sk-new"
    assert launched["app_state"].session_config.model == "gpt-4o-mini"


def test_provider_and_base_url_overrides(monkeypatch, launched) -> None:
    config = ready_config()
    config.providers.providers["deepseek"] = ProviderConfig(
        provider_type=ProviderType.DEEPSEEK, api_key="sk-ds"
    )

    run_main(
        monkeypatch,
        ["--provider", "deepseek", "--base-url", "http://localhost:8088/v1"],
        config,
    )

    assert config.providers.active_provider == "deepseek"
    assert config.providers.providers["deepseek"].base_url == "http://localhost:8088/v1"


def test_proxy_flags_are_mutually_exclusive_in_effect(monkeypatch, launched) -> None:
    config = ready_config()

    run_main(monkeypatch, ["--proxy", "http://127.0.0.1:7897"], config)

    assert config.proxy_mode == "custom"
    assert config.proxy_url == "http://127.0.0.1:7897"


def test_no_proxy_clears_any_configured_proxy(monkeypatch, launched) -> None:
    config = ready_config()
    config.proxy_mode = "custom"
    config.proxy_url = "http://127.0.0.1:7897"

    run_main(monkeypatch, ["--no-proxy"], config)

    assert config.proxy_mode == "none"
    assert config.proxy_url == ""


def test_cwd_override_sets_the_working_directory(monkeypatch, launched, tmp_path) -> None:
    work = tmp_path / "work"
    work.mkdir()

    run_main(monkeypatch, ["--cwd", str(work)])

    assert launched["app_state"].get_cwd() == str(work)


def test_permission_and_yes_flags_change_the_permission_mode(monkeypatch, launched) -> None:
    from openlaoke.types.core_types import PermissionMode

    run_main(monkeypatch, ["--permission", "auto"])

    assert launched["app_state"].permission_config.mode == PermissionMode.AUTO

    run_main(monkeypatch, ["-y"])

    assert launched["app_state"].permission_config.mode == PermissionMode.AUTO
    assert launched["app_state"].auto_accept is True


def test_verbose_local_and_caveman_switches(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["--verbose", "--local", "--caveman"])

    state = launched["app_state"]
    assert state.verbose is True
    assert state.local_mode is True
    assert state.caveman_mode is True


def test_no_caveman_turns_it_off(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["--no-caveman"])

    assert launched["app_state"].caveman_mode is False


def test_budget_and_history_flags(monkeypatch, launched) -> None:
    run_main(
        monkeypatch,
        [
            "--max-tokens",
            "512",
            "--thinking-budget",
            "64",
            "--max-tool-history",
            "128",
            "--max-steps",
            "3",
        ],
    )

    state = launched["app_state"]
    assert state.max_tool_history == 128
    assert state.max_steps == 3
    assert launched["config"].max_tokens == 512


def test_reasoning_effort_override(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["--reasoning-effort", "high"])

    assert launched["app_state"].session_config.reasoning_effort == "high"
    assert launched["config"].reasoning_effort == "high"


def test_mode_flag_sets_the_harness_mode(monkeypatch, launched) -> None:
    from openlaoke.core.harness_modes import get_mode

    run_main(monkeypatch, ["--mode", "jcode"])

    assert launched["app_state"].harness_mode == "jcode"
    assert launched["app_state"].max_steps == get_mode("jcode").max_steps


def test_all_tools_flag(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["--all-tools"])

    assert launched["app_state"].use_all_tools is True


def test_auto_approve_from_config(monkeypatch, launched) -> None:
    config = ready_config()
    config.auto_approve_all = True

    run_main(monkeypatch, [], config)

    from openlaoke.types.core_types import PermissionMode

    assert launched["app_state"].permission_config.mode == PermissionMode.AUTO


# --------------------------------------------------------------------------- #
# main(): mode selection
# --------------------------------------------------------------------------- #


def test_a_prompt_runs_headless(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["fix", "the", "build"])

    assert launched["mode"] == "headless"
    assert launched["prompt"] == "fix the build"


def test_bot_mode_routes_to_the_bot_runner(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["--bot", "helper", "say", "hi"])

    assert launched["mode"] == "bot"
    assert launched["bot"] == "helper"
    assert launched["prompt"] == "say hi"


def test_room_mode_routes_to_the_bot_runner(monkeypatch, launched) -> None:
    run_main(monkeypatch, ["--room", "dev", "ship", "it"])

    assert launched["mode"] == "bot"
    assert launched["room"] == "dev"


def test_no_arguments_starts_the_repl(monkeypatch, launched) -> None:
    run_main(monkeypatch, [])

    assert launched["mode"] == "interactive"


# --------------------------------------------------------------------------- #
# _run_interactive
# --------------------------------------------------------------------------- #


def test_interactive_hands_the_config_to_the_repl(monkeypatch, tmp_path) -> None:
    from openlaoke.core.state import create_app_state

    seen: dict[str, Any] = {}

    class FakeREPL:
        def __init__(self, app_state):
            seen["app_state"] = app_state
            self.app_config = None

        async def run(self) -> None:
            seen["ran"] = True

    monkeypatch.setattr(cli, "REPL", FakeREPL)
    state = create_app_state(cwd=str(tmp_path))
    config = ready_config()

    asyncio.run(cli._run_interactive(state, config))

    assert seen["ran"] is True
    assert seen["app_state"] is state


# --------------------------------------------------------------------------- #
# _run_non_interactive
# --------------------------------------------------------------------------- #


class FakeClient:
    instances: list[FakeClient] = []

    def __init__(self, providers, proxy=None):
        self.providers = providers
        self.proxy = proxy
        self.closed = False
        FakeClient.instances.append(self)

    async def close(self) -> None:
        self.closed = True


def patch_headless(monkeypatch, stop_reason: str = "done", error: str = ""):
    from openlaoke.core.engine import EngineResult

    FakeClient.instances = []
    monkeypatch.setattr(cli, "MultiProviderClient", FakeClient)
    captured: dict[str, Any] = {}

    async def run_loop(**kwargs):
        captured.update(kwargs)
        return EngineResult(
            stop_reason=stop_reason, iterations=2, error=error, messages=[], text_parts=["hi"]
        )

    monkeypatch.setattr("openlaoke.core.engine.run_loop", run_loop)
    return captured


def test_headless_run_closes_the_client_and_prints_cost(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    captured = patch_headless(monkeypatch)
    state = create_app_state(cwd=str(tmp_path))
    config = ready_config()

    asyncio.run(cli._run_non_interactive("do it", state, config))

    assert FakeClient.instances and FakeClient.instances[0].closed is True
    assert captured["messages"] == [{"role": "user", "content": "do it"}]
    assert captured["send_kwargs"]["max_tokens"] == config.max_tokens
    assert "Session cost" in capsys.readouterr().out


def test_headless_run_uses_all_tools_when_asked(monkeypatch, tmp_path) -> None:
    from openlaoke.core.state import create_app_state

    captured = patch_headless(monkeypatch)
    state = create_app_state(cwd=str(tmp_path))
    state.use_all_tools = True

    asyncio.run(cli._run_non_interactive("do it", state, ready_config()))

    names = {tool["name"] for tool in captured["policy"].tools}
    assert "WebSearch" in names or "Panel" in names or len(names) > 10


def test_headless_error_exits_with_one(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.engine import STOP_ERROR
    from openlaoke.core.state import create_app_state

    patch_headless(monkeypatch, stop_reason=STOP_ERROR, error="upstream refused")
    state = create_app_state(cwd=str(tmp_path))

    with pytest.raises(SystemExit) as excinfo:
        asyncio.run(cli._run_non_interactive("do it", state, ready_config()))

    assert excinfo.value.code == 1
    assert "upstream refused" in capsys.readouterr().out


def test_headless_stats_are_printed_on_request(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    patch_headless(monkeypatch)
    monkeypatch.setenv("OPENLAOKE_STATS", "1")
    state = create_app_state(cwd=str(tmp_path))

    asyncio.run(cli._run_non_interactive("do it", state, ready_config()))

    out = capsys.readouterr().out
    assert "[stats] steps=2" in out
    assert "input_tokens=" in out


# --------------------------------------------------------------------------- #
# _run_bot_prompt
# --------------------------------------------------------------------------- #


class FakeBotMode:
    def __init__(self, *, reply: str = "hello there", turns: Any = None):
        self.reply = reply
        self.turns = turns if turns is not None else []
        self.drained = [{"bot": "helper", "from": "other", "reply": "noted"}]
        self.error: Exception | None = None

    async def ask(self, name: str, prompt: str) -> str:
        if self.error:
            raise self.error
        return self.reply

    async def room_send(self, room: str, prompt: str) -> list[Any]:
        if self.error:
            raise self.error
        return self.turns

    async def drain(self) -> list[dict]:
        return self.drained


def patch_bot(monkeypatch, mode: FakeBotMode) -> None:
    import openlaoke.core.bot_mode as bot_mode

    monkeypatch.setattr(bot_mode, "get_bot_mode", lambda state: mode)
    monkeypatch.setattr(bot_mode, "slug", lambda name: name.lower())


def test_bot_prompt_prints_the_reply_and_the_inbox(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    patch_bot(monkeypatch, FakeBotMode(reply="the answer"))
    state = create_app_state(cwd=str(tmp_path))

    asyncio.run(cli._run_bot_prompt("hi", state, ready_config(), "helper", None))

    out = capsys.readouterr().out
    assert "the answer" in out
    assert "@helper <- @other: noted" in out
    assert "Session cost" in out


def test_a_silent_bot_says_so(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    patch_bot(monkeypatch, FakeBotMode(reply=""))
    state = create_app_state(cwd=str(tmp_path))

    asyncio.run(cli._run_bot_prompt("hi", state, ready_config(), "helper", None))

    assert "stayed silent" in capsys.readouterr().out


def test_room_prompt_prints_turns(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    turns = [SimpleNamespace(member="Helper", text="room reply")]
    patch_bot(monkeypatch, FakeBotMode(turns=turns))
    state = create_app_state(cwd=str(tmp_path))

    asyncio.run(cli._run_bot_prompt("ship it", state, ready_config(), None, "dev"))

    assert "@helper: room reply" in capsys.readouterr().out


def test_an_empty_room_is_reported(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    patch_bot(monkeypatch, FakeBotMode(turns=[]))
    state = create_app_state(cwd=str(tmp_path))

    asyncio.run(cli._run_bot_prompt("ship it", state, ready_config(), None, "dev"))

    assert "nobody" in capsys.readouterr().out


def test_an_unknown_bot_exits_with_one(monkeypatch, tmp_path, capsys) -> None:
    from openlaoke.core.state import create_app_state

    mode = FakeBotMode()
    mode.error = ValueError("no bot named ghost")
    patch_bot(monkeypatch, mode)
    state = create_app_state(cwd=str(tmp_path))

    with pytest.raises(SystemExit) as excinfo:
        asyncio.run(cli._run_bot_prompt("hi", state, ready_config(), "ghost", None))

    assert excinfo.value.code == 1
    assert "no bot named ghost" in capsys.readouterr().out


def test_engine_kwargs_honour_the_flag_then_the_mode() -> None:
    from openlaoke.core.harness_modes import get_mode

    mode = get_mode("balanced")

    assert cli.engine_kwargs_for(SimpleNamespace(max_steps=5), mode)["max_iterations"] == 5
    assert (
        cli.engine_kwargs_for(SimpleNamespace(max_steps=None), mode)["max_iterations"]
        == mode.max_steps
    )
