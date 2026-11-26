"""Tests for the slash commands in commands/base.py.

Every command is driven through its real execute() with a real AppState built
by create_app_state (cwd pointing at a tmp dir), so the wiring into app state
is exercised rather than mocked. Anything that would touch ~/.openlaoke
(config writes, sessions, exports) is redirected into tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openlaoke.commands import base as cmd
from openlaoke.commands.base import (
    BatchCommand,
    CacheCommand,
    ClearCommand,
    CommandContext,
    CompactCommand,
    EditsCommand,
    ExitCommand,
    ExportCommand,
    HelpCommand,
    HistoryCommand,
    McpCommand,
    MemoryCommand,
    ModeCommand,
    RestoreCommand,
    ResumeCommand,
    ScheduleCommand,
    SearchCommand,
    SessionsCommand,
    SettingsCommand,
    SleepCommand,
    StatsCommand,
    ThemeCommand,
    ThinkingCommand,
    TodosCommand,
)
from openlaoke.core.state import create_app_state
from openlaoke.types.core_types import MessageRole, UserMessage


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path))


def ctx(state, args: str = "") -> CommandContext:
    return CommandContext(app_state=state, args=args)


@pytest.fixture(autouse=True)
def isolated_file_history(tmp_path, monkeypatch):
    """Keep the snapshot store out of ~/.openlaoke."""
    monkeypatch.setattr(
        "openlaoke.utils.file_history.HISTORY_DIR", str(tmp_path / "file_history")
    )


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Keep the memory store out of ~/.openlaoke (it is keyed by project cwd)."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    monkeypatch.setattr("openlaoke.core.memory_store.MEMORY_DIR", str(memory_dir))
    return memory_dir


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Keep config writes out of the real ~/.openlaoke."""
    saved: list[object] = []
    class Cfg:
        def __init__(self) -> None:
            self.mode = "balanced"
            self.reasoning_effort = None
            self.flag = True
            self.count = 3
            self.ratio = 0.5
            self.label = "text"
            self.nothing = None
            self._private = "hidden"

    config = Cfg()

    monkeypatch.setattr(cmd, "load_config", lambda: config, raising=False)
    monkeypatch.setattr("openlaoke.utils.config.load_config", lambda: config)
    monkeypatch.setattr(
        "openlaoke.utils.config.save_config", lambda c: saved.append(c)
    )
    return saved


# --------------------------------------------------------------------------- #
# Simple commands
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_help_lists_commands_and_skips_hidden(monkeypatch, state) -> None:
    class Visible(cmd.SlashCommand):
        name = "visible"
        description = "does things"
        aliases = ["v"]

        async def execute(self, ctx):  # pragma: no cover - not called
            return cmd.CommandResult()

    class Hidden(Visible):
        name = "hidden"
        hidden = True

    monkeypatch.setattr(
        "openlaoke.commands.registry.get_all_commands", lambda: [Visible(), Hidden()]
    )
    result = await HelpCommand().execute(ctx(state))
    assert result.success is True
    assert "/visible (/v) - does things" in result.message
    assert "hidden" not in result.message
    assert "Use /quit to exit." in result.message


@pytest.mark.asyncio
async def test_exit_sets_the_exit_flag(state) -> None:
    result = await ExitCommand().execute(ctx(state))
    assert result.should_exit is True


@pytest.mark.asyncio
async def test_clear_empties_the_history(state) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="hi"))
    result = await ClearCommand().execute(ctx(state))
    assert state.messages == []
    assert result.should_clear is True
    assert result.message == "Screen cleared."


@pytest.mark.asyncio
async def test_thinking_on_off_show_and_status(state) -> None:
    command = ThinkingCommand()
    assert "Thinking display: off" in (await command.execute(ctx(state, "off"))).message
    assert state.thinking_enabled is False
    assert "Thinking display: on" in (await command.execute(ctx(state, "on"))).message
    assert state.thinking_enabled is True

    state.last_thinking = "deliberations"
    assert (await command.execute(ctx(state, "show"))).message == "deliberations"
    state.last_thinking = ""
    assert "no thinking recorded" in (await command.execute(ctx(state, "last"))).message

    status = (await command.execute(ctx(state))).message
    assert "on" in status
    assert "Use /thinking on|off|show." in status


