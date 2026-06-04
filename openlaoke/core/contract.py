"""Contract / Definition-of-Done system.

Declarative assertion list the agent commits to. Agent cannot deliver final
response while any assertion remains pending or failed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Assertion:
    id: str
    description: str
    state: str = "pending"  # pending, passed, failed, skipped
    evidence: str = ""


@dataclass
class Contract:
    id: str
    description: str
    work_dir: str = ""
    assertions: list[Assertion] = field(default_factory=list)
    state: str = "active"  # active, completed, aborted
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(UTC).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def is_done(self) -> bool:
        if not self.assertions:
            return False
        return all(a.state in ("passed", "skipped") for a in self.assertions)

    @property
    def pending_assertions(self) -> list[Assertion]:
        return [a for a in self.assertions if a.state == "pending"]

    @property
    def failed_assertions(self) -> list[Assertion]:
        return [a for a in self.assertions if a.state == "failed"]

    @property
    def blockers(self) -> list[Assertion]:
        return [a for a in self.assertions if a.state in ("pending", "failed")]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "work_dir": self.work_dir,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "assertions": [
                {"id": a.id, "description": a.description, "state": a.state, "evidence": a.evidence}
                for a in self.assertions
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Contract:
        return cls(
            id=d.get("id", ""),
            description=d.get("description", ""),
            work_dir=d.get("work_dir", ""),
            state=d.get("state", "active"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            assertions=[
                Assertion(
                    id=a.get("id", ""),
                    description=a.get("description", ""),
                    state=a.get("state", "pending"),
                    evidence=a.get("evidence", ""),
                )
                for a in d.get("assertions", [])
            ],
        )


@dataclass
class ContractStore:
    base_dir: str = ""

    def get_dir(self) -> str:
        if self.base_dir:
            return self.base_dir
        return os.path.join(os.getcwd(), ".openlaoke", "contracts")

    def save(self, contract: Contract) -> None:
        contract.updated_at = datetime.now(UTC).isoformat()
        d = self.get_dir()
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, f"{contract.id}.json")
        tmp = fp + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(contract.to_dict(), f, indent=2)
            os.replace(tmp, fp)
        except OSError:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def load(self, contract_id: str) -> Contract | None:
        fp = os.path.join(self.get_dir(), f"{contract_id}.json")
        if not os.path.exists(fp):
            return None
        try:
            with open(fp, encoding="utf-8") as f:
                return Contract.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            return None

    def load_active(self) -> list[Contract]:
        d = self.get_dir()
        if not os.path.isdir(d):
            return []
        contracts = []
        for fn in sorted(os.listdir(d), reverse=True):
            if fn.endswith(".json"):
                try:
                    c = self.load(fn.replace(".json", ""))
                    if c and c.state == "active":
                        contracts.append(c)
                except Exception:
                    pass
        return contracts

    def list_all(self) -> list[Contract]:
        d = self.get_dir()
        if not os.path.isdir(d):
            return []
        contracts = []
        for fn in sorted(os.listdir(d), reverse=True):
            if fn.endswith(".json"):
                try:
                    c = self.load(fn.replace(".json", ""))
                    if c:
                        contracts.append(c)
                except Exception:
                    pass
        return contracts


@dataclass
class ContractGuard:
    """Prevents agent from claiming completion when assertions are pending/failed."""

    _enabled: bool = True

    def check_done_claim(self, output: str, active_contracts: list[Contract]) -> str | None:
        """Check if agent is claiming completion while assertions remain.
        Returns correction message or None."""
        if not self._enabled:
            return None
        if not active_contracts:
            return None
        done_patterns = [
            r"(?i)\b(i'?m done|i('?ve| have) finished|task completed|all done)\b",
            r"(?i)\b(everything is done|completed successfully|work is done)\b",
        ]
        is_done_claim = any(re.search(p, output) for p in done_patterns)
        if not is_done_claim:
            return None
        for contract in active_contracts:
            blockers = contract.blockers
            if blockers:
                items = "\n".join(f"  [{a.state}] {a.id}: {a.description}" for a in blockers)
                return (
                    "[CONTRACT-GUARD] You claimed completion but have unfulfilled assertions:\n"
                    f"{items}\n"
                    "Complete all assertions before claiming done, or use contract_assert_skip."
                )
        return None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
