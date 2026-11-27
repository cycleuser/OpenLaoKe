"""Tests for the append-only transcript: journal, replay and recovery."""

from __future__ import annotations

import asyncio
import json
import os
import stat

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

    lines = open(transcript.path, encoding="utf-8").read().splitlines()
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
    lines = open(transcript.path, encoding="utf-8").read().splitlines()
    with open(transcript.path, "w", encoding="utf-8") as handle:
        handle.write("\n".join([lines[0], "not json", lines[2]]) + "\n")

    health = transcript.health()

    assert health.corrupt_lines == [2]
    assert health.ok is False
    assert "corrupt lines: 2" in health.render()


def test_duplicate_sequence_numbers_are_reported(tmp_path):
    transcript = _transcript(tmp_path)
    transcript.append_message(_message("one"))
    line = open(transcript.path, encoding="utf-8").read().splitlines()[-1]
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
    state = create_app_state(cwd=str(tmp_path), persist_path=str(tmp_path / "sessions" / "abc.json"))
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
