"""Tests for the append-only transcript: journal, replay and recovery."""

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

import pytest

from openlaoke.core.sessions import SessionManager
from openlaoke.core.state import AppState, create_app_state
from openlaoke.core.transcript import Transcript, transcript_path_for
from openlaoke.types.core_types import MessageRole, UserMessage


def _transcript(tmp_path) -> Transcript:
    return Transcript(
        str(tmp_path / "sessions" / "session_1.jsonl"),
        session_id="session_1",
        cwd="/tmp/project",
        model="test-model",
    )


def _message(text: str) -> UserMessage:
    return UserMessage(role=MessageRole.USER, content=text)


def test_appending_writes_a_header_and_one_line_per_message(tmp_path):
    transcript = _transcript(tmp_path)

    assert transcript.append_message(_message("hello")) == 1
    assert transcript.append_message(_message("again")) == 2

    lines = Path(transcript.path).read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header["type"] == "session.start"
    assert header["session_id"] == "session_1"
    assert header["cwd"] == "/tmp/project"
    assert header["model"] == "test-model"
    assert json.loads(lines[1])["seq"] == 1
    assert stat.S_IMODE(os.stat(transcript.path).st_mode) == 0o600


def test_replay_returns_the_messages_in_order(tmp_path):
    transcript = _transcript(tmp_path)
    for text in ("one", "two", "three"):
        transcript.append_message(_message(text))

    header, records = transcript.replay()

    assert header["session_id"] == "session_1"
    assert [record["message"]["content"] for record in records] == ["one", "two", "three"]
    assert transcript.health().ok is True


def test_a_new_transcript_object_continues_the_sequence(tmp_path):
    first = _transcript(tmp_path)
    first.append_message(_message("one"))

    second = _transcript(tmp_path)
    assert second.append_message(_message("two")) == 2

    assert [record["seq"] for record in second.replay()[1]] == [1, 2]
    assert second.health().duplicate_seqs == []


def test_a_torn_final_line_is_skipped_and_reported(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("kept"))
    with open(transcript.path, "a", encoding="utf-8") as handle:
        handle.write('{"type": "message", "seq": 2, "mess')

    health = transcript.health()

    assert health.torn_tail is True
    assert health.corrupt_lines == []
    assert [record["seq"] for record in transcript.replay()[1]] == [1]
    assert transcript.append_message(_message("after")) == 2


def test_corruption_in_the_middle_is_reported_not_hidden(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))
    transcript.append_message(_message("two"))
    lines = Path(transcript.path).read_text(encoding="utf-8").splitlines()
    with open(transcript.path, "w", encoding="utf-8") as handle:
        handle.write("\n".join([lines[0], "not json", lines[2]]) + "\n")

    health = transcript.health()

    assert health.corrupt_lines == [2]
    assert health.ok is False
    assert "corrupt lines: 2" in health.render()


