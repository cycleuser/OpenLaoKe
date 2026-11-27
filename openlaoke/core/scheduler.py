"""Local scheduler: intervals, daily times, and one-shot reminders.

Scope is deliberately small: three schedule forms and a JSON file. A cron
expression parser would be more powerful and much easier to get subtly wrong.
Entries either queue a prompt for the model or run a shell command in the
background, and both paths are visible in `/schedule`.

Nothing fires unless the session is running: this is a local harness, not a
daemon. The list survives restarts, so a daily entry missed overnight runs on
the next start.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEDULE_PATH = os.path.join(os.path.expanduser("~"), ".openlaoke", "schedule.json")
MAX_ENTRIES = 100
# Every run appends one JSON line next to the schedule file. The point is that
# "did last night's job actually work" is answerable without scrolling the
# transcript: an entry that reports ``runs: 12`` and no history hides twelve
# failures.
MAX_HISTORY_RECORDS = 500
MAX_HISTORY_BYTES = 256 * 1024

_EVERY = re.compile(
    r"^every\s+(\d+(?:\.\d+)?)\s*(s|sec|seconds?|m|min|minutes?|h|hours?|d|days?)$", re.I
)
_DAILY = re.compile(r"^daily\s+(\d{1,2}):(\d{2})$", re.I)
_ONCE = re.compile(r"^(?:once\s+)?(\d{4}-\d{2}-\d{2})[T ](\d{1,2}):(\d{2})$")

_UNIT_SECONDS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


class ScheduleError(ValueError):
    """The schedule string could not be understood."""


@dataclass
class RunRecord:
    """One firing of one entry."""

    id: str
    name: str
    at: float
    status: str = "ok"
    detail: str = ""
    duration_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in known})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def describe(self) -> str:
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.at))
        took = f" {self.duration_ms}ms" if self.duration_ms else ""
        detail = f" {self.detail[:60]}" if self.detail else ""
        return f"{when} {self.id:<10} {self.status:<6}{took} {self.name[:24]}{detail}"


@dataclass
class ScheduleEntry:
    id: str
    name: str
    when: str
    prompt: str = ""
    command: str = ""
    enabled: bool = True
    created_at: float = 0.0
    next_run: float = 0.0
    last_run: float = 0.0
    runs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleEntry:
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in known})

    def describe(self) -> str:
        target = self.prompt or self.command
        kind = "prompt" if self.prompt else "command"
        state = "on " if self.enabled else "off"
        next_at = (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self.next_run)) if self.next_run else "-"
        )
        return (
            f"{state} {self.id:<10} {self.name[:22]:<22} {self.when:<16} "
            f"next {next_at}  [{kind}] {target[:40]}"
        )


def parse_when(when: str, now: float | None = None) -> float:
    """Return the next run timestamp for a schedule string."""
    moment = now if now is not None else time.time()
    text = when.strip()

    match = _EVERY.match(text)
    if match:
        amount, unit = match.group(1), match.group(2).lower()
        return moment + float(amount) * _UNIT_SECONDS[unit]

    match = _DAILY.match(text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ScheduleError(f"time out of range: {text}")
        local = time.localtime(moment)
        today = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, hour, minute, 0, 0, 0, -1))
        return today if today > moment else today + 86400

    match = _ONCE.match(text)
    if match:
        day, hour, minute = match.group(1), int(match.group(2)), int(match.group(3))
        try:
            stamp = time.mktime(time.strptime(f"{day} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M"))
        except ValueError as exc:
            raise ScheduleError(f"bad date: {text}") from exc
        if stamp <= moment:
            raise ScheduleError(f"{text} is in the past")
        return stamp

    raise ScheduleError(
        f"cannot read '{when}'. Use 'every 30m', 'daily 09:00', or '2026-11-09T08:30'."
    )


def _is_once(when: str) -> bool:
    return bool(_ONCE.match(when.strip()))


@dataclass
class Scheduler:
    """A JSON-backed list of schedules plus the arithmetic for when they fire."""

    path: str = SCHEDULE_PATH
    entries: list[ScheduleEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return
        raw = payload.get("entries") if isinstance(payload, dict) else payload
        if isinstance(raw, list):
            self.entries = [ScheduleEntry.from_dict(item) for item in raw if isinstance(item, dict)]

    # ── run history ──────────────────────────────────────────────────────

    @property
    def history_path(self) -> str:
        stem, extension = os.path.splitext(self.path)
        return f"{stem}-runs{extension or '.jsonl'}"

    def record_run(
        self,
        entry: ScheduleEntry,
        *,
        status: str = "ok",
        detail: str = "",
        started_at: float | None = None,
        duration_ms: int = 0,
    ) -> RunRecord:
        """Append one history record; never lets a log failure stop a schedule."""
        record = RunRecord(
            id=entry.id,
            name=entry.name,
            at=started_at if started_at is not None else time.time(),
            status=status,
            detail=detail[:400],
            duration_ms=max(0, int(duration_ms)),
        )
        try:
            self._append_history(record)
        except OSError:
            import logging

            logging.getLogger(__name__).warning(
                "Could not append scheduler run history to %s", self.history_path
            )
        return record

    def _append_history(self, record: RunRecord) -> None:
        path = self.history_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = (json.dumps(record.to_dict(), ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written == 0:
                    raise OSError("short write while appending scheduler history")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        self._rotate_history(path)

    def _rotate_history(self, path: str) -> None:
        try:
            if os.path.getsize(path) <= MAX_HISTORY_BYTES:
                return
            with open(path, encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            return
        keep = lines[-MAX_HISTORY_RECORDS:]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.writelines(keep)
        os.replace(tmp, path)

    def history(self, identifier: str = "", limit: int = 20) -> list[RunRecord]:
        path = self.history_path
        if not os.path.exists(path):
            return []
        records: list[RunRecord] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    # A torn final line is expected after a crash; skip it.
                    continue
                if not isinstance(payload, dict):
                    continue
                record = RunRecord.from_dict(payload)
                if identifier and identifier not in (record.id, record.name):
                    continue
                records.append(record)
        return records[-max(1, limit) :]

    def render_history(self, identifier: str = "", limit: int = 20) -> str:
        records = self.history(identifier, limit)
        if not records:
            return "No scheduled runs recorded yet."
        failures = sum(1 for record in records if record.status != "ok")
        lines = [record.describe() for record in records]
        lines.append(f"({len(records)} run(s), {failures} not ok, log: {self.history_path})")
        return "\n".join(lines)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = {"version": 1, "entries": [entry.to_dict() for entry in self.entries]}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def add(
        self,
        name: str,
        when: str,
        prompt: str = "",
        command: str = "",
        now: float | None = None,
    ) -> ScheduleEntry:
        if not prompt.strip() and not command.strip():
            raise ScheduleError("a schedule needs a prompt or a command")
        if prompt.strip() and command.strip():
            raise ScheduleError("give either a prompt or a command, not both")
        if len(self.entries) >= MAX_ENTRIES:
            raise ScheduleError(f"schedule is full at {MAX_ENTRIES} entries")

        moment = now if now is not None else time.time()
        next_run = parse_when(when, moment)
        entry = ScheduleEntry(
            id=f"s{int(moment) % 1_000_000:06d}{len(self.entries):02d}",
            name=name.strip() or when.strip(),
            when=when.strip(),
            prompt=prompt.strip(),
            command=command.strip(),
            created_at=moment,
            next_run=next_run,
        )
        self.entries.append(entry)
        self.save()
        return entry

    def cancel(self, identifier: str) -> bool:
        for index, entry in enumerate(self.entries):
            if entry.id == identifier or entry.name == identifier:
                self.entries.pop(index)
                self.save()
                return True
        return False

    def set_enabled(self, identifier: str, enabled: bool) -> ScheduleEntry | None:
        entry = self.get(identifier)
        if entry is None:
            return None
        entry.enabled = enabled
        if enabled and entry.next_run <= time.time():
            entry.next_run = parse_when(entry.when)
        self.save()
        return entry

    def get(self, identifier: str) -> ScheduleEntry | None:
        for entry in self.entries:
            if entry.id == identifier or entry.name == identifier:
                return entry
        return None

    def due(self, now: float | None = None) -> list[ScheduleEntry]:
        moment = now if now is not None else time.time()
        return [
            entry
            for entry in self.entries
            if entry.enabled and entry.next_run and entry.next_run <= moment
        ]

    def mark_run(
        self,
        entry: ScheduleEntry,
        now: float | None = None,
        *,
        status: str = "ok",
        detail: str = "",
        started_at: float | None = None,
        duration_ms: int = 0,
    ) -> None:
        moment = now if now is not None else time.time()
        entry.last_run = moment
        entry.runs += 1
        if _is_once(entry.when):
            entry.enabled = False
            entry.next_run = 0.0
        else:
            entry.next_run = parse_when(entry.when, moment)
        self.save()
        self.record_run(
            entry,
            status=status,
            detail=detail,
            started_at=started_at if started_at is not None else moment,
            duration_ms=duration_ms,
        )

    def render(self) -> str:
        if not self.entries:
            return "No scheduled entries."
        lines = [
            entry.describe()
            for entry in sorted(self.entries, key=lambda item: item.next_run or 9e18)
        ]
        lines.append(f"({len(self.entries)} entr(y/ies), {len(self.due())} due now)")
        return "\n".join(lines)


def get_scheduler(app_state: Any = None, path: str | None = None) -> Scheduler:
    """One scheduler per session, cached on the state when one is given."""
    if app_state is not None:
        existing = getattr(app_state, "_scheduler", None)
        if isinstance(existing, Scheduler):
            return existing
        scheduler = Scheduler(path=path or SCHEDULE_PATH)
        app_state._scheduler = scheduler
        return scheduler
    return Scheduler(path=path or SCHEDULE_PATH)
