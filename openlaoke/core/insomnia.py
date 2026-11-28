"""Unattended, long-running work mode.

The rest of the harness assumes a person at the keyboard: one turn per message,
a step budget of 25-80, and any provider error ending the turn. A run that is
supposed to last for hours or days breaks every one of those assumptions, so
insomnia mode replaces them:

* the queue drains without asking for input (``next_task``), and the step budget
  comes from ``insomnia_max_iterations`` instead of the harness mode;
* a failed turn is retried with exponential backoff rather than ending the run
  (``backoff_seconds``), and the failure is written down;
* the live history is trimmed at turn boundaries once it passes a limit
  (``plan_trim``), because the snapshot is rewritten on every save and a run that
  never trims writes an ever-growing file forever;
* everything that happened is appended to a log beside the session
  (``InsomniaLog``) so the person who wakes up can see what ran.

Nothing here talks to the model; the REPL owns that. This module is the policy.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

# Defaults. Deliberately generous: the point of the mode is that it does not
# stop, so the limits exist to bound damage, not to bound the shift.
MAX_ITERATIONS = 1000
RETRY_LIMIT = 8
BACKOFF_BASE_SECONDS = 15.0
BACKOFF_CAP_SECONDS = 600.0
HISTORY_LIMIT = 400
LOG_MAX_BYTES = 1_000_000

# Two limits matter to a run nobody is watching: money and disk. Both are on by
# default and both can be turned off (0 means unlimited / never prune), because
# "do not stop" is the point of the mode and only the operator knows when the
# wallet is the limit rather than the clock.
COST_LIMIT_USD = 10.0
# Same 30 days as `/artifacts prune`, so an unattended run never deletes
# evidence the manual command would have kept.
ARTIFACT_DAYS = 30
ARTIFACT_PRUNE_INTERVAL = 600.0


def spent_usd(state: Any) -> float:
    """What this session has cost so far, in the provider's currency."""
    cost = getattr(state, "cost_info", None)
    return float(getattr(cost, "total_cost", 0.0) or 0.0)


def cost_limit(state: Any) -> float:
    """The configured cap; ``0`` means unlimited."""
    try:
        return float(getattr(state, "insomnia_max_cost", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def cost_limit_reached(state: Any) -> bool:
    """True when the run has spent its budget and must stop before more work."""
    limit = cost_limit(state)
    return limit > 0 and spent_usd(state) >= limit


def artifact_retention_days(state: Any) -> int:
    """How old an artifact must be before an unattended run deletes it."""
    try:
        return max(0, int(getattr(state, "insomnia_artifact_days", 0) or 0))
    except (TypeError, ValueError):
        return 0


def log_path_for(state: Any, root: str | None = None) -> str:
    """Where this session's run log goes; ``insomnia_log_path`` wins if set."""
    configured = getattr(state, "insomnia_log_path", None)
    if configured:
        return os.path.expanduser(str(configured))
    base = root or os.path.join(os.path.expanduser("~"), ".openlaoke", "insomnia")
    session_id = str(getattr(state, "session_id", "") or "session")
    safe = "".join(
        character for character in session_id if character.isalnum() or character in "-_"
    )
    return os.path.join(base, f"{safe or 'session'}.log")


@dataclass
class InsomniaLog:
    """Append-only record of an unattended run, bounded by rotation."""

    path: str
    max_bytes: int = LOG_MAX_BYTES
    _failures: int = field(default=0, init=False)

    def append(self, event: str, **fields: Any) -> None:
        """Write one line. A log that cannot be written never stops the run."""
        record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()), "event": event}
        record.update(fields)
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._rotate_if_needed()
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError:
            # Losing a log line is bad; losing the run because of it is worse.
            self._failures += 1

    def _rotate_if_needed(self) -> None:
        try:
            if os.path.getsize(self.path) < self.max_bytes:
                return
        except OSError:
            return
        rotated = f"{self.path}.1"
        try:
            os.replace(self.path, rotated)
        except OSError:
            # Rotation is best effort; appending to the current file still works.
            return

    def tail(self, limit: int = 20) -> list[str]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            return []
        return [line.rstrip("\n") for line in lines[-max(1, limit) :]]

    def render_tail(self, limit: int = 12) -> str:
        lines = self.tail(limit)
        if not lines:
            return f"No run log yet ({self.path})."
        rows = [f"Run log: {self.path} (last {len(lines)} event(s))"]
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                rows.append(f"  {line}")
                continue
            detail = " ".join(
                f"{key}={value}" for key, value in record.items() if key not in ("at", "event")
            )
            rows.append(f"  {record.get('at', '?')} {record.get('event', '?')} {detail}".rstrip())
        return "\n".join(rows)


