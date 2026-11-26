"""Tests for bot mode: roster, chats, rooms, delivery and routines."""

from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace

import pytest
from rich.console import Console

from openlaoke.commands import bot_commands
from openlaoke.commands.base import CommandContext
from openlaoke.commands.registry import get_command, register_all
from openlaoke.core import bot_mode as bot_module
from openlaoke.core.bot_mode import (
    CURRENT_BOT,
    MAX_BOTS,
    MAX_GROUP_MEMBERS,
    BotMode,
    Room,
    _merge_consecutive,
    get_bot_mode,
    parse_mentions,
    slug,
)
from openlaoke.core.repl import REPL
from openlaoke.core.scheduler import ScheduleEntry, Scheduler
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.message_agent_tool import MessageAgentTool
from openlaoke.types.core_types import TokenUsage
from openlaoke.utils.theme import ThemeManager


class FakeClient:
    """Scripted provider: one reply string per request, or an exception."""

    def __init__(self, factory: Factory, key: str) -> None:
        self.factory = factory
        self.key = key

    async def send_message(self, **kwargs):
        snapshot = dict(kwargs)
        snapshot["messages"] = [dict(row) for row in kwargs.get("messages", [])]
        self.factory.calls.setdefault(self.key, []).append(snapshot)
        script = self.factory.scripts.setdefault(self.key, [])
        item = script.pop(0) if script else "(script empty)"
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(content=item, tool_uses=[]), TokenUsage(), None

    async def close(self) -> None:
        return None


class Factory:
    def __init__(self, scripts: dict[str, list] | None = None) -> None:
        self.scripts = {slug(key): list(value) for key, value in (scripts or {}).items()}
        self.calls: dict[str, list[dict]] = {}

    def __call__(self, profile) -> FakeClient:
        return FakeClient(self, slug(profile.name))

    def prompts(self, name: str) -> list[str]:
        return [call["system_prompt"] for call in self.calls.get(slug(name), [])]

    def messages(self, name: str) -> list[list[dict]]:
        return [call["messages"] for call in self.calls.get(slug(name), [])]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_module, "BOTS_ROOT", str(tmp_path / "bots"))
    state = create_app_state(cwd=str(tmp_path))
    mode = get_bot_mode(state)
    factory = Factory()
    mode._client_factory = factory
    return mode, state, factory, tmp_path


def run(coro):
    return asyncio.run(coro)


def make_ctx(state) -> ToolContext:
    return ToolContext(app_state=state, tool_use_id="bot-test")


# -- roster ------------------------------------------------------------------


def test_create_resolve_and_persist(env) -> None:
    mode, _state, _factory, _tmp = env
    profile = mode.create_bot(
        "Alice", title="Lead engineer", description="plans the work", model="m1", section="core"
    )
    assert profile.handle == "@alice"
    assert profile.face
    assert mode.get_bot("@ALICE") is profile
    assert mode.get_bot("Lead engineer") is profile
    assert "@alice" in mode.roster_text()

    again = BotMode(mode.app_state, root=mode.root)
    assert again.get_bot("alice") is not None
    assert again.get_bot("alice").title == "Lead engineer"


def test_hide_show_and_remove_archives(env) -> None:
    mode, _state, _factory, _tmp = env
    mode.create_bot("Alice", title="Lead")
    mode.create_bot("Bob")
    mode.hide_bot("alice")
    assert "alice" not in mode.roster_text()
    assert "alice" in mode.roster_text(include_hidden=True)
    mode.hide_bot("alice", hidden=False)
    assert "alice" in mode.roster_text()

    mode.save_history("alice", [{"role": "user", "content": "hi"}])
    archived = mode.remove_bot("alice")
    assert archived and "archived" in archived
    assert mode.get_bot("alice") is None


