"""Swarm: several workers on separate lanes, one board they can write to.

The unit of parallelism is a worker with its own conversation and its own task
record, not a thread of shared state. That avoids the failure mode where two
agents edit the same file while both believe they own it: writes are attributed
to a lane, and the board says which lane touched which path.

What is implemented honestly:

* ``start`` spawns workers and returns immediately with their ids,
* ``await`` blocks on them with a timeout,
* ``status`` reports state, results and the paths each lane has touched,
* ``note``/``messages`` are the board: a worker (or the parent) can leave a
  message for the others,
* ``cancel`` stops the remaining ones.

A worker is a sub-agent run in the same process; it is not isolated from the
filesystem. Two lanes editing the same file at once is a coordination mistake,
not something the harness prevents, which is exactly why the board records it.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

CURRENT_MEMBER: ContextVar[str] = ContextVar("openlaoke_swarm_member", default="")
MAX_MEMBERS = 6
MAX_BOARD_MESSAGES = 200


@dataclass
class BoardMessage:
    member: str
    text: str
    at: float = 0.0

    def line(self) -> str:
        stamp = time.strftime("%H:%M:%S", time.localtime(self.at or time.time()))
        return f"[{stamp}] {self.member or 'parent'}: {self.text}"


@dataclass
class SwarmMember:
    id: str
    name: str
    prompt: str
    status: str = "pending"  # pending | running | done | failed | cancelled
    task_id: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    result: str = ""
    error: str = ""
    touched: set[str] = field(default_factory=set)
    task: asyncio.Task | None = field(default=None, repr=False)

    def describe(self) -> str:
        elapsed = (self.finished_at or time.time()) - self.started_at if self.started_at else 0.0
        rows = [f"{self.id} {self.name:<14} {self.status:<9} {elapsed:5.1f}s  {self.prompt[:60]}"]
        if self.touched:
            rows.append("    touched: " + ", ".join(sorted(self.touched)[:8]))
        if self.result:
            first = " ".join(self.result.split())[:160]
            rows.append(f"    result: {first}")
        if self.error:
            rows.append(f"    error: {self.error[:160]}")
        return "\n".join(rows)


class SwarmBoard:
    """Shared state between lanes: messages and the touch ledger."""

    def __init__(self) -> None:
        self.messages: list[BoardMessage] = []
        self.touched: dict[str, str] = {}
        self.members: dict[str, SwarmMember] = {}

    def post(self, text: str, member: str = "") -> BoardMessage:
        message = BoardMessage(member=member, text=" ".join(text.split()), at=time.time())
        self.messages.append(message)
        del self.messages[:-MAX_BOARD_MESSAGES]
        return message

    def touch(self, path: str, member: str = "") -> None:
        if not path:
            return
        self.touched[path] = member or "parent"
        owner = member or "parent"
        record = self.members.get(owner)
        if record is not None:
            record.touched.add(path)

    def render_messages(self, limit: int = 20) -> str:
        if not self.messages:
            return "No board messages."
        return "\n".join(message.line() for message in self.messages[-limit:])

    def render_touched(self) -> str:
        if not self.touched:
            return "No files touched yet."
        rows = [f"{path}  <-  {owner}" for path, owner in sorted(self.touched.items())]
        return "\n".join(rows)


class Swarm:
    """Owns the worker tasks and the board for one session."""

    def __init__(self, app_state: Any) -> None:
        self.app_state = app_state
        self.board = SwarmBoard()
        self._counter = 0

    def start(
        self,
        tasks: list[dict[str, str]],
        max_concurrency: int = MAX_MEMBERS,
    ) -> list[SwarmMember]:
        if not tasks:
            raise ValueError("nothing to start")
        if len(tasks) > MAX_MEMBERS:
            raise ValueError(f"at most {MAX_MEMBERS} workers per swarm, got {len(tasks)}")

        members: list[SwarmMember] = []
        for item in tasks:
            self._counter += 1
            member = SwarmMember(
                id=f"w{self._counter}",
                name=str(item.get("name") or f"worker-{self._counter}"),
                prompt=str(item.get("prompt") or "").strip(),
            )
            if not member.prompt:
                raise ValueError(f"worker '{member.name}' has no prompt")
            self.board.members[member.id] = member
            members.append(member)

        semaphore = asyncio.Semaphore(max(1, max_concurrency))
        for member in members:
            member.status = "running"
            member.started_at = time.time()
            member.task = asyncio.create_task(self._run(member, semaphore))
        return members

    async def _run(self, member: SwarmMember, semaphore: asyncio.Semaphore) -> None:
        async with semaphore:
            token = CURRENT_MEMBER.set(member.id)
            try:
                from openlaoke.core.agent_runner import run_subagent
                from openlaoke.core.task import TaskManager
                from openlaoke.types.core_types import TaskType

                manager = TaskManager(self.app_state)
                task_state = manager.create_task_state(TaskType.LOCAL_AGENT, f"swarm:{member.name}")
                member.task_id = task_state.id
                result = await run_subagent(
                    prompt=member.prompt,
                    description=f"swarm:{member.name}",
                    app_state=self.app_state,
                    task_state=task_state,
                )
                member.result = result
                member.status = "done"
            except asyncio.CancelledError:
                member.status = "cancelled"
                member.finished_at = time.time()
                raise
            except Exception as exc:  # noqa: BLE001 - reported through the member
                member.status = "failed"
                member.error = str(exc)
            finally:
                member.finished_at = time.time()
                CURRENT_MEMBER.reset(token)

    def get(self, identifier: str) -> SwarmMember | None:
        if identifier in self.board.members:
            return self.board.members[identifier]
        for member in self.board.members.values():
            if member.name == identifier:
                return member
        return None

    def members(self) -> list[SwarmMember]:
        return list(self.board.members.values())

    def running(self) -> list[SwarmMember]:
        return [member for member in self.members() if member.status == "running"]

    async def await_members(
        self, identifiers: list[str] | None = None, timeout: float | None = None
    ) -> tuple[list[SwarmMember], bool]:
        """Wait for the named members (or all). Returns (members, all_finished)."""
        targets = [self.get(item) for item in identifiers] if identifiers else self.members()
        pending = [
            member for member in targets if member and member.task and not member.task.done()
        ]
        waiting = [member.task for member in pending if member.task is not None]
        timed_out = False
        if waiting:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*waiting, return_exceptions=True),
                    timeout=timeout,
                )
            except TimeoutError:
                timed_out = True
        finished = [member for member in targets if member]
        return finished, not timed_out and all(
            not member.task or member.task.done() for member in finished
        )

    async def cancel(self, identifiers: list[str] | None = None) -> int:
        targets = [self.get(item) for item in identifiers] if identifiers else self.members()
        cancelled = 0
        for member in targets:
            if member and member.task and not member.task.done():
                member.task.cancel()
                cancelled += 1
        for member in targets:
            if member and member.task and not member.task.done():
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await member.task
        return cancelled

    def report(self, max_chars: int = 4000) -> str:
        """Collect the lanes' results into one bounded report.

        Each lane gets an equal slice, so one talkative worker cannot crowd the
        others out of the budget the parent actually reads.
        """
        members = [member for member in self.members() if member.result or member.error]
        if not members:
            return "No worker output yet."
        per_member = max(200, max_chars // len(members))
        blocks: list[str] = []
        for member in members:
            body = member.result or f"FAILED: {member.error}"
            if len(body) > per_member:
                body = body[:per_member] + "\n... (this lane's output was truncated)"
            blocks.append(f"## {member.name} ({member.id}, {member.status})\n{body}")
        text = "\n\n".join(blocks)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (swarm report truncated)"
        return text

    def render(self) -> str:
        members = self.members()
        if not members:
            return "No workers in this swarm."
        counts: dict[str, int] = {}
        for member in members:
            counts[member.status] = counts.get(member.status, 0) + 1
        header = ", ".join(f"{status} {count}" for status, count in sorted(counts.items()))
        return header + "\n" + "\n".join(member.describe() for member in members)


def get_swarm(app_state: Any) -> Swarm:
    existing = getattr(app_state, "_swarm", None)
    if isinstance(existing, Swarm):
        return existing
    swarm = Swarm(app_state)
    app_state._swarm = swarm
    app_state._swarm_board = swarm.board
    return swarm