def test_duplicate_sequence_numbers_are_reported(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))
    line = Path(transcript.path).read_text(encoding="utf-8").splitlines()[-1]
    with open(transcript.path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    health = transcript.health()

    assert health.duplicate_seqs == [1]
    assert health.ok is False


def test_an_empty_journal_reports_cleanly(tmp_path):
    transcript = _transcript(tmp_path)

    health = transcript.health()

    assert health.records == 0
    assert health.last_seq == 0
    assert health.ok is True
    assert transcript.replay() == ({}, [])


def test_a_session_with_a_path_journals_every_message(tmp_path):
    path = str(tmp_path / "sessions" / "session_9.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)

    state.add_message(_message("first"))
    state.add_message(_message("second"))

    transcript = Transcript(transcript_path_for(path))
    assert [record["message"]["content"] for record in transcript.replay()[1]] == [
        "first",
        "second",
    ]


def test_a_journal_failure_does_not_break_the_turn(tmp_path, caplog):
    path = str(tmp_path / "sessions" / "session_9.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)

    def refuse(_message):
        raise OSError("read-only")

    state._transcript.append_message = refuse
    state.add_message(_message("still recorded in memory"))

    assert state.messages[-1].content == "still recorded in memory"
    assert "Could not append to the session transcript" in caplog.text


def test_a_truncated_snapshot_is_recovered_from_the_journal(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    state = create_app_state(
        cwd=str(tmp_path), persist_path=str(tmp_path / "sessions" / "abc.json")
    )
    state.session_id = "abc"
    state.set_persist_path(str(tmp_path / "sessions" / "abc.json"))
    state.add_message(_message("survives the crash"))
    manager.save_session(state)

    # Simulate the crash the atomic write cannot save you from: something else
    # truncated (or corrupted) the snapshot.
    snapshot = tmp_path / "sessions" / "abc.json"
    snapshot.write_text(snapshot.read_text()[:40])

    recovered = manager.load_session("abc")

    assert recovered is not None
    assert [message.content for message in recovered.messages] == ["survives the crash"]
    assert recovered.cwd == str(tmp_path)


def test_recovery_returns_nothing_when_there_is_no_journal(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(exist_ok=True)
    (tmp_path / "sessions" / "broken.json").write_text("{")

    assert manager.load_session("broken") is None


def test_an_unreadable_snapshot_path_returns_none(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))

    assert manager.load_session("does-not-exist") is None


def test_the_transcript_command_reports_health(tmp_path):
    from openlaoke.commands.base import TranscriptCommand

    path = str(tmp_path / "sessions" / "abc.json")
    state = AppState(session_id="abc", cwd=str(tmp_path))
    state.set_persist_path(path)
    state.add_message(_message("hello there"))

    class Ctx:
        app_state = state
        args = "5"

    result = asyncio.run(TranscriptCommand().execute(Ctx()))

    assert result.success is True
    assert "hello there" in result.message
    assert "record(s)" in result.message


def test_the_transcript_command_explains_a_session_that_was_never_saved(tmp_path):
    from openlaoke.commands.base import TranscriptCommand

    class Ctx:
        app_state = AppState(session_id="anonymous", cwd=str(tmp_path))
        args = ""

    result = asyncio.run(TranscriptCommand().execute(Ctx()))

    assert "never saved" in result.message


def test_the_transcript_command_rejects_a_bad_count(tmp_path):
    from openlaoke.commands.base import TranscriptCommand

    state = AppState(session_id="abc", cwd=str(tmp_path))
    state.set_persist_path(str(tmp_path / "abc.json"))

    class Ctx:
        app_state = state
        args = "not-a-number"

    result = asyncio.run(TranscriptCommand().execute(Ctx()))

    assert result.success is False
    assert "Usage" in result.message


def test_health_render_names_every_problem(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))
    line = Path(transcript.path).read_text(encoding="utf-8").splitlines()[-1]
    with open(transcript.path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.write("not json\n")
        handle.write('{"type": "message", "seq": 9, "mess')

    rendered = transcript.health().render()

    assert "torn final line" in rendered
    assert "duplicate seq: 1" in rendered
    assert "corrupt lines: 4" in rendered


def test_a_zero_length_write_is_an_error_not_a_silent_success(tmp_path, monkeypatch):
    import openlaoke.core.transcript as transcript_module

    transcript = _transcript(tmp_path)
    monkeypatch.setattr(transcript_module.os, "write", lambda _fd, _view: 0)

    with pytest.raises(OSError, match="short write"):
        transcript.append_message(_message("body"))


def test_records_returns_the_raw_lines(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))

    records = transcript.records()

    assert records[0]["type"] == "session.start"
    assert records[1]["message"]["content"] == "one"


def test_a_non_object_line_counts_as_corruption(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))
    with open(transcript.path, "a", encoding="utf-8") as handle:
        handle.write("[1, 2]\n")

    assert transcript.health().corrupt_lines == [3]


def test_an_empty_file_replays_to_nothing(tmp_path):
    transcript = _transcript(tmp_path)
    Path(transcript.path).parent.mkdir(parents=True)
    Path(transcript.path).write_text("")

    assert transcript.health().records == 0
    assert transcript.replay() == ({}, [])


def test_the_load_messages_helper_returns_raw_dicts(tmp_path):
    from openlaoke.core.transcript import load_messages

    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))
    transcript.append_message(_message("two"))

    assert [item["content"] for item in load_messages(transcript.path)] == ["one", "two"]


def test_deleting_a_session_removes_its_journal_too(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)
    state.add_message(_message("secret planning notes"))
    manager.save_session(state)
    journal = Path(transcript_path_for(path))
    assert journal.exists()

    assert manager.delete_session("abc") is True

    assert not Path(path).exists()
    assert not journal.exists()
    # The conversation must not survive a delete in a second file.
    assert "secret planning notes" not in "".join(
        item.read_text(errors="ignore")
        for item in (tmp_path / "sessions").iterdir()
        if item.is_file()
    )


def test_deleting_a_session_that_only_has_a_journal_still_works(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)
    state.add_message(_message("only in the journal"))
    Path(path).unlink(missing_ok=True)

    assert manager.delete_session("abc") is True
    assert not Path(transcript_path_for(path)).exists()


def test_a_journal_only_session_is_listed_as_recovered(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)
    state.add_message(_message("one"))
    state.add_message(_message("two"))
    Path(path).unlink(missing_ok=True)  # snapshot lost, journal survives

    sessions = [info for info in manager.list_sessions() if info.session_id == "abc"]

    assert len(sessions) == 1
    assert sessions[0].recovered is True
    assert sessions[0].message_count == 2
    assert sessions[0].cwd == str(tmp_path)
    assert sessions[0].model


def test_a_corrupt_snapshot_is_listed_once_not_twice(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)
    state.add_message(_message("one"))
    Path(path).write_text("{ truncated")

    sessions = [info for info in manager.list_sessions() if info.session_id == "abc"]

    assert len(sessions) == 1
    assert sessions[0].recovered is True