# --------------------------------------------------------------------------- #
# /settings
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_settings_without_args_dumps_scalars_only(state) -> None:
    message = (await SettingsCommand().execute(ctx(state))).message
    assert "Settings:" in message
    assert "mode = 'balanced'" in message
    assert "count = 3" in message
    assert "_private" not in message
    # Container values are skipped rather than dumped.
    assert "Usage: /settings <key> <value>" in message


@pytest.mark.asyncio
async def test_settings_single_key_reports_value(state) -> None:
    assert (await SettingsCommand().execute(ctx(state, "count"))).message == "count = 3"
    assert "None" in (await SettingsCommand().execute(ctx(state, "missing"))).message


@pytest.mark.asyncio
async def test_settings_unknown_key_is_rejected(state, isolated_config) -> None:
    result = await SettingsCommand().execute(ctx(state, "nope 1"))
    assert result.success is False
    assert "Unknown setting: nope" in result.message
    assert isolated_config == []


@pytest.mark.asyncio
async def test_settings_parses_bool_int_float_and_string(state, isolated_config) -> None:
    command = SettingsCommand()
    await command.execute(ctx(state, "flag false"))
    await command.execute(ctx(state, "count 42"))
    await command.execute(ctx(state, "ratio 0.25"))
    await command.execute(ctx(state, "label hello world"))
    config = isolated_config[0]
    assert config.flag is False
    assert config.count == 42
    assert config.ratio == 0.25
    assert config.label == "hello world"
    assert len(isolated_config) == 4


@pytest.mark.asyncio
async def test_settings_falls_back_to_raw_string_on_bad_number(state, isolated_config) -> None:
    result = await SettingsCommand().execute(ctx(state, "count not-a-number"))
    assert result.message == "count = 'not-a-number'"
    assert isolated_config[0].count == "not-a-number"


# --------------------------------------------------------------------------- #
# /mode
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_mode_without_args_lists_modes(state) -> None:
    message = (await ModeCommand().execute(ctx(state))).message
    assert "Harness mode: balanced" in message
    assert "Switch: /mode <name>" in message


@pytest.mark.asyncio
async def test_mode_show_alias_lists_modes(state) -> None:
    for alias in ("list", "ls", "show"):
        assert "Harness mode:" in (await ModeCommand().execute(ctx(state, alias))).message


@pytest.mark.asyncio
async def test_mode_rejects_unknown_name(state) -> None:
    result = await ModeCommand().execute(ctx(state, "turbo-nonsense"))
    assert result.success is False
    assert "Unknown mode: turbo-nonsense" in result.message
    assert "Valid modes:" in result.message


@pytest.mark.asyncio
async def test_mode_switch_updates_state_config_and_guard(state, isolated_config) -> None:
    invalidated: list[bool] = []
    state._cache_guard = type("G", (), {"invalidate": lambda _self: invalidated.append(True)})()

    result = await ModeCommand().execute(ctx(state, "pi"))

    assert result.success is True
    assert result.message.startswith("Harness mode: pi")
    assert state.harness_mode == "pi"
    assert state.max_steps > 0
    assert isolated_config[0].mode == "pi"
    assert invalidated == [True]


@pytest.mark.asyncio
async def test_mode_switch_without_a_guard_or_session_config(state, isolated_config) -> None:
    state._cache_guard = None
    state.session_config = None
    result = await ModeCommand().execute(ctx(state, "balanced"))
    assert result.success is True


# --------------------------------------------------------------------------- #
# /compact
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_compact_reports_the_message_delta(state) -> None:
    for i in range(6):
        state.messages.append(UserMessage(role=MessageRole.USER, content=f"message {i} " + "x" * 200))
    result = await CompactCommand().execute(ctx(state))
    assert result.message.startswith("Compacted context: 6 ->")
    assert result.success is True


@pytest.mark.asyncio
async def test_compact_on_a_short_history_is_a_noop(state) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="hi"))
    result = await CompactCommand().execute(ctx(state))
    assert result.message == "Compacted context: 1 -> 1 message(s)."
    assert len(state.messages) == 1


# --------------------------------------------------------------------------- #
# /sessions, /resume, /search
# --------------------------------------------------------------------------- #


