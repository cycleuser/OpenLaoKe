"""Diff two (or more) cross-tool run JSONs into a human-readable report.

Produces a per-task matrix showing which tools passed/failed, plus an
overall winner table. Used to decide whether OpenLaoKe is ahead of, on par
with, or behind opencode/pi/claude on the shared task suite.
"""

from __future__ import annotations

import json
from pathlib import Path


def _load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _task_matrix(runs: list[dict]) -> dict[str, dict[str, dict]]:
    """task_id -> tool -> {passed, score, duration_ms}"""
    matrix: dict[str, dict[str, dict]] = {}
    for run in runs:
        for tool in run.get("tools", []):
            name = tool["tool"]
            for o in tool.get("outcomes", []):
                matrix.setdefault(o["task_id"], {})[name] = {
                    "passed": o["passed"],
                    "score": o["score"],
                    "duration_ms": o["duration_ms"],
                    "error": o.get("error", ""),
                }
    return matrix


def compare(paths: list[str]) -> None:
    runs = [_load(p) for p in paths]
    labels = [Path(p).stem for p in paths]

    # If a single run contains multiple tools, compare those tools directly.
    if len(runs) == 1 and len(runs[0].get("tools", [])) >= 2:
        _compare_tools_in_run(runs[0])
        return

    _compare_runs(runs, labels)


def _compare_tools_in_run(run: dict) -> None:
    """Per-task matrix of tools within a single run."""
    tools = run.get("tools", [])
    labels = [t["tool"] for t in tools]
    # tool -> task_id -> outcome
    by_tool: dict[str, dict[str, dict]] = {}
    for t in tools:
        by_tool[t["tool"]] = {o["task_id"]: o for o in t.get("outcomes", [])}

    all_tasks = sorted({tid for d in by_tool.values() for tid in d})

    print("\n" + "=" * 80)
    header = f"{'task':28} " + " ".join(f"{label:>12}" for label in labels)
    print(header)
    print("-" * 80)
    wins = {label: 0 for label in labels}
    ties = 0
    for tid in all_tasks:
        cells = []
        for label in labels:
            o = by_tool.get(label, {}).get(tid)
            if o is None:
                cells.append(f"{'-':>12}")
            else:
                cells.append(f"{'PASS' if o['passed'] else 'fail':>12}")
        passed_tools = [
            label for label in labels if by_tool.get(label, {}).get(tid, {}).get("passed")
        ]
        if len(passed_tools) == 1:
            wins[passed_tools[0]] += 1
        elif len(passed_tools) > 1:
            ties += 1
        print(f"{tid:28} " + " ".join(cells))

    print("-" * 80)
    print(f"{'WIN count':28} " + " ".join(f"{wins.get(label, 0):>12}" for label in labels))
    print(f"{'TIES':28} {ties:>12}")
    print("=" * 80)

    print(f"\n{'tool':28} {'pass':>7} {'score':>8} {'mean_ms':>9}")
    print("-" * 64)
    for t in sorted(tools, key=lambda x: -x["score"]):
        print(
            f"{t['tool']:28} {t['passed']:>3}/{t['total']:<4} {t['score']:>7.1%} {t['mean_duration_ms']:>8.0f}"
        )


def _compare_runs(runs: list[dict], labels: list[str]) -> None:
    matrix = _task_matrix(runs)

    print("\n" + "=" * 80)
    header = f"{'task':28} " + " ".join(f"{label:>12}" for label in labels)
    print(header)
    print("-" * 80)
    wins = {label: 0 for label in labels}
    ties = 0
    for tid in sorted(matrix):
        row = matrix[tid]
        cells = []
        for label in labels:
            r = row.get(label)
            if r is None:
                cells.append(f"{'-':>12}")
            else:
                mark = "PASS" if r["passed"] else "fail"
                cells.append(f"{mark:>12}")
        passed_tools = [label for label in labels if row.get(label, {}).get("passed")]
        if len(passed_tools) == 1:
            wins[passed_tools[0]] += 1
        elif len(passed_tools) > 1:
            ties += 1
        print(f"{tid:28} " + " ".join(cells))

    print("-" * 80)
    print(f"{'WIN count':28} " + " ".join(f"{wins.get(label, 0):>12}" for label in labels))
    print(f"{'TIES':28} {ties:>12}")
    print("=" * 80)

    # Overall scorecard per run
    print(f"\n{'run':28} {'pass':>7} {'score':>8} {'mean_ms':>9}")
    print("-" * 64)
    for run, label in zip(runs, labels, strict=False):
        tools = run.get("tools", [])
        total_pass = sum(t["passed"] for t in tools)
        total_tasks = sum(t["total"] for t in tools)
        scores = [t["score"] for t in tools]
        durs = [t["mean_duration_ms"] for t in tools]
        score = sum(scores) / len(scores) if scores else 0
        mean_ms = sum(durs) / len(durs) if durs else 0
        print(f"{label:28} {total_pass:>3}/{total_tasks:<4} {score:>7.1%} {mean_ms:>8.0f}")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Compare cross-tool benchmark runs")
    p.add_argument("runs", nargs="+", help="paths to run JSON files")
    args = p.parse_args()
    compare(args.runs)


if __name__ == "__main__":
    main()
