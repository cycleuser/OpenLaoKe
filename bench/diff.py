"""Benchmark diff tool - compare two harness runs.

Exit-coded verdict: 0=improved, 1=regressed, 2=noise.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass


@dataclass
class DiffResult:
    improved: bool = False
    regressed: bool = False
    noise: bool = False
    mean_reward_delta: float = 0.0
    pass_count_delta: int = 0
    wall_clock_delta: float = 0.0
    tool_call_delta: int = 0
    per_task_delta: list[dict] | None = None
    exit_code: int = 2


def diff(baseline_path: str, feature_path: str, threshold: float = 0.05) -> DiffResult:
    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(feature_path) as f:
        feature = json.load(f)

    base_score = baseline.get("overall_score", 0)
    feat_score = feature.get("overall_score", 0)
    base_passed = baseline.get("total_passed", 0)
    feat_passed = feature.get("total_passed", 0)
    base_time = baseline.get("total_duration_ms", 0)
    feat_time = feature.get("total_duration_ms", 0)
    base_calls = baseline.get("total_tool_calls", 0)
    feat_calls = feature.get("total_tool_calls", 0)

    mean_delta = feat_score - base_score
    pass_delta = feat_passed - base_passed
    time_delta = feat_time - base_time
    call_delta = feat_calls - base_calls

    per_task = []
    base_tasks = {}
    feat_tasks = {}
    for s in baseline.get("suites", []):
        for r in s.get("results", []):
            base_tasks[r["task_id"]] = r
    for s in feature.get("suites", []):
        for r in s.get("results", []):
            feat_tasks[r["task_id"]] = r
    for tid in set(base_tasks) | set(feat_tasks):
        bt = base_tasks.get(tid, {"passed": False, "score": 0})
        ft = feat_tasks.get(tid, {"passed": False, "score": 0})
        per_task.append(
            {
                "task_id": tid,
                "baseline_passed": bt.get("passed"),
                "feature_passed": ft.get("passed"),
                "score_delta": ft.get("score", 0) - bt.get("score", 0),
            }
        )

    regressed_tasks = [t for t in per_task if t["baseline_passed"] and not t["feature_passed"]]

    if mean_delta > threshold:
        exit_code = 0
        improved = True
    elif regressed_tasks:
        exit_code = 1
        regressed = True
    else:
        exit_code = 2
        noise = True

    return DiffResult(
        improved=improved,
        regressed=regressed,
        noise=noise,
        mean_reward_delta=mean_delta,
        pass_count_delta=pass_delta,
        wall_clock_delta=time_delta,
        tool_call_delta=call_delta,
        per_task_delta=per_task,
        exit_code=exit_code,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Diff two benchmark runs")
    parser.add_argument("baseline", help="Path to baseline JSON")
    parser.add_argument("feature", help="Path to feature JSON")
    parser.add_argument("--threshold", type=float, default=0.05, help="Improvement threshold")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = diff(args.baseline, args.feature, args.threshold)

    if args.json:
        print(
            json.dumps(
                {
                    "verdict": "improved"
                    if result.improved
                    else "regressed"
                    if result.regressed
                    else "noise",
                    "mean_reward_delta": result.mean_reward_delta,
                    "pass_count_delta": result.pass_count_delta,
                    "tool_call_delta": result.tool_call_delta,
                    "wall_clock_delta": result.wall_clock_delta,
                    "per_task": result.per_task_delta,
                    "exit_code": result.exit_code,
                },
                indent=2,
            )
        )
    else:
        verdict = "IMPROVED" if result.improved else ("REGRESSED" if result.regressed else "NOISE")
        print(f"Verdict: {verdict}")
        print(f"Mean reward delta: {result.mean_reward_delta:+.4f}")
        print(f"Pass count delta: {result.pass_count_delta:+d}")
        print(f"Tool call delta: {result.tool_call_delta:+d}")
        print(f"Wall clock delta: {result.wall_clock_delta:+.0f}ms")

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
