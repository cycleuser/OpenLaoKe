"""Tests for the cron scheduler engine."""

from __future__ import annotations

import asyncio
import time

import pytest

from openlaoke.bus.queue import MessageBus
from openlaoke.cron.model import CronJob, JobKind, ScheduleKind
from openlaoke.cron.scheduler import CronScheduler, next_cron_time


@pytest.fixture
def scheduler(tmp_path):
    bus = MessageBus()
    store = str(tmp_path / "cron.jsonl")
    return CronScheduler(bus=bus, store_path=store, max_sleep_ms=100)


class TestCronScheduler:
    def test_add_job(self, scheduler) -> None:
        job = CronJob(
            job_id="j1",
            name="test",
            schedule_kind=ScheduleKind.EVERY,
            schedule_value="60",
            job_kind=JobKind.REMINDER,
            payload={"message": "hello"},
        )

        async def scenario():
            result = await scheduler.add_job(job)
            assert result.next_run_at > 0
            jobs = await scheduler.list_jobs()
            assert len(jobs) == 1
            assert jobs[0].job_id == "j1"

        asyncio.run(scenario())

    def test_remove_job(self, scheduler) -> None:
        job = CronJob(
            job_id="j2",
            name="removable",
            schedule_kind=ScheduleKind.EVERY,
            schedule_value="120",
            job_kind=JobKind.REMINDER,
            payload={},
        )

        async def scenario():
            await scheduler.add_job(job)
            ok = await scheduler.remove_job("j2")
            assert ok
            assert await scheduler.get_job("j2") is None

        asyncio.run(scenario())

    def test_remove_nonexistent(self, scheduler) -> None:
        async def scenario():
            ok = await scheduler.remove_job("nope")
            assert not ok

        asyncio.run(scenario())

    def test_dispatch_increments_run_count(self, scheduler) -> None:
        job = CronJob(
            job_id="j3",
            name="counter",
            schedule_kind=ScheduleKind.EVERY,
            schedule_value="1",
            job_kind=JobKind.REMINDER,
            payload={"message": "tick"},
        )

        async def scenario():
            await scheduler.add_job(job)
            await scheduler._dispatch(job)
            assert job.run_count == 1
            assert job.last_run_at > 0
            history = scheduler.get_run_history("j3")
            assert len(history) == 1

        asyncio.run(scenario())

    def test_max_runs_removes_job(self, scheduler) -> None:
        job = CronJob(
            job_id="j4",
            name="limited",
            schedule_kind=ScheduleKind.EVERY,
            schedule_value="1",
            job_kind=JobKind.REMINDER,
            payload={},
            max_runs=1,
        )

        async def scenario():
            await scheduler.add_job(job)
            await scheduler._dispatch(job)
            assert await scheduler.get_job("j4") is None

        asyncio.run(scenario())

    def test_disabled_job_skipped(self, scheduler) -> None:
        job = CronJob(
            job_id="j5",
            name="disabled",
            schedule_kind=ScheduleKind.EVERY,
            schedule_value="1",
            job_kind=JobKind.REMINDER,
            payload={},
            enabled=False,
            next_run_at=0,
        )

        async def scenario():
            await scheduler.add_job(job)
            await scheduler._tick()
            assert job.run_count == 0

        asyncio.run(scenario())

    def test_start_stop(self, scheduler) -> None:
        async def scenario():
            await scheduler.start()
            assert scheduler._running
            await asyncio.sleep(0.15)
            await scheduler.stop()
            assert not scheduler._running

        asyncio.run(scenario())

    def test_persistence(self, tmp_path) -> None:
        store = str(tmp_path / "persist.jsonl")
        bus = MessageBus()
        job = CronJob(
            job_id="j6",
            name="persist_test",
            schedule_kind=ScheduleKind.AT,
            schedule_value=str(time.time() + 9999),
            job_kind=JobKind.REMINDER,
            payload={},
        )

        async def add():
            s = CronScheduler(bus=bus, store_path=store)
            await s.add_job(job)

        asyncio.run(add())

        s2 = CronScheduler(bus=bus, store_path=store)

        async def check():
            found = await s2.get_job("j6")
            assert found is not None
            assert found.name == "persist_test"

        asyncio.run(check())

    def test_at_schedule(self, scheduler) -> None:
        future = str(time.time() + 3600)
        job = CronJob(
            job_id="j7",
            name="one_shot",
            schedule_kind=ScheduleKind.AT,
            schedule_value=future,
            job_kind=JobKind.REMINDER,
            payload={},
        )

        async def scenario():
            result = await scheduler.add_job(job)
            assert result.next_run_at == float(future)

        asyncio.run(scenario())


class TestCronExpression:
    def test_every_minute(self) -> None:
        nt = next_cron_time("* * * * *", "UTC", time.time())
        assert nt > time.time() - 1

    def test_specific_hour(self) -> None:
        nt = next_cron_time("0 3 * * *", "UTC", time.time())
        assert nt > time.time()

    def test_cron_field_parser(self) -> None:
        from openlaoke.cron.scheduler import _parse_cron_field

        assert _parse_cron_field("*", 0, 59) == set(range(60))
        assert _parse_cron_field("5", 0, 59) == {5}
        assert _parse_cron_field("1-5", 0, 59) == {1, 2, 3, 4, 5}
        assert _parse_cron_field("*/15", 0, 59) == {0, 15, 30, 45}
