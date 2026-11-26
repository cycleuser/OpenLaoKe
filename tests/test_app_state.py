"""Tests for AppState: notifications, persistence, tasks, counters and lazily built stores."""

from __future__ import annotations

import json
import os
from pathlib import Path

from openlaoke.core.state import AppState, create_app_state
from openlaoke.types.core_types import (
    CostInfo,
    MessageRole,
    TaskState,
    TaskStatus,
    TaskType,
    TokenUsage,
    UserMessage,
)


def make(tmp_path: Path) -> AppState:
    state = create_app_state(cwd=str(tmp_path), model="gpt-4o")
    state._persist_path = None
    return state


# --------------------------------------------------------------------------- #
# cwd and environment
# --------------------------------------------------------------------------- #


def test_set_cwd_keeps_both_fields_in_sync(tmp_path) -> None:
    state = make(tmp_path)
    target = tmp_path / "sub"
    target.mkdir()

    state.set_cwd(str(target))

    assert state.cwd == str(target)
    assert state.working_directory == state.cwd
    assert state.get_cwd() == str(target)


def test_a_relative_cwd_is_made_absolute(tmp_path, monkeypatch) -> None:
    state = make(tmp_path)
    monkeypatch.chdir(tmp_path)

    state.set_cwd("nested")

    assert os.path.isabs(state.cwd)
    assert state.cwd.endswith("nested")


def test_env_vars_merge_over_the_process_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENLAOKE_TEST_VAR", "system")
    state = make(tmp_path)
    state.env_vars["OPENLAOKE_TEST_VAR"] = "session"

    merged = state.get_env_vars()

    assert merged["OPENLAOKE_TEST_VAR"] == "session"
    assert "PATH" in merged


# --------------------------------------------------------------------------- #
# messages
# --------------------------------------------------------------------------- #


def test_message_accessors(tmp_path) -> None:
    state = make(tmp_path)
    assert state.get_last_message() is None
    assert state.get_message_count() == 0
    assert state.get_messages() == []

    state.add_message(UserMessage(role=MessageRole.USER, content="hello"), persist=False)

    assert state.get_message_count() == 1
    assert state.get_messages()[0].content == "hello"
    assert state.get_last_message() is state.messages[-1]

    # The returned list is a copy: appending to it cannot corrupt history.
    state.get_messages().append("junk")
    assert state.get_message_count() == 1


# --------------------------------------------------------------------------- #
# tasks and counters
# --------------------------------------------------------------------------- #


def task(task_id: str, status: TaskStatus = TaskStatus.RUNNING) -> TaskState:
    return TaskState(id=task_id, type=TaskType.LOCAL_BASH, status=status, description="job")


def test_task_registry(tmp_path) -> None:
    state = make(tmp_path)
    running = task("bg_1")
    done = task("bg_2", TaskStatus.COMPLETED)

    state.add_task(running)
    state.add_task(done)

    assert state.get_task("bg_1") is running
    assert state.get_task("missing") is None
    assert {t.id for t in state.get_all_tasks()} == {"bg_1", "bg_2"}
    assert [t.id for t in state.get_active_tasks()] == ["bg_1"]

    running.status = TaskStatus.KILLED
    state.update_task(running)

    assert state.get_active_tasks() == []


def test_failed_and_killed_tasks_are_not_active(tmp_path) -> None:
    state = make(tmp_path)
    for index, status in enumerate(
        (TaskStatus.PENDING, TaskStatus.FAILED, TaskStatus.KILLED, TaskStatus.COMPLETED)
    ):
        state.tasks[f"t{index}"] = task(f"t{index}", status)

    assert [t.status for t in state.get_active_tasks()] == [TaskStatus.PENDING]


def test_token_and_cost_accumulators(tmp_path) -> None:
    state = make(tmp_path)

    state.accumulate_tokens(TokenUsage(input_tokens=10, output_tokens=5))
    state.accumulate_tokens(TokenUsage(input_tokens=1, output_tokens=2))
    state.accumulate_cost(
        CostInfo(input_cost=0.1, output_cost=0.2, cache_read_cost=0.05, cache_creation_cost=0.01)
    )
    state.accumulate_cost(
        CostInfo(input_cost=0.1, output_cost=0.2, cache_read_cost=0.05, cache_creation_cost=0.01)
    )

    assert state.token_usage.input_tokens == 11
    assert state.token_usage.output_tokens == 7
    assert round(state.cost_info.input_cost, 4) == 0.2
    assert round(state.cost_info.output_cost, 4) == 0.4
    assert round(state.cost_info.cache_read_cost, 4) == 0.1
    assert round(state.cost_info.cache_creation_cost, 4) == 0.02


# --------------------------------------------------------------------------- #
# listeners
# --------------------------------------------------------------------------- #


def test_listeners_are_notified_and_can_unsubscribe(tmp_path) -> None:
    state = make(tmp_path)
    seen: list[str] = []

    def listener(app: AppState) -> None:
        seen.append(app.session_id)

    state.subscribe(listener)
    state.set_error("boom")

    assert seen == [state.session_id]
    assert state.error_message == "boom"

    state.unsubscribe(listener)
    state.set_error(None)
    assert seen == [state.session_id]


