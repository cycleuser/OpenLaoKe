"""Deeper cases for the pi-compatible commands.

tests/test_pi_commands.py covers the command surface; this file goes after the
behaviour underneath it: the rewind path, the transcript handling of /import,
what /share leaves on disk, and the messages that used to claim success while
doing nothing.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from openlaoke.commands import pi_commands as pi
from openlaoke.commands.base import CommandContext
from openlaoke.core.state import create_app_state
from openlaoke.snapshot.store import SnapshotStore
from openlaoke.types.core_types import AssistantMessage, MessageRole, UserMessage


@pytest.fixture(autouse=True)
def isolated_openlaoke_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".openlaoke").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(pi, "_OPENLAOKE_DIR", home / ".openlaoke")
    monkeypatch.chdir(tmp_path)
    return home / ".openlaoke"


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path))


def ctx(state, args: str = "") -> CommandContext:
    return CommandContext(app_state=state, args=args)


def record_turns(state, turns: int) -> SnapshotStore:
    store = SnapshotStore(base_dir=str(pi._OPENLAOKE_DIR / "snapshots"))
    state._snapshot_store = store
    for turn in range(1, turns + 1):
        store.capture_file(state.session_id, turn, "/tmp/openlaoke-absent.txt")
    return store


# --------------------------------------------------------------------------- #
# /tree
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_tree_marks_only_the_tip(state) -> None:
    record_turns(state, 3)

    message = (await pi.TreeCommand().execute(ctx(state))).message

    marked = [line for line in message.splitlines() if line.strip().startswith("*")]
    assert len(marked) == 1
    assert "turn 3:" in marked[0]


@pytest.mark.asyncio
async def test_tree_rejects_a_non_numeric_target(state) -> None:
    record_turns(state, 1)
    result = await pi.TreeCommand().execute(ctx(state, "back"))

    assert result.success is False
    assert result.message == "Usage: /tree <turn-number>"


@pytest.mark.asyncio
async def test_tree_rewind_puts_the_files_back(state, tmp_path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("first\n", encoding="utf-8")
    store = SnapshotStore(base_dir=str(pi._OPENLAOKE_DIR / "snapshots"))
    state._snapshot_store = store
    store.capture_file(state.session_id, 1, str(target))
    target.write_text("second\n", encoding="utf-8")
    store.capture_file(state.session_id, 2, str(target))
    target.write_text("third\n", encoding="utf-8")

    result = await pi.TreeCommand().execute(ctx(state, "2"))

    assert result.success is True
    assert "Rewound to turn 2" in result.message
    # Turn 2's snapshot is the content at the start of turn 2, i.e. "second".
    assert target.read_text(encoding="utf-8") == "second\n"


# --------------------------------------------------------------------------- #
# /fork, /clone
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fork_records_the_parent_and_switches(state) -> None:
    record_turns(state, 2)
    original = state.session_id

    result = await pi.ForkCommand().execute(ctx(state))

    assert result.success is True
    assert state.session_id != original
    assert f"parent {original}" in result.message


@pytest.mark.asyncio
async def test_fork_with_a_turn_number(state) -> None:
    record_turns(state, 2)
    result = await pi.ForkCommand().execute(ctx(state, "1"))

    assert result.success is True
    assert "turn 1" in result.message


@pytest.mark.asyncio
async def test_fork_rejects_a_non_numeric_turn(state) -> None:
    record_turns(state, 1)
    result = await pi.ForkCommand().execute(ctx(state, "tip"))

    assert result.success is False
    assert result.message == "Usage: /fork [turn-number]"


# --------------------------------------------------------------------------- #
# /import
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_import_reads_a_pi_jsonl_transcript_with_blocks(state, tmp_path) -> None:
    path = tmp_path / "transcript.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "list the files"}),
                "",
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "one"},
                            {"type": "text", "text": "two"},
                            {"type": "tool_use", "id": "x", "name": "Read", "input": {}},
                        ],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = await pi.ImportCommand().execute(ctx(state, str(path)))

    assert result.success is True
    assert [m.content for m in state.messages] == ["list the files", "one two"]


@pytest.mark.asyncio
async def test_import_replaces_the_current_conversation(state, tmp_path) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="old turn"))
    path = tmp_path / "only.jsonl"
    path.write_text(json.dumps({"role": "user", "content": "new turn"}), encoding="utf-8")

    await pi.ImportCommand().execute(ctx(state, str(path)))

    assert [m.content for m in state.messages] == ["new turn"]


@pytest.mark.asyncio
async def test_import_reports_a_broken_file(state, tmp_path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    result = await pi.ImportCommand().execute(ctx(state, str(path)))

    assert result.success is False
    assert result.message.startswith("Import failed:")


@pytest.mark.asyncio
async def test_import_of_a_file_without_messages_fails(state, tmp_path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"messages": []}), encoding="utf-8")

    result = await pi.ImportCommand().execute(ctx(state, str(path)))

    assert result.success is False
    assert result.message == "No messages found to import."


# --------------------------------------------------------------------------- #
# /share
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_share_removes_the_transcript_it_uploaded(state, monkeypatch) -> None:
    monkeypatch.setattr(pi.shutil, "which", lambda name: "/opt/homebrew/bin/gh")
    state.messages.append(AssistantMessage(role=MessageRole.ASSISTANT, content="the answer"))
    seen: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["payload"] = json.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(cmd, 0, stdout="https://gist.github.com/abc\n", stderr="")

    monkeypatch.setattr(pi.subprocess, "run", fake_run)
    result = await pi.ShareCommand().execute(ctx(state))

    assert result.success is True
    assert result.message == "Shared as secret gist: https://gist.github.com/abc"
    assert seen["cmd"][:3] == ["gh", "gist", "create"]
    assert seen["payload"]["messages"][0]["content"] == "the answer"
    # A plaintext copy of the conversation must not be left behind.
    assert not (pi._OPENLAOKE_DIR / f"share_{state.session_id}.json").exists()


@pytest.mark.asyncio
async def test_share_cleans_up_even_when_the_upload_fails(state, monkeypatch) -> None:
    monkeypatch.setattr(pi.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        pi.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in"),
    )

    result = await pi.ShareCommand().execute(ctx(state))

    assert result.success is False
    assert result.message == "Share failed: not logged in"
    assert not (pi._OPENLAOKE_DIR / f"share_{state.session_id}.json").exists()


@pytest.mark.asyncio
async def test_share_reports_an_os_error(state, monkeypatch) -> None:
    monkeypatch.setattr(pi.shutil, "which", lambda name: "/usr/bin/gh")

    def boom(cmd, **kwargs):
        raise OSError("gh vanished")

    monkeypatch.setattr(pi.subprocess, "run", boom)
    result = await pi.ShareCommand().execute(ctx(state))

    assert result.success is False
    assert "Share failed: gh vanished" in result.message


# --------------------------------------------------------------------------- #
# /copy
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_copy_stores_the_text_when_no_clipboard_tool_works(state, monkeypatch) -> None:
    state.messages.append(AssistantMessage(role=MessageRole.ASSISTANT, content="copy me"))
    monkeypatch.setattr(pi, "_copy_to_clipboard", lambda text: False)

    result = await pi.CopyCommand().execute(ctx(state))

    assert "stored in session.clipboard_content" in result.message
    assert state.clipboard_content == "copy me"


def test_copy_to_clipboard_uses_the_first_available_tool(monkeypatch) -> None:
    available = {"wl-copy"}
    monkeypatch.setattr(
        pi.shutil, "which", lambda name: f"/usr/bin/{name}" if name in available else None
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        pi.subprocess,
        "run",
        lambda cmd, **kw: (
            calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        ),
    )

    assert pi._copy_to_clipboard("text") is True
    assert calls == [["wl-copy"]]


def test_copy_to_clipboard_reports_failure_when_every_tool_errors(monkeypatch) -> None:
    monkeypatch.setattr(pi.shutil, "which", lambda name: f"/usr/bin/{name}")

    def failing_run(cmd, **kwargs):
        # check=True turns a non-zero exit into CalledProcessError, which is what
        # the helper catches to try the next clipboard tool.
        raise subprocess.CalledProcessError(1, cmd, output="", stderr="cannot open display")

    monkeypatch.setattr(pi.subprocess, "run", failing_run)
    assert pi._copy_to_clipboard("text") is False


# --------------------------------------------------------------------------- #
# /changelog
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_changelog_honours_a_line_limit(tmp_path, state) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        "\n".join(f"line {i}" for i in range(50)), encoding="utf-8"
    )

    message = (await pi.ChangelogCommand().execute(ctx(state, "3"))).message

    assert message.splitlines() == ["line 0", "line 1", "line 2"]


@pytest.mark.asyncio
async def test_changelog_a_zero_limit_still_shows_one_line(tmp_path, state) -> None:
    (tmp_path / "CHANGELOG.md").write_text("a\nb\n", encoding="utf-8")
    assert (await pi.ChangelogCommand().execute(ctx(state, "0"))).message == "a"


@pytest.mark.asyncio
async def test_changelog_reports_a_read_error(monkeypatch, state, tmp_path) -> None:
    target = tmp_path / "CHANGELOG.md"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(pi, "_changelog_path", lambda: target)

    def boom(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", boom)
    result = await pi.ChangelogCommand().execute(ctx(state))

    assert result.success is False
    assert "Could not read changelog: permission denied" in result.message


# --------------------------------------------------------------------------- #
# /login, /logout
# --------------------------------------------------------------------------- #


@pytest.fixture()
def config_file(tmp_path, monkeypatch):
    import openlaoke.utils.config as config_module

    path = tmp_path / "config-home" / "config.json"
    path.parent.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    monkeypatch.setattr(config_module, "CONFIG_DIR", path.parent)
    return path


@pytest.mark.asyncio
async def test_login_without_a_key_saves_nothing_and_says_so(config_file, state) -> None:
    result = await pi.LoginCommand().execute(ctx(state, "openai"))

    assert result.success is False
    assert "nothing was saved" in result.message
    assert not config_file.exists()


@pytest.mark.asyncio
async def test_login_saves_the_key_and_activates_the_provider(config_file, state) -> None:
    result = await pi.LoginCommand().execute(ctx(state, "openai sk-test-key"))

    assert result.success is True
    stored = json.loads(config_file.read_text(encoding="utf-8"))
    assert stored["providers"]["providers"]["openai"]["api_key"] == "sk-test-key"
    assert stored["providers"]["active_provider"] == "openai"


@pytest.mark.asyncio
async def test_logout_clears_a_saved_key(config_file, state) -> None:
    await pi.LoginCommand().execute(ctx(state, "openai sk-test-key"))
    result = await pi.LogoutCommand().execute(ctx(state, "openai"))

    assert result.success is True
    stored = json.loads(config_file.read_text(encoding="utf-8"))
    assert stored["providers"]["providers"]["openai"]["api_key"] == ""


# --------------------------------------------------------------------------- #
# /scoped-models
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_scoped_models_ignores_a_repeat_and_clears(state) -> None:
    command = pi.ScopedModelsCommand()
    await command.execute(ctx(state, "add a"))
    await command.execute(ctx(state, "add a"))
    assert command._load() == ["a"]

    assert (await command.execute(ctx(state, "clear"))).message == "Cleared scoped models."
    assert command._load() == []


@pytest.mark.asyncio
async def test_scoped_models_survives_a_corrupt_store(state) -> None:
    command = pi.ScopedModelsCommand()
    command._path().parent.mkdir(parents=True, exist_ok=True)
    command._path().write_text("{not a list", encoding="utf-8")

    assert command._load() == []
    assert "No scoped models" in (await command.execute(ctx(state))).message
