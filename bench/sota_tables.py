#!/usr/bin/env python
"""Turn the SOTA matrix result files into the markdown tables the article uses.

The article is generated from these numbers instead of being typed by hand, so a
stale cell cannot survive a re-run.

Usage:
  python bench/sota_tables.py --results results/sota-spark-1.7b-q4.json results/sota-lfm3-1.7b-q4.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics

TASK_ORDER = [
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
TASK_LABEL = {
    "merge": "merge（锚点）",
    "download": "download（锚点）",
    "fix_tests": "修测试",
    "spec_impl": "按规格实现",
    "refactor": "拆包重构",
    "cli": "命令行工具",
    "datatrans": "JSON→CSV",
    "sqlite": "写 SQL",
    "regex": "日志抽取",
    "git": "git 提交",
    "docx_table": "Word 表格",
    "async": "并发",
}
HARNESS_ORDER = ["openlaoke", "pi", "jcode", "opencode"]
HARNESS_LABEL = {"openlaoke": "OpenLaoKe", "pi": "pi", "jcode": "Jcode", "opencode": "OpenCode"}
MODEL_LABEL = {"spark-1.7b-q4": "Spark-1.7B", "lfm3-1.7b-q4": "LFM3-1.7B"}


def load(paths: list[pathlib.Path]) -> dict[str, dict[str, dict[str, dict]]]:
    """{model: {(task, harness): row}}"""
    out: dict[str, dict[tuple[str, str], dict]] = {}
    for path in paths:
        data = json.loads(path.read_text())
        model = data["model"]
        out[model] = {(r["task"], r["harness"]): r for r in data["results"]}
    return out  # type: ignore[return-value]


def cell(row: dict | None) -> str:
    if row is None:
        return "-"
    mark = "⏱" if row["timed_out"] else ("✅" if row["passed"] else "❌")
    return f"{mark}{row['seconds']:.0f}s"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", nargs="+", type=pathlib.Path, required=True)
    args = parser.parse_args()
    table = load(args.results)
    models = [m for m in MODEL_LABEL if m in table]

    print("### 逐任务（单元格 = 结果 + 墙钟秒数）\n")
    for model in models:
        rows = table[model]
        print(f"**{MODEL_LABEL[model]}**\n")
        print("| 任务 | " + " | ".join(HARNESS_LABEL[h] for h in HARNESS_ORDER) + " |")
        print("|---|" + "---|" * len(HARNESS_ORDER))
        for task in TASK_ORDER:
            cells = [cell(rows.get((task, h))) for h in HARNESS_ORDER]
            print(f"| {TASK_LABEL[task]} | " + " | ".join(cells) + " |")
        print()

    print("### 按工具汇总\n")
    print("| 组合 | 通过 | 通过项平均耗时 |")
    print("|---|---:|---:|")
    summary = []
    for model in models:
        for harness in HARNESS_ORDER:
            got = [r for (t, h), r in table[model].items() if h == harness]
            passed = [r for r in got if r["passed"]]
            avg = statistics.mean(r["seconds"] for r in passed) if passed else None
            summary.append((f"{HARNESS_LABEL[harness]} + {MODEL_LABEL[model]}", len(passed), len(got), avg))
    for name, ok, total, avg in sorted(summary, key=lambda item: (-item[1], item[3] or 9e9)):
        print(f"| {name} | {ok}/{total} | " + (f"{avg:.1f}s" if avg else "-") + " |")

    print("\n### 按模型合计\n")
    for model in models:
        got = list(table[model].values())
        print(f"- {MODEL_LABEL[model]}: {sum(1 for r in got if r['passed'])}/{len(got)}")

    print("\n### 按任务看难度\n")
    print("| 任务 | " + " | ".join(f"{HARNESS_LABEL[h]}" for h in HARNESS_ORDER) + " |")
    print("|---|" + "---|" * len(HARNESS_ORDER))
    for task in TASK_ORDER:
        wins = []
        for harness in HARNESS_ORDER:
            n = sum(1 for m in models if table[m].get((task, harness), {}).get("passed"))
            wins.append(f"{n}/{len(models)}")
        print(f"| {TASK_LABEL[task]} | " + " | ".join(wins) + " |")


if __name__ == "__main__":
    main()