def make_session_info(tmp_path, session_id: str = "session_a", created: float = 0.0, count: int = 3):
    path = tmp_path / f"{session_id}.json"
    path.write_text("{}", encoding="utf-8")
    return type(
        "Info",
        (),
        {
            "session_id": session_id,
            "created_at": created,
            "message_count": count,
            "model": "claude-sonnet-4",
            "cwd": str(tmp_path),
            "path": str(path),
        },
    )()


@pytest.mark.asyncio
async def test_sessions_with_no_history(tmp_path, monkeypatch, state) -> None:
    class Manager:
        def list_sessions(self):
            return []

    monkeypatch.setattr("openlaoke.core.sessions.SessionManager", Manager)
    result = await SessionsCommand().execute(ctx(state))
    assert result.message == "No saved sessions yet."


@pytest.mark.asyncio
async def test_sessions_marks_the_current_one(tmp_path, monkeypatch, state) -> None:
    infos = [make_session_info(tmp_path, state.session_id), make_session_info(tmp_path, "other")]

    class Manager:
        def list_sessions(self):
            return infos

    monkeypatch.setattr("openlaoke.core.sessions.SessionManager", Manager)
    message = (await SessionsCommand().execute(ctx(state))).message
    assert "2 session(s); * marks this one" in message
    assert f" *{state.session_id}" in message
    assert "  other" in message


@pytest.mark.asyncio
async def test_sessions_caps_the_listing(tmp_path, monkeypatch, state) -> None:
    infos = [make_session_info(tmp_path, f"session_{i:02d}") for i in range(40)]

    class Manager:
        def list_sessions(self):
            return infos

    monkeypatch.setattr("openlaoke.core.sessions.SessionManager", Manager)
    message = (await SessionsCommand().execute(ctx(state))).message
    assert "40 session(s)" in message
    assert len(message.splitlines()) == 26  # header + 25 rows


@pytest.mark.asyncio
async def test_resume_with_no_sessions(monkeypatch, state) -> None:
    class Manager:
        def list_sessions(self):
            return []

    monkeypatch.setattr("openlaoke.core.sessions.SessionManager", Manager)
    assert (await ResumeCommand().execute(ctx(state))).message == "No sessions found to resume."


@pytest.mark.asyncio
async def test_resume_marks_the_latest_session(tmp_path, monkeypatch, state) -> None:
    infos = [make_session_info(tmp_path, "latest"), make_session_info(tmp_path, "older")]

    class Manager:
        def list_sessions(self):
            return infos

    monkeypatch.setattr("openlaoke.core.sessions.SessionManager", Manager)
    result = await ResumeCommand().execute(ctx(state))
    assert "latest" in result.message
    assert "will be resumed on next start" in result.message
    assert state.resume_session is True


@pytest.mark.asyncio
async def test_search_requires_a_query(state) -> None:
    result = await SearchCommand().execute(ctx(state, "  "))
    assert result.success is False
    assert "Use '/search <query>'" in result.message


@pytest.mark.asyncio
async def test_search_with_no_hits(monkeypatch, state) -> None:
    monkeypatch.setattr("openlaoke.core.session_index.search_sessions", lambda q, limit=10: [])
    result = await SearchCommand().execute(ctx(state, "widget"))
    assert result.message == "No session messages match 'widget'."


@pytest.mark.asyncio
async def test_search_renders_each_hit(monkeypatch, state) -> None:
    hit = type("Hit", (), {"line": lambda _self: "session_a: hello widget"})()
    monkeypatch.setattr("openlaoke.core.session_index.search_sessions", lambda q, limit=10: [hit])
    result = await SearchCommand().execute(ctx(state, "widget"))
    assert result.message == "session_a: hello widget"


# --------------------------------------------------------------------------- #
# /memory
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_memory_summary_recall_and_clear(tmp_path, state) -> None:
    command = MemoryCommand()
    summary = (await command.execute(ctx(state))).message
    assert summary.startswith("Memory is empty")

    from openlaoke.core.memory_store import get_store

    real_store = get_store(state)
    assert str(tmp_path) in real_store.path  # the store is not touching ~
    real_store.remember("Build command: pytest -q", tags=["build"])

    populated = (await command.execute(ctx(state))).message
    assert "1 note(s)" in populated
    assert "tags: build×1" in populated

    recalled = (await command.execute(ctx(state, "pytest"))).message
    assert "pytest -q" in recalled

    missing = (await command.execute(ctx(state, "nothing-matches-this"))).message
    assert missing == "No matching notes."

    cleared = (await command.execute(ctx(state, "clear"))).message
    assert "Cleared 1 note(s)" in cleared


