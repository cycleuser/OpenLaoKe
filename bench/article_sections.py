#!/usr/bin/env python
"""Render the article sections straight from the result files.

Typing a hundred numbers into prose is how benchmark articles end up disagreeing
with their own data. Each section here is generated and then spliced into the
markdown, so a re-run only needs the splice redone.

Usage:
  python bench/article_sections.py --coding section
  python bench/article_sections.py --daily section
  python bench/article_sections.py --appendix section
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS = ROOT / "results"

CODING_TASKS = [
    ("merge", "merge"),
    ("download", "download"),
    ("fix_tests", "修测试"),
    ("spec_impl", "按规格实现"),
    ("refactor", "拆包重构"),
    ("cli", "命令行工具"),
    ("datatrans", "JSON→CSV"),
    ("sqlite", "写 SQL"),
    ("regex", "日志抽取"),
    ("git", "git 提交"),
    ("docx_table", "Word 表格"),
    ("async", "并发"),
]
DAILY_TASKS = [
    ("tidy_notes", "整理笔记"),
    ("clean_csv", "清洗表格"),
    ("receipt", "票据转 JSON"),
    ("meeting", "会议纪要"),
    ("index", "笔记索引"),
    ("email", "邮件回复"),
    ("weekly", "周报汇总"),
    ("budget", "预算表"),
]
HARNESS = ["openlaoke", "pi", "jcode", "opencode"]
HARNESS_LABEL = {"openlaoke": "OpenLaoKe", "pi": "pi", "jcode": "Jcode", "opencode": "OpenCode"}
MODELS = [("spark-1.7b-q4", "Spark-1.7B"), ("lfm3-1.7b-q4", "LFM3-1.7B")]


def load(pattern: str) -> dict[str, dict]:
    out = {}
    for model, _label in MODELS:
        path = RESULTS / pattern.format(model=model)
        if path.exists():
            data = json.loads(path.read_text())
            out[model] = {(r["task"], r["harness"]): r for r in data["results"]}
    return out


def mark(row: dict | None, key: str = "passed") -> str:
    if row is None:
        return "-"
    if row.get(key) or (key == "verified" and row.get("verified")):
        return f"✅{row['seconds']:.0f}s"
    if row["timed_out"]:
        return f"⏱{row['seconds']:.0f}s"
    return f"❌{row['seconds']:.0f}s"


def coding_section() -> str:
    table = load("sota-{model}.json")
    lines: list[str] = []
    for model, label in MODELS:
        rows = table.get(model, {})
        if not rows:
            continue
        lines.append(f"**{label}**（单元格 = 结果 + 墙钟秒数）\n")
        lines.append("| 任务 | " + " | ".join(HARNESS_LABEL[h] for h in HARNESS) + " |")
        lines.append("|---|" + "---|" * len(HARNESS))
        for key, name in CODING_TASKS:
            lines.append(f"| {name} | " + " | ".join(mark(rows.get((key, h))) for h in HARNESS) + " |")
        lines.append("")

    lines.append("按组合汇总：\n")
    lines.append("| 组合 | 通过 | 通过项平均耗时 | 失败形态（超时/没产出/产出不对） |")
    lines.append("|---|---:|---:|---|")
    summary = []
    for model, label in MODELS:
        rows = table.get(model, {})
        for harness in HARNESS:
            got = [r for (t, h), r in rows.items() if h == harness]
            if not got:
                continue
            ok = [r for r in got if r["passed"]]
            avg = statistics.mean(r["seconds"] for r in ok) if ok else None
            timeouts = sum(1 for r in got if not r["passed"] and r["timed_out"])
            empty = sum(
                1
                for r in got
                if not r["passed"] and not r["timed_out"] and not (r.get("detail") or "").strip()
            )
            wrong = len(got) - len(ok) - timeouts - empty
            summary.append((-len(ok), avg or 9e9, HARNESS_LABEL[harness], label, len(ok), len(got), avg, timeouts, empty, wrong))
    for _n, _a, harness, label, ok, total, avg, timeouts, empty, wrong in sorted(summary):
        avg_text = f"{avg:.1f}s" if avg else "-"
        lines.append(f"| {harness} + {label} | {ok}/{total} | {avg_text} | {timeouts} / {empty} / {wrong} |")
    lines.append("")
    for model, label in MODELS:
        rows = table.get(model, {})
        if rows:
            ok = sum(1 for r in rows.values() if r["passed"])
            lines.append(f"- {label}：**{ok}/{len(rows)}**")
    lines.append("")
    lines.append("![十二项编码任务矩阵](images/sota-17b/sota-matrix.png)\n")
    lines.append("![每个组合通过了多少项](images/sota-17b/sota-scores.png)")
    return "\n".join(lines)


def daily_section() -> str:
    table = load("daily2-{model}.json")
    if not table:
        table = load("daily-{model}.json")
    lines: list[str] = []
    for model, label in MODELS:
        rows = table.get(model, {})
        if not rows:
            continue
        lines.append(f"**{label}**（单元格 = 产物对不对 + 墙钟秒数；带 ⏱ 表示产物对但没在 120 秒内退出）\n")
        lines.append("| 任务 | " + " | ".join(HARNESS_LABEL[h] for h in HARNESS) + " |")
        lines.append("|---|" + "---|" * len(HARNESS))
        for key, name in DAILY_TASKS:
            lines.append(f"| {name} | " + " | ".join(mark(rows.get((key, h)), "verified") for h in HARNESS) + " |")
        lines.append("")

    lines.append("两个口径的合计：\n")
    lines.append("| 组合 | 产物正确 | 按时交付 | 通过项平均耗时 |")
    lines.append("|---|---:|---:|---:|")
    summary = []
    for model, label in MODELS:
        rows = table.get(model, {})
        for harness in HARNESS:
            got = [r for (t, h), r in rows.items() if h == harness]
            if not got:
                continue
            verified = [r for r in got if r.get("verified")]
            passed = [r for r in got if r["passed"]]
            avg = statistics.mean(r["seconds"] for r in passed) if passed else None
            summary.append((-len(verified), -len(passed), label, HARNESS_LABEL[harness], len(verified), len(passed), len(got), avg))
    for _a, _b, label, harness, verified, passed, total, avg in sorted(summary):
        lines.append(
            f"| {harness} + {label} | {verified}/{total} | {passed}/{total} | "
            + (f"{avg:.1f}s" if avg else "-")
            + " |"
        )
    lines.append("")
    for model, label in MODELS:
        rows = table.get(model, {})
        if rows:
            verified = sum(1 for r in rows.values() if r.get("verified"))
            passed = sum(1 for r in rows.values() if r["passed"])
            lines.append(f"- {label}：产物正确 **{verified}/{len(rows)}**，按时交付 **{passed}/{len(rows)}**")
    lines.append("")
    return "\n".join(lines)


def appendix_section() -> str:
    path = RESULTS / "cap2-graded.json"
    if not path.exists():
        return "（缺 cap2-graded.json）"
    data = json.loads(path.read_text())
    lines: list[str] = []
    first = next(iter(data))
    for idx, item in enumerate(data[first]["rows"], start=1):
        lines.append(f"### 第 {idx} 题 · {item['group']} · `{item['id']}`\n")
        lines.append("**提示词**\n")
        lines.append("```text\n" + item["q"].strip() + "\n```\n")
        for name in ("spark", "lfm3"):
            block = data[name]["rows"][idx - 1]
            verdict = "✅" if block["ok"] else "❌"
            label = "Spark-1.7B" if name == "spark" else "LFM3-1.7B"
            lines.append(f"**{label}** {verdict} {block['why']}\n")
            lines.append("```text\n" + block["answer"].strip() + "\n```\n")
    return "\n".join(lines)


SECTIONS = {
    "coding": coding_section,
    "daily": daily_section,
    "appendix": appendix_section,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("section", choices=sorted(SECTIONS))
    args = parser.parse_args()
    print(SECTIONS[args.section]())


if __name__ == "__main__":
    main()
