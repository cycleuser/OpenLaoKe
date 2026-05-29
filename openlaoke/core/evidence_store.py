"""Evidence store - tracks what was tried, what worked, what failed per task.

Inspired by smallcode's evidence.js for automated capture of task outcomes.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvidenceEntry:
    task_id: str
    strategy: str
    outcome: str  # "worked" | "failed" | "partial"
    details: str = ""
    tokens_used: int = 0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class EvidenceStore:
    """Records what was attempted and the outcome for each task.

    Used by the agent to avoid retrying failed strategies and to
    automatically select working approaches for similar tasks.
    """

    def __init__(self, store_dir: str | None = None) -> None:
        self._dir = Path(store_dir) if store_dir else Path.home() / ".openlaoke" / "evidence"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[EvidenceEntry] = []
        self._load()

    def record(
        self,
        task_id: str,
        strategy: str,
        outcome: str,
        details: str = "",
        tokens_used: int = 0,
        duration_ms: float = 0.0,
    ) -> None:
        entry = EvidenceEntry(
            task_id=task_id,
            strategy=strategy,
            outcome=outcome,
            details=details[:2000],
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )
        self._entries.append(entry)
        self._save()

    def get_failed_strategies(self, task_id: str) -> set[str]:
        return {
            e.strategy
            for e in self._entries
            if e.task_id == task_id and e.outcome == "failed"
        }

    def get_working_strategies(self, task_id: str) -> list[EvidenceEntry]:
        return [e for e in self._entries if e.task_id == task_id and e.outcome == "worked"]

    def has_been_tried(self, task_id: str, strategy: str) -> bool:
        return any(
            e.task_id == task_id and e.strategy == strategy and e.outcome == "failed"
            for e in self._entries
        )

    def get_recent(self, limit: int = 20) -> list[EvidenceEntry]:
        return sorted(self._entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_stats(self) -> dict[str, int]:
        worked = sum(1 for e in self._entries if e.outcome == "worked")
        failed = sum(1 for e in self._entries if e.outcome == "failed")
        return {"total": len(self._entries), "worked": worked, "failed": failed}

    def _save(self) -> None:
        try:
            data = {
                "entries": [
                    {
                        "task_id": e.task_id,
                        "strategy": e.strategy,
                        "outcome": e.outcome,
                        "details": e.details,
                        "tokens_used": e.tokens_used,
                        "duration_ms": e.duration_ms,
                        "timestamp": e.timestamp,
                    }
                    for e in self._entries[-1000:]
                ],
                "saved_at": time.time(),
            }
            (self._dir / "evidence.json").write_text(json.dumps(data, indent=2))
        except OSError:
            pass

    def _load(self) -> None:
        path = self._dir / "evidence.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            for e in data.get("entries", []):
                self._entries.append(
                    EvidenceEntry(
                        task_id=e["task_id"],
                        strategy=e["strategy"],
                        outcome=e["outcome"],
                        details=e.get("details", ""),
                        tokens_used=e.get("tokens_used", 0),
                        duration_ms=e.get("duration_ms", 0.0),
                        timestamp=e.get("timestamp", time.time()),
                    )
                )
        except (OSError, json.JSONDecodeError):
            pass
