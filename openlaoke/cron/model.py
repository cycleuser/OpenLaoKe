"""Cron data model."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ScheduleKind(StrEnum):
    AT = "at"
    EVERY = "every"
    CRON = "cron"


class JobKind(StrEnum):
    SYSTEM_EVENT = "system_event"
    REMINDER = "reminder"


@dataclass
class CronJob:
    """A scheduled task."""

    job_id: str
    name: str
    schedule_kind: ScheduleKind
    schedule_value: str
    job_kind: JobKind
    payload: dict[str, Any]
    timezone: str = "UTC"
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_run_at: float = 0.0
    next_run_at: float = 0.0
    run_count: int = 0
    max_runs: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "schedule_kind": self.schedule_kind.value,
            "schedule_value": self.schedule_value,
            "job_kind": self.job_kind.value,
            "payload": self.payload,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "max_runs": self.max_runs,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronJob:
        return cls(
            job_id=data.get("job_id", uuid.uuid4().hex[:10]),
            name=data.get("name", "unnamed"),
            schedule_kind=ScheduleKind(data.get("schedule_kind", "every")),
            schedule_value=data.get("schedule_value", "60"),
            job_kind=JobKind(data.get("job_kind", "reminder")),
            payload=data.get("payload", {}),
            timezone=data.get("timezone", "UTC"),
            enabled=bool(data.get("enabled", True)),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            last_run_at=float(data.get("last_run_at", 0.0) or 0.0),
            next_run_at=float(data.get("next_run_at", 0.0) or 0.0),
            run_count=int(data.get("run_count", 0)),
            max_runs=int(data.get("max_runs", 0)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CronRun:
    """A single past execution of a job."""

    job_id: str
    started_at: float
    finished_at: float
    success: bool
    error: str = ""
