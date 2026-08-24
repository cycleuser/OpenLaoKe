"""Cross-tool runner: drives OpenLaoKe / opencode / pi / claude headless modes
over a shared task suite and emits a comparable scorecard.

Design principles:
- Same tasks, same verifier, same sandbox discipline for every agent.
- No trust in agent self-reported success: verify by inspecting the filesystem.
- Isolated temp working dir per (tool, task) so agents can't interfere.
- Hard wall-clock timeout per task so a stuck agent can't stall the run.
- Reusable: the output JSON is directly diffable via bench.cross.compare.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Reuse the existing task suites + verifier so we don't reinvent test cases.
_BENCH_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BENCH_ROOT))

from bench.harness import (  # noqa: E402
    TaskVerifier,
    get_polyglot_tasks,
    get_smoke_tasks,
    get_tooluse_tasks,
)

ALL_SUITES = {
    "smoke": get_smoke_tasks(),
    "polyglot": get_polyglot_tasks(),
    "tooluse": get_tooluse_tasks(),
}

DEFAULT_TIMEOUT = 180
DEFAULT_MAX_STEPS_MSG = "Keep responses minimal. Stop as soon as the task is done."


@dataclass
class TaskOutcome:
    task_id: str
    suite: str
    tool: str
    passed: bool
    score: float
    duration_ms: float
    error: str
    stdout_tail: str = ""
    exit_code: int = 0


@dataclass
class ToolScorecard:
    tool: str
    total: int
    passed: int
    score: float
    mean_duration_ms: float
    outcomes: list[TaskOutcome] = field(default_factory=list)


@dataclass
class CrossResult:
    run_id: str
    tools: list[ToolScorecard] = field(default_factory=list)
    suite_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "suites": self.suite_names,
            "tools": [
                {
                    "tool": t.tool,
                    "total": t.total,
                    "passed": t.passed,
                    "score": t.score,
                    "mean_duration_ms": t.mean_duration_ms,
                    "outcomes": [asdict(o) for o in t.outcomes],
                }
                for t in self.tools
            ],
        }


def _seed(work_dir: str, setup: dict[str, Any] | None) -> None:
    if not setup:
        return
    writes = setup.get("write", {})
    for rel, content in writes.items():
        p = os.path.join(work_dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(rel) else None
        with open(p, "w") as f:
            f.write(content)


async def _run_cmd(cmd: list[str], cwd: str, timeout: float) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"

    try:
        raw, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "<timeout>"
    text = raw.decode("utf-8", errors="replace") if raw else ""
    return proc.returncode if proc.returncode is not None else -1, text


# ── Tool adapters ────────────────────────────────────────────────────────────
# Each adapter turns (prompt, work_dir, timeout) into a headless command.


def _openlaoke_cmd(prompt: str, work_dir: str) -> list[str]:
    exe = sys.executable
    return [exe, "-m", "openlaoke", "-c", work_dir, prompt]


def _opencode_cmd(prompt: str, work_dir: str) -> list[str]:
    return ["opencode", "run", "--dir", work_dir, prompt]


def _pi_cmd(prompt: str, work_dir: str) -> list[str]:
    return ["pi", "--print", "-p", prompt, "--no-session"]


def _claude_cmd(prompt: str, work_dir: str) -> list[str]:
    return ["claude", "-p", prompt, "--cwd", work_dir, "--output-format", "text"]


ADAPTERS = {
    "openlaoke": _openlaoke_cmd,
    "opencode": _opencode_cmd,
    "pi": _pi_cmd,
    "claude": _claude_cmd,
}


async def run_one(
    tool: str,
    task: dict[str, Any],
    timeout: float,
    verifier: TaskVerifier,
) -> TaskOutcome:
    work_dir = tempfile.mkdtemp(prefix=f"xtool_{tool}_{task['id']}_")
    _seed(work_dir, task.get("setup"))
    cmd = ADAPTERS[tool](task["prompt"], work_dir)
    start = time.monotonic()
    code, stdout = await _run_cmd(cmd, work_dir, timeout)
    duration = (time.monotonic() - start) * 1000
    ok, score, error = verifier.verify(task, work_dir)
    tail = stdout[-1200:] if len(stdout) > 1200 else stdout
    shutil.rmtree(work_dir, ignore_errors=True)
    return TaskOutcome(
        task_id=task["id"],
        suite=task.get("suite", "?"),
        tool=tool,
        passed=ok,
        score=score,
        duration_ms=duration,
        error=error or ("" if code == 0 else f"exit={code}"),
        stdout_tail=tail,
        exit_code=code,
    )


async def run_tool(
    tool: str,
    suites: list[str],
    timeout: float,
    verifier: TaskVerifier,
) -> ToolScorecard:
    tasks: list[dict[str, Any]] = []
    for s in suites:
        for t in ALL_SUITES.get(s, []):
            t = dict(t)
            t["suite"] = s
            tasks.append(t)
    outcomes: list[TaskOutcome] = []
    for task in tasks:
        out = await run_one(tool, task, timeout, verifier)
        outcomes.append(out)
        flag = "PASS" if out.passed else "FAIL"
        print(
            f"  [{tool:10}] {flag} {out.suite}/{out.task_id} ({out.duration_ms:.0f}ms) {out.error}"
        )
    passed = sum(1 for o in outcomes if o.passed)
    scores = [o.score for o in outcomes]
    durations = [o.duration_ms for o in outcomes]
    return ToolScorecard(
        tool=tool,
        total=len(outcomes),
        passed=passed,
        score=statistics.mean(scores) if scores else 0.0,
        mean_duration_ms=statistics.mean(durations) if durations else 0.0,
        outcomes=outcomes,
    )


async def run_cross(
    tools: list[str],
    suites: list[str],
    timeout: float,
) -> CrossResult:
    verifier = TaskVerifier()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    result = CrossResult(run_id=run_id, suite_names=suites)
    for tool in tools:
        if tool not in ADAPTERS:
            print(f"  [skip] unknown tool: {tool}")
            continue
        print(f"== {tool} ==")
        sc = await run_tool(tool, suites, timeout, verifier)
        result.tools.append(sc)
    return result


def save(result: CrossResult, path: str | None = None) -> str:
    if path is None:
        path = str(_BENCH_ROOT / "bench" / "cross" / "results" / f"{result.run_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    return path


def print_scorecard(result: CrossResult) -> None:
    print("\n" + "=" * 64)
    print(f"{'tool':12} {'pass':>6} {'score':>7} {'mean_ms':>9}")
    print("-" * 64)
    for t in sorted(result.tools, key=lambda x: -x.score):
        print(f"{t.tool:12} {t.passed:>3}/{t.total:<3} {t.score:>6.1%} {t.mean_duration_ms:>8.0f}")
    print("=" * 64)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Cross-tool agent benchmark")
    p.add_argument(
        "--tools",
        default="openlaoke,opencode,pi",
        help="comma-separated tool names (openlaoke,opencode,pi,claude)",
    )
    p.add_argument(
        "--suites",
        default="smoke,polyglot",
        help="comma-separated suite names (smoke,polyglot,tooluse)",
    )
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="per-task timeout (s)")
    p.add_argument("--save", default=None, help="output JSON path")
    args = p.parse_args()

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    suites = [s.strip() for s in args.suites.split(",") if s.strip()]
    result = asyncio.run(run_cross(tools, suites, args.timeout))
    path = save(result, args.save)
    print_scorecard(result)
    print(f"saved: {path}")


if __name__ == "__main__":
    main()
