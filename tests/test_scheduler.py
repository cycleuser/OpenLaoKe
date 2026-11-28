"""Tests for the local scheduler and the Schedule tool (P18)."""

from __future__ import annotations

import asyncio
import time

import pytest

from openlaoke.core.scheduler import ScheduleError, Scheduler, parse_when
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.schedule_tool import ScheduleTool


def _scheduler(tmp_path) -> Scheduler:
    return Scheduler(path=str(tmp_path / "schedule.json"))


def _ctx(tmp_path, scheduler: Scheduler) -> ToolContext:
    state = create_app_state(cwd=str(tmp_path))
    state._scheduler = scheduler
    return ToolContext(app_state=state, tool_use_id="s1")


def test_every_parses_units(tmp_path) -> None:
    now = 1_800_000_000.0
    assert parse_when("every 30m", now) == now + 1800
    assert parse_when("every 2 hours", now) == now + 7200
    assert parse_when("every 90s", now) == now + 90


def test_daily_is_the_next_occurrence(tmp_path) -> None:
    # 2026-11-08 14:00 local
    now = time.mktime((2026, 11, 8, 14, 0, 0, 0, 0, -1))
    later_today = parse_when("daily 18:30", now)
    assert time.localtime(later_today).tm_yday == time.localtime(now).tm_yday
    tomorrow = parse_when("daily 09:00", now)
    assert tomorrow > now
    assert time.localtime(tomorrow).tm_hour == 9


def test_once_must_be_in_the_future(tmp_path) -> None:
    now = time.mktime((2026, 11, 8, 14, 0, 0, 0, 0, -1))
    future = parse_when("2026-11-09T08:30", now)
    assert future > now
    with pytest.raises(ScheduleError):
        parse_when("2026-11-01T08:30", now)


def test_unknown_form_is_rejected_with_a_hint() -> None:
    with pytest.raises(ScheduleError) as excinfo:
        parse_when("weekly monday")
    assert "every 30m" in str(excinfo.value)


def test_add_list_cancel_and_due(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    now = time.time()
    entry = scheduler.add("check builds", "every 1h", prompt="look at CI", now=now)
    assert scheduler.due(now + 1) == []
    assert scheduler.due(now + 3601) == [entry]

    assert "check builds" in scheduler.render()
    assert scheduler.cancel("check builds")
    assert scheduler.entries == []
    assert not scheduler.cancel("check builds")


def test_mark_run_reschedules_and_disables_one_shots(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    now = time.time()
    recurring = scheduler.add("hourly", "every 1h", command="echo hi", now=now)
    scheduler.mark_run(recurring, now + 3600)
    assert recurring.runs == 1
    assert recurring.enabled
    assert recurring.next_run > now + 3600

    once = scheduler.add(
        "later", time.strftime("%Y-%m-%dT%H:%M", time.localtime(now + 7200)), prompt="x", now=now
    )
    scheduler.mark_run(once, now + 7201)
    assert not once.enabled
    assert once.next_run == 0


def test_an_entry_needs_exactly_one_action(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    with pytest.raises(ScheduleError):
        scheduler.add("empty", "every 1h")
    with pytest.raises(ScheduleError):
        scheduler.add("both", "every 1h", prompt="a", command="b")


def test_schedule_survives_a_restart(tmp_path) -> None:
    path = str(tmp_path / "schedule.json")
    first = Scheduler(path=path)
    first.add("keep me", "every 2h", prompt="remember", now=time.time())
    second = Scheduler(path=path)
    assert [entry.name for entry in second.entries] == ["keep me"]


def test_tool_round_trip(tmp_path) -> None:
    scheduler = _scheduler(tmp_path)
    ctx = _ctx(tmp_path, scheduler)

    added = asyncio.run(
        ScheduleTool().call(
            ctx, action="add", name="standup", when="daily 09:00", prompt="summarise"
        )
    )
    assert not added.is_error
    assert "standup" in added.content

    listing = asyncio.run(ScheduleTool().call(ctx, action="list"))
    assert "standup" in listing.content

    paused = asyncio.run(ScheduleTool().call(ctx, action="pause", id="standup"))
    assert "off" in paused.content
    assert scheduler.get("standup").enabled is False

    resumed = asyncio.run(ScheduleTool().call(ctx, action="resume", id="standup"))
    assert "on" in resumed.content

    cancelled = asyncio.run(ScheduleTool().call(ctx, action="cancel", id="standup"))
    assert "Cancelled" in cancelled.content
    assert scheduler.entries == []


def test_tool_rejects_bad_input(tmp_path) -> None:
    ctx = _ctx(tmp_path, _scheduler(tmp_path))
    assert asyncio.run(
        ScheduleTool().call(ctx, action="add", when="sometimes", prompt="x")
    ).is_error
    assert asyncio.run(ScheduleTool().call(ctx, action="cancel", id="nope")).is_error
    assert asyncio.run(ScheduleTool().call(ctx, action="explode")).is_error


def test_schedule_command_mentions_the_disabled_loop(tmp_path) -> None:
    from openlaoke.commands.base import ScheduleCommand

    class Ctx:
        def __init__(self, state):
            self.app_state = state
            self.args = ""
            self.app_config = None

    state = create_app_state(cwd=str(tmp_path))
    state._scheduler = _scheduler(tmp_path)
    message = asyncio.run(ScheduleCommand().execute(Ctx(state))).message
    assert "No scheduled entries" in message
    assert "enable_scheduler" in message


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset is POSIX only")
def test_a_daily_schedule_keeps_its_wall_clock_time_across_a_dst_change(monkeypatch) -> None:
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    try:
        # 2026-03-29 02:00 CET becomes 03:00 CEST: that day is 23 hours long.
        moment = time.mktime(time.strptime("2026-03-28 10:00", "%Y-%m-%d %H:%M"))
        next_run = parse_when("daily 09:00", moment)
        local = time.localtime(next_run)
        assert time.strftime("%Y-%m-%d", local) == "2026-03-29"
        assert (local.tm_hour, local.tm_min) == (9, 0), time.strftime("%Y-%m-%d %H:%M %Z", local)
    finally:
        monkeypatch.undo()
        time.tzset()


def test_one_malformed_entry_does_not_discard_the_others(tmp_path) -> None:
    import json

    path = tmp_path / "schedule.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"id": "a1", "name": "good", "when": "every 30m", "next_run": 1_900_000_000},
                    {"name": "no id and no when"},
                    {"id": "a3", "name": "stringy", "when": "daily 09:00", "next_run": "soon"},
                    "not an object",
                ]
            }
        ),
        encoding="utf-8",
    )

    scheduler = Scheduler(path=str(path))

    assert [entry.id for entry in scheduler.entries] == ["a1", "a3"]
    # A string timestamp is coerced instead of raising inside due().
    assert scheduler.entries[1].next_run == 0.0
    assert scheduler.due(now=1_950_000_000) == [scheduler.entries[0]]
