"""Task supervision system - ensures tasks are completed."""

from __future__ import annotations

from openlaoke.core.supervisor.checker import TaskCompletionChecker
from openlaoke.core.supervisor.requirements import TaskRequirements
from openlaoke.core.supervisor.supervisor import TaskSupervisor

__all__ = [
    "TaskSupervisor",
    "TaskCompletionChecker",
    "TaskRequirements",
]