@pytest.mark.asyncio
async def test_memory_wipe_alias(tmp_path, state) -> None:
    from openlaoke.core.memory_store import get_store

    get_store(state).remember("X", "y")
    result = await MemoryCommand().execute(ctx(state, "wipe"))
    assert "Cleared 1 note(s)" in result.message


# --------------------------------------------------------------------------- #
# /batch
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_batch_without_a_registry(state) -> None:
    state._tool_registry = None
    result = await BatchCommand().execute(ctx(state))
    assert result.success is False
    assert "No tool registry" in result.message


@pytest.mark.asyncio
async def test_batch_status_on_and_off(state) -> None:
    from openlaoke.core.tool import ToolRegistry

    state._tool_registry = ToolRegistry()
    command = BatchCommand()

    assert "Batch is off" in (await command.execute(ctx(state))).message

    enabled = await command.execute(ctx(state, "on"))
    assert "Batch enabled" in enabled.message
    assert state._tool_registry.get("Batch") is not None

    assert "Batch is on" in (await command.execute(ctx(state))).message

    disabled = await command.execute(ctx(state, "off"))
    assert "Batch disabled" in disabled.message
    assert state._tool_registry.get("Batch") is None


@pytest.mark.asyncio
async def test_batch_rejects_a_bad_argument(state) -> None:
    from openlaoke.core.tool import ToolRegistry

    state._tool_registry = ToolRegistry()
    result = await BatchCommand().execute(ctx(state, "maybe"))
    assert result.success is False
    assert "Use '/batch on' or '/batch off'." in result.message


# --------------------------------------------------------------------------- #
# /edits, /stats
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_edits_renders_the_edit_stats(state) -> None:
    state.edit_stats = {
        "files_created": 2,
        "files_modified": 1,
        "lines_added": 10,
        "lines_removed": 3,
        "per_file": {"a.py": {"added": 7, "removed": 1}, "b.py": {"added": 3, "removed": 2}},
    }
    message = (await EditsCommand().execute(ctx(state))).message
    assert "Files: 2 created, 1 modified" in message
    assert "Lines: +10 / -3 (net +7)" in message
    assert "Largest changes:" in message
    assert "a.py" in message


@pytest.mark.asyncio
async def test_edits_with_no_recorded_changes(state) -> None:
    message = (await EditsCommand().execute(ctx(state))).message
    assert message == "No edits recorded in this session."


@pytest.mark.asyncio
async def test_stats_reports_tokens_tools_edits_tasks_and_session(state) -> None:
    from openlaoke.types.core_types import TokenUsage

    state.token_usage = TokenUsage(input_tokens=1000, output_tokens=200, cache_read_tokens=500)
    state.tool_call_counts = {"Read": 3, "Grep": 1}
    state.edit_stats = {"files_created": 1, "lines_added": 5}
    state.messages.append(UserMessage(role=MessageRole.USER, content="hi"))

    message = (await StatsCommand().execute(ctx(state))).message
    assert "Tokens: 1,000 in / 200 out" in message
    assert "cache read 500 (50%)" in message
    assert "Tool calls: 4 Read×3, Grep×1" in message
    assert "Tasks: 0 open" in message
    assert "Background jobs: 0 running" in message
    assert f"Session: {state.session_id} (1 messages)" in message


@pytest.mark.asyncio
async def test_stats_without_usage_or_tools(state) -> None:
    message = (await StatsCommand().execute(ctx(state))).message
    assert "cache read 0 (n/a)" in message
    assert "Tool calls: none yet" in message


@pytest.mark.asyncio
async def test_stats_includes_cost_memory_monitor_and_background(state) -> None:
    from openlaoke.types.core_types import CostInfo

    state.cost_info = CostInfo(input_cost=0.5, output_cost=0.25)
    state._memory_store = type("M", (), {"entries": {1: "a", 2: "b"}})()
    state._cache_monitor = type("CM", (), {"readings": [1], "avg_hit_rate": lambda _self: 0.42})()

    from openlaoke.types.core_types import TaskState, TaskStatus, TaskType

    task = TaskState(id="t1", type=TaskType.LOCAL_BASH, status=TaskStatus.RUNNING)
    state.tasks[task.id] = task

    message = (await StatsCommand().execute(ctx(state))).message
    assert "Estimated cost: $0.7500" in message
    assert "Memory notes: 2" in message
    assert "Cache hit rate (recent): 42%" in message
    assert "Background jobs: 1 running, 1 total" in message


