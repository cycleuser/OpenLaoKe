"""Tests for the scheduler's run history (and for one job not stopping the rest)."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import time
from pathlib import Path

import pytest

from openlaoke.core.scheduler import Scheduler
from openlaoke.core.state import AppState


def _scheduler(tmp_path) -> Scheduler:
    return Scheduler(path=str(tmp_path / "schedule.json"))


def test_mark_run_writes_one_history_record(tmp_path):
    scheduler = _scheduler(tmp_path)
    entry = scheduler.add("build", "every 1h", command="make")
    started = time.time() - 2

    scheduler.mark_run(entry, status="ok", detail="exit 0", started_at=started, duration_ms=2000)

    records = scheduler.history()
    assert len(records) == 1
    assert records[0].id == entry.id
    assert records[0].name == "build"
    assert records[0].status == "ok"
    assert records[0].detail == "exit 0"
    assert records[0].duration_ms == 2000
    assert records[0].at == pytest.approx(started, abs=1)
    assert entry.runs == 1


def test_a_failure_is_recorded_and_readable(tmp_path):
    scheduler = _scheduler(tmp_path)
    ok = scheduler.add("nightly", "daily 03:00", command="make nightly")
    broken = scheduler.add("broken", "daily 04:00", command="false")

    scheduler.mark_run(ok)
    scheduler.mark_run(broken, status="error", detail="CalledProcessError: exit 1")

    assert [record.status for record in scheduler.history()] == ["ok", "error"]
    text = scheduler.render_history()
    assert "error" in text
    assert "1 not ok" in text
    assert "CalledProcessError" in text


def test_history_can_be_filtered_by_entry(tmp_path):
    scheduler = _scheduler(tmp_path)
    first = scheduler.add("first", "every 1h", command="a")
    second = scheduler.add("second", "every 1h", command="b")
    scheduler.mark_run(first)
    scheduler.mark_run(second)
    scheduler.mark_run(first)

    assert len(scheduler.history(first.id)) == 2
    assert len(scheduler.history("second")) == 1
    assert len(scheduler.history(limit=2)) == 2


def test_the_history_file_is_private_and_json_lines(tmp_path):
    scheduler = _scheduler(tmp_path)
    entry = scheduler.add("job", "every 1h", command="true")

    scheduler.mark_run(entry)

    path = scheduler.history_path
    assert path.endswith("-runs.json")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    line = Path(path).read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(line)["id"] == entry.id


def test_a_torn_final_line_is_skipped_rather_than_failing(tmp_path):
    scheduler = _scheduler(tmp_path)
    entry = scheduler.add("job", "every 1h", command="true")
    scheduler.mark_run(entry)
    with open(scheduler.history_path, "a", encoding="utf-8") as handle:
        handle.write('{"id": "trunc')

    records = scheduler.history()

    assert [record.id for record in records] == [entry.id]


def test_an_unwritable_history_does_not_stop_the_schedule(tmp_path, monkeypatch, caplog):
    scheduler = _scheduler(tmp_path)
    entry = scheduler.add("job", "every 1h", command="true")

    def refuse(*_args, **_kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(scheduler, "_append_history", refuse)

    scheduler.mark_run(entry)

    assert entry.runs == 1
    assert entry.next_run > time.time()
    assert "Could not append scheduler run history" in caplog.text


def test_history_rotates_instead_of_growing_forever(tmp_path, monkeypatch):
    import openlaoke.core.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "MAX_HISTORY_BYTES", 400)
    monkeypatch.setattr(scheduler_module, "MAX_HISTORY_RECORDS", 3)
    scheduler = _scheduler(tmp_path)
    entry = scheduler.add("noisy", "every 1h", command="true")

    for index in range(8):
        scheduler.mark_run(entry, detail=f"run {index}")

    records = scheduler.history(limit=50)
    assert len(records) == 3
    assert records[-1].detail == "run 7"


def test_render_history_says_so_when_nothing_has_run(tmp_path):
    assert "No scheduled runs" in _scheduler(tmp_path).render_history()


def test_the_schedule_command_shows_the_log(tmp_path, monkeypatch):
    from openlaoke.commands.base import ScheduleCommand
    from openlaoke.core import scheduler as scheduler_module

    scheduler = _scheduler(tmp_path)
    entry = scheduler.add("build", "every 1h", command="make")
    scheduler.mark_run(entry, status="error", detail="exit 1")
    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda _state=None, path=None: scheduler)

    class Ctx:
        app_state = AppState(session_id="s", cwd=str(tmp_path))
        args = "log"
        app_config = None

    result = asyncio.run(ScheduleCommand().execute(Ctx()))

    assert result.success is True
    assert "error" in result.message
    assert scheduler.history_path in result.message


def test_the_schedule_command_rejects_an_unknown_argument(tmp_path):
    from openlaoke.commands.base import ScheduleCommand

    class Ctx:
        app_state = AppState(session_id="s", cwd=str(tmp_path))
        args = "wibble"
        app_config = None

    result = asyncio.run(ScheduleCommand().execute(Ctx()))

    assert result.success is False
    assert "Usage" in result.message


class _FakeConsole:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *args, **kwargs) -> None:
        self.lines.append(str(args[0]) if args else "")


class _FakeRepl:
    """Only the attributes ``_scheduler_loop`` touches."""

    def __init__(self, state: AppState) -> None:
        self.app_state = state
        self._running = True
        self._input_queue: list[str] = []
        self.console = _FakeConsole()

    def _c(self, _name):
        return "white"

    async def _run_bot_routine(self, _entry):
        return None


def test_a_failing_scheduled_command_is_recorded_and_the_loop_survives(tmp_path, monkeypatch):
    from openlaoke.core import repl as repl_module
    from openlaoke.core import scheduler as scheduler_module
    from openlaoke.core import task as task_module

    scheduler = _scheduler(tmp_path)
    # Added two hours ago, so both are due on the first pass of the loop.
    due_at = time.time() - 7200
    bad = scheduler.add("bad", "every 1h", command="exit 1", now=due_at)
    good = scheduler.add("good", "every 1h", command="true", now=due_at)
    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda _state=None, path=None: scheduler)

    class Manager:
        async def run_bash(self, command, **_kwargs):
            if command == "exit 1":
                raise RuntimeError("boom")
            return None

    monkeypatch.setattr(task_module, "get_task_manager", lambda _state: Manager())
    fake = _FakeRepl(AppState(session_id="s", cwd=str(tmp_path)))

    async def run_once():
        task = asyncio.create_task(repl_module.REPL._scheduler_loop(fake, 0.0))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_once())

    statuses = {record.id: record.status for record in scheduler.history(limit=10)}
    assert statuses[bad.id] == "error"
    assert statuses[good.id] == "ok"
    assert any("failed" in line for line in fake.console.lines)
