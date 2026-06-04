"""Trace recorder and bench diff.

* :class:`TraceRecorder` — every agent turn is serialized to JSONL.
  ``/trace list`` enumerates; ``/trace show <id>`` prints; ``/trace test
  <id>`` re-runs the trace as a regression test.
* ``core_trace`` — the detailed per-turn trace from
  ``openlaoke.core.trace_recorder`` (tool calls, tokens, timing).
* :func:`bench_diff` — compares two bench runs and returns a verdict
  (improved/regressed/noise) with an exit code 0/1/2 for CI gating.
* :func:`health_check` — startup provider reachability + config validation.
"""

from __future__ import annotations

from openlaoke.control.health import HealthReport, run_health_checks
from openlaoke.core.trace_recorder import TraceRecorder as CoreTraceRecorder

__all__ = [
    "CoreTraceRecorder",
    "HealthReport",
    "TraceRecorder",
    "bench_diff",
    "run_health_checks",
]

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXIT_IMPROVED = 0
EXIT_REGRESSED = 1
EXIT_NOISE = 2


@dataclass
class TraceRecord:
    """A single recorded turn."""

    trace_id: str
    session_id: str
    turn_index: int
    started_at: float
    finished_at: float
    user_text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    assistant_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "trace_id": self.trace_id,
                "session_id": self.session_id,
                "turn_index": self.turn_index,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "user_text": self.user_text,
                "tool_calls": self.tool_calls,
                "assistant_text": self.assistant_text,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_jsonl(cls, line: str) -> TraceRecord:
        data = json.loads(line)
        return cls(
            trace_id=data["trace_id"],
            session_id=data["session_id"],
            turn_index=data.get("turn_index", 0),
            started_at=float(data.get("started_at", 0.0) or 0.0),
            finished_at=float(data.get("finished_at", 0.0) or 0.0),
            user_text=data.get("user_text", ""),
            tool_calls=list(data.get("tool_calls", []) or []),
            assistant_text=data.get("assistant_text", ""),
            metadata=dict(data.get("metadata", {}) or {}),
        )


class TraceRecorder:
    """Per-session JSONL trace store."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = base_dir or os.path.expanduser("~/.openlaoke/traces")
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        return os.path.join(self.base_dir, f"{session_id}.jsonl")

    def record(self, record: TraceRecord) -> None:
        if not record.trace_id:
            record.trace_id = uuid.uuid4().hex[:10]
        with open(self._path(record.session_id), "a", encoding="utf-8") as f:
            f.write(record.to_jsonl() + "\n")

    def list_traces(self, session_id: str = "") -> list[TraceRecord]:
        out: list[TraceRecord] = []
        pattern = f"{session_id}.jsonl" if session_id else "*.jsonl"
        for path in Path(self.base_dir).glob(pattern):
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        out.append(TraceRecord.from_jsonl(line))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(out, key=lambda r: r.started_at, reverse=True)

    def get(self, trace_id: str) -> TraceRecord | None:
        for record in self.list_traces():
            if record.trace_id == trace_id:
                return record
        return None


def bench_diff(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    noise_threshold: float = 0.05,
) -> dict[str, Any]:
    """Compare two bench-run summaries.

    * ``pass_rate`` (0..1) — increase is improvement
    * ``avg_duration_ms`` — decrease is improvement
    * ``avg_tokens`` — decrease is improvement

    Returns a dict with ``verdict`` and ``exit_code``.
    """
    before_pass = float(before.get("pass_rate", 0.0))
    after_pass = float(after.get("pass_rate", 0.0))
    before_dur = float(before.get("avg_duration_ms", 0.0))
    after_dur = float(after.get("avg_duration_ms", 0.0))
    before_tok = float(before.get("avg_tokens", 0.0))
    after_tok = float(after.get("avg_tokens", 0.0))

    pass_delta = after_pass - before_pass
    dur_delta = (after_dur - before_dur) / max(before_dur, 1.0)
    tok_delta = (after_tok - before_tok) / max(before_tok, 1.0)

    improved = (
        pass_delta > noise_threshold
        or (dur_delta < -noise_threshold)
        or (tok_delta < -noise_threshold)
    )
    regressed = (
        pass_delta < -noise_threshold or dur_delta > noise_threshold or tok_delta > noise_threshold
    )

    if improved and not regressed:
        verdict, exit_code = "improved", EXIT_IMPROVED
    elif regressed and not improved:
        verdict, exit_code = "regressed", EXIT_REGRESSED
    else:
        verdict, exit_code = "noise", EXIT_NOISE
    return {
        "verdict": verdict,
        "exit_code": exit_code,
        "pass_delta": pass_delta,
        "dur_delta_pct": dur_delta,
        "tok_delta_pct": tok_delta,
        "before": before,
        "after": after,
    }