def test_a_journal_without_messages_is_not_listed(tmp_path):
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(parents=True, exist_ok=True)
    Path(tmp_path / "sessions" / "empty.jsonl").write_text("")

    assert [info for info in manager.list_sessions() if info.session_id == "empty"] == []


def test_the_sessions_command_marks_a_journal_only_row(tmp_path, monkeypatch):
    from openlaoke.commands import base as commands_base
    from openlaoke.core import sessions as sessions_module

    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)
    state.add_message(_message("one"))
    Path(path).unlink(missing_ok=True)
    # /sessions imports SessionManager inside execute(), so patch it at source.
    monkeypatch.setattr(sessions_module, "SessionManager", lambda *a, **k: manager)

    class Ctx:
        app_state = AppState(session_id="other", cwd=str(tmp_path))
        args = ""

    result = asyncio.run(commands_base.SessionsCommand().execute(Ctx()))

    assert "journal only" in result.message


def test_the_sessions_command_prunes_old_sessions_and_their_data(tmp_path, monkeypatch):
    import time as _time

    from openlaoke.commands import base as commands_base
    from openlaoke.core import sessions as sessions_module
    from openlaoke.core.tool_output_store import ToolOutputStore

    monkeypatch.setenv("OPENLAOKE_ARTIFACT_DIR", str(tmp_path / "art"))
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "old.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "old"
    state.set_persist_path(path)
    state.add_message(_message("ancient"))
    manager.save_session(state)
    artifact = ToolOutputStore(None, "old").store("Bash", "old output")
    long_ago = _time.time() - 90 * 86400
    payload = json.loads(Path(path).read_text())
    payload["created_at"] = long_ago
    Path(path).write_text(json.dumps(payload))
    # Age means the last write, so the files themselves have to be old: a
    # snapshot written a moment ago is a session still in use.
    for candidate in (path, transcript_path_for(path)):
        os.utime(candidate, (long_ago, long_ago))
    monkeypatch.setattr(sessions_module, "SessionManager", lambda *a, **k: manager)

    class Ctx:
        app_state = AppState(session_id="other", cwd=str(tmp_path))
        args = "prune 30"

    result = asyncio.run(commands_base.SessionsCommand().execute(Ctx()))

    assert "Removed 1 session(s)" in result.message
    assert not Path(path).exists()
    assert not Path(transcript_path_for(path)).exists()
    assert not Path(artifact.path).exists()


def test_the_sessions_command_rejects_an_unknown_argument(tmp_path, monkeypatch):
    from openlaoke.commands import base as commands_base
    from openlaoke.core import sessions as sessions_module

    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    monkeypatch.setattr(sessions_module, "SessionManager", lambda *a, **k: manager)

    class Ctx:
        app_state = AppState(session_id="other", cwd=str(tmp_path))
        args = "wibble"

    result = asyncio.run(commands_base.SessionsCommand().execute(Ctx()))

    assert result.success is False
    assert "Usage" in result.message


def test_the_sessions_command_rejects_a_bad_age(tmp_path, monkeypatch):
    from openlaoke.commands import base as commands_base
    from openlaoke.core import sessions as sessions_module

    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    monkeypatch.setattr(sessions_module, "SessionManager", lambda *a, **k: manager)

    class Ctx:
        app_state = AppState(session_id="other", cwd=str(tmp_path))
        args = "prune soon"

    result = asyncio.run(commands_base.SessionsCommand().execute(Ctx()))

    assert result.success is False


def test_a_resumed_session_journals_the_id_it_was_loaded_as(tmp_path):
    """The header is written on the first append, not when the state is built."""
    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)
    manager.save_session(state)
    Path(transcript_path_for(path)).unlink(missing_ok=True)  # pre-journal snapshot

    resumed = manager.load_session("abc")
    assert resumed is not None
    resumed.add_message(_message("after the resume"))

    header, _records = Transcript(transcript_path_for(path)).replay()
    assert header["session_id"] == "abc"
    assert header["cwd"] == str(tmp_path)


def test_the_journal_header_is_not_rewritten_on_every_message(tmp_path):
    path = str(tmp_path / "sessions" / "abc.json")
    state = create_app_state(cwd=str(tmp_path), persist_path=path)
    state.session_id = "abc"
    state.set_persist_path(path)

    state.add_message(_message("one"))
    state.add_message(_message("two"))

    lines = Path(transcript_path_for(path)).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["type"] for line in lines] == ["session.start", "message", "message"]


def test_the_transcript_command_shows_the_header(tmp_path):
    from openlaoke.commands.base import TranscriptCommand

    path = str(tmp_path / "sessions" / "abc.json")
    state = AppState(session_id="abc", cwd=str(tmp_path))
    state.set_persist_path(path)
    state.add_message(_message("hello"))

    class Ctx:
        app_state = state
        args = ""

    result = asyncio.run(TranscriptCommand().execute(Ctx()))

    assert "session abc" in result.message
    assert f"cwd {tmp_path}" in result.message
    assert "model" in result.message
    assert "started" in result.message
