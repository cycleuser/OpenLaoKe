"""SubagentManager: spawn isolated child agents.

The :class:`SubagentManager` is the single point that spawns a child
agent in its own session with a filtered tool registry. The
filtered registry excludes ``task``, ``run_skill``, ``install_skill``,
and the four built-in subagent wrappers, so **delegation stays one
layer deep**.

The parent's event stream is nested under the parent tool call ID;
child call IDs are namespaced as ``<parentID>/<childID>`` to avoid
collisions.

A ``run_in_background: true`` invocation registers a job and returns
its ID; the parent can poll via ``bash_output`` / ``wait`` later.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from openlaoke.skill.subagents import SubagentSpec

logger = logging.getLogger(__name__)


@dataclass
class SubagentJob:
    job_id: str
    parent_session_id: str
    parent_call_id: str
    spec_name: str
    prompt: str
    status: str = "pending"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: str = ""
    error: str = ""
    run_in_background: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubagentStatus:
    phase: str = "pending"
    iteration: int = 0
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str = ""


class SubagentManager:
    """Spawns and tracks isolated subagent jobs."""

    _DELEGATION_BANLIST = frozenset(
        {
            "task",
            "subagent",
            "spawn",
            "run_skill",
            "install_skill",
            "explore",
            "research",
            "review",
            "security_review",
        }
    )

    def __init__(self) -> None:
        self._jobs: dict[str, SubagentJob] = {}
        self._max_concurrent = 1
        self._semaphore: asyncio.Semaphore | None = None

    def set_max_concurrent(self, n: int) -> None:
        self._max_concurrent = max(1, n)
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    def filter_tools(
        self,
        available: list[str],
        spec: SubagentSpec,
    ) -> list[str]:
        """Return a filtered tool list for the child agent.

        Excludes delegation tools (``task``, ``run_skill``,
        ``install_skill``, the four subagent wrappers) to enforce
        one-layer nesting.
        """
        allowed = set(spec.allowed_tools or available)
        return [
            name for name in available if name in allowed and name not in self._DELEGATION_BANLIST
        ]

    def spawn(
        self,
        parent_session_id: str,
        parent_call_id: str,
        spec: SubagentSpec,
        prompt: str,
        run_in_background: bool = False,
    ) -> SubagentJob:
        job = SubagentJob(
            job_id=uuid.uuid4().hex[:10],
            parent_session_id=parent_session_id,
            parent_call_id=parent_call_id,
            spec_name=spec.name,
            prompt=prompt,
            run_in_background=run_in_background,
        )
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> SubagentJob | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

    def list_jobs(self, session_id: str = "") -> list[SubagentJob]:
        if not session_id:
            return list(self._jobs.values())
        return [j for j in self._jobs.values() if j.parent_session_id == session_id]

    def status(self, job_id: str) -> SubagentStatus:
        job = self._jobs.get(job_id)
        if not job:
            return SubagentStatus(phase="unknown", stop_reason="not_found")
        return SubagentStatus(
            phase=job.status,
            stop_reason=job.error or "running" if job.status == "running" else job.status,
        )

    async def wait(self, job_id: str, timeout: float = 300.0) -> SubagentJob:
        """Block until the job finishes, polling its status."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self._jobs.get(job_id)
            if not job:
                break
            if job.status in ("completed", "failed", "cancelled"):
                return job
            await asyncio.sleep(0.1)
        return self._jobs.get(job_id)  # type: ignore[return-value]

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in ("completed", "failed", "cancelled"):
            return False
        job.status = "cancelled"
        job.finished_at = time.time()
        return True