# --------------------------------------------------------------------------- #
# The queue
# --------------------------------------------------------------------------- #


def normalize_task(item: Any) -> dict[str, Any] | None:
    """A queue entry as a dict. Strings are accepted; junk is refused."""
    if isinstance(item, str):
        text = item.strip()
        return {"prompt": text, "attempts": 0, "added_at": time.time()} if text else None
    if isinstance(item, dict):
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            return None
        return {
            "prompt": prompt,
            "attempts": int(item.get("attempts") or 0),
            "added_at": float(item.get("added_at") or time.time()),
            "last_error": str(item.get("last_error") or ""),
        }
    return None


def queue_tasks(state: Any) -> list[dict[str, Any]]:
    """The queue with every entry normalized, junk dropped."""
    raw = getattr(state, "insomnia_task_queue", None) or []
    tasks: list[dict[str, Any]] = []
    for item in raw:
        task = normalize_task(item)
        if task is not None:
            tasks.append(task)
    return tasks


def enqueue(state: Any, prompt: str) -> dict[str, Any] | None:
    """Append one task and persist the queue."""
    task = normalize_task(prompt)
    if task is None:
        return None
    state.insomnia_task_queue = queue_tasks(state) + [task]
    state._persist()
    return task


def next_task(state: Any) -> dict[str, Any] | None:
    """Pop the next task, leaving the queue on disk without it."""
    tasks = queue_tasks(state)
    if not tasks:
        state.insomnia_task_queue = []
        return None
    task = tasks.pop(0)
    task["attempts"] = int(task.get("attempts") or 0) + 1
    state.insomnia_task_queue = tasks
    state._persist()
    return task


def requeue(state: Any, task: dict[str, Any], error: str = "") -> None:
    """Put a failed task back in front of the queue for a later attempt."""
    entry = normalize_task(task) or dict(task)
    entry["attempts"] = int(task.get("attempts") or 0)
    entry["last_error"] = error[:400]
    state.insomnia_task_queue = [entry] + queue_tasks(state)
    state._persist()


def backoff_seconds(
    attempt: int,
    *,
    base: float = BACKOFF_BASE_SECONDS,
    cap: float = BACKOFF_CAP_SECONDS,
) -> float:
    """15s, 30s, 60s, ... capped. Attempt 1 is the first retry."""
    if attempt <= 0:
        return 0.0
    return min(cap, base * (2 ** (attempt - 1)))


# --------------------------------------------------------------------------- #
# Keeping the live history bounded
# --------------------------------------------------------------------------- #


def _role_of(message: Any) -> str:
    role = getattr(message, "role", None)
    if isinstance(message, dict):
        role = message.get("role", role)
    if role is not None and hasattr(role, "value"):
        return str(role.value)
    return str(role or "")


def _is_turn_start(message: Any) -> bool:
    """A real user message, not a tool result and not an injected block."""
    if _role_of(message) != "user":
        return False
    if isinstance(message, dict):
        return not message.get("system_injected")
    return not getattr(message, "tool_use_id", None)


def plan_trim(messages: list[Any], keep: int = HISTORY_LIMIT) -> tuple[list[Any], int]:
    """Drop the oldest turns, keeping the sequence a provider will accept.

    The cut has to land on a user message: an assistant ``tool_calls`` message
    whose results were dropped is a dangling tool_call_id, and every provider
    rejects that. The first message (the original goal) is kept so the model does
    not lose why it is working, and one note says where the rest went.
    """
    from openlaoke.types.core_types import MessageRole, SystemMessage

    if keep < 2 or len(messages) <= keep:
        return list(messages), 0

    start = len(messages) - keep
    while start < len(messages) and not _is_turn_start(messages[start]):
        start += 1
    if start >= len(messages):
        return list(messages), 0

    head: list[Any] = []
    if messages and _is_turn_start(messages[0]):
        head = [messages[0]]

    dropped = start - len(head)
    if dropped <= 0:
        return list(messages), 0

    note = SystemMessage(
        role=MessageRole.SYSTEM,
        content=(
            f"[{dropped} earlier message(s) are no longer in the live context. "
            "They are still in the journal: /transcript shows them, /search finds them.]"
        ),
        subtype="compact",
    )
    return head + [note] + list(messages[start:]), dropped


def trim_history(state: Any, keep: int = HISTORY_LIMIT) -> int:
    """Trim ``state.messages`` in place when it is too long; returns how many went."""
    messages = getattr(state, "messages", None)
    if not messages:
        return 0
    kept, dropped = plan_trim(list(messages), keep)
    if dropped <= 0:
        return 0
    state.messages = kept
    state._persist()
    return dropped
