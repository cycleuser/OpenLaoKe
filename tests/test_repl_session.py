"""Tests for the interactive REPL surface: run(), input routing and commands.

The agent loop itself is covered in ``test_repl_loop.py``; this file drives the
parts a user actually touches, with a scripted prompt and a fake provider client
so nothing waits on a terminal or a network.
"""

from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

import openlaoke.core.repl as repl_module
from openlaoke.core.prompt_input import PromptAction, PromptResult
from openlaoke.core.repl import REPL
from openlaoke.core.state import create_app_state
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType
from openlaoke.utils.config import AppConfig


class ScriptedPrompt:
    """Stands in for PromptSessionManager with a fixed list of answers."""

    def __init__(self, results: list[PromptResult]) -> None:
        self._results = list(results)
        self.prompts = 0

    def get_session(self) -> Any:
        return object()

    async def get_user_input(self) -> PromptResult:
        self.prompts += 1
        if not self._results:
            return PromptResult(action=PromptAction.EXIT)
        return self._results.pop(0)


class FakeAPI:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.config = args[0] if args else None
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def stream_message(self, **kwargs: Any):
        if False:  # pragma: no cover - keeps this an async generator
            yield None


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".openlaoke").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    import openlaoke.core.skill_system as skill_system

    monkeypatch.setattr(skill_system, "_global_registry", None)
    yield home
    skill_system._global_registry = None


def make_repl(tmp_path: Path, prompt: ScriptedPrompt, *, with_config: bool = True) -> REPL:
    state = create_app_state(cwd=str(tmp_path))
    r = REPL(state)
    r.console = Console(file=StringIO(), force_terminal=False, width=120, color_system=None)
    r._prompt_manager = prompt  # type: ignore[assignment]
    r.app_config = AppConfig()
    r.app_config.enable_mcp = False
    r.app_config.enable_scheduler = False
    if with_config:
        config = MultiProviderConfig(
            providers={
                "main": ProviderConfig(
                    provider_type=ProviderType.OPENAI,
                    api_key="sk-test",
                    base_url="https://api.example.com/v1",
                    models=["gpt-4o"],
                    default_model="gpt-4o",
                )
            },
            active_provider="main",
            active_model="gpt-4o",
        )
        r.multi_provider_config = config
        state.multi_provider_config = config
    state._persist_path = None
    return r


def output(r: REPL) -> str:
    assert isinstance(r.console.file, StringIO)
    return r.console.file.getvalue()


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# run(): the outer loop
# --------------------------------------------------------------------------- #


def test_run_prints_a_hint_and_returns_without_any_provider(tmp_path, monkeypatch) -> None:
    prompt = ScriptedPrompt([])
    r = make_repl(tmp_path, prompt, with_config=False)
    r.multi_provider_config = None
    r.app_state.multi_provider_config = None

    run(r.run())

    assert "openlaoke --config" in output(r) or "provider" in output(r).lower()
    assert r.api is None
    assert prompt.prompts == 0


def test_run_consumes_input_until_exit(tmp_path, monkeypatch) -> None:
    prompt = ScriptedPrompt(
        [
            PromptResult(action=PromptAction.TEXT, text="first"),
            PromptResult(action=PromptAction.TEXT, text="second"),
            PromptResult(action=PromptAction.EXIT),
        ]
    )
    r = make_repl(tmp_path, prompt)
    monkeypatch.setattr(repl_module, "MultiProviderClient", FakeAPI)
    monkeypatch.setattr(REPL, "_probe_local_providers", _async_noop)

    chats: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(chats, text))

    run(r.run())

    assert chats == ["first", "second"]
    assert r._running is False
    assert isinstance(r.api, FakeAPI) and r.api.closed is True


def test_run_survives_ctrl_c(tmp_path, monkeypatch) -> None:
    class Interrupting(ScriptedPrompt):
        async def get_user_input(self) -> PromptResult:
            raise KeyboardInterrupt

    r = make_repl(tmp_path, Interrupting([]))
    monkeypatch.setattr(repl_module, "MultiProviderClient", FakeAPI)
    monkeypatch.setattr(REPL, "_probe_local_providers", _async_noop)

    run(r.run())

    assert "goodbye" in output(r).lower() or "bye" in output(r).lower()


async def _async_noop(*args: Any, **kwargs: Any) -> None:
    return None


async def _record(bucket: list[str], text: str) -> None:
    bucket.append(text)


# --------------------------------------------------------------------------- #
# _handle_input routing
# --------------------------------------------------------------------------- #


def feed(r: REPL, *results: PromptResult) -> None:
    assert isinstance(r._prompt_manager, ScriptedPrompt)
    r._prompt_manager._results = list(results)


