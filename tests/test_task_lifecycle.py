"""Tests for the task lifecycle: shell jobs, cancellation and sub-agents.

The shell paths run real processes (echo, sleep, false) rather than a mock, so
the deadline, backgrounding and cancellation behaviour is the real thing.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import pytest

from openlaoke.core import agent_runner
from openlaoke.core.state import create_app_state
from openlaoke.core.task import (
    BashOutcome,
    TaskManager,
    get_task_manager,
)
from openlaoke.types.core_types import TaskStatus, TaskType


@pytest.fixture(autouse=True)
def isolated_outputs(tmp_path, monkeypatch):
    """Keep task logs out of the real ~/.openlaoke."""
    home = tmp_path / "home"
    (home / ".openlaoke").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path))


@pytest.fixture()
def manager(state):
    return TaskManager(state)


# --------------------------------------------------------------------------- #
# Task records
# --------------------------------------------------------------------------- #


def test_create_task_state_records_a_pending_task(manager, state) -> None:
    task = manager.create_task_state(TaskType.LOCAL_BASH, "list files", "call_1")

    assert task.status is TaskStatus.PENDING
    assert task.description == "list files"
    assert task.tool_use_id == "call_1"
    assert task.output_file.endswith(f"{task.id}.log")
    assert state.get_task(task.id) is task


def test_task_ids_are_unique(manager) -> None:
    first = manager.create_task_state(TaskType.LOCAL_BASH, "a")
    second = manager.create_task_state(TaskType.LOCAL_BASH, "a")
    assert first.id != second.id


def test_get_task_manager_returns_one_instance_per_state(state) -> None:
    assert get_task_manager(state) is get_task_manager(state)


def test_an_unwritable_output_directory_falls_back_to_temp(monkeypatch, state) -> None:
    real_open = open

    def fake_open(path, *args, **kwargs):
        # The write test file is what fails when the directory is read-only.
        if str(path).endswith(".write_test"):
            raise PermissionError("read-only")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    manager = TaskManager(state)

    assert "openlaoke_task_outputs" in manager._output_dir


# --------------------------------------------------------------------------- #
# run_bash
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_successful_command_returns_its_output_and_code(manager) -> None:
    outcome = await manager.run_bash("echo hello", "say hello")

    assert outcome.output.strip() == "hello"
    assert outcome.exit_code == 0
    assert outcome.finished is True
    assert outcome.task_id


@pytest.mark.asyncio
async def test_a_failing_command_reports_the_exit_code(manager, state) -> None:
    outcome = await manager.run_bash("exit 3", "fail")

    assert outcome.exit_code == 3
    assert state.get_task(outcome.task_id).status is TaskStatus.FAILED


@pytest.mark.asyncio
async def test_stdout_and_stderr_both_land_in_the_log(manager) -> None:
    outcome = await manager.run_bash("echo out; echo err 1>&2", "both")
    assert "out" in outcome.output
    assert "err" in outcome.output


@pytest.mark.asyncio
async def test_the_working_directory_is_honoured(manager, tmp_path) -> None:
    target = tmp_path / "sub"
    target.mkdir()

    outcome = await manager.run_bash("pwd", "where am i", working_dir=str(target))

    assert outcome.output.strip() == str(target)


@pytest.mark.asyncio
async def test_a_hard_timeout_kills_the_process(manager, state) -> None:
    started = time.monotonic()
    outcome = await manager.run_bash("sleep 5", "sleep", timeout=0.3)
    elapsed = time.monotonic() - started

    assert outcome.timed_out is True
    assert outcome.backgrounded is False
    assert outcome.exit_code is None
    assert elapsed < 4
    assert state.get_task(outcome.task_id).status is TaskStatus.KILLED


@pytest.mark.asyncio
async def test_a_soft_deadline_backgrounds_the_job(manager, state) -> None:
    outcome = await manager.run_bash("sleep 1; echo done", "slow", auto_background_ms=100)

    assert outcome.backgrounded is True
    assert outcome.finished is False
    assert state.get_task(outcome.task_id).status is TaskStatus.RUNNING

    # The job keeps going and its output can be read once it finishes.
    final = await manager.wait_for(outcome.task_id, timeout=5)
    assert final is not None
    assert final.status is TaskStatus.COMPLETED
    assert "done" in manager.read_output(final)


@pytest.mark.asyncio
async def test_no_deadline_waits_for_the_command(manager) -> None:
    outcome = await manager.run_bash("echo quick", "quick", auto_background_ms=None)
    assert outcome.finished is True


@pytest.mark.asyncio
async def test_a_command_that_cannot_start_is_reported(manager, monkeypatch) -> None:
    async def boom(*args, **kwargs):
        raise OSError("no shell here")

    monkeypatch.setattr("asyncio.create_subprocess_shell", boom)
    outcome = await manager.run_bash("echo x", "x")

    assert outcome.exit_code == 1
    assert "no shell here" in outcome.output


# --------------------------------------------------------------------------- #
# Reading and cancelling
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_read_output_can_start_at_an_offset(manager) -> None:
    outcome = await manager.run_bash("echo abcdef", "text")
    task = manager.app_state.get_task(outcome.task_id)

    whole = manager.read_output(task)
    tail = manager.read_output(task, offset=len(whole.splitlines()[0]))

    assert whole.strip() == "abcdef"
    assert tail.strip() == ""


@pytest.mark.asyncio
async def test_tail_output_keeps_the_last_lines(manager) -> None:
    outcome = await manager.run_bash("printf '1\\n2\\n3\\n4\\n'", "numbers")
    task = manager.app_state.get_task(outcome.task_id)

    assert manager.tail_output(task, 2) == "3\n4"


@pytest.mark.asyncio
async def test_cancel_stops_a_running_job(manager, state) -> None:
    outcome = await manager.run_bash("sleep 5", "long", auto_background_ms=100)

    assert await manager.cancel(outcome.task_id) is True
    await asyncio.sleep(0.2)
    assert state.get_task(outcome.task_id).status is TaskStatus.KILLED


@pytest.mark.asyncio
async def test_cancel_rejects_a_finished_or_unknown_task(manager) -> None:
    outcome = await manager.run_bash("echo done", "done")

    assert await manager.cancel(outcome.task_id) is False
    assert await manager.cancel("no-such-task") is False


def test_kill_task_marks_an_active_task_killed(manager, state) -> None:
    task = manager.create_task_state(TaskType.LOCAL_BASH, "pending")
    task.status = TaskStatus.RUNNING
    state.update_task(task)

    manager.kill_task(task.id)

    assert state.get_task(task.id).status is TaskStatus.KILLED


def test_kill_task_leaves_a_finished_task_alone(manager, state) -> None:
    task = manager.create_task_state(TaskType.LOCAL_BASH, "done")
    task.status = TaskStatus.COMPLETED
    state.update_task(task)

    manager.kill_task(task.id)

    assert state.get_task(task.id).status is TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_active_tasks_excludes_finished_ones(manager, state) -> None:
    finished = await manager.run_bash("echo done", "done")
    pending = manager.create_task_state(TaskType.LOCAL_BASH, "pending")

    active = [task.id for task in manager.get_active_tasks()]

    assert pending.id in active
    assert finished.task_id not in active


@pytest.mark.asyncio
async def test_wait_for_returns_none_for_an_unknown_task(manager) -> None:
    assert await manager.wait_for("ghost", timeout=0.1) is None


# --------------------------------------------------------------------------- #
# BashOutcome
# --------------------------------------------------------------------------- #


def test_bash_outcome_finished_flag() -> None:
    assert BashOutcome("x", 0).finished is True
    assert BashOutcome("x", None, backgrounded=True).finished is False
    assert BashOutcome("x", None, timed_out=True).finished is False


# --------------------------------------------------------------------------- #
# run_agent
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_agent_records_a_completed_subagent(monkeypatch, manager, state) -> None:
    async def fake_run(**kwargs):
        assert kwargs["prompt"] == "do it"
        assert kwargs["description"] == "task"
        return "the result"

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", fake_run)

    result = await manager.run_agent("do it", "task")

    assert result == "the result"
    tasks = state.get_all_tasks()
    assert tasks[-1].status is TaskStatus.COMPLETED
    assert tasks[-1].output == "the result"


@pytest.mark.asyncio
async def test_run_agent_turns_a_failure_into_a_message(monkeypatch, manager, state) -> None:
    async def fake_run(**kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", fake_run)

    result = await manager.run_agent("do it", "task")

    assert result == "Agent failed: model exploded"
    assert state.get_all_tasks()[-1].status is TaskStatus.FAILED


@pytest.mark.asyncio
async def test_run_agent_propagates_cancellation(monkeypatch, manager, state) -> None:
    async def fake_run(**kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", fake_run)

    with pytest.raises(asyncio.CancelledError):
        await manager.run_agent("do it", "task")
    assert state.get_all_tasks()[-1].status is TaskStatus.KILLED


# --------------------------------------------------------------------------- #
# Sub-agent state files
# --------------------------------------------------------------------------- #


def test_subagent_state_round_trips(tmp_path) -> None:
    path = str(tmp_path / "sub" / "subagent_1.json")

    agent_runner._save_subagent_state(path, "prompt", [{"role": "user"}], ["part"], 3, "failed", "boom")
    loaded = agent_runner._load_subagent_state(path)

    assert loaded is not None
    assert loaded["prompt"] == "prompt"
    assert loaded["iteration"] == 3
    assert loaded["status"] == "failed"
    assert loaded["error"] == "boom"


def test_saving_to_an_impossible_path_is_only_logged(tmp_path) -> None:
    # A file where the directory should be makes makedirs fail.
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    agent_runner._save_subagent_state(str(blocker / "sub" / "s.json"), "p", [], [], 0, "running")


def test_loading_a_missing_or_broken_state_returns_none(tmp_path) -> None:
    assert agent_runner._load_subagent_state(str(tmp_path / "absent.json")) is None

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert agent_runner._load_subagent_state(str(broken)) is None


def test_list_resumable_subagents_filters_and_sorts(tmp_path, monkeypatch) -> None:
    base = tmp_path / "home" / ".openlaoke"
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    (base / "subagent_a.json").write_text(
        json.dumps({"status": "failed", "iteration": 2, "result_parts": ["x"], "error": "e"}),
        encoding="utf-8",
    )
    (base / "subagent_b.json").write_text(
        json.dumps({"status": "completed", "iteration": 5, "result_parts": []}), encoding="utf-8"
    )
    (base / "subagent_c.json").write_text(
        json.dumps({"status": "cancelled", "iteration": 1, "result_parts": ["x", "y"]}),
        encoding="utf-8",
    )
    (base / "subagent_broken.json").write_text("{nope", encoding="utf-8")
    (base / "notes.json").write_text("{}", encoding="utf-8")

    resumable = agent_runner.list_resumable_subagents()

    assert [item["id"] for item in resumable] == ["c", "a"]
    assert resumable[0]["result_chars"] == 2
    assert resumable[1]["error"] == "e"


def test_list_resumable_subagents_without_a_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "nothing-here"))
    assert agent_runner.list_resumable_subagents() == []


def test_a_failed_subagent_summary_mentions_how_to_resume() -> None:
    summary = agent_runner._partial_summary(["half a thought"], "rate limited", "/tmp/s.json")

    assert "Sub-agent failed: rate limited" in summary
    assert "half a thought" in summary
    assert "resume_from" in summary
    assert "/tmp/s.json" in summary


def test_a_failed_subagent_summary_without_output() -> None:
    summary = agent_runner._partial_summary([], "boom", "/tmp/s.json")
    assert "(no assistant output before failure)" in summary


@pytest.mark.asyncio
async def test_run_subagent_without_a_provider_says_so(state) -> None:
    task = state.get_all_tasks()
    assert task == []

    from openlaoke.types.core_types import TaskState

    result = await agent_runner.run_subagent(
        prompt="hi",
        description="d",
        app_state=state,
        task_state=TaskState(id="t1", type=TaskType.LOCAL_AGENT, status=TaskStatus.RUNNING),
    )

    assert result == "Sub-agent error: No provider configured"


# --------------------------------------------------------------------------- #
# run_subagent: the state contract around the loop
# --------------------------------------------------------------------------- #


def configured_state(tmp_path) -> Any:
    """An AppState with a provider that reports itself as configured."""
    from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType

    state = create_app_state(cwd=str(tmp_path))
    state.multi_provider_config = MultiProviderConfig(
        providers={
            "main": ProviderConfig(
                provider_type=ProviderType.OPENAI,
                api_key="sk-test",
                base_url="https://api.example.com/v1",
                default_model="m",
                models=["m"],
            )
        },
        active_provider="main",
        active_model="m",
    )
    return state


def task_state(tmp_path) -> Any:
    from openlaoke.types.core_types import TaskState

    return TaskState(
        id="t1",
        type=TaskType.LOCAL_AGENT,
        status=TaskStatus.RUNNING,
        output_file=str(tmp_path / "out.log"),
    )


@pytest.mark.asyncio
async def test_a_successful_subagent_cleans_up_its_state_file(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from openlaoke.core import engine

    state = configured_state(tmp_path)
    seen: dict[str, Any] = {}

    async def fake_loop(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn", messages=[{"role": "user"}], text_parts=["first", "second"], error=None
        )

    monkeypatch.setattr(engine, "run_loop", fake_loop)

    result = await agent_runner.run_subagent(
        "do it", "task", state, task_state(tmp_path)
    )

    assert result == "first\nsecond"
    assert seen["messages"] == [{"role": "user", "content": "do it"}]
    assert "sub-agent" in seen["system_prompt"]
    # The saved state is removed once the run finished, so it does not show up
    # as resumable later.
    assert agent_runner.list_resumable_subagents() == []


@pytest.mark.asyncio
async def test_a_subagent_without_output_says_no_output(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from openlaoke.core import engine

    state = configured_state(tmp_path)

    async def fake_loop(**kwargs):
        return SimpleNamespace(stop_reason="end_turn", messages=[], text_parts=["", ""], error=None)

    monkeypatch.setattr(engine, "run_loop", fake_loop)

    assert await agent_runner.run_subagent("p", "d", state, task_state(tmp_path)) == "(no output)"


@pytest.mark.asyncio
async def test_a_failed_subagent_keeps_a_resumable_state_file(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from openlaoke.core import engine

    state = configured_state(tmp_path)

    async def fake_loop(**kwargs):
        return SimpleNamespace(
            stop_reason=engine.STOP_ERROR,
            messages=[{"role": "assistant", "content": "partial"}],
            text_parts=["half"],
            error="rate limited",
        )

    monkeypatch.setattr(engine, "run_loop", fake_loop)

    result = await agent_runner.run_subagent("p", "d", state, task_state(tmp_path))

    assert "Sub-agent failed: rate limited" in result
    assert "half" in result
    resumable = agent_runner.list_resumable_subagents()
    assert len(resumable) == 1
    assert resumable[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_a_cancelled_subagent_saves_its_state_and_reraises(tmp_path, monkeypatch) -> None:
    from openlaoke.core import engine

    state = configured_state(tmp_path)

    async def fake_loop(**kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(engine, "run_loop", fake_loop)

    with pytest.raises(asyncio.CancelledError):
        await agent_runner.run_subagent("p", "d", state, task_state(tmp_path))

    resumable = agent_runner.list_resumable_subagents()
    assert [item["status"] for item in resumable] == ["cancelled"]


@pytest.mark.asyncio
async def test_a_subagent_resumes_from_a_saved_conversation(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from openlaoke.core import engine

    state = configured_state(tmp_path)
    saved = tmp_path / "saved.json"
    agent_runner._save_subagent_state(
        str(saved),
        "original prompt",
        [{"role": "user", "content": "original prompt"}],
        ["earlier work"],
        2,
        "failed",
        "boom",
    )
    seen: dict[str, Any] = {}

    async def fake_loop(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(stop_reason="end_turn", messages=[], text_parts=["done"], error=None)

    monkeypatch.setattr(engine, "run_loop", fake_loop)

    result = await agent_runner.run_subagent(
        "p", "d", state, task_state(tmp_path), resume_from=str(saved)
    )

    assert result == "done"
    # The recorded conversation is reused instead of starting from the prompt.
    assert seen["messages"] == [{"role": "user", "content": "original prompt"}]
    # And the remaining step budget accounts for the two turns already spent.
    from openlaoke.core.harness_modes import get_mode

    mode = get_mode(state.harness_mode)
    assert seen["policy"].max_iterations == mode.max_steps - 2


@pytest.mark.asyncio
async def test_a_missing_resume_file_starts_over(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    from openlaoke.core import engine

    state = configured_state(tmp_path)
    seen: dict[str, Any] = {}

    async def fake_loop(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(stop_reason="end_turn", messages=[], text_parts=["ok"], error=None)

    monkeypatch.setattr(engine, "run_loop", fake_loop)

    await agent_runner.run_subagent(
        "fresh prompt", "d", state, task_state(tmp_path), resume_from=str(tmp_path / "gone.json")
    )

    assert seen["messages"] == [{"role": "user", "content": "fresh prompt"}]
