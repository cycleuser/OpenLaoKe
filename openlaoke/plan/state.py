"""Per-session evidence ledger and final-answer readiness check.

The ledger records host-observed evidence about tool calls: success,
read-only-ness, and (for writers) the file diff and timestamp. The
``ready_for_final_answer`` function refuses to accept a "done" answer
if a successful writer fired recently and either the project checks
or a successful ``complete_step`` did not run after the latest write.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    tool_name: str
    success: bool
    read_only: bool
    timestamp: float = field(default_factory=time.time)
    path: str = ""
    complete_step: bool = False
    project_check: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Ledger:
    session_id: str
    entries: list[Evidence] = field(default_factory=list)
    project_checks: list[dict[str, Any]] = field(default_factory=list)

    def record(self, evidence: Evidence) -> None:
        self.entries.append(evidence)

    def latest_write(self) -> Evidence | None:
        for entry in reversed(self.entries):
            if not entry.read_only and entry.success:
                return entry
        return None

    def latest_complete_step(self) -> Evidence | None:
        for entry in reversed(self.entries):
            if entry.complete_step and entry.success:
                return entry
        return None

    def has_project_check_after_write(self) -> bool:
        latest = self.latest_write()
        if latest is None:
            return True
        for entry in self.entries:
            if entry.project_check and entry.timestamp >= latest.timestamp and entry.success:
                return True
        return False

    def has_complete_step_after_write(self) -> bool:
        latest = self.latest_write()
        if latest is None:
            return True
        for entry in self.entries:
            if entry.complete_step and entry.timestamp >= latest.timestamp and entry.success:
                return True
        return False


@dataclass
class ReadinessCheck:
    project_checks: list[dict[str, Any]] = field(default_factory=list)
    require_complete_step: bool = True
    max_retries: int = 3

    def missing_evidence(self, ledger: Ledger) -> list[str]:
        latest_write = ledger.latest_write()
        if latest_write is None:
            return []
        missing: list[str] = []
        if self.project_checks and not ledger.has_project_check_after_write():
            names = ", ".join(c.get("name", "?") for c in self.project_checks)
            missing.append(f"project check ({names})")
        if self.require_complete_step and not ledger.has_complete_step_after_write():
            missing.append("complete_step")
        return missing


@dataclass
class PlanState:
    """Per-session plan state."""

    enabled: bool = False
    plan_text: str = ""
    auto_approve: bool = False
    approved_at: float = 0.0
    evidence: Ledger = field(default_factory=lambda: Ledger(session_id=""))
    readiness: ReadinessCheck = field(default_factory=ReadinessCheck)
    sub_steps: list[dict[str, Any]] = field(default_factory=list)
    current_sub_step: int = -1
    retries: int = 0

    def begin_plan(self, text: str) -> None:
        self.enabled = True
        self.plan_text = text
        self.auto_approve = False
        self.approved_at = 0.0

    def approve(self) -> None:
        self.enabled = False
        self.auto_approve = True
        self.approved_at = time.time()

    def exit(self) -> None:
        self.enabled = False
        self.auto_approve = False

    def is_writer_allowed(self) -> bool:
        """Plan mode blocks writer tools unless explicitly approved."""
        return self.auto_approve or not self.enabled


def plan_mode_block_message(tool_name: str) -> str:
    return (
        f"Plan mode is read-only. The tool '{tool_name}' was blocked. "
        "Present the plan via SubmitPlanApproval. After approval the model "
        "may execute the plan without re-prompting for each writer tool."
    )
