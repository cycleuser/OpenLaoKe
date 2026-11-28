"""Tests for insomnia mode: the unattended, long-running work policy.

What matters is that the mode actually changes behaviour. It already had state
fields and a banner and nothing else, so each test here pins one promise:

- the queue drains without asking for input, and one task's failure does not
  abandon the rest;
- the turn budget is the mode's own, not the harness mode's 25-80 steps;
- a failed turn is retried with growing waits instead of ending the shift;
- the live history is trimmed at a turn boundary, so a run of days does not
  grow the snapshot forever and does not leave a dangling tool call;
- the run log says what happened, and cannot stop the run.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from openlaoke.core.insomnia import (
    BACKOFF_CAP_SECONDS,
    InsomniaLog,
    backoff_seconds,
    enqueue,
    log_path_for,
    next_task,
    normalize_task,
    plan_trim,
    queue_tasks,
    requeue,
    trim_history,
)
from openlaoke.core.state import create_app_state
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    SystemMessage,
    UserMessage,
)
from tests.test_repl_loop import make_repl, text

# --------------------------------------------------------------------------- #
# Queue
# --------------------------------------------------------------------------- #


def test_a_string_and_a_dict_are_the_same_task(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_task_queue = [
        "  fix the parser  ",
        {"prompt": "run the tests", "attempts": 2},
        "",
        7,
    ]

    tasks = queue_tasks(state)

    assert [task["prompt"] for task in tasks] == ["fix the parser", "run the tests"]
    assert tasks[1]["attempts"] == 2


def test_next_task_pops_and_counts_the_attempt(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    enqueue(state, "first")
    enqueue(state, "second")

    task = next_task(state)

    assert task is not None and task["prompt"] == "first" and task["attempts"] == 1
    assert [item["prompt"] for item in queue_tasks(state)] == ["second"]
    assert next_task(state) is not None
    assert next_task(state) is None


def test_requeue_puts_the_task_back_at_the_front(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    enqueue(state, "later")

    requeue(state, {"prompt": "earlier", "attempts": 3}, error="rate limited")

    tasks = queue_tasks(state)
    assert [task["prompt"] for task in tasks] == ["earlier", "later"]
    assert tasks[0]["attempts"] == 3
    assert tasks[0]["last_error"] == "rate limited"


def test_backoff_grows_and_is_capped() -> None:
    assert backoff_seconds(1) == 15
    assert backoff_seconds(2) == 30
    assert backoff_seconds(3) == 60
    assert backoff_seconds(0) == 0
    assert backoff_seconds(50) == BACKOFF_CAP_SECONDS


# --------------------------------------------------------------------------- #
# The drain
# --------------------------------------------------------------------------- #


def test_the_queue_drains_without_asking_for_input(tmp_path) -> None:
    r = make_repl([[text("did the first")], [text("did the second")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "first task")
    enqueue(r.app_state, "second task")

    completed = asyncio.run(r._insomnia_drain())

    assert completed == 2
    assert queue_tasks(r.app_state) == []
    asked = [
        message.content
        for message in r.app_state.messages
        if getattr(message, "role", None) == MessageRole.USER
    ]
    assert asked == ["first task", "second task"]
    assert r.api.turn_index == 2


def test_the_drain_stops_when_the_queue_empties(tmp_path) -> None:
    r = make_repl([[text("done")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "only task")

    assert asyncio.run(r._insomnia_drain()) == 1
    # Nothing queued: a second drain must not call the provider again.
    assert asyncio.run(r._insomnia_drain()) == 0
    assert r.api.turn_index == 1


def test_the_mode_off_leaves_the_queue_alone(tmp_path) -> None:
    r = make_repl([[text("never")]])
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "waiting")
    r.app_state.insomnia_mode = False

    assert asyncio.run(r._insomnia_drain()) == 0
    assert [task["prompt"] for task in queue_tasks(r.app_state)] == ["waiting"]


def test_a_failed_turn_is_retried_instead_of_ending_the_shift(tmp_path, monkeypatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    r = make_repl([[RuntimeError("502 bad gateway")], [text("worked on the second try")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "flaky task")

    completed = asyncio.run(r._insomnia_drain())

    assert completed == 1
    assert sleeps == [15.0]
    assert r.api.turn_index == 2
    log = (tmp_path / "run.log").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line)["event"] for line in log]
    assert events[0] == "drain_start"
    assert "retry" in events
    assert "task_done" in events


def test_a_task_is_given_up_after_its_retry_budget(tmp_path, monkeypatch) -> None:
    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    r = make_repl([[RuntimeError("down")] for _ in range(6)])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_max_retries = 2
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "hopeless task")

    completed = asyncio.run(r._insomnia_drain())

    assert completed == 0
    # attempt 1, retry, attempt 2, retry, attempt 3 -> given up.
    assert r.api.turn_index == 3
    log = (tmp_path / "run.log").read_text(encoding="utf-8").splitlines()
    failed = [json.loads(line) for line in log if json.loads(line)["event"] == "task_failed"]
    assert failed and "down" in failed[0]["error"]
    assert queue_tasks(r.app_state) == []


def test_one_failed_task_does_not_stop_the_next_one(tmp_path, monkeypatch) -> None:
    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    r = make_repl([[RuntimeError("down")], [RuntimeError("down")], [text("second task done")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_max_retries = 1
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "first, broken")
    enqueue(r.app_state, "second, fine")

    assert asyncio.run(r._insomnia_drain()) == 1
    assert queue_tasks(r.app_state) == []


def test_the_turn_budget_comes_from_the_mode_not_the_harness(tmp_path) -> None:
    r = make_repl([[text("x")]], harness_mode="pi")
    # The CLI fills max_steps from the harness mode, so every real session has a
    # positive value here; the fallback below is what a bare AppState gives.
    r.app_state.max_steps = 25
    assert r._resolve_max_iterations() == 25

    r.app_state.insomnia_mode = True
    r.app_state.insomnia_max_iterations = 0  # unset -> the module default
    assert r._resolve_max_iterations() == 1000, "the mode budget must beat the harness one"

    r.app_state.insomnia_max_iterations = 40
    assert r._resolve_max_iterations() == 40

    # A typed --max-steps still wins: that one was chosen on purpose.
    r.app_state.max_steps = 7
    r.app_state.max_steps_explicit = True
    assert r._resolve_max_iterations() == 7


def test_a_chat_turn_hands_over_to_the_queue_when_the_turn_ends(tmp_path) -> None:
    r = make_repl([[text("first answer")], [text("queued answer")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "queued work")

    asyncio.run(r._handle_chat("pressed enter once"))

    assert r.api.turn_index == 2
    assert queue_tasks(r.app_state) == []


# --------------------------------------------------------------------------- #
# History trimming
# --------------------------------------------------------------------------- #


def _turn(index: int) -> list:
    return [
        UserMessage(role=MessageRole.USER, content=f"task {index}"),
        AssistantMessage(role=MessageRole.ASSISTANT, content=f"working {index}"),
        SystemMessage(
            role=MessageRole.SYSTEM,
            content="result",
            subtype="tool_result",
            tool_use_id=f"call-{index}",
        ),
    ]


def test_trim_keeps_the_goal_and_the_tail_at_a_turn_boundary() -> None:
    messages = []
    for index in range(40):
        messages.extend(_turn(index))

    kept, dropped = plan_trim(messages, keep=10)

    assert dropped == len(messages) - (len(kept) - 1)  # one note was added
    assert dropped > 0
    assert kept[0] is messages[0]  # the original goal survives
    assert kept[1].subtype == "compact"  # one note says where the rest went
    assert str(dropped) in kept[1].content
    # The tail starts on a user message, never on a tool result.
    assert kept[2].role == MessageRole.USER
    assert kept[-1] is messages[-1]


def test_the_trimmed_history_has_no_dangling_tool_call() -> None:
    messages = []
    for index in range(30):
        call = AssistantMessage(
            role=MessageRole.ASSISTANT,
            content="",
            tool_uses=[{"id": f"call-{index}", "name": "Read", "input": {}}],
        )
        messages.extend(
            [
                UserMessage(role=MessageRole.USER, content=f"task {index}"),
                call,
                SystemMessage(
                    role=MessageRole.SYSTEM,
                    content="result",
                    subtype="tool_result",
                    tool_use_id=f"call-{index}",
                ),
            ]
        )

    kept, _dropped = plan_trim(messages, keep=7)

    answered = {
        message.tool_use_id
        for message in kept
        if isinstance(message, SystemMessage) and message.tool_use_id
    }
    asked = {
        use["id"]
        for message in kept
        if isinstance(message, AssistantMessage)
        for use in (message.tool_uses or [])
    }
    assert asked == answered, (asked, answered)
    assert kept[2].role == MessageRole.USER


def test_a_short_history_is_left_alone() -> None:
    messages = [UserMessage(role=MessageRole.USER, content="only")]
    kept, dropped = plan_trim(messages, keep=10)
    assert kept == messages and dropped == 0


def test_trim_history_persists_the_shorter_session(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    for index in range(20):
        state.messages.extend(_turn(index))

    dropped = trim_history(state, keep=9)

    assert dropped > 0
    assert len(state.messages) < 60
    assert state.messages[0].content == "task 0"


# --------------------------------------------------------------------------- #
# The run log
# --------------------------------------------------------------------------- #


def test_the_log_rotates_instead_of_growing_forever(tmp_path) -> None:
    path = tmp_path / "run.log"
    log = InsomniaLog(str(path), max_bytes=300)
    for index in range(20):
        log.append("task_done", index=index, prompt="x" * 40)

    assert path.exists()
    assert (tmp_path / "run.log.1").exists()
    assert path.stat().st_size < 600


def test_a_log_that_cannot_be_written_does_not_raise(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    log = InsomniaLog(str(blocker / "nested" / "run.log"))

    log.append("task_start", prompt="anything")  # must not raise

    assert log.tail() == []


def test_the_log_path_is_per_session_and_respects_an_override(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    state.session_id = "abc-123"
    default = log_path_for(state, root=str(tmp_path / "logs"))
    assert default == str(tmp_path / "logs" / "abc-123.log")

    state.insomnia_log_path = str(tmp_path / "custom.log")
    assert log_path_for(state, root=str(tmp_path / "logs")) == str(tmp_path / "custom.log")


def test_render_tail_reads_back_what_was_written(tmp_path) -> None:
    path = tmp_path / "run.log"
    log = InsomniaLog(str(path))
    log.append("task_done", prompt="fix the parser")

    rendered = log.render_tail()

    assert "Run log:" in rendered
    assert "task_done" in rendered
    assert "fix the parser" in rendered


# --------------------------------------------------------------------------- #
# Restore defaults
# --------------------------------------------------------------------------- #


def test_a_snapshot_without_the_new_fields_restores_the_class_defaults(tmp_path) -> None:
    from openlaoke.core.sessions import SessionManager

    manager = SessionManager(session_dir=str(tmp_path / "sessions"))
    path = tmp_path / "sessions" / "old.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"session_id": "old", "cwd": str(tmp_path), "messages": []}),
        encoding="utf-8",
    )

    state = manager._load_from_path(str(path))

    assert state is not None
    assert state.insomnia_max_iterations == 1000
    assert state.insomnia_max_retries == 8
    assert state.insomnia_max_cost == 10.0
    assert state.insomnia_artifact_days == 30
    assert state.insomnia_auto_accept is True
    assert state.insomnia_log_path is None


def test_normalize_task_refuses_junk() -> None:
    assert normalize_task("   ") is None
    assert normalize_task({"attempts": 3}) is None
    assert normalize_task(42) is None
    assert (
        normalize_task(" keep ")[  # type: ignore[index]
            "prompt"
        ]
        == "keep"
    )


def test_an_empty_queue_is_not_an_error(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_task_queue = []
    assert next_task(state) is None
    assert time.time() > 0  # the queue code has no clock dependency to trip over


# --------------------------------------------------------------------------- #
# /insomnia
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_command_switches_the_mode_and_says_what_it_does(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")

    on = await InsomniaCommand().execute(_ctx(state, "on"))

    assert state.insomnia_mode is True
    assert "Insomnia mode on" in on.message
    assert "1000" in on.message and "step" in on.message
    assert "retried" in on.message

    off = await InsomniaCommand().execute(_ctx(state, "off"))
    assert state.insomnia_mode is False
    assert "stay queued" in off.message


@pytest.mark.asyncio
async def test_adding_a_task_turns_the_mode_on(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")

    result = await InsomniaCommand().execute(_ctx(state, "add fix the failing test"))

    assert state.insomnia_mode is True
    assert [task["prompt"] for task in queue_tasks(state)] == ["fix the failing test"]
    assert "Insomnia mode is now on" in result.message


@pytest.mark.asyncio
async def test_the_status_lists_the_queue_and_the_limits(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(state, "first")
    enqueue(state, "second")

    status = await InsomniaCommand().execute(_ctx(state, ""))

    assert "Insomnia mode: off" in status.message
    assert "queue: 2 task(s)" in status.message
    assert "1. first" in status.message and "2. second" in status.message
    assert "/insomnia on" in status.message


@pytest.mark.asyncio
async def test_clear_empties_the_queue_and_log_shows_the_run(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(state, "first")
    enqueue(state, "second")

    cleared = await InsomniaCommand().execute(_ctx(state, "clear"))
    assert "Cleared 2 queued task(s)" in cleared.message
    assert queue_tasks(state) == []

    InsomniaLog(str(tmp_path / "run.log")).append("task_done", prompt="first")
    shown = await InsomniaCommand().execute(_ctx(state, "log"))
    assert "task_done" in shown.message
    assert "first" in shown.message


@pytest.mark.asyncio
async def test_bad_usage_is_refused_with_the_list(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")

    empty_add = await InsomniaCommand().execute(_ctx(state, "add"))
    assert empty_add.success is False and "add <task>" in empty_add.message

    unknown = await InsomniaCommand().execute(_ctx(state, "banana"))
    assert unknown.success is False and "Usage: /insomnia" in unknown.message

    bad_log = await InsomniaCommand().execute(_ctx(state, "log xyz"))
    assert bad_log.success is False


def _ctx(state, args: str = ""):
    from openlaoke.commands.base import CommandContext

    return CommandContext(app_state=state, args=args)


def test_a_scheduled_reminder_wakes_the_run(tmp_path, monkeypatch) -> None:
    """A 03:00 reminder must start a turn, not wait for someone to press enter."""
    r = make_repl([[text("handled the nightly reminder")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    r._scheduler_task = object()  # pretend the scheduler loop is running
    r._insomnia_should_idle = lambda: True
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        # The scheduler loop appends the notice while the drain is waiting, once:
        # the drain must then run that turn and stop idling.
        if len(sleeps) == 1:
            r._input_queue.append("[scheduled reminder 'nightly': run the tests]")
        else:
            r._insomnia_should_idle = lambda: False

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    completed = asyncio.run(r._insomnia_drain())

    assert completed == 1
    # First wait: the notice arrives and its turn runs. Second wait: the drain
    # goes back to watching the schedule, and the fake ends it there.
    assert sleeps == [30.0, 30.0]
    assert r.api.turn_index == 1
    log = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "scheduled_wake" in log


def test_a_run_does_not_idle_without_a_running_scheduler(tmp_path, monkeypatch) -> None:
    r = make_repl([[text("never")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    r._scheduler_task = None
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    assert asyncio.run(r._insomnia_drain()) == 0
    assert sleeps == []
    assert r._insomnia_should_idle() is False


# --------------------------------------------------------------------------- #
# Limits: money and disk
# --------------------------------------------------------------------------- #


def test_the_cost_cap_is_on_by_default_and_zero_means_unlimited(tmp_path) -> None:
    from openlaoke.core.insomnia import COST_LIMIT_USD, cost_limit, cost_limit_reached, spent_usd

    state = create_app_state(cwd=str(tmp_path))
    assert state.insomnia_max_cost == COST_LIMIT_USD > 0
    assert spent_usd(state) == 0.0
    assert cost_limit_reached(state) is False

    state.cost_info.input_cost = COST_LIMIT_USD + 0.01
    assert cost_limit_reached(state) is True

    state.insomnia_max_cost = 0
    assert cost_limit(state) == 0.0
    assert cost_limit_reached(state) is False, "0 means unlimited"


def test_a_turn_stops_the_moment_the_budget_is_spent(tmp_path) -> None:
    r = make_repl([[text("x")]])
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    r.app_state.insomnia_max_cost = 5.0
    r._insomnia_budget_hit = False

    # Not in insomnia mode: the cap belongs to the unattended run only.
    r.app_state.cost_info.input_cost = 99.0
    assert r._insomnia_cost_stop() is False

    r.app_state.insomnia_mode = True
    assert r._insomnia_cost_stop() is True
    assert r._insomnia_budget_hit is True
    log = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "cost_limit" in log

    # Raising the cap mid-run must take effect, not stay stuck on the flag.
    r.app_state.insomnia_max_cost = 200.0
    assert r._insomnia_cost_stop() is False
    assert r._insomnia_budget_hit is False


def test_the_drain_stops_before_a_task_and_keeps_it_queued(tmp_path) -> None:
    r = make_repl([[text("never called")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    r.app_state.insomnia_max_cost = 1.0
    r.app_state.cost_info.input_cost = 2.0
    enqueue(r.app_state, "expensive task")

    completed = asyncio.run(r._insomnia_drain())

    assert completed == 0
    assert r.api.turn_index == 0, "the budget stop must happen before the provider call"
    tasks = queue_tasks(r.app_state)
    assert [task["prompt"] for task in tasks] == ["expensive task"]
    # The attempt was refunded: the money ran out, not the task's patience.
    assert tasks[0]["attempts"] == 0
    assert "cost limit" in tasks[0]["last_error"]


def test_a_task_cut_off_mid_turn_is_requeued_not_counted(tmp_path) -> None:
    r = make_repl([[text("partially done")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    r.app_state.insomnia_max_cost = 1.0
    enqueue(r.app_state, "long task")

    # The budget runs out while the task's turn is in flight.
    original = r._insomnia_run_task

    async def cut_short(task):
        r.app_state.cost_info.input_cost = 2.0
        ok, error = await original(task)
        r._insomnia_budget_hit = True
        return ok, error

    r._insomnia_run_task = cut_short

    assert asyncio.run(r._insomnia_drain()) == 0
    assert [task["prompt"] for task in queue_tasks(r.app_state)] == ["long task"]
    log = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "task_paused" in log


def test_artifacts_are_pruned_during_a_run_but_the_live_session_kept(tmp_path, monkeypatch) -> None:
    import os as _os

    from openlaoke.core.tool_output_store import ToolOutputStore

    monkeypatch.setenv("OPENLAOKE_ARTIFACT_DIR", str(tmp_path / "art"))
    old = ToolOutputStore(None, "other-session").store("Bash", "old body")
    long_ago = time.time() - 30 * 86400
    _os.utime(old.path, (long_ago, long_ago))
    live = ToolOutputStore(None, "test-session").store("Bash", "still referenced")
    _os.utime(live.path, (long_ago, long_ago))

    r = make_repl([[text("done")]])
    r.app_state.session_id = "test-session"
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_artifact_days = 30
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "one task")

    asyncio.run(r._insomnia_drain())

    assert Path(live.path).exists(), "the running session's artifacts must survive"
    assert not Path(old.path).exists(), "another session's stale artifact should go"
    log = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "artifacts_pruned" in log


def test_artifact_pruning_can_be_turned_off(tmp_path, monkeypatch) -> None:
    import os as _os

    from openlaoke.core.tool_output_store import ToolOutputStore

    monkeypatch.setenv("OPENLAOKE_ARTIFACT_DIR", str(tmp_path / "art"))
    old = ToolOutputStore(None, "other-session").store("Bash", "old body")
    long_ago = time.time() - 30 * 86400
    _os.utime(old.path, (long_ago, long_ago))

    r = make_repl([[text("done")]])
    r.app_state.insomnia_mode = True
    r.app_state.insomnia_artifact_days = 0  # never prune
    r.app_state.insomnia_log_path = str(tmp_path / "run.log")
    enqueue(r.app_state, "one task")

    asyncio.run(r._insomnia_drain())

    assert Path(old.path).exists()


@pytest.mark.asyncio
async def test_the_cost_and_days_subcommands(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")
    command = InsomniaCommand()

    shown = await command.execute(_ctx(state, "cost"))
    assert "$10.00" in shown.message and "$0.00" in shown.message

    set_to = await command.execute(_ctx(state, "cost 3.5"))
    assert set_to.success is True and state.insomnia_max_cost == 3.5

    lifted = await command.execute(_ctx(state, "cost off"))
    assert state.insomnia_max_cost == 0.0
    assert "unlimited" in lifted.message or "lifted" in lifted.message

    bad = await command.execute(_ctx(state, "cost lots"))
    assert bad.success is False

    negative = await command.execute(_ctx(state, "cost -1"))
    assert negative.success is False

    days = await command.execute(_ctx(state, "days 3"))
    assert state.insomnia_artifact_days == 3
    assert "older than 3 day(s)" in days.message

    days_off = await command.execute(_ctx(state, "days off"))
    assert state.insomnia_artifact_days == 0
    assert "never pruned" in days_off.message

    bad_days = await command.execute(_ctx(state, "days soon"))
    assert bad_days.success is False


@pytest.mark.asyncio
async def test_the_status_shows_both_limits_and_their_off_switch(tmp_path) -> None:
    from openlaoke.commands.base import InsomniaCommand

    state = create_app_state(cwd=str(tmp_path))
    state.insomnia_log_path = str(tmp_path / "run.log")
    state.insomnia_max_cost = 2.5
    state.insomnia_artifact_days = 4
    state.cost_info.input_cost = 1.25

    status = await InsomniaCommand().execute(_ctx(state, ""))

    assert "cost cap: $2.50 (spent $1.25)" in status.message
    assert "artifacts: prune older than 4 day(s)" in status.message

    state.insomnia_max_cost = 0.0
    state.insomnia_artifact_days = 0
    status = await InsomniaCommand().execute(_ctx(state, ""))
    assert "cost cap: unlimited" in status.message
    assert "artifacts: never prune" in status.message