def test_removing_a_bot_prunes_room_membership(env) -> None:
    mode, _state, _factory, _tmp = env
    for name in ("Alice", "Bob", "Carol"):
        mode.create_bot(name)
    mode.create_room("Dev", ["Alice", "Bob", "Carol"])
    mode.remove_bot("carol")
    assert mode.get_room("dev").members == ["Alice", "Bob"]


def test_validation_rules(env) -> None:
    mode, _state, _factory, _tmp = env
    mode.create_bot("Alice")
    with pytest.raises(ValueError, match="already exists"):
        mode.create_bot("alice")
    with pytest.raises(ValueError, match="longer"):
        mode.create_bot("x" * 41)
    with pytest.raises(ValueError, match="permission"):
        mode.create_bot("Bad", permission="root")
    with pytest.raises(ValueError, match="cannot set"):
        mode.update_bot("alice", nope=1)
    for index in range(MAX_BOTS - 1):
        mode.create_bot(f"bot{index}")
    with pytest.raises(ValueError, match="full"):
        mode.create_bot("one-too-many")


def test_mentions_parse_handles_and_user() -> None:
    assert parse_mentions("ask @alice and @bob, thanks") == ["alice", "bob"]
    assert parse_mentions("no handles here") == []
    assert parse_mentions("@alice. then @alice again") == ["alice"]


def test_avatar_is_stable() -> None:
    mode_face = bot_module.avatar_for("Alice")
    assert mode_face == bot_module.avatar_for("Alice")
    assert mode_face != bot_module.avatar_for("Bob")