# --------------------------------------------------------------------------- #
# /sleep
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_sleep_refuses_while_swarm_runs(state) -> None:
    state._swarm = type("S", (), {"running": lambda _self: True})()
    result = await SleepCommand().execute(ctx(state))
    assert result.success is False
    assert "Refusing to hibernate" in result.message
    assert state._swarm is not None


@pytest.mark.asyncio
async def test_sleep_releases_derived_caches(state) -> None:
    class Readings(list):
        pass

    state._memory_store = object()
    state._cache_monitor = type("CM", (), {"readings": Readings([1, 2, 3])})()
    state._swarm = type("S", (), {"running": lambda _self: False})()
    state._swarm_board = object()
    manager = type("TM", (), {"_procs": {"a": 1}, "_handles": {"b": 2}})()
    state._task_manager = manager

    result = await SleepCommand().execute(ctx(state))

    assert result.message.startswith("Released ")
    assert "memory index" in result.message
    assert "cache readings (3)" in result.message
    assert "swarm board" in result.message
    assert "task handles" in result.message
    assert "Collected" in result.message
    assert state._memory_store is None
    assert manager._procs == {}
    assert manager._handles == {}


@pytest.mark.asyncio
async def test_sleep_with_nothing_to_release(state) -> None:
    result = await SleepCommand().execute(ctx(state))
    assert "nothing to release" in result.message


# --------------------------------------------------------------------------- #
# /schedule, /mcp, /cache, /todos
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_schedule_notes_that_the_loop_is_off(state) -> None:
    result = await ScheduleCommand().execute(ctx(state))
    assert "scheduler loop is off" in result.message


@pytest.mark.asyncio
async def test_mcp_without_runtime(state) -> None:
    state._mcp_runtime = None
    result = await McpCommand().execute(ctx(state))
    assert "MCP runtime is not attached" in result.message


@pytest.mark.asyncio
async def test_mcp_lists_runtime_summary_and_contributed_tools(state) -> None:
    from openlaoke.core.tool import ToolRegistry

    registry = ToolRegistry()
    for name in ("mcp__files__read", "Read"):
        tool = type("T", (), {"name": name})()
        registry._tools[name] = tool  # direct insert: fake tools, no schema

    state._tool_registry = registry
    state._mcp_runtime = type("R", (), {"summary": lambda _self: "2 servers, 1 tool"})()

    message = (await McpCommand().execute(ctx(state))).message
    assert "2 servers, 1 tool" in message
    assert "tools: mcp__files__read" in message


@pytest.mark.asyncio
async def test_cache_without_monitor(state) -> None:
    state._cache_monitor = None
    assert "Cache monitor is not attached" in (await CacheCommand().execute(ctx(state))).message


@pytest.mark.asyncio
async def test_cache_renders_the_monitor(state) -> None:
    state._cache_monitor = type("CM", (), {"render": lambda _self: "hit rate 90%"})()
    assert (await CacheCommand().execute(ctx(state))).message == "hit rate 90%"


@pytest.mark.asyncio
async def test_todos_renders_the_store(state) -> None:
    message = (await TodosCommand().execute(ctx(state))).message
    assert isinstance(message, str)


# --------------------------------------------------------------------------- #
# /export
# --------------------------------------------------------------------------- #


@pytest.fixture()
def home_redirect(tmp_path, monkeypatch):
    """Point ~/.openlaoke into tmp_path so exports never touch the real home."""
    real_expanduser = cmd.os.path.expanduser

    def fake_expanduser(path: str) -> str:
        if path.startswith("~"):
            return str(tmp_path / path[2:] if path.startswith("~/") else tmp_path)
        return real_expanduser(path)

    monkeypatch.setattr(cmd.os.path, "expanduser", fake_expanduser)
    return tmp_path


