"""Task list the harness keeps, so a weak model does not have to.

The list is the harness's memory of what remains, which makes three things
possible that a bare prompt cannot do: waking the model when it stops early,
skipping items that are genuinely blocked instead of retrying them forever, and
refusing to record an item as done until it says what proved it.

Shaped after jcode's phases/lanes/items hierarchy (docs/HARNESS.md:139) with the
swarm-specific parts removed: phases order the work, lanes group work that could
run in parallel, and ``after`` names specific prerequisites instead of waiting
for a whole phase to close.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"
STATUSES = (STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_CANCELLED)

OPEN_STATUSES = (STATUS_PENDING, STATUS_IN_PROGRESS)

MAX_AUTO_POKES = 3
MAX_PLAN_ITEMS = 1024


@dataclass
class TodoItem:
    """One tracked unit of work."""

    name: str
    status: str = STATUS_PENDING
    phase: str = ""
    lane: str = ""
    after: list[str] = field(default_factory=list)
    evidence: str = ""
    blocked_reason: str = ""
    external_blocker: str = ""
    review_at: str = ""
    attempts: int = 0
    outcome: str = ""
    assessment: dict[str, str] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def completely_blocked(self) -> bool:
        """Blocked in a way that no automatic continuation can clear."""
        return bool(self.blocked_reason)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TodoItem:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items() if key in known})

    def render(self) -> str:
        mark = {
            STATUS_PENDING: "[ ]",
            STATUS_IN_PROGRESS: "[~]",
            STATUS_DONE: "[x]",
            STATUS_CANCELLED: "[-]",
        }.get(self.status, "[?]")
        parts = [f"{mark} {self.name}"]
        if self.status != STATUS_PENDING:
            parts.append(f"({self.status})")
        if self.completely_blocked:
            parts.append(f"BLOCKED: {self.blocked_reason}")
        elif self.external_blocker:
            parts.append(f"waiting on: {self.external_blocker}")
        if self.after:
            parts.append("after " + ", ".join(self.after))
        if self.evidence and self.status == STATUS_DONE:
            parts.append(f"proven by: {self.evidence}")
        if self.attempts:
            parts.append(f"attempts={self.attempts}")
        return "  " + "  ".join(parts)


class TodoStore:
    """Ordered task list persisted with the session."""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state: dict[str, Any] = state if state is not None else {"items": []}
        self._state.setdefault("items", [])
        self.items: list[TodoItem] = [TodoItem.from_dict(raw) for raw in self._state["items"]]

    def apply(self, patches: list[dict[str, Any]]) -> tuple[list[TodoItem], list[str]]:
        """Patch items by unique name. Returns (touched, warnings)."""
        warnings: list[str] = []
        touched: list[TodoItem] = []
        for patch in patches:
            name = str(patch.get("name") or "").strip()
            if not name:
                warnings.append("skipped a patch without 'name'")
                continue
            item = self.get(name)
            creating = item is None
            if item is None:
                if len(self.items) >= MAX_PLAN_ITEMS:
                    warnings.append(f"plan is full at {MAX_PLAN_ITEMS} items; ignored '{name}'")
                    continue
                item = TodoItem(name=name)
                self.items.append(item)

            rename_to = str(patch.get("rename_to") or "").strip()
            for key, value in patch.items():
                if key in ("name", "rename_to") or value is None:
                    continue
                if key == "completely_blocked":
                    reason = value.get("reason") if isinstance(value, dict) else value
                    item.blocked_reason = str(reason or "")
                    continue
                if key == "external_blocker":
                    reason = value.get("reason") if isinstance(value, dict) else value
                    item.external_blocker = str(reason or "")
                    item.review_at = (
                        str((value or {}).get("review_at", "")) if isinstance(value, dict) else ""
                    )
                    continue
                if key == "after":
                    item.after = [str(dep) for dep in value] if isinstance(value, list) else []
                    continue
                if key == "assessment" and isinstance(value, dict):
                    item.assessment = {str(k): str(v) for k, v in value.items()}
                    continue
                if hasattr(item, key):
                    setattr(item, key, str(value) if not isinstance(value, (int, float)) else value)

            if rename_to:
                self._rename(name, rename_to)
                item.name = rename_to

            if creating:
                item.attempts = 0

            if item.status == STATUS_DONE and not item.evidence.strip():
                item.status = STATUS_IN_PROGRESS
                warnings.append(
                    f"'{item.name}' was marked done with no evidence; kept as in_progress. "
                    "Say which command or check proved it."
                )
            if item.status == STATUS_DONE:
                item.blocked_reason = ""
                item.external_blocker = ""
            if item.status in OPEN_STATUSES:
                item.attempts += 1
            touched.append(item)

        self._flush()
        return touched, warnings

    def _rename(self, old: str, new: str) -> None:
        for item in self.items:
            item.after = [new if dep == old else dep for dep in item.after]

    def get(self, name: str) -> TodoItem | None:
        for item in self.items:
            if item.name == name:
                return item
        return None

    def open_items(self) -> list[TodoItem]:
        return [item for item in self.items if item.is_open]

    def actionable_items(self) -> list[TodoItem]:
        """Open items that are neither blocked nor waiting on unfinished work."""
        ready: list[TodoItem] = []
        for item in self.open_items():
            if item.completely_blocked or item.external_blocker:
                continue
            if any(self._dependency_state(dep) != STATUS_DONE for dep in item.after):
                continue
            ready.append(item)
        return ready

    def _dependency_state(self, name: str) -> str:
        item = self.get(name)
        # A deleted or cancelled prerequisite never counts as satisfied.
        return item.status if item else STATUS_CANCELLED

    def blocked_items(self) -> list[TodoItem]:
        return [item for item in self.items if item.is_open and item.completely_blocked]

    def signature(self) -> str:
        payload = "|".join(
            f"{item.name}:{item.status}:{item.blocked_reason}" for item in self.items
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def render(self, detail: bool = False) -> str:
        if not self.items:
            return "No tasks recorded."
        lines: list[str] = []
        current_phase: str | None = None
        for item in self.items:
            if item.phase and item.phase != current_phase:
                current_phase = item.phase
                lines.append(f"phase: {item.phase}")
            lines.append(item.render())
        summary = (
            f"{len(self.open_items())} open, {len(self.items)} total"
            f", {len(self.blocked_items())} blocked"
        )
        if detail:
            lines.append(f"({summary})")
        return "\n".join(lines)

    def digest(self) -> str:
        """Compact weak-point reminder used by the automatic continuation."""
        ready = self.actionable_items()
        lines = ["You stopped while tasks are still open."]
        if ready:
            lines.append("Next unblocked tasks:")
            lines.extend(item.render() for item in ready[:5])
            lines.append("Continue with the first one, or mark it done with evidence.")
        else:
            waiting = [item for item in self.open_items() if item.external_blocker]
            if waiting:
                lines.append("Every open task is waiting on something external:")
                lines.extend(item.render() for item in waiting[:5])
                lines.append("Set completely_blocked with a reason if it cannot proceed.")
            else:
                lines.append("Every open task is blocked or waiting on an unfinished task:")
                lines.extend(item.render() for item in self.open_items()[:5])
        return "\n".join(lines)

    def clear(self) -> None:
        self.items = []
        self._flush()

    def replace(self, items: list[TodoItem]) -> None:
        self.items = items
        self._flush()

    def _flush(self) -> None:
        self._state["items"] = [item.to_dict() for item in self.items]