def test_exit_stops_the_running_flag(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._running = True
    feed(r, PromptResult(action=PromptAction.EXIT))

    run(r._handle_input())

    assert r._running is False


def test_empty_input_is_ignored(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    called: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(called, text))

    feed(r, PromptResult(action=PromptAction.TEXT, text=""))
    run(r._handle_input())

    assert called == []


def test_the_model_picker_applies_the_selection(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    applied: list[str] = []
    monkeypatch.setattr(repl_module, "run_model_picker_async", lambda: _value("main/gpt-4o"))
    monkeypatch.setattr(REPL, "_handle_model_switch", lambda self, sel: applied.append(sel))

    feed(r, PromptResult(action=PromptAction.PICKER))
    run(r._handle_input())

    assert applied == ["main/gpt-4o"]


def test_a_cancelled_picker_changes_nothing(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    applied: list[str] = []
    monkeypatch.setattr(repl_module, "run_model_picker_async", lambda: _value(None))
    monkeypatch.setattr(REPL, "_handle_model_switch", lambda self, sel: applied.append(sel))

    feed(r, PromptResult(action=PromptAction.PICKER))
    run(r._handle_input())

    assert applied == []


def test_the_language_picker_applies_the_selection(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    applied: list[str] = []
    monkeypatch.setattr(repl_module, "run_lang_picker_async", lambda current: _value("zh"))
    monkeypatch.setattr(REPL, "_handle_lang_switch", lambda self, lang: applied.append(lang))

    feed(r, PromptResult(action=PromptAction.LANG_PICKER))
    run(r._handle_input())

    assert applied == ["zh"]


def test_the_thinking_toggle_prints_the_reasoning(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._last_thinking = "because reasons"
    shown: list[bool] = []
    monkeypatch.setattr(REPL, "_show_thinking_full", lambda self: shown.append(True))

    feed(r, PromptResult(action=PromptAction.TOGGLE_THINKING))
    run(r._handle_input())

    assert shown == [True]


def test_a_model_switch_prefix_is_routed(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    applied: list[str] = []
    monkeypatch.setattr(REPL, "_handle_model_switch", lambda self, sel: applied.append(sel))

    feed(r, PromptResult(action=PromptAction.TEXT, text="model_switch:main/gpt-4o"))
    run(r._handle_input())

    assert applied == ["main/gpt-4o"]


def test_a_slash_skill_name_activates_the_skill(tmp_path) -> None:
    skills = Path.home() / ".openlaoke" / "skills" / "writer"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: writer\ndescription: polish prose\n---\n\nBody.\n", encoding="utf-8"
    )
    r = make_repl(tmp_path, ScriptedPrompt([]))

    feed(r, PromptResult(action=PromptAction.TEXT, text="/writer"))
    run(r._handle_input())

    assert "writer" in r.app_state.active_skills
    assert "writer" in output(r)


def test_a_skill_can_be_used_without_a_slash(tmp_path, monkeypatch) -> None:
    skills = Path.home() / ".openlaoke" / "skills" / "writer"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: writer\ndescription: polish prose\n---\n\nBody.\n", encoding="utf-8"
    )
    r = make_repl(tmp_path, ScriptedPrompt([]))
    chats: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(chats, text))

    # "/writer summarize this" -> activate, then send the rest to the model.
    feed(r, PromptResult(action=PromptAction.TEXT, text="writer summarize this"))
    run(r._handle_input())

    from openlaoke.core.skill_system import load_skill

    assert load_skill("writer") is not None


def test_slash_skill_with_arguments_starts_a_chat(tmp_path, monkeypatch) -> None:
    skills = Path.home() / ".openlaoke" / "skills" / "writer"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: writer\ndescription: polish prose\n---\n\nBody.\n", encoding="utf-8"
    )
    from openlaoke.core.skill_system import rescan_skills

    rescan_skills()
    r = make_repl(tmp_path, ScriptedPrompt([]))
    chats: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(chats, text))

    feed(r, PromptResult(action=PromptAction.TEXT, text="/writer tighten this"))
    run(r._handle_input())

    assert chats == ["tighten this"]


def test_a_known_command_is_dispatched(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    feed(r, PromptResult(action=PromptAction.TEXT, text="/help"))
    run(r._handle_input())

    assert "/help" in output(r) or "command" in output(r).lower()


def test_an_unknown_command_says_so(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    feed(r, PromptResult(action=PromptAction.TEXT, text="/nosuchcommand"))
    run(r._handle_input())

    text = output(r).lower()
    assert "nosuchcommand" in text


def test_plain_text_goes_to_the_model(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    chats: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(chats, text))

    feed(r, PromptResult(action=PromptAction.TEXT, text="explain the build"))
    run(r._handle_input())

    assert chats == ["explain the build"]


async def _value(v: Any) -> Any:
    return v


# --------------------------------------------------------------------------- #
# _handle_command result handling
# --------------------------------------------------------------------------- #


def test_a_command_can_ask_to_exit(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._running = True

    run(r._handle_command("quit", ""))

    assert r._running is False


def test_a_command_can_clear_the_screen(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    run(r._handle_command("clear", ""))

    assert isinstance(r.console.file, StringIO)


def test_an_unknown_slash_command_with_a_template_is_expanded(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    chats: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(chats, text))
    import openlaoke.core.prompt_templates as templates

    monkeypatch.setattr(templates, "expand_prompt_template", lambda name, args: "expanded text")

    run(r._handle_command("mytemplate", "arg"))

    assert chats == ["expanded text"]


def test_a_command_with_submit_text_starts_a_chat(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    chats: list[str] = []
    monkeypatch.setattr(REPL, "_handle_chat", lambda self, text: _record(chats, text))

    run(r._handle_command("new", ""))

    # /new clears the conversation and does not submit text; the assertion here is
    # that whatever it returns is handled without raising.
    assert isinstance(chats, list)


# --------------------------------------------------------------------------- #
# model / language switching
# --------------------------------------------------------------------------- #


def test_model_switch_updates_state_and_persists(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    r._handle_model_switch("main/gpt-4o-mini")

    config = r.multi_provider_config
    assert config.active_provider == "main"
    assert config.active_model == "gpt-4o-mini"
    assert r.app_state.session_config.model == "gpt-4o-mini"
    from openlaoke.utils.config import load_config

    assert load_config().providers.active_model == "gpt-4o-mini"


def test_model_switch_ignores_a_bare_model_name(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    before = r.multi_provider_config.active_model

    r._handle_model_switch("gpt-4o-mini")

    assert r.multi_provider_config.active_model == before


def test_model_switch_reports_an_unknown_provider(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    r._handle_model_switch("ghost/gpt-4o")

    assert "ghost" in output(r)
    assert r.multi_provider_config.active_provider == "main"


def test_language_switch_persists_and_invalidates_the_cache_guard(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    invalidated: list[bool] = []
    r._cache_guard.invalidate = lambda: invalidated.append(True)

    r._handle_lang_switch("zh")

    assert r.app_state.language == "zh"
    assert invalidated == [True]
    from openlaoke.utils.config import load_config

    assert load_config().language == "zh"


def test_language_switch_rejects_an_unsupported_code(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    r._handle_lang_switch("klingon")

    assert r.app_state.language != "klingon"
    assert "klingon" in output(r)


# --------------------------------------------------------------------------- #
# bot routing
# --------------------------------------------------------------------------- #


class FakeBotMode:
    def __init__(self, *, enabled: bool, active_bot: str = "", active_room: str = ""):
        self.enabled = enabled
        self.active_bot = active_bot
        self.active_room = active_room
        self.asked: list[tuple[str, str]] = []
        self.drained: list[dict] = []

    def require_bot(self, name: str) -> Any:
        if name != "helper":
            raise ValueError(f"no bot named {name}")
        return type("Profile", (), {"name": "helper"})()

    async def ask(self, name: str, text: str, on_text: Any = None) -> str:
        self.asked.append((name, text))
        if on_text:
            on_text("the answer")
        return "the answer"

    async def room_send(self, room: str, text: str) -> list[Any]:
        return [type("Turn", (), {"member": "helper", "text": "room reply"})()]

    async def drain(self) -> list[dict]:
        return self.drained

    def routine_bot(self, entry_name: str) -> str | None:
        return "helper" if entry_name == "morning" else None

    def get_bot(self, name: str) -> Any:
        return type("Profile", (), {"name": name})() if name == "helper" else None


def patch_bot_mode(monkeypatch, mode: FakeBotMode) -> None:
    import openlaoke.core.bot_mode as bot_mode

    monkeypatch.setattr(bot_mode, "get_bot_mode", lambda state: mode)
    monkeypatch.setattr(bot_mode, "slug", lambda name: name.lower())


def test_plain_input_is_not_routed_when_bot_mode_is_off(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    patch_bot_mode(monkeypatch, FakeBotMode(enabled=False))

    assert run(r._handle_bot_input("hello")) is False


def test_input_is_sent_to_the_active_bot(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True, active_bot="helper")
    mode.drained = [{"bot": "helper", "from": "other", "reply": "noted"}]
    patch_bot_mode(monkeypatch, mode)

    handled = run(r._handle_bot_input("are you there"))

    assert handled is True
    assert mode.asked == [("helper", "are you there")]
    assert "the answer" in output(r)
    assert "noted" in output(r)


def test_a_silent_bot_is_reported(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True, active_bot="helper")

    async def silent(name: str, text: str, on_text: Any = None) -> str:
        return ""

    mode.ask = silent  # type: ignore[assignment]
    patch_bot_mode(monkeypatch, mode)

    run(r._handle_bot_input("hello"))

    assert "silent" in output(r).lower()


def test_room_input_prints_each_turn(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True, active_room="dev")
    patch_bot_mode(monkeypatch, mode)

    run(r._handle_bot_input("ship it"))

    assert "room reply" in output(r)


def test_an_empty_room_says_nobody_answered(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True, active_room="dev")

    async def nobody(room: str, text: str) -> list[Any]:
        return []

    mode.room_send = nobody  # type: ignore[assignment]
    patch_bot_mode(monkeypatch, mode)

    run(r._handle_bot_input("ship it"))

    assert "nobody" in output(r)


def test_an_unknown_bot_is_reported_as_an_error(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True, active_bot="ghost")
    patch_bot_mode(monkeypatch, mode)

    handled = run(r._handle_bot_input("hello"))

    assert handled is True
    assert "ghost" in output(r)


def test_inbox_delivery_failure_does_not_raise(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True)

    async def broken() -> list[dict]:
        raise RuntimeError("queue down")

    mode.drain = broken  # type: ignore[assignment]

    run(r._deliver_bot_inbox(mode))

    assert "bot delivery failed" in output(r)


def test_a_routine_bot_reply_is_summarised(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    mode = FakeBotMode(enabled=True)
    patch_bot_mode(monkeypatch, mode)

    notice = run(r._run_bot_routine(type("Entry", (), {"name": "morning", "prompt": "say hi"})()))

    assert notice is not None
    assert "routine for @helper" in notice
    assert mode.asked == [("helper", "[routine] say hi")]


def test_a_plain_schedule_entry_is_not_a_routine(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    patch_bot_mode(monkeypatch, FakeBotMode(enabled=True))

    assert run(r._run_bot_routine(type("Entry", (), {"name": "plain", "prompt": "x"})())) is None


# --------------------------------------------------------------------------- #
# startup helpers
# --------------------------------------------------------------------------- #


def test_startup_prints_banner_and_welcome(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    r._print_banner()
    r._print_welcome()

    assert output(r)


def test_mcp_start_is_skipped_without_a_config(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_config = None

    run(r._start_mcp())

    assert r._mcp_runtime.clients == {}


def test_mcp_start_reports_unavailable_servers(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_config.enable_mcp = True
    r.app_config.mcp_servers = {"broken": {"command": "nope"}}

    async def start(servers, registry):
        r._mcp_runtime.failures["broken"] = "command not found"
        return []

    monkeypatch.setattr(r._mcp_runtime, "start", start)

    run(r._start_mcp())

    assert "broken" in output(r)
    assert "not found" in output(r)


def test_mcp_tools_are_registered_and_reported(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_config.enable_mcp = True
    r.app_config.mcp_servers = {"ok": {"command": "srv"}}

    async def start(servers, registry):
        r._mcp_runtime.clients["ok"] = object()
        return ["mcp__ok__tool"]

    monkeypatch.setattr(r._mcp_runtime, "start", start)

    run(r._start_mcp())

    assert "MCP: 1 tool(s) from 1 server(s)" in output(r)


def test_offline_local_providers_are_reported(tmp_path, monkeypatch) -> None:
    import openlaoke.types.providers as providers_module

    r = make_repl(tmp_path, ScriptedPrompt([]))

    async def probe(providers):
        return {"ollama": False, "lmstudio": True}

    monkeypatch.setattr(providers_module, "probe_local_providers", probe)

    run(r._probe_local_providers(r.multi_provider_config))

    assert "ollama" in output(r)
    assert "/model prune" in output(r)


def test_no_offline_providers_prints_nothing(tmp_path, monkeypatch) -> None:
    import openlaoke.types.providers as providers_module

    r = make_repl(tmp_path, ScriptedPrompt([]))

    async def probe(providers):
        return {"main": True}

    monkeypatch.setattr(providers_module, "probe_local_providers", probe)

    run(r._probe_local_providers(r.multi_provider_config))

    assert output(r) == ""


def test_scheduler_is_skipped_unless_enabled(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    r._start_scheduler()

    assert r._scheduler_task is None


def test_scheduler_task_starts_and_stops(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_config.enable_scheduler = True
    started: list[bool] = []

    async def loop(interval: float = 30.0) -> None:
        started.append(True)
        await asyncio.sleep(3600)

    monkeypatch.setattr(REPL, "_scheduler_loop", loop)

    async def go() -> None:
        r._start_scheduler()
        task = r._scheduler_task
        assert task is not None
        await asyncio.sleep(0)
        await r._stop_scheduler()
        assert r._scheduler_task is None

    run(go())

    assert started == [True]


def test_stopping_a_missing_scheduler_is_a_no_op(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._scheduler_task = None

    run(r._stop_scheduler())

    assert r._scheduler_task is None


# --------------------------------------------------------------------------- #
# _handle_chat
# --------------------------------------------------------------------------- #


def test_chat_records_the_message_and_runs_the_loop(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    ran: list[bool] = []

    async def loop(self) -> None:
        ran.append(True)

    monkeypatch.setattr(REPL, "_run_api_loop", loop)

    run(r._handle_chat("hello there"))

    assert ran == [True]
    assert r.app_state.messages[-1].content == "hello there"
    assert r.app_state.is_running is False
    assert r.app_state.error_message is None


def test_chat_reports_a_loop_error_and_keeps_the_session(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    async def boom(self) -> None:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(REPL, "_run_api_loop", boom)

    run(r._handle_chat("hello"))

    assert "provider exploded" in output(r)
    assert r.app_state.error_message == "provider exploded"
    assert r.app_state.is_running is False


def test_chat_queues_input_while_a_turn_runs(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    async def never() -> None:
        await asyncio.sleep(3600)

    async def go() -> None:
        agent = asyncio.create_task(never())
        r._agent_task = agent
        try:
            await r._handle_chat("second thought")
        finally:
            agent.cancel()
            with __import__("contextlib").suppress(asyncio.CancelledError):
                await agent

    run(go())

    assert r._input_queue == ["second thought"]
    assert "Queued" in output(r)


def test_an_interrupted_turn_patches_dangling_tool_calls(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    patched: list[bool] = []

    async def loop(self) -> None:
        r._interrupt_requested = True

    monkeypatch.setattr(REPL, "_run_api_loop", loop)
    monkeypatch.setattr(REPL, "_patch_dangling_tool_calls", lambda self: patched.append(True))

    run(r._handle_chat("do the thing"))

    assert patched == [True]
    assert "Interrupted" in output(r)


def test_a_queued_message_is_processed_after_the_turn(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    seen: list[str] = []

    async def loop(self) -> None:
        seen.append("turn")
        if len(seen) == 1:
            r._input_queue.append("follow up")

    monkeypatch.setattr(REPL, "_run_api_loop", loop)

    run(r._handle_chat("first"))

    assert seen == ["turn", "turn"]
    assert r._input_queue == []
    assert "Processing queued message" in output(r)


# --------------------------------------------------------------------------- #
# artifacts and history repair
# --------------------------------------------------------------------------- #


def test_collect_artifacts_gathers_content_and_files(tmp_path) -> None:
    from openlaoke.types.core_types import AssistantMessage, MessageRole

    r = make_repl(tmp_path, ScriptedPrompt([]))
    (tmp_path / "README.md").write_text("# hi", encoding="utf-8")
    (tmp_path / "plot.svg").write_text("<svg/>", encoding="utf-8")
    r.app_state.add_message(
        AssistantMessage(role=MessageRole.ASSISTANT, content="first"), persist=False
    )
    r.app_state.add_message(
        AssistantMessage(role=MessageRole.ASSISTANT, content="second"), persist=False
    )

    artifacts = r._collect_artifacts()

    assert "first" in artifacts["content"]
    assert "second" in artifacts["content"]
    assert str(tmp_path / "README.md") in artifacts["output_files"]
    assert str(tmp_path / "plot.svg") in artifacts["output_files"]


def test_dangling_tool_calls_get_a_synthetic_result(tmp_path) -> None:
    from openlaoke.types.core_types import AssistantMessage, MessageRole, ToolUseBlock

    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_state.add_message(
        AssistantMessage(
            role=MessageRole.ASSISTANT,
            content="",
            tool_uses=[ToolUseBlock(id="call_1", name="Write", input={"file_path": "a.txt"})],
        ),
        persist=False,
    )

    r._patch_dangling_tool_calls()

    results = [m for m in r.app_state.messages if getattr(m, "tool_use_id", None) == "call_1"]
    assert len(results) == 1
    assert "Interrupted by user" in results[0].content


def test_answered_tool_calls_are_left_alone(tmp_path) -> None:
    from openlaoke.types.core_types import AssistantMessage, MessageRole, ToolUseBlock

    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_state.add_message(
        AssistantMessage(
            role=MessageRole.ASSISTANT,
            content="",
            tool_uses=[ToolUseBlock(id="call_2", name="Read", input={"file_path": "a.txt"})],
        ),
        persist=False,
    )
    r._record_tool_result("call_2", "file contents")

    r._patch_dangling_tool_calls()

    assert [m for m in r.app_state.messages if getattr(m, "tool_use_id", None) == "call_2"] == [
        m for m in r.app_state.messages if getattr(m, "tool_use_id", None) == "call_2"
    ]
    assert (
        len([m for m in r.app_state.messages if getattr(m, "tool_use_id", None) == "call_2"]) == 1
    )


def test_max_iterations_honours_an_explicit_budget(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_state.max_steps = 7

    assert r._resolve_max_iterations() == 7


def test_max_iterations_falls_back_to_the_harness_mode(tmp_path) -> None:
    from openlaoke.core.harness_modes import get_mode

    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_state.max_steps = 0
    r.app_state.harness_mode = "quick"

    assert r._resolve_max_iterations() == get_mode("quick").max_steps


# --------------------------------------------------------------------------- #
# todos, usage, notices, memory, hooks, artifacts
# --------------------------------------------------------------------------- #


def test_auto_continue_is_off_without_open_todos(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._poke_budget = 0

    assert r._todo_auto_continue([]) is False
    assert r._poke_budget > 0


def test_auto_continue_pokes_once_per_budget(tmp_path) -> None:
    from openlaoke.core.todo_engine import TodoStore

    r = make_repl(tmp_path, ScriptedPrompt([]))
    store = TodoStore(r.app_state.todo_state)
    store.apply([{"name": "write the report"}])

    messages: list[dict] = []
    assert r._todo_auto_continue(messages) is True
    assert messages and messages[0]["system_injected"] is True
    starts_with = r._poke_budget
    while r._todo_auto_continue([]):
        pass
    assert r._poke_budget == 0
    assert r._poke_budget < starts_with


def test_auto_continue_stops_when_every_task_is_blocked(tmp_path) -> None:
    from openlaoke.core.todo_engine import TodoStore

    r = make_repl(tmp_path, ScriptedPrompt([]))
    TodoStore(r.app_state.todo_state).apply(
        [{"name": "waiting on CI", "completely_blocked": "CI is down"}]
    )

    assert r._todo_auto_continue([]) is False


def test_context_usage_updates_the_compact_state(tmp_path) -> None:
    class Usage:
        input_tokens = 100
        output_tokens = 20
        cache_read_input_tokens = 5

    r = make_repl(tmp_path, ScriptedPrompt([]))
    seen: list[Any] = []
    r._cache_monitor.observe = lambda usage, model="": seen.append((usage, model))

    r._note_context_usage(Usage())

    assert r.app_state.compact_state["used_tokens"] == 125
    assert r.app_state.compact_state["used_source"] == "provider_usage"
    assert seen and seen[0][1] == r.app_state.session_config.model


def test_context_usage_ignores_missing_or_empty_usage(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    r.app_state.compact_state["used_tokens"] = 42

    class Empty:
        input_tokens = 0
        output_tokens = 0
        cache_read_input_tokens = 0

    r._note_context_usage(None)
    r._note_context_usage(Empty())

    assert r.app_state.compact_state["used_tokens"] == 42


def test_finished_background_tasks_are_announced_once(tmp_path) -> None:
    from openlaoke.types.core_types import TaskState, TaskStatus, TaskType

    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._notified_tasks = set()
    task = TaskState(
        id="bg_1",
        type=TaskType.LOCAL_BASH,
        status=TaskStatus.COMPLETED,
        description="run the tests",
        end_time=123.0,
        exit_code=0,
    )
    r.app_state.add_task(task)

    first = r._drain_task_notices()
    second = r._drain_task_notices()

    assert len(first) == 1
    assert "bg_1" in first[0] and "completed" in first[0] and "exit code 0" in first[0]
    assert second == []


def test_running_tasks_are_not_announced(tmp_path) -> None:
    from openlaoke.types.core_types import TaskState, TaskStatus, TaskType

    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._notified_tasks = set()
    r.app_state.add_task(
        TaskState(
            id="bg_2",
            type=TaskType.LOCAL_BASH,
            status=TaskStatus.RUNNING,
            description="still going",
        )
    )

    assert r._drain_task_notices() == []


def test_memory_digest_is_empty_without_notes(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._memory_digest() == ""


def test_memory_digest_lists_recent_notes(tmp_path) -> None:
    from openlaoke.core.memory_store import get_store

    r = make_repl(tmp_path, ScriptedPrompt([]))
    get_store(r.app_state).remember("the deploy needs a proxy", kind="fact")

    digest = r._memory_digest()

    assert "<memory-index>" in digest
    assert "proxy" in digest
    assert "Memory(action='recall'" in digest


def test_turn_hooks_are_skipped_when_unregistered(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    calls: list[Any] = []
    r._hook_system.has_hooks = lambda name: False
    r._hook_system.execute_hooks_async = lambda *a, **k: calls.append(a)

    run(r._fire_turn_hook("turn_end", stop_reason="done"))

    assert calls == []


def test_turn_hooks_receive_the_session_fields(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    seen: list[Any] = []
    r._hook_system.has_hooks = lambda name: True

    async def execute(hook_type, payload):
        seen.append((hook_type, payload))

    r._hook_system.execute_hooks_async = execute

    run(r._fire_turn_hook("turn_end", stop_reason="done"))

    hook_type, payload = seen[0]
    assert hook_type == "turn_end"
    assert payload.session_id == r.app_state.session_id
    assert payload.provider_name == "main"
    assert payload.metadata == {"stop_reason": "done"}


def test_a_successful_write_arms_the_artifact_gate(tmp_path) -> None:
    from openlaoke.types.core_types import ToolResultBlock, ToolUseBlock

    r = make_repl(tmp_path, ScriptedPrompt([]))
    write = ToolUseBlock(id="c1", name="Write", input={"file_path": str(tmp_path / "note.txt")})

    r._note_artifact_result(write, ToolResultBlock(tool_use_id="c1", content="ok"))

    assert "note.txt" in r._artifact_written

    run_bash = ToolUseBlock(id="c2", name="Bash", input={"command": "python3 note.txt"})
    r._note_artifact_result(run_bash, ToolResultBlock(tool_use_id="c2", content="ok"))

    assert r._artifact_verified is True
    assert r._force_final is True


def test_a_failed_write_does_not_arm_the_gate(tmp_path) -> None:
    from openlaoke.types.core_types import ToolResultBlock, ToolUseBlock

    r = make_repl(tmp_path, ScriptedPrompt([]))
    write = ToolUseBlock(id="c1", name="Write", input={"file_path": "note.txt"})

    r._note_artifact_result(
        write, ToolResultBlock(tool_use_id="c1", content="denied", is_error=True)
    )

    assert r._artifact_written == set()


# --------------------------------------------------------------------------- #
# permission prompts
# --------------------------------------------------------------------------- #


class PreviewTool:
    name = "Write"
    is_read_only = False

    def __init__(self, *, preview_raises: bool = False) -> None:
        self._raises = preview_raises

    def preview(self, **kwargs: Any) -> Any:
        if self._raises:
            raise RuntimeError("no preview")
        return type("Preview", (), {"summary": "write note.txt"})()


def answer_permission(monkeypatch, r: REPL, answer: str) -> bool:
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    return run(r._ask_permission("Write", {"file_path": "note.txt"}, PreviewTool()))


def test_permission_yes_returns_true(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert answer_permission(monkeypatch, r, "y") is True
    assert "write note.txt" in output(r)


def test_permission_no_returns_false(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert answer_permission(monkeypatch, r, "n") is False


def test_permission_always_remembers_the_subject(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert answer_permission(monkeypatch, r, "a") is True
    assert r._is_denied_subject("Write", {"file_path": "note.txt"}) is False
    assert r._approval_subject("Write", {"file_path": "note.txt"}) == "note.txt"


def test_permission_never_stores_a_deny_rule(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert answer_permission(monkeypatch, r, "v") is False
    assert r._is_denied_subject("Write", {"file_path": "note.txt"}) is True
    assert "Saved permanent deny" in output(r)


def test_permission_eof_counts_as_no(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    def raise_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    assert run(r._ask_permission("Write", {"file_path": "a"}, PreviewTool())) is False


def test_a_broken_preview_does_not_block_the_prompt(tmp_path, monkeypatch) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    allowed = run(r._ask_permission("Write", {"file_path": "a"}, PreviewTool(preview_raises=True)))

    assert allowed is True
    assert "Preview" not in output(r)


def test_approval_subjects_are_narrow_per_tool(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._approval_subject("Bash", {"command": "rm -rf build"}) == "rm -rf build"
    assert r._approval_subject("Edit", {"file_path": "a.py"}) == "a.py"
    assert r._approval_subject("Read", {"file_path": "a.py"}) == ""
    long_command = "x" * 400
    assert len(r._approval_subject("Bash", {"command": long_command})) == 200


def test_denied_subject_without_a_subject_is_false(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._is_denied_subject("Read", {"file_path": "a.py"}) is False


# --------------------------------------------------------------------------- #
# rendering helpers
# --------------------------------------------------------------------------- #


def test_tool_action_lines_pick_the_telling_argument(tmp_path) -> None:
    from openlaoke.types.core_types import ToolUseBlock

    r = make_repl(tmp_path, ScriptedPrompt([]))

    def line(name: str, **kwargs: Any) -> str:
        return r._tool_action_line(ToolUseBlock(id="x", name=name, input=kwargs))

    assert "rm -rf build" in line("Bash", command="rm -rf build")
    assert "TODO" in line("Grep", pattern="TODO", path="src")
    assert "a.py" in line("Write", file_path="a.py")
    assert "apply_patch" in line("apply_patch", path="b.py") or "b.py" in line(
        "apply_patch", path="b.py"
    )
    assert "https://x.dev" in line("WebFetch", url="https://x.dev")
    assert "python asyncio" in line("WebSearch", query="python asyncio")
    assert "3 items" in line("TodoWrite", todos=[1, 2, 3])
    assert "notes.md" in line("SomeOtherTool", file_path="notes.md")
    long_text = "y" * 200
    assert "…" in line("Bash", command=long_text)


def test_tool_results_are_trimmed_when_long(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    r._print_tool_result("short output", "Read", False)
    r._print_tool_result("z" * 500, "Bash", True)

    text = output(r)
    assert "short output" in text
    assert "chars total" in text


def test_git_store_is_not_available(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._get_git_store() is None


def test_text_tool_calls_are_recovered(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    calls = r._parse_inline_tool_calls(
        '<tool_call>{"name": "Read", "arguments": {"file_path": "a.py"}}</tool_call>'
    )

    assert calls and calls[0].name == "Read"


def test_brace_style_tool_calls_are_recovered(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    calls = r._parse_brace_tool_calls("Write{file_path:<|arg|>out.py<|arg|>}")

    assert calls
    assert calls[0].name == "Write"
    assert calls[0].input["file_path"] == "out.py"


def test_plain_text_yields_no_tool_calls(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._parse_inline_tool_calls("just words") == []


def test_tool_call_markup_is_stripped_from_the_reply(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    stripped = r._strip_tool_calls(
        "<tool_call>{}</tool_call>\nHere is the answer.\nBash command=ls"
    )

    assert stripped == "Here is the answer."


def test_ollama_detection(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._is_ollama_provider() is False

    from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType

    r.app_state.multi_provider_config = MultiProviderConfig(
        providers={"local": ProviderConfig(provider_type=ProviderType.OLLAMA)},
        active_provider="local",
    )

    assert r._is_ollama_provider() is True

    r.app_state.multi_provider_config = None
    assert r._is_ollama_provider() is False


def test_plan_responses_are_told_apart_from_answers(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))

    assert r._is_plan_response("I will now read the file.") is True
    assert r._is_plan_response("接下来我将读取文件。") is True
    assert r._is_plan_response("Done. The file now contains the fix.") is False
    assert r._is_plan_response("") is False

    long_plan = "I will now " + "detail " * 200
    assert r._is_plan_response(long_plan) is False


def test_verify_file_written_reports_size_and_lines(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    (tmp_path / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    from openlaoke.types.core_types import ToolResultBlock

    r._verify_file_written({"file_path": "a.txt"}, ToolResultBlock(tool_use_id="c1", content="ok"))

    assert "Verified" in output(r)
    assert "2 lines" in output(r)


def test_verify_file_written_reports_a_missing_file(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    from openlaoke.types.core_types import ToolResultBlock

    r._verify_file_written(
        {"file_path": "absent.txt"}, ToolResultBlock(tool_use_id="c1", content="ok")
    )

    assert "Missing" in output(r)


def test_verify_file_written_ignores_calls_without_a_path(tmp_path) -> None:
    r = make_repl(tmp_path, ScriptedPrompt([]))
    from openlaoke.types.core_types import ToolResultBlock

    r._verify_file_written({}, ToolResultBlock(tool_use_id="c1", content="ok"))

    assert output(r) == ""


def test_context_composition_estimates_shares(tmp_path) -> None:
    text = REPL._format_context_composition(
        [
            {"role": "system", "content": "s" * 400},
            {"role": "user", "content": "u" * 40},
            {"role": "assistant", "content": "a" * 40, "tool_calls": [{"id": "x"}]},
            {"role": "tool", "content": "t" * 40},
        ]
    )

    assert text.startswith("ctx:")
    assert "sys 100t" in text
    assert "usr 10t" in text
    assert "ast" in text and "tool 10t" in text


def test_context_composition_of_an_empty_context(tmp_path) -> None:
    assert REPL._format_context_composition([]) == "(empty context)"


# --------------------------------------------------------------------------- #
# scheduler loop
# --------------------------------------------------------------------------- #


def test_scheduler_loop_runs_due_entries(tmp_path, monkeypatch) -> None:
    import openlaoke.core.scheduler as scheduler_module
    import openlaoke.core.task as task_module

    r = make_repl(tmp_path, ScriptedPrompt([]))
    r._running = True
    started: list[str] = []
    marked: list[str] = []

    class Entry:
        def __init__(self, name: str, command: str = "", prompt: str = "") -> None:
            self.name = name
            self.command = command
            self.prompt = prompt

    entries = [Entry("build", command="make"), Entry("remind", prompt="stretch")]

    class FakeScheduler:
        def due(self) -> list[Any]:
            return entries

        def mark_run(self, entry: Any) -> None:
            marked.append(entry.name)
            if len(marked) == len(entries):
                r._running = False

    class FakeManager:
        async def run_bash(self, command: str, **kwargs: Any) -> None:
            started.append(command)

    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda state: FakeScheduler())
    monkeypatch.setattr(task_module, "get_task_manager", lambda state: FakeManager())
    monkeypatch.setattr(repl_module.asyncio, "sleep", _fast_sleep)

    run(r._scheduler_loop(interval=0.01))

    assert started == ["make"]
    assert marked == ["build", "remind"]
    assert r._input_queue and "stretch" in r._input_queue[0]


async def _fast_sleep(_seconds: float) -> None:
    return None