@pytest.mark.asyncio
async def test_export_json_to_the_default_location(home_redirect, state) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="hello"))
    result = await ExportCommand().execute(ctx(state, "json"))
    assert result.success is True
    path = Path(result.message.removeprefix("Session exported to "))
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["session_id"] == state.session_id
    assert data["messages"][0]["content"] == "hello"


@pytest.mark.asyncio
async def test_export_markdown_default(home_redirect, state) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="hello"))
    result = await ExportCommand().execute(ctx(state, ""))
    path = Path(result.message.removeprefix("Session exported to "))
    assert path.suffix == ".md"
    body = path.read_text(encoding="utf-8")
    assert f"# Session {state.session_id}" in body
    assert "## user" in body
    assert "hello" in body


@pytest.mark.asyncio
async def test_export_to_an_explicit_filename(home_redirect, state, tmp_path) -> None:
    target = tmp_path / "custom.md"
    result = await ExportCommand().execute(ctx(state, f"md {target}"))
    assert result.success is True
    assert target.exists()


@pytest.mark.asyncio
async def test_export_rejects_an_unknown_format(home_redirect, state) -> None:
    result = await ExportCommand().execute(ctx(state, "pdf"))
    assert result.success is False
    assert "Unknown format: pdf" in result.message


@pytest.mark.asyncio
async def test_export_reports_os_errors(home_redirect, state, monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", fail)
    result = await ExportCommand().execute(ctx(state, "json"))
    assert result.success is False
    assert "Export failed: disk full" in result.message


# --------------------------------------------------------------------------- #
# /theme
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_theme_shows_the_current_one(state) -> None:
    message = (await ThemeCommand().execute(ctx(state))).message
    assert "Current theme: dark" in message
    assert "Available: dark, light" in message


@pytest.mark.asyncio
async def test_theme_switches_and_rejects(state) -> None:
    assert (await ThemeCommand().execute(ctx(state, "light"))).message == "Theme set to: light"
    assert state.theme == "light"

    result = await ThemeCommand().execute(ctx(state, "neon"))
    assert result.success is False
    assert "Unknown theme: neon" in result.message
    assert state.theme == "light"


# --------------------------------------------------------------------------- #
# /context (the model-window discovery fallback)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_context_falls_back_to_provider_discovery_when_the_window_is_unknown(
    state, monkeypatch
) -> None:
    from openlaoke.commands.base import ContextCommand
    from openlaoke.types.providers import (
        MultiProviderConfig,
        ProviderConfig,
        ProviderType,
    )

    config = cmd.load_config()
    config.providers = MultiProviderConfig(
        providers={"openai": ProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk")},
        active_provider="openai",
    )
    config.context_cap_tokens = None
    state.compact_state.clear()

    async def discover(provider, model):
        return 64_000

    monkeypatch.setattr(
        "openlaoke.core.model_discovery.get_effective_context_limit", discover
    )
    message = (await ContextCommand().execute(ctx(state))).message
    assert "Model window : 64,000" in message
    assert "Effective    : 64,000 tokens" in message


@pytest.mark.asyncio
async def test_context_survives_a_failing_discovery(state, monkeypatch) -> None:
    from openlaoke.commands.base import ContextCommand
    from openlaoke.types.providers import (
        MultiProviderConfig,
        ProviderConfig,
        ProviderType,
    )

    config = cmd.load_config()
    config.providers = MultiProviderConfig(
        providers={"openai": ProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk")},
        active_provider="openai",
    )
    config.context_cap_tokens = None
    state.compact_state.clear()

    async def boom(provider, model):
        raise RuntimeError("catalog unreachable")

    monkeypatch.setattr("openlaoke.core.model_discovery.get_effective_context_limit", boom)
    message = (await ContextCommand().execute(ctx(state))).message
    # Unknown window: conservative default and the explicit note.
    assert "unknown" in message
    assert "conservative default" in message


# --------------------------------------------------------------------------- #
# /history, /restore
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_history_without_snapshots_explains_how_they_appear(state) -> None:
    result = await HistoryCommand().execute(ctx(state))
    assert result.success is True
    assert "No file snapshots yet" in result.message
    assert "edit or write tool" in result.message


@pytest.mark.asyncio
async def test_history_lists_tracked_files(state, tmp_path) -> None:
    from openlaoke.utils.file_history import track_file_edit

    target = tmp_path / "tracked.py"
    target.write_text("keep me\n", encoding="utf-8")
    track_file_edit(str(target))

    message = (await HistoryCommand().execute(ctx(state))).message

    assert "1 file(s) with snapshots:" in message
    assert str(target) in message
    assert "1 versions" in message
    assert "latest v1" in message
    assert "/restore <path> [version]" in message


@pytest.mark.asyncio
async def test_history_with_a_path_shows_the_versions(state, tmp_path) -> None:
    from openlaoke.utils.file_history import save_snapshot

    target = tmp_path / "versions.py"
    target.write_text("x", encoding="utf-8")
    save_snapshot(str(target), "one")

    message = (await HistoryCommand().execute(ctx(state, str(target)))).message

    assert message.startswith(f"History for {target}:")
    assert "v1:" in message
    assert "size: 3 bytes" in message


@pytest.mark.asyncio
async def test_history_with_a_path_that_was_never_touched(state, tmp_path) -> None:
    missing = str(tmp_path / "never.py")
    assert (
        await HistoryCommand().execute(ctx(state, missing))
    ).message == f"No history found for {missing}"


@pytest.mark.asyncio
async def test_restore_without_arguments_shows_the_usage(state) -> None:
    result = await RestoreCommand().execute(ctx(state))
    assert result.success is False
    assert result.message == "Usage: /restore <path> [version]"


@pytest.mark.asyncio
async def test_restore_rejects_a_non_numeric_version(state, tmp_path) -> None:
    target = tmp_path / "f.py"
    target.write_text("x", encoding="utf-8")
    result = await RestoreCommand().execute(ctx(state, f"{target} latest"))
    assert result.success is False
    assert "Not a version number: latest" in result.message


@pytest.mark.asyncio
async def test_restore_without_a_snapshot_fails_clearly(state, tmp_path) -> None:
    target = str(tmp_path / "unknown.py")
    result = await RestoreCommand().execute(ctx(state, target))
    assert result.success is False
    assert result.message.startswith(f"No a saved snapshot for {target}.")
    assert "/history" in result.message


@pytest.mark.asyncio
async def test_restore_writes_the_latest_snapshot(state, tmp_path) -> None:
    from openlaoke.utils.file_history import save_snapshot

    target = tmp_path / "restored.py"
    target.write_text("broken\n", encoding="utf-8")
    save_snapshot(str(target), "good\n")
    target.write_text("really broken\n", encoding="utf-8")

    result = await RestoreCommand().execute(ctx(state, str(target)))

    assert result.success is True
    assert result.message == f"Restored {target} to v1 (5 bytes)."
    assert target.read_text(encoding="utf-8") == "good\n"


@pytest.mark.asyncio
async def test_restore_accepts_a_v_prefixed_version(state, tmp_path) -> None:
    from openlaoke.utils.file_history import save_snapshot

    target = tmp_path / "pick.py"
    target.write_text("c", encoding="utf-8")
    save_snapshot(str(target), "first\n")
    save_snapshot(str(target), "second\n")

    result = await RestoreCommand().execute(ctx(state, f"{target} v1"))

    assert result.success is True
    assert "to v1 (6 bytes)" in result.message
    assert target.read_text(encoding="utf-8") == "first\n"


@pytest.mark.asyncio
async def test_restore_reports_an_unknown_version(state, tmp_path) -> None:
    from openlaoke.utils.file_history import save_snapshot

    target = tmp_path / "only-one.py"
    target.write_text("c", encoding="utf-8")
    save_snapshot(str(target), "only")

    result = await RestoreCommand().execute(ctx(state, f"{target} 7"))

    assert result.success is False
    assert result.message.startswith(f"No saved version 7 for {target}.")


@pytest.mark.asyncio
async def test_restore_reports_a_write_failure(state, tmp_path, monkeypatch) -> None:
    from openlaoke.utils import file_history

    target = tmp_path / "locked.py"
    target.write_text("c", encoding="utf-8")
    file_history.save_snapshot(str(target), "old")

    monkeypatch.setattr(file_history, "restore_snapshot", lambda *_a, **_k: False)
    result = await RestoreCommand().execute(ctx(state, str(target)))

    assert result.success is False
    assert result.message == f"Could not write {target}."