def test_unsubscribing_an_unknown_listener_is_a_no_op(tmp_path) -> None:
    state = make(tmp_path)

    state.unsubscribe(lambda app: None)

    assert state._listeners == []


def test_a_raising_listener_does_not_break_the_caller(tmp_path) -> None:
    state = make(tmp_path)
    seen: list[int] = []

    def bad(_app: AppState) -> None:
        raise RuntimeError("listener is broken")

    state.subscribe(bad)
    state.subscribe(lambda app: seen.append(1))

    state.set_pending_input("typed")

    assert seen == [1]
    assert state.pending_user_input == "typed"


# --------------------------------------------------------------------------- #
# context cap
# --------------------------------------------------------------------------- #


def test_context_cap_round_trip(tmp_path) -> None:
    state = make(tmp_path)

    assert state.context_cap is None

    state.set_context_cap(32000)
    assert state.context_cap == 32000

    state.set_context_cap(0)
    assert state.context_cap is None

    state.set_context_cap(None)
    assert "context_cap" not in state.compact_state


def test_a_nonsense_context_cap_is_ignored(tmp_path) -> None:
    state = make(tmp_path)
    state.compact_state["context_cap"] = "lots"

    assert state.context_cap is None


# --------------------------------------------------------------------------- #
# persistence
# --------------------------------------------------------------------------- #


def test_persisting_writes_the_session_file(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path), model="gpt-4o")
    path = tmp_path / "sessions" / "s.json"
    state.set_persist_path(str(path))
    state.add_message(UserMessage(role=MessageRole.USER, content="hi"), persist=False)
    state.accumulate_tokens(TokenUsage(input_tokens=3, output_tokens=2))
    state.set_context_cap(8000)

    state._persist()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["session_id"] == state.session_id
    assert data["model"] == "gpt-4o"
    assert data["messages"][0]["content"] == "hi"
    assert data["token_usage"]["input_tokens"] == 3
    assert data["compact_state"]["context_cap"] == 8000


def test_persisting_without_a_path_does_nothing(tmp_path) -> None:
    state = make(tmp_path)

    state._persist()

    assert state._persist_path is None


def test_a_failed_persist_is_logged_not_raised(tmp_path, caplog) -> None:
    state = create_app_state(cwd=str(tmp_path))
    state.set_persist_path(str(tmp_path / "readonly" / "s.json"))
    (tmp_path / "readonly").mkdir()
    os.chmod(tmp_path / "readonly", 0o500)
    try:
        with caplog.at_level("WARNING"):
            state._persist()
    finally:
        os.chmod(tmp_path / "readonly", 0o700)

    assert any("Failed to persist" in message for message in caplog.messages)


def test_to_dict_is_a_summary(tmp_path) -> None:
    state = make(tmp_path)
    state.add_message(UserMessage(role=MessageRole.USER, content="x"), persist=False)
    state.accumulate_tokens(TokenUsage(input_tokens=1, output_tokens=1))

    summary = state.to_dict()

    assert summary["session_id"] == state.session_id
    assert summary["message_count"] == 1
    assert summary["task_count"] == 0
    assert summary["token_usage"] == {"input_tokens": 1, "output_tokens": 1}
    assert "total_cost" in summary["cost_info"]


# --------------------------------------------------------------------------- #
# lazily built stores
# --------------------------------------------------------------------------- #


def test_snapshot_store_is_built_once(tmp_path, monkeypatch) -> None:
    import openlaoke.snapshot.store as store_module

    built: list[bool] = []

    class FakeStore:
        def __init__(self) -> None:
            built.append(True)

    monkeypatch.setattr(store_module, "SnapshotStore", FakeStore)
    state = make(tmp_path)

    first = state.snapshot_store
    second = state.snapshot_store

    assert first is second
    assert built == [True]


def test_file_state_is_built_once(tmp_path) -> None:
    state = make(tmp_path)

    first = state.get_file_state()
    second = state.get_file_state()

    assert first is second
    assert first.was_read("anything") is False


# --------------------------------------------------------------------------- #
# environment helpers and factory
# --------------------------------------------------------------------------- #


def test_a_state_without_a_cwd_uses_the_process_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    state = AppState(session_id="s")
    try:
        assert state.cwd == str(tmp_path)
        assert state.working_directory == state.cwd
    finally:
        state._persist_path = None


def test_session_env_variables_can_be_set_snapshotted_and_unset(tmp_path) -> None:
    state = make(tmp_path)

    state.set_env_var("BUILD_ENV", "staging")

    assert state.snapshot_env()["BUILD_ENV"] == "staging"
    assert state.unset_env_var("BUILD_ENV") is True
    assert state.unset_env_var("BUILD_ENV") is False
    assert "BUILD_ENV" not in state.snapshot_env()


def test_adding_a_message_persists_by_default(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    path = tmp_path / "s.json"
    state.set_persist_path(str(path))

    state.add_message(UserMessage(role=MessageRole.USER, content="persist me"))

    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["messages"][-1]["content"] == "persist me"


def test_the_factory_applies_the_persist_path(tmp_path) -> None:
    path = tmp_path / "sessions" / "s.json"

    state = create_app_state(cwd=str(tmp_path), persist_path=str(path))

    assert state._persist_path == str(path)
    assert state.session_id.startswith("session_")
