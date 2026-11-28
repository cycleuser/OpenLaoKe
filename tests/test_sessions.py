"""Tests for session persistence (save, list, load, delete, cleanup).

Every test uses a SessionManager pointed at tmp_path, so the real
~/.openlaoke/sessions is never touched. The interesting part is the round trip:
what survives a save/load cycle and how a hand-written or corrupt file degrades.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from openlaoke.core.sessions import SessionInfo, SessionManager, _message_from_dict
from openlaoke.core.state import create_app_state
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    SystemMessage,
    TaskState,
    TaskStatus,
    TaskType,
    TokenUsage,
    UserMessage,
)


@pytest.fixture()
def manager(tmp_path):
    return SessionManager(session_dir=str(tmp_path / "sessions"))


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path), model="test-model")


def write_session(directory, name: str, payload: dict) -> str:
    path = os.path.join(directory, f"{name}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


def test_manager_creates_its_directory(tmp_path) -> None:
    target = tmp_path / "nested" / "sessions"
    SessionManager(session_dir=str(target))
    assert target.is_dir()


def test_manager_defaults_to_the_home_directory() -> None:
    manager = SessionManager()
    assert manager.session_dir.endswith(os.path.join(".openlaoke", "sessions"))


# --------------------------------------------------------------------------- #
# Save
# --------------------------------------------------------------------------- #


def test_save_session_writes_the_file_and_sets_the_persist_path(manager, state) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="hello"))
    path = manager.save_session(state)

    assert path == os.path.join(manager.session_dir, f"{state.session_id}.json")
    assert os.path.exists(path)
    assert state._persist_path == path

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["session_id"] == state.session_id
    assert data["messages"][0]["content"] == "hello"
    assert data["session_config"]["model"] == "test-model"


def test_save_is_idempotent_across_calls(manager, state) -> None:
    state.messages.append(UserMessage(role=MessageRole.USER, content="one"))
    path = manager.save_session(state)
    state.messages.append(UserMessage(role=MessageRole.USER, content="two"))
    manager.save_session(state)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert len(data["messages"]) == 2


# --------------------------------------------------------------------------- #
# List
# --------------------------------------------------------------------------- #


def test_list_sessions_is_empty_for_a_fresh_directory(manager) -> None:
    assert manager.list_sessions() == []


def test_list_sessions_returns_summaries_newest_first(manager) -> None:
    write_session(
        manager.session_dir,
        "old",
        {
            "session_id": "old",
            "created_at": 1000.0,
            "cwd": "/a",
            "messages": [{"role": "user", "content": "x"}],
            "tasks": {"t1": {}, "t2": {}},
            "session_config": {"model": "m-old"},
        },
    )
    write_session(
        manager.session_dir,
        "new",
        {
            "session_id": "new",
            "created_at": 2000.0,
            "cwd": "/b",
            "messages": [],
            "session_config": {"model": "m-new"},
        },
    )
    sessions = manager.list_sessions()
    assert [s.session_id for s in sessions] == ["new", "old"]
    newest = sessions[0]
    assert newest.model == "m-new"
    assert newest.cwd == "/b"
    assert newest.message_count == 0
    assert newest.task_count == 0
    assert sessions[1].message_count == 1
    assert sessions[1].task_count == 2


def test_list_sessions_falls_back_to_the_filename_and_mtime(manager) -> None:
    path = write_session(manager.session_dir, "no-id", {"messages": []})
    sessions = manager.list_sessions()
    assert sessions[0].session_id == "no-id"
    assert sessions[0].created_at == pytest.approx(os.path.getmtime(path))
    assert sessions[0].model == "unknown"
    assert sessions[0].cwd == ""


def test_list_sessions_skips_non_json_and_corrupt_files(manager) -> None:
    write_session(manager.session_dir, "good", {"session_id": "good", "messages": []})
    Path(manager.session_dir, "notes.txt").write_text("nope")
    Path(manager.session_dir, "broken.json").write_text("{oops")

    sessions = manager.list_sessions()
    assert [s.session_id for s in sessions] == ["good"]


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #


def test_load_missing_session_returns_none(manager) -> None:
    assert manager.load_session("ghost") is None


def test_save_then_load_round_trips_messages(manager, state) -> None:
    state.messages.extend(
        [
            UserMessage(role=MessageRole.USER, content="question"),
            AssistantMessage(role=MessageRole.ASSISTANT, content="answer", stop_reason="stop"),
            SystemMessage(role=MessageRole.SYSTEM, content="tool output", subtype="result"),
        ]
    )
    manager.save_session(state)

    loaded = manager.load_session(state.session_id)
    assert loaded is not None
    assert [type(m).__name__ for m in loaded.messages] == [
        "UserMessage",
        "AssistantMessage",
        "SystemMessage",
    ]
    assert loaded.messages[0].content == "question"
    assert loaded.messages[1].stop_reason == "stop"
    assert loaded.messages[2].subtype == "result"
    assert loaded.session_id == state.session_id
    assert loaded.cwd == state.cwd
    assert loaded.session_config.model == "test-model"


def test_load_restores_usage_cost_and_counters(manager, state, tmp_path) -> None:
    state.token_usage = TokenUsage(input_tokens=10, output_tokens=5, cache_read_tokens=3)
    state.tool_call_counts = {"Read": 2}
    state.edit_stats = {"files_created": 1}
    state.todo_state = {"todos": [{"content": "x"}]}
    state.compact_state = {"used_tokens": 42}
    state.guard_state = {"hits": 1}
    state.risk_events = [{"cmd": "rm -rf /"}]
    manager.save_session(state)

    loaded = manager.load_session(state.session_id)
    assert loaded is not None
    assert loaded.token_usage.input_tokens == 10
    assert loaded.token_usage.cache_read_tokens == 3
    assert loaded.tool_call_counts == {"Read": 2}
    assert loaded.edit_stats == {"files_created": 1}
    assert loaded.todo_state == {"todos": [{"content": "x"}]}
    assert loaded.compact_state == {"used_tokens": 42}
    assert loaded.guard_state == {"hits": 1}
    assert loaded.risk_events == [{"cmd": "rm -rf /"}]
    assert loaded.cost_info.input_cost == state.cost_info.input_cost


def test_load_restores_tasks_including_unknown_enum_values(manager, state) -> None:
    state.tasks["ok"] = TaskState(
        id="ok", type=TaskType.LOCAL_BASH, status=TaskStatus.RUNNING, description="d"
    )
    manager.save_session(state)

    path = os.path.join(manager.session_dir, f"{state.session_id}.json")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["tasks"]["weird"] = {
        "type": "wat",
        "status": "bogus",
        "description": "fallback",
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)

    loaded = manager.load_session(state.session_id)
    assert loaded is not None
    assert loaded.tasks["ok"].status == TaskStatus.RUNNING
    assert loaded.tasks["weird"].type == TaskType.LOCAL_BASH
    assert loaded.tasks["weird"].status == TaskStatus.PENDING
    assert loaded.tasks["weird"].description == "fallback"


def test_load_restores_insomnia_settings(manager, state) -> None:
    state.insomnia_mode = True
    state.insomnia_task_queue = [{"prompt": "task", "attempts": 2, "added_at": 1.0}]
    state.insomnia_max_iterations = 7
    state.insomnia_auto_accept = True
    state.insomnia_log_path = "/tmp/log"
    manager.save_session(state)

    loaded = manager.load_session(state.session_id)
    assert loaded is not None
    assert loaded.insomnia_mode is True
    assert [task["prompt"] for task in loaded.insomnia_task_queue] == ["task"]
    assert loaded.insomnia_task_queue[0]["attempts"] == 2
    assert loaded.insomnia_max_iterations == 7
    assert loaded.insomnia_auto_accept is True
    assert loaded.insomnia_log_path == "/tmp/log"


def test_a_hand_edited_insomnia_block_cannot_wedge_the_run(manager, state) -> None:
    """A budget of "lots" used to raise inside every turn, forever."""
    manager.save_session(state)
    path = os.path.join(manager.session_dir, f"{state.session_id}.json")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["insomnia_mode"] = "yes"
    data["insomnia_auto_accept"] = "false"
    data["insomnia_max_iterations"] = "lots"
    data["insomnia_max_retries"] = None
    data["insomnia_max_cost"] = "ten dollars"
    data["insomnia_artifact_hours"] = -5
    data["insomnia_log_path"] = 42
    data["insomnia_task_queue"] = ["a bare string", {"no": "prompt"}, 17]
    Path(path).write_text(json.dumps(data), encoding="utf-8")

    loaded = manager.load_session(state.session_id)

    assert loaded is not None
    assert loaded.insomnia_mode is True
    assert loaded.insomnia_auto_accept is False, "'false' is not True"
    assert loaded.insomnia_max_iterations == 1000
    assert loaded.insomnia_max_retries == 8
    assert loaded.insomnia_max_cost == 10.0
    assert loaded.insomnia_artifact_hours == 0.0, "a negative window means never prune"
    assert loaded.insomnia_log_path is None, "a number is not a path"
    # The string survives as a task; the other two records are dropped.
    assert [task["prompt"] for task in loaded.insomnia_task_queue] == ["a bare string"]


def test_load_uses_the_model_fallbacks_in_the_file(manager) -> None:
    write_session(
        manager.session_dir,
        "legacy",
        {"session_id": "legacy", "model": "legacy-model", "messages": []},
    )
    loaded = manager.load_session("legacy")
    assert loaded is not None
    assert loaded.session_config.model == "legacy-model"

    write_session(manager.session_dir, "bare", {"session_id": "bare", "messages": []})
    default_loaded = manager.load_session("bare")
    assert default_loaded.session_config.model == "claude-sonnet-4-20250514"


def test_load_tolerates_missing_optional_sections(manager) -> None:
    write_session(manager.session_dir, "minimal", {"session_id": "minimal"})
    loaded = manager.load_session("minimal")
    assert loaded is not None
    assert loaded.messages == []
    assert loaded.tasks == {}
    assert loaded.token_usage.input_tokens == 0


def test_load_returns_none_for_a_corrupt_file(manager) -> None:
    Path(manager.session_dir, "bad.json").write_text("{nope")
    assert manager.load_session("bad") is None


def test_load_latest_picks_the_newest_session(manager) -> None:
    write_session(manager.session_dir, "a", {"session_id": "a", "created_at": 1.0, "messages": []})
    write_session(manager.session_dir, "b", {"session_id": "b", "created_at": 9.0, "messages": []})
    loaded = manager.load_latest()
    assert loaded is not None
    assert loaded.session_id == "b"


def test_load_latest_without_sessions(manager) -> None:
    assert manager.load_latest() is None


def test_load_latest_uses_the_filename_when_the_file_has_no_session_id(manager) -> None:
    write_session(
        manager.session_dir, "good", {"session_id": "good", "created_at": 1.0, "messages": []}
    )
    write_session(manager.session_dir, "legacy", {"created_at": 5.0})
    loaded = manager.load_latest()
    assert loaded is not None
    # Without the filename fallback the resumed session would keep an empty id
    # and its next save would write a file literally called ".json".
    assert loaded.session_id == "legacy"


# --------------------------------------------------------------------------- #
# Delete / cleanup
# --------------------------------------------------------------------------- #


def test_delete_session(manager) -> None:
    write_session(manager.session_dir, "gone", {"session_id": "gone", "messages": []})
    assert manager.delete_session("gone") is True
    assert manager.delete_session("gone") is False


def test_cleanup_old_sessions_removes_only_expired_ones(manager) -> None:
    now = time.time()
    write_session(
        manager.session_dir, "ancient", {"session_id": "ancient", "created_at": now - 90 * 86400}
    )
    write_session(manager.session_dir, "recent", {"session_id": "recent", "created_at": now})

    removed = manager.cleanup_old_sessions(max_age_days=30)

    assert removed == 1
    assert [s.session_id for s in manager.list_sessions()] == ["recent"]


# --------------------------------------------------------------------------- #
# Message decoding
# --------------------------------------------------------------------------- #


def test_message_from_dict_prefers_the_typed_parser() -> None:
    message = _message_from_dict({"type": "user", "content": "hi"})
    assert isinstance(message, UserMessage)
    assert message.content == "hi"


def test_message_from_dict_falls_back_to_a_system_message() -> None:
    message = _message_from_dict({"content": "legacy", "subtype": "warning", "tool_use_id": "c1"})
    assert isinstance(message, SystemMessage)
    assert message.content == "legacy"
    assert message.subtype == "warning"
    assert message.tool_use_id == "c1"


def test_session_info_defaults() -> None:
    info = SessionInfo(
        session_id="s", path="/p", created_at=0.0, message_count=0, task_count=0, model="m", cwd=""
    )
    assert info.session_id == "s"


def test_message_from_dict_fallback_defaults() -> None:
    message = _message_from_dict({})
    assert isinstance(message, SystemMessage)
    assert message.content == ""
    assert message.subtype == "info"
    assert message.tool_use_id == ""


def test_message_from_dict_keeps_a_defensive_fallback(monkeypatch) -> None:
    # message_from_dict currently always returns a message, but the wrapper's
    # contract tolerates None, so the fallback stays and is pinned here.
    import openlaoke.core.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod, "message_from_dict", lambda _data: None)
    message = sessions_mod._message_from_dict({"content": "kept", "subtype": "error"})
    assert isinstance(message, SystemMessage)
    assert message.content == "kept"
    assert message.subtype == "error"


def test_an_old_export_in_the_sessions_directory_is_not_a_session(manager, state) -> None:
    manager.save_session(state)
    # /export used to write {"session_id": ..., "exported_at": ...} here.
    write_session(
        manager.session_dir,
        f"session_{state.session_id}",
        {"session_id": state.session_id, "exported_at": "now", "messages": []},
    )

    listed = manager.list_sessions()

    assert [Path(item.path).name for item in listed] == [f"{state.session_id}.json"]