def test_merge_consecutive_collapses_same_role() -> None:
    merged = _merge_consecutive(
        [
            {"role": "user", "content": "one"},
            {"role": "user", "content": "two"},
            {"role": "assistant", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
    )
    assert [row["role"] for row in merged] == ["user", "assistant"]
    assert merged[0]["content"] == "one\n\ntwo"
    assert merged[1]["content"] == "a\n\nb"


# -- bot chats ---------------------------------------------------------------


def test_ask_uses_identity_model_and_history(env) -> None:
    mode, state, factory, _tmp = env
    mode.create_bot("Alice", title="Lead", description="plans", persona="Be terse.", model="m1")
    factory.scripts["alice"] = ["first reply", "second reply"]

    assert run(mode.ask("alice", "hello")) == "first reply"
    assert run(mode.ask("alice", "again")) == "second reply"

    first_call, second_call = factory.calls["alice"]
    assert "You are **Alice** (@alice)" in first_call["system_prompt"]
    assert "You are Alice (@alice), a named bot" in first_call["system_prompt"]
    assert "Be terse." in first_call["system_prompt"]
    assert first_call["model"] == "m1"
    assert second_call["messages"][0] == {"role": "user", "content": "hello"}
    assert second_call["messages"][1] == {"role": "assistant", "content": "first reply"}
    assert second_call["messages"][-1] == {"role": "user", "content": "again"}

    history = mode.history("alice")
    assert [row["role"] for row in history] == ["user", "assistant", "user", "assistant"]
    assert state.cost_info.total_cost == 0.0


def test_ask_uses_session_model_when_bot_has_none(env) -> None:
    mode, state, factory, _tmp = env
    state.session_config.model = "session-model"
    mode.create_bot("Alice")
    factory.scripts["alice"] = ["ok"]
    run(mode.ask("alice", "hi"))
    assert factory.calls["alice"][0]["model"] == "session-model"


def test_silent_reply_is_returned_empty_but_kept(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    factory.scripts["alice"] = ["[SILENT]"]
    assert run(mode.ask("alice", "nothing to say?")) == ""
    assert mode.history("alice")[-1]["content"] == "[SILENT]"


def test_provider_error_becomes_a_readable_reply(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    factory.scripts["alice"] = [RuntimeError("provider exploded")]
    reply = run(mode.ask("alice", "hi"))
    assert "bot @alice error" in reply and "provider exploded" in reply
    assert mode.history("alice")[-1]["role"] == "user"


def test_teammates_appear_in_the_prompt(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob", title="Researcher", description="finds papers")
    factory.scripts["alice"] = ["ok"]
    run(mode.ask("alice", "who else is here?"))
    prompt = factory.prompts("alice")[0]
    assert "@bob" in prompt and "finds papers" in prompt
    assert "MessageAgent" in prompt


def test_readonly_bot_gets_a_restricted_allow_list(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Watcher", permission="readonly")
    factory.scripts["watcher"] = ["ok"]
    run(mode.ask("watcher", "look"))
    allowed = factory.calls["watcher"][0]["tools"]
    assert allowed is not None  # schemas are still offered
    profile = mode.get_bot("watcher")
    assert "Write" not in mode._allowed_tools(profile)
    assert "Read" in mode._allowed_tools(profile)


def test_clear_history_archives_it(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    factory.scripts["alice"] = ["one"]
    run(mode.ask("alice", "hi"))
    archived = mode.clear_history("alice")
    assert archived and "chat." in archived
    assert mode.history("alice") == []
    assert "No messages" in mode.history_text("alice")


# -- delivery ----------------------------------------------------------------


def test_message_agent_queues_and_delivers(env) -> None:
    mode, state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob", title="Researcher")
    tool = MessageAgentTool(mode)
    ctx = make_ctx(state)

    token = CURRENT_BOT.set("alice")
    try:
        queued = run(tool.call(ctx, target="@bob", message="look this up"))
        assert not queued.is_error
        assert "Queued for @bob" in queued.content
        assert len(mode.inbox("bob")) == 1

        factory.scripts["bob"] = ["bob says hi"]
        waited = run(tool.call(ctx, target="bob", message="and now?", wait=True))
        assert "bob says hi" in waited.content
    finally:
        CURRENT_BOT.reset(token)

    assert mode.inbox("bob", status="delivered")[0]["reply"] == "bob says hi"
    assert len(mode.inbox("bob", status="pending")) == 1
    assert mode.history("bob")[0]["content"].startswith("Message from 🤖 alice (@alice):")


def test_message_agent_rejects_bad_targets(env) -> None:
    mode, state, _factory, _tmp = env
    mode.create_bot("Alice")
    tool = MessageAgentTool(mode)
    ctx = make_ctx(state)

    outside = run(tool.call(ctx, target="alice", message="hi"))
    assert outside.is_error and "only works inside" in outside.content

    token = CURRENT_BOT.set("alice")
    try:
        assert run(tool.call(ctx, target="alice", message="hi")).is_error
        assert run(tool.call(ctx, target="ghost", message="hi")).is_error
        assert run(tool.call(ctx, target="", message="hi")).is_error
        assert run(tool.call(ctx, target="alice", message=" ")).is_error
    finally:
        CURRENT_BOT.reset(token)


def test_bot_provider_override_does_not_mutate_session_config(env, monkeypatch) -> None:
    from openlaoke.types.providers import (
        MultiProviderConfig,
        ProviderConfig,
        ProviderType,
    )

    mode, state, _factory, _tmp = env

    def provider(name: str) -> ProviderConfig:
        return ProviderConfig(
            provider_type=ProviderType.OPENAI,
            base_url=f"https://{name}.example/v1",
            default_model=f"{name}-model",
            api_key="test-key",
        )

    config = MultiProviderConfig(
        providers={"alpha": provider("alpha"), "beta": provider("beta")},
        active_provider="alpha",
    )
    state.multi_provider_config = config
    profile = mode.create_bot("Alice", provider="beta")
    mode._client_factory = None

    captured: dict[str, object] = {}

    class FakeMP:
        def __init__(self, cfg, proxy=None) -> None:
            captured["config"] = cfg
            captured["proxy"] = proxy

    monkeypatch.setattr("openlaoke.core.multi_provider_api.MultiProviderClient", FakeMP)
    mode._make_client(profile)
    assert captured["config"].active_provider == "beta"
    assert config.active_provider == "alpha"

    mode.update_bot("alice", provider="ghost")
    with pytest.raises(ValueError, match="not configured"):
        mode._make_client(mode.get_bot("alice"))


def test_message_agent_refuses_to_wait_on_a_busy_bot(env) -> None:
    mode, state, _factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    tool = MessageAgentTool(mode)
    ctx = make_ctx(state)

    async def scenario():
        token = CURRENT_BOT.set("alice")
        lock = mode._lock("chat:bob")
        await lock.acquire()
        try:
            result = await tool.call(ctx, target="bob", message="hi", wait=True)
        finally:
            lock.release()
            CURRENT_BOT.reset(token)
        return result

    result = asyncio.run(scenario())
    assert result.is_error
    assert "mid-turn" in result.content


def test_deliver_and_drain(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    mode.create_bot("Carol")
    factory.scripts["bob"] = ["bob reply"]
    factory.scripts["carol"] = ["carol reply"]
    mode.enqueue("alice", "bob", "question for bob")
    mode.enqueue("alice", "carol", "question for carol")

    delivered = run(mode.deliver("bob"))
    assert delivered == [{"bot": "Bob", "from": "alice", "reply": "bob reply"}]
    assert mode.inbox("bob") == []
    assert len(mode.inbox("carol")) == 1

    drained = run(mode.drain())
    assert [row["bot"] for row in drained] == ["Carol"]
    assert drained[0]["reply"] == "carol reply"


# -- rooms -------------------------------------------------------------------


def test_room_round_robin_and_persistence(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    room = mode.create_room("Dev", ["Alice", "Bob"])
    factory.scripts["alice"] = ["alice here"]
    factory.scripts["bob"] = ["bob here"]

    turns = run(mode.room_send("dev", "hello team"))
    assert [(turn.member, turn.round) for turn in turns] == [("Alice", 1), ("Bob", 1)]
    log = mode.room_log_text("dev")
    assert "alice here" in log and "bob here" in log

    alice_history = mode.room_history(room, mode.get_bot("alice"))
    assert [row["role"] for row in alice_history] == ["user", "assistant"]

    reloaded = BotMode(mode.app_state, root=mode.root)
    assert reloaded.get_room("dev").members == ["Alice", "Bob"]
    assert len(reloaded.get_room("dev").log) == 3


def test_room_mention_handoff_and_one_turn_per_bot(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    mode.create_room("Dev", ["Alice", "Bob"])
    factory.scripts["alice"] = ["this needs @bob", "should not run"]
    factory.scripts["bob"] = ["bob answering"]

    turns = run(mode.room_send("dev", "@alice take a look"))
    assert [(turn.member, turn.round) for turn in turns] == [("Alice", 1), ("Bob", 2)]
    assert len(factory.calls["alice"]) == 1


def test_room_user_mention_stops_and_flags(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    mode.create_room("Dev", ["Alice", "Bob"])
    factory.scripts["alice"] = ["I need @user to decide"]
    factory.scripts["bob"] = ["unused"]

    turns = run(mode.room_send("dev", "@alice which option?"))
    assert len(turns) == 1
    assert mode.get_room("dev").needs_user is True
    assert "waiting on you" in mode.room_log_text("dev")


def test_room_silence_and_round_cap(env) -> None:
    mode, _state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    mode.create_room("Dev", ["Alice", "Bob"])
    factory.scripts["alice"] = ["[SILENT]", "handing to @bob"]
    factory.scripts["bob"] = ["bob once", "bob twice"]

    first = run(mode.room_send("dev", "anyone?", max_rounds=1))
    assert [(turn.member, turn.round) for turn in first] == [("Bob", 1)]

    second = run(mode.room_send("dev", "@alice again", max_rounds=3))
    assert [(turn.member, turn.round) for turn in second] == [("Alice", 1), ("Bob", 2)]


def test_room_validation_and_archiving(env) -> None:
    mode, _state, _factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    with pytest.raises(ValueError, match="at least two"):
        mode.create_room("Solo", ["Alice"])
    for index in range(MAX_GROUP_MEMBERS):
        mode.create_bot(f"extra{index}")
    with pytest.raises(ValueError, match="at most"):
        mode.create_room("Big", [bot.name for bot in mode.list_bots()])
    mode.create_room("Dev", ["Alice", "Bob"])
    with pytest.raises(ValueError, match="already exists"):
        mode.create_room("dev", ["Alice", "Bob"])
    with pytest.raises(ValueError, match="no room"):
        mode.require_room("ghost")

    mode.activate_room("dev")
    archived = mode.remove_room("dev")
    assert archived and "room-" in archived
    assert mode.active_room == ""
    assert mode.get_room("dev") is None


def test_room_member_add_remove_needs_two(env) -> None:
    mode, _state, _factory, _tmp = env
    for name in ("Alice", "Bob", "Carol"):
        mode.create_bot(name)
    room: Room = mode.create_room("Dev", ["Alice", "Bob"])
    room.members.append("Carol")
    mode.save_room(room)
    assert "carol" in mode.rooms_text()
    assert "3 bot(s)" in mode.rooms_text()


def test_activation_state(env) -> None:
    mode, _state, _factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    mode.create_room("Dev", ["Alice", "Bob"])
    mode.activate_bot("alice")
    assert mode.enabled and mode.active_room == ""
    assert "Active bot" in mode.roster_text()
    mode.activate_room("dev")
    assert mode.enabled and mode.active_bot == ""
    assert "Active room" in mode.roster_text()
    mode.deactivate()
    assert not mode.enabled


# -- commands ----------------------------------------------------------------


@pytest.fixture
def runner(env, monkeypatch):
    mode, state, factory, tmp = env
    register_all()
    scheduler = Scheduler(path=str(tmp / "schedule.json"))
    monkeypatch.setattr(bot_commands, "get_scheduler", lambda _state: scheduler)

    async def call(args: str):
        command = get_command("bot")
        assert command is not None
        return await command.execute(CommandContext(app_state=state, args=args))

    return call, mode, factory, scheduler


def test_command_roster_lifecycle(runner) -> None:
    call, mode, factory, _scheduler = runner

    created = run(call("new Alice --title 'Lead engineer' --desc 'plans work' --model m1"))
    assert "Created" in created.message
    assert "Lead engineer" in run(call("show alice")).message

    inline = run(call("new Bob --title=Reviewer --section=core --readonly"))
    assert "Created" in inline.message
    assert mode.get_bot("bob").permission == "readonly"
    assert mode.get_bot("bob").section == "core"

    edited = run(call("edit alice title=Architect skills=a,b permission=readonly"))
    assert "Architect" in edited.message
    assert mode.get_bot("alice").permission == "readonly"
    assert mode.get_bot("alice").skills == ["a", "b"]

    assert "alice" in run(call("use alice")).message
    assert mode.active_bot == "alice"
    assert "Bot mode off" in run(call("off")).message
    assert not mode.enabled

    assert "hidden" in run(call("hide alice")).message
    assert "alice" not in run(call("list")).message
    assert "alice" in run(call("list all")).message
    assert "visible" in run(call("unhide alice")).message

    factory.scripts["alice"] = ["dm reply"]
    assert "dm reply" in run(call("dm alice hello")).message
    assert "dm reply" in run(call("history alice")).message
    assert "fresh chat" in run(call("clear alice")).message
    assert "Reloaded" in run(call("reload")).message
    assert "Removed" in run(call("rm alice")).message


def test_command_errors_are_reported(runner) -> None:
    call, _mode, _factory, _scheduler = runner
    for args in ("new", "use ghost", "show ghost", "edit alice", "bogus", "room new x alice"):
        result = run(call(args))
        assert not result.success, args
        assert result.message


def test_command_rooms(runner) -> None:
    call, mode, _factory, _scheduler = runner
    run(call("new Alice"))
    run(call("new Bob"))
    run(call("new Carol"))

    created = run(call("room new Dev Alice Bob"))
    assert "#dev" in created.message
    assert "carol" in run(call("room add dev carol")).message
    assert "carol" in run(call("room show dev")).message
    assert "3 bot(s)" in run(call("room list")).message
    assert "Removed" in run(call("room remove dev carol")).message
    used = run(call("room use dev"))
    assert "#dev" in used.message
    assert mode.active_room == "dev"
    assert "normal agent" in run(call("room off")).message
    assert "Removed room" in run(call("room rm dev")).message


def test_command_routines(runner) -> None:
    call, mode, _factory, scheduler = runner
    run(call("new Alice"))
    added = run(call("routine add alice 'every 30m' summarize the inbox"))
    assert "Routine" in added.message
    assert len(scheduler.entries) == 1
    assert scheduler.entries[0].name.startswith("[bot:alice]")
    assert "summarize the inbox" in run(call("routine list")).message

    entry_id = scheduler.entries[0].id
    assert entry_id in run(call(f"routine rm {entry_id}")).message
    assert scheduler.entries == []
    assert "No bot routines" in run(call("routine list")).message
    assert not run(call("routine rm nope")).success


# -- REPL and CLI integration ------------------------------------------------


def _repl_stub(state):
    repl = object.__new__(REPL)
    repl.app_state = state
    stream = io.StringIO()
    repl.console = Console(file=stream, record=True, width=120, force_terminal=False)
    repl._theme = ThemeManager("dark")
    return repl, stream


def test_repl_routes_plain_input_to_the_active_bot(env) -> None:
    mode, state, factory, _tmp = env
    mode.create_bot("Alice")
    factory.scripts["alice"] = ["bot reply"]
    mode.activate_bot("alice")
    repl, stream = _repl_stub(state)

    handled = run(repl._handle_bot_input("hello"))
    assert handled
    assert "bot reply" in stream.getvalue()
    assert mode.history("alice")[0]["content"] == "hello"


def test_repl_routes_plain_input_to_the_active_room(env) -> None:
    mode, state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    mode.create_room("Dev", ["Alice", "Bob"])
    factory.scripts["alice"] = ["alice line"]
    factory.scripts["bob"] = ["bob line"]
    mode.activate_room("dev")
    repl, stream = _repl_stub(state)

    assert run(repl._handle_bot_input("hello room"))
    output = stream.getvalue()
    assert "@alice" in output and "alice line" in output
    assert "@bob" in output and "bob line" in output


def test_repl_input_routes_commands_and_bot_chat(env) -> None:
    from types import SimpleNamespace

    mode, state, factory, _tmp = env
    repl, stream = _repl_stub(state)
    factory.scripts["alice"] = ["routed reply"]
    register_all()

    queue = ["/bot new Alice", "/bot use alice", "hello", "/bot off"]

    async def fake_input():
        return SimpleNamespace(
            is_exit=False,
            is_picker=False,
            is_lang_picker=False,
            is_toggle_thinking=False,
            text=queue.pop(0),
        )

    repl._prompt_manager = SimpleNamespace(get_user_input=fake_input)
    repl._running = True

    async def scenario():
        for _ in range(4):
            await repl._handle_input()

    asyncio.run(scenario())
    output = stream.getvalue()
    assert "Created" in output
    assert "routed reply" in output
    assert "Bot mode off" in output
    assert mode.history("alice")[0]["content"] == "hello"
    assert not mode.enabled


def test_repl_stays_out_of_the_way_when_bot_mode_is_off(env) -> None:
    mode, state, _factory, _tmp = env
    mode.create_bot("Alice")
    repl, _stream = _repl_stub(state)
    assert run(repl._handle_bot_input("hello")) is False


def test_repl_runs_bot_routines_and_drains_mail(env) -> None:
    mode, state, factory, _tmp = env
    mode.create_bot("Alice")
    mode.create_bot("Bob")
    factory.scripts["alice"] = ["routine done", "reply to bob"]
    factory.scripts["bob"] = ["bob answer"]
    mode.enqueue("bob", "alice", "question")
    repl, stream = _repl_stub(state)

    entry = ScheduleEntry(
        id="s1", name=BotMode.routine_name("alice", "daily digest"), when="daily 09:00"
    )
    entry.prompt = "summarize"
    notice = run(repl._run_bot_routine(entry))
    assert notice and "routine done" in notice
    # the queued message from Bob was delivered after the routine
    output = stream.getvalue()
    assert "reply to bob" in output
    assert mode.inbox("alice", status="delivered")

    plain = ScheduleEntry(id="s2", name="plain reminder", when="daily 10:00")
    plain.prompt = "drink water"
    assert run(repl._run_bot_routine(plain)) is None


def test_cli_bot_prompt_runs_a_single_turn(env, monkeypatch) -> None:
    from openlaoke.entrypoints import cli

    mode, state, factory, _tmp = env
    mode.create_bot("Alice")
    factory.scripts["alice"] = ["cli reply"]

    run(cli._run_bot_prompt("hello from cli", state, state.app_config, "alice", None))
    assert factory.messages("alice")[0][-1]["content"] == "hello from cli"


def test_cli_bot_prompt_reports_unknown_bot(env) -> None:
    from openlaoke.entrypoints import cli

    _mode, state, _factory, _tmp = env
    with pytest.raises(SystemExit):
        run(cli._run_bot_prompt("hi", state, None, "ghost", None))


# -- command error paths and edges -------------------------------------------


def test_flag_parsing_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="unknown flag"):
        bot_commands._parse_flags(["Alice", "--colour", "red"])
    with pytest.raises(ValueError, match="needs a value"):
        bot_commands._parse_flags(["Alice", "--title"])

    positional, flags = bot_commands._parse_flags(
        ["Alice", "--title=Lead", "--readonly", "--skills", "a,b"]
    )
    assert positional == ["Alice"]
    assert flags == {"title": "Lead", "readonly": "true", "skills": "a,b"}


def test_truthy_values() -> None:
    for value in ("1", "true", "yes", "on", " TRUE "):
        assert bot_commands._truthy(value) is True
    for value in ("0", "false", "", "no", "off"):
        assert bot_commands._truthy(value) is False


def test_profile_text_shows_a_persona_when_set(runner) -> None:
    call, mode, _factory, _scheduler = runner
    run(call("new Alice --persona 'You are terse.'"))

    text = run(call("show alice")).message

    assert "persona:     You are terse." in text
    assert "inbox:" in text


def test_command_handles_quotes_and_empty_help(runner) -> None:
    call, _mode, _factory, _scheduler = runner

    assert "Bot mode:" in run(call("help")).message
    assert "Bot mode:" in run(call("?")).message
    broken = run(call('new "unclosed'))
    assert broken.success is False
    assert "Error:" in broken.message


def test_every_subcommand_reports_missing_arguments(runner) -> None:
    call, _mode, _factory, _scheduler = runner

    for args in (
        "new",
        "use",
        "show",
        "edit",
        "hide",
        "unhide",
        "rm",
        "history",
        "clear",
        "dm alice",
        "room use",
        "room show",
        "room add dev",
        "room rm",
        "routine add alice every",
        "routine rm",
    ):
        result = run(call(args))
        assert result.success is False, args
        assert "usage" in result.message.lower(), args


def test_edit_rejects_bad_pairs_and_unknown_permission(runner) -> None:
    call, mode, _factory, _scheduler = runner
    run(call("new Alice"))

    no_pair = run(call("edit alice title"))
    assert no_pair.success is False
    assert "expected key=value" in no_pair.message

    bad_permission = run(call("edit alice permission=admin"))
    assert bad_permission.success is False
    assert "permission must be auto or readonly" in bad_permission.message

    nothing = run(call("edit alice"))
    assert "nothing to change" in nothing.message

    assert mode.get_bot("alice").permission == "auto"


def test_edit_accepts_the_desc_alias_and_hidden_flag(runner) -> None:
    call, mode, _factory, _scheduler = runner
    run(call("new Alice"))

    run(call("edit alice desc=short hidden=yes"))

    profile = mode.get_bot("alice")
    assert profile.description == "short"
    assert profile.hidden is True


def test_history_limit_is_clamped(runner) -> None:
    call, _mode, factory, _scheduler = runner
    run(call("new Alice"))
    factory.scripts["alice"] = ["one"]
    run(call("dm alice hello"))  # the chat has to exist before history shows it

    for suffix in ("0", "9999", "notanumber"):
        assert "one" in run(call(f"history alice {suffix}")).message, suffix


def test_room_errors_and_limits(runner) -> None:
    call, mode, _factory, _scheduler = runner
    for name in ("Alice", "Bob", "Carol"):
        run(call("new " + name))
    run(call("room new dev Alice Bob"))

    too_few = run(call("room new solo Alice"))
    assert too_few.success is False
    assert "up to" in too_few.message

    unknown = run(call("room dance dev"))
    assert unknown.success is False
    assert "unknown room action" in unknown.message

    assert "already in" in run(call("room add dev alice")).message
    assert "not in" in run(call("room remove dev carol")).message

    # Adding a third bot works, but removing back down to one is refused.
    run(call("room add dev carol"))
    run(call("room remove dev carol"))
    assert "at least two bots" in run(call("room remove dev alice")).message


def test_a_room_cannot_exceed_the_member_cap(runner) -> None:
    call, mode, _factory, _scheduler = runner
    for index in range(MAX_GROUP_MEMBERS + 2):
        run(call(f"new Bot{index}"))
    members = [f"Bot{index}" for index in range(MAX_GROUP_MEMBERS - 1)]
    run(call("room new big " + " ".join(f"bot{i}" for i in range(2))))
    room = mode.get_room("big")
    assert room is not None
    for index in range(2, MAX_GROUP_MEMBERS):
        run(call(f"room add big bot{index}"))

    overflow = run(call(f"room add big bot{MAX_GROUP_MEMBERS}"))

    assert overflow.success is False
    assert "at most" in overflow.message
    assert members  # keep the fixture bots referenced


def test_routine_errors(runner) -> None:
    call, mode, _factory, scheduler = runner
    run(call("new Alice"))

    assert "usage" in run(call("routine add alice every")).message.lower()

    missing = run(call("routine rm nope"))
    assert missing.success is False
    assert "no bot routine matching" in missing.message

    unknown = run(call("routine dance"))
    assert unknown.success is False
    assert "unknown routine action" in unknown.message

    # A plain (non-bot) schedule entry is not listed as a bot routine.
    scheduler.add(name="daily standup", when="every 1h", prompt="report")
    assert "No bot routines yet." in run(call("routine list")).message


def test_bare_bot_prints_the_roster_and_new_requires_a_name(runner) -> None:
    call, _mode, _factory, _scheduler = runner
    run(call("new Alice"))

    assert "alice" in run(call("")).message
    nameless = run(call("new --title OnlyFlags"))
    assert nameless.success is False
    assert "needs a name" in nameless.message


def test_room_log_accepts_a_limit(runner) -> None:
    call, _mode, _factory, _scheduler = runner
    run(call("new Alice"))
    run(call("new Bob"))
    run(call("room new dev Alice Bob"))

    assert "#dev" in run(call("room show dev 5")).message
