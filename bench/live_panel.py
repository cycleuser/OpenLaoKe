#!/usr/bin/env python
"""Render the matrix run as a live markdown dashboard.

Watching a hundred-minute benchmark through a terminal scrollback is a bad
experience: the interesting number (passes per tool) is never on screen. This
prints one screen with progress, per-combination scores, the failure mix, and the
last few results, so a panel can be refreshed while the run continues.

Usage:
  python bench/live_panel.py --results results/sota-spark-1.7b-q4.json results/sota-lfm3-1.7b-q4.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics

TASKS = [
    "merge",
    "download",
    "fix_tests",
    "spec_impl",
    "refactor",
    "cli",
    "datatrans",
    "sqlite",
    "regex",
    "git",
    "docx_table",
    "async",
]
HARNESS = ["openlaoke", "pi", "jcode", "opencode"]
HARNESS_LABEL = {"openlaoke": "OpenLaoKe", "pi": "pi", "jcode": "Jcode", "opencode": "OpenCode"}
MODEL_LABEL = {"spark-1.7b-q4": "Spark-1.7B", "lfm3-1.7b-q4": "LFM3-1.7B"}
TASK_LABEL = {
    "merge": "merge",
    "download": "download",
    "fix_tests": "修测试",
    "spec_impl": "按规格",
    "refactor": "拆包",
    "cli": "CLI",
    "datatrans": "JSON→CSV",
    "sqlite": "SQL",
    "regex": "抽取",
    "git": "git",
    "docx_table": "docx",
    "async": "并发",
}


def bar(done: int, total: int, width: int = 24) -> str:
    filled = round(width * done / total) if total else 0
    return "█" * filled + "·" * (width - filled)


def load(paths: list[pathlib.Path]) -> dict[str, dict]:
    models: dict[str, dict] = {}
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        models[data["model"]] = data
    return models


def render(models: dict[str, dict]) -> str:
    lines: list[str] = ["## 十二项任务 · 跑分实时看板", ""]
    total_slots = len(TASKS) * len(HARNESS)

    for model, data in models.items():
        rows = data["results"]
        done = len(rows)
        passed = sum(1 for r in rows if r["passed"])
        lines.append(
            f"**{MODEL_LABEL.get(model, model)}** `{bar(done, total_slots)}` "
            f"{done}/{total_slots} 项 · 通过 {passed}"
        )
    lines.append("")

    lines.append("| 组合 | 通过 | 已跑 | 通过项均耗时 | 超时 | 没产出 | 产出不对 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    ranked = []
    for model, data in models.items():
        rows = data["results"]
        for harness in HARNESS:
            got = [r for r in rows if r["harness"] == harness]
            if not got:
                continue
            ok = [r for r in got if r["passed"]]
            avg = statistics.mean(r["seconds"] for r in ok) if ok else None
            timeouts = sum(1 for r in got if not r["passed"] and r["timed_out"])
            empty = sum(
                1 for r in got if not r["passed"] and not r["timed_out"] and not (r.get("detail") or "").strip()
            )
            wrong = len(got) - len(ok) - timeouts - empty
            ranked.append(
                (
                    -len(ok),
                    avg or 9e9,
                    f"| {HARNESS_LABEL[harness]} + {MODEL_LABEL.get(model, model)} | {len(ok)}/{len(TASKS)} "
                    f"| {len(got)}/{len(TASKS)} | " + (f"{avg:.1f}s" if avg else "-") + " | "
                    f"{timeouts} | {empty} | {wrong} |",
                )
            )
    for _a, _b, row in sorted(ranked):
        lines.append(row)
    lines.append("")

    lines.append("### 最近结果")
    recent = []
    for model, data in models.items():
        for row in data["results"][-6:]:
            recent.append((row["seconds"], model, row))
    for _s, model, row in recent[-8:]:
        mark = "✅" if row["passed"] else ("⏱" if row["timed_out"] else "❌")
        detail = (row.get("detail") or "").replace("\n", " ")[:44]
        lines.append(
            f"- {mark} `{HARNESS_LABEL[row['harness']]} + {MODEL_LABEL.get(model, model)}` "
            f"{TASK_LABEL.get(row['task'], row['task'])} · {row['seconds']:.0f}s · {detail}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", nargs="+", type=pathlib.Path, required=True)
    args = parser.parse_args()
    print(render(load(args.results)))


if __name__ == "__main__":
    main()
