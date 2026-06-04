"""Cron scheduler engine.

Runs scheduled jobs in the background, dispatching events through the
message bus. Supports one-shot (``at``), recurring (``every``), and
cron-expression (``cron``) schedules.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path

from openlaoke.bus.events import InboundMessage
from openlaoke.bus.queue import MessageBus
from openlaoke.cron.model import CronJob, CronRun, JobKind, ScheduleKind

logger = logging.getLogger(__name__)


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        if part == "*":
            values.update(range(min_val, max_val + 1))
        elif "/" in part:
            base, _, step = part.partition("/")
            start = min_val if base == "*" else int(base)
            step = int(step)
            for v in range(start, max_val + 1, step):
                values.add(v)
        elif "-" in part:
            lo, _, hi = part.partition("-")
            values.update(range(int(lo), int(hi) + 1))
        else:
            values.add(int(part))
    return values


def next_cron_time(expression: str, timezone: str, after: float) -> float:
    import datetime as _dt

    try:
        try:
            import zoneinfo

            tz = zoneinfo.ZoneInfo(timezone)
        except ImportError:
            import pytz

            tz = pytz.timezone(timezone)
    except Exception:
        tz = _dt.UTC

    parts = expression.split()
    if len(parts) != 5:
        return after + 86400.0

    minute_set = _parse_cron_field(parts[0], 0, 59)
    hour_set = _parse_cron_field(parts[1], 0, 23)
    dom_set = _parse_cron_field(parts[2], 1, 31)
    month_set = _parse_cron_field(parts[3], 1, 12)
    dow_set = _parse_cron_field(parts[4], 0, 6)

    dt = _dt.datetime.fromtimestamp(after + 60, tz=tz).replace(second=0, microsecond=0)
    for _ in range(525960):
        if (
            dt.minute in minute_set
            and dt.hour in hour_set
            and dt.day in dom_set
            and dt.month in month_set
            and dt.weekday() in dow_set
        ):
            return dt.timestamp()
        dt += _dt.timedelta(minutes=1)
    return after + 86400.0


class CronScheduler:
    """Background scheduler that fires :class:`CronJob` entries.

    Uses a single :class:`asyncio.Task` that sleeps in small chunks so
    it can be cancelled cleanly.
    """

    def __init__(
        self,
        bus: MessageBus,
        store_path: str | None = None,
        max_sleep_ms: int = 5000,
    ) -> None:
        self.bus = bus
        self.store_path = store_path or os.path.expanduser("~/.openlaoke/cron_jobs.jsonl")
        self.max_sleep_ms = max_sleep_ms
        self._jobs: dict[str, CronJob] = {}
        self._run_history: list[CronRun] = []
        self._task: asyncio.Task | None = None
        self._running = False
        self._load_jobs()

    def _load_jobs(self) -> None:
        path = Path(self.store_path)
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    job = CronJob.from_dict(data)
                    self._jobs[job.job_id] = job
                except Exception:
                    logger.warning("Skipping malformed cron job entry")

    def _save_job(self, job: CronJob) -> None:
        path = Path(self.store_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict] = []
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line.strip())
                        if d.get("job_id") != job.job_id:
                            existing.append(d)
                    except Exception:
                        continue
        with open(path, "w", encoding="utf-8") as f:
            for d in existing:
                f.write(json.dumps(d) + "\n")
            f.write(json.dumps(job.to_dict()) + "\n")

    def _remove_job_file(self, job_id: str) -> None:
        path = Path(self.store_path)
        if not path.exists():
            return
        remaining: list[dict] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    if d.get("job_id") != job_id:
                        remaining.append(d)
                except Exception:
                    continue
        with open(path, "w", encoding="utf-8") as f:
            for d in remaining:
                f.write(json.dumps(d) + "\n")

    def compute_next_run(self, job: CronJob) -> float:
        now = time.time()
        if job.schedule_kind == ScheduleKind.AT:
            return float(job.schedule_value)
        if job.schedule_kind == ScheduleKind.EVERY:
            interval = float(job.schedule_value)
            return now + interval
        if job.schedule_kind == ScheduleKind.CRON:
            return next_cron_time(job.schedule_value, job.timezone, now)
        return now + 3600.0

    async def add_job(self, job: CronJob) -> CronJob:
        job.next_run_at = self.compute_next_run(job)
        self._jobs[job.job_id] = job
        self._save_job(job)
        logger.info("Cron job added: %s (%s)", job.name, job.job_id)
        return job

    async def remove_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._remove_job_file(job_id)
        logger.info("Cron job removed: %s", job_id)
        return True

    async def list_jobs(self) -> list[CronJob]:
        return list(self._jobs.values())

    async def get_job(self, job_id: str) -> CronJob | None:
        return self._jobs.get(job_id)

    async def _dispatch(self, job: CronJob) -> None:
        job.last_run_at = time.time()
        job.run_count += 1
        job.next_run_at = self.compute_next_run(job)
        self._save_job(job)

        run = CronRun(
            job_id=job.job_id,
            started_at=job.last_run_at,
            finished_at=time.time(),
            success=True,
        )
        self._run_history.append(run)

        if job.job_kind == JobKind.REMINDER:
            msg = InboundMessage(
                text=job.payload.get("message", job.name),
                session_key="cron",
                sender_id="cron",
                channel="cron",
                metadata={
                    "job_id": job.job_id,
                    "job_name": job.name,
                    **job.payload,
                },
            )
            await self.bus.publish_inbound(msg)

        if 0 < job.max_runs <= job.run_count:
            await self.remove_job(job.job_id)

    async def _tick(self) -> None:
        now = time.time()
        for job in list(self._jobs.values()):
            if not job.enabled:
                continue
            if job.next_run_at <= now:
                try:
                    await self._dispatch(job)
                except Exception:
                    logger.exception("Error dispatching cron job %s", job.job_id)

    async def _run_loop(self) -> None:
        logger.info("Cron scheduler started")
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("Cron tick error")
            sleep_seconds = min(self.max_sleep_ms / 1000.0, 5.0)
            await asyncio.sleep(sleep_seconds)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        logger.info("Cron scheduler stopped")

    def get_run_history(self, job_id: str | None = None) -> list[CronRun]:
        if job_id is None:
            return list(self._run_history)
        return [r for r in self._run_history if r.job_id == job_id]
