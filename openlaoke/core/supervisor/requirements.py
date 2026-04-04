"""Task requirements specification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskRequirements:
    name: str
    description: str
    check_type: str
    critical: bool = True
    patterns: list[str] = field(default_factory=list)
    threshold: float | int | None = None
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.critical:
            self.weight = 2.0


@dataclass
class RequirementCheckResult:
    requirement: TaskRequirements
    satisfied: bool
    actual_value: Any = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
