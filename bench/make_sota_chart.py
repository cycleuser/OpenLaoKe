#!/usr/bin/env python
"""Two figures for the SOTA matrix: the pass grid, and score against speed.

Reads the same result files the article tables come from, so the picture and the
text cannot disagree.

Usage:
  python bench/make_sota_chart.py \
    --spark results/sota-spark-1.7b-q4.json \
    --lfm3 results/sota-lfm3-1.7b-q4.json \
    --out-dir ../../blog/微信公众号草稿/images/spark-vs-lfm3
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

TASKS = [
    ("merge", "merge"),
    ("download", "download"),
    ("fix_tests", "fix\ntests"),
    ("spec_impl", "spec"),
    ("refactor", "refactor"),
    ("cli", "cli"),
    ("datatrans", "json→csv"),
    ("sqlite", "sql"),
    ("regex", "regex"),
    ("git", "git"),
    ("docx_table", "docx"),
    ("async", "async"),
]
HARNESS = ["openlaoke", "pi", "jcode", "opencode"]
HARNESS_LABEL = {"openlaoke": "OpenLaoKe", "pi": "pi", "jcode": "Jcode", "opencode": "OpenCode"}
MODELS = [("spark", "Spark-1.7B", "#C2410C"), ("lfm3", "LFM3-1.7B", "#1D4ED8")]

INK = "#111827"
MUTED = "#6B7280"
FAINT = "#9CA3AF"
LINE = "#E5E7EB"
FAIL = "#DC2626"
PAPER = "#FCFCFD"

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False


def load(path: pathlib.Path) -> dict[tuple[str, str], dict]:
    data = json.loads(path.read_text())
    return {(r["task"], r["harness"]): r for r in data["results"]}


def tick(ax, cx, cy, s, color, lw=2.2):
    ax.plot(
        [cx - 0.20 * s, cx - 0.05 * s, cx + 0.22 * s],
        [cy + 0.00 * s, cy - 0.16 * s, cy + 0.20 * s],
        color=color,
        lw=lw,
        solid_capstyle="round",
        solid_joinstyle="round",
        zorder=5,
    )


def cross(ax, cx, cy, s, color, lw=1.9):
    for dx in (1, -1):
        ax.plot(
            [cx - 0.13 * s * dx, cx + 0.13 * s * dx],
            [cy - 0.13 * s, cy + 0.13 * s],
            color=color,
            lw=lw,
            solid_capstyle="round",
            zorder=5,
        )


def grid(out_path: pathlib.Path, tables: dict[str, dict], title: str, subtitle: str) -> None:
    groups = []
    for key, label, hue in MODELS:
        rows = tables[key]
        present = [h for h in HARNESS if any((t, h) in rows for t, _ in TASKS)]
        present.sort(
            key=lambda h: (-sum(1 for t, _ in TASKS if rows.get((t, h), {}).get("passed")), HARNESS.index(h))
        )
        groups.append((label, hue, present, rows))

    cw, ch = 1.0, 0.94
    ox = 0.45
    left_pad = 2.15
    right_pad = 1.25
    head_band = 2.15
    group_band = 0.66
    group_gap = 0.32
    foot_band = 1.25
    n_rows = sum(len(g[2]) for g in groups)
    width = ox + left_pad + len(TASKS) * cw + right_pad
    height = (
        head_band
        + foot_band
        + n_rows * ch
        + len(groups) * group_band
        + (len(groups) - 1) * group_gap
    )
    fig_w = 13.4
    fig = plt.figure(figsize=(fig_w, fig_w * height / width), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(ox, height - 0.5, title, fontsize=18, color=INK, va="top", fontweight="bold")
    ax.text(ox, height - 1.0, subtitle, fontsize=9.8, color=MUTED, va="top")

    head_y = height - head_band
    gx = ox + left_pad + len(TASKS) * cw + right_pad / 2 - 0.1
    for j, (_key, label) in enumerate(TASKS):
        ax.text(
            ox + left_pad + j * cw + cw / 2,
            head_y + 0.28,
            label,
            ha="center",
            va="center",
            fontsize=9.6,
            color=INK,
            linespacing=1.15,
        )
    ax.text(gx, head_y + 0.28, "通过", ha="center", va="center", fontsize=11, color=INK)
    ax.plot([ox, width], [head_y - 0.12, head_y - 0.12], color=LINE, lw=1.1)

    y = head_y - 0.12
    for gi, (label, hue, present, rows) in enumerate(groups):
        y -= group_band * 0.55
        passed = sum(1 for (t, h), r in rows.items() if r["passed"])
        total = len(rows)
        ax.text(ox, y - 0.05, label, fontsize=12.5, color=hue, va="center", fontweight="bold")
        ax.text(
            ox + 1.62,
            y - 0.05,
            f"{passed}/{total} 通过 · {100 * passed / total:.0f}%",
            fontsize=10.5,
            color=MUTED,
            va="center",
        )
        y -= group_band * 0.45

        for harness in present:
            ax.text(
                ox + left_pad - 0.26,
                y - ch / 2,
                HARNESS_LABEL[harness],
                ha="right",
                va="center",
                fontsize=11.5,
                color=INK,
            )
            row_pass = 0
            for j, (task, _label) in enumerate(TASKS):
                row = rows.get((task, harness))
                x0 = ox + left_pad + j * cw + 0.05
                y0 = y - ch + 0.05
                w = cw - 0.10
                h = ch - 0.10
                cx, cy = x0 + w / 2, y0 + h / 2
                ok = bool(row and row["passed"])
                if ok:
                    row_pass += 1
                    ax.add_patch(
                        FancyBboxPatch(
                            (x0, y0),
                            w,
                            h,
                            boxstyle="round,pad=0,rounding_size=0.10",
                            linewidth=0.0,
                            facecolor=hue,
                            alpha=0.11,
                            zorder=1,
                        )
                    )
                    ax.add_patch(
                        FancyBboxPatch(
                            (x0, y0),
                            w,
                            h,
                            boxstyle="round,pad=0,rounding_size=0.10",
                            linewidth=0.9,
                            facecolor="none",
                            edgecolor=hue,
                            alpha=0.45,
                            zorder=2,
                        )
                    )
                    tick(ax, cx, cy + 0.10, 0.86, hue)
                    ax.text(
                        cx,
                        cy - 0.25,
                        f"{row['seconds']:.0f}s",
                        ha="center",
                        va="center",
                        fontsize=8.0,
                        color=MUTED,
                        zorder=5,
                    )
                else:
                    dash = (0, (2.2, 1.9)) if (row and row["timed_out"]) else "solid"
                    ax.add_patch(
                        FancyBboxPatch(
                            (x0, y0),
                            w,
                            h,
                            boxstyle="round,pad=0,rounding_size=0.10",
                            linewidth=0.9,
                            facecolor=PAPER,
                            edgecolor=LINE,
                            linestyle=dash,
                            zorder=2,
                        )
                    )
                    cross(ax, cx, cy + 0.10, 0.86, FAIL)
                    note = "超时" if (row and row["timed_out"]) else "错误"
                    ax.text(
                        cx,
                        cy - 0.25,
                        note,
                        ha="center",
                        va="center",
                        fontsize=8.0,
                        color=FAINT,
                        zorder=5,
                    )
            ax.text(
                gx,
                y - ch / 2,
                f"{row_pass}/{len(TASKS)}",
                ha="center",
                va="center",
                fontsize=11,
                color=INK if row_pass >= 8 else MUTED,
            )
            y -= ch
        if gi < len(groups) - 1:
            y -= group_gap

    ly = 0.66
    sw, shh = 0.36, 0.26
    items = [
        ("pass", 0.0, "通过（格子里是墙钟秒数）"),
        ("fail", 3.55, "未通过"),
        ("timeout", 5.50, "撞上 120 秒上限"),
    ]
    for kind, dx, text in items:
        lx = ox + dx
        dash = (0, (2.2, 1.9)) if kind == "timeout" else "solid"
        ax.add_patch(
            FancyBboxPatch(
                (lx, ly - shh / 2),
                sw,
                shh,
                boxstyle="round,pad=0,rounding_size=0.06",
                linewidth=0.9,
                facecolor=PAPER,
                edgecolor=LINE,
                linestyle=dash,
            )
        )
        if kind == "pass":
            ax.add_patch(
                FancyBboxPatch(
                    (lx, ly - shh / 2),
                    sw,
                    shh,
                    boxstyle="round,pad=0,rounding_size=0.06",
                    linewidth=0.9,
                    facecolor="#1D4ED8",
                    alpha=0.10,
                )
            )
            tick(ax, lx + sw / 2, ly + 0.015, 0.5, "#1D4ED8", lw=1.8)
        elif kind == "fail":
            cross(ax, lx + sw / 2, ly + 0.015, 0.5, FAIL, lw=1.6)
        ax.text(lx + sw + 0.15, ly - 0.005, text, fontsize=9.4, color=MUTED, va="center")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    print(f"saved {out_path} ({out_path.stat().st_size // 1024} KB)")


def scatter(out_path: pathlib.Path, tables: dict[str, dict], title: str, subtitle: str) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 6.2), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    points = []
    for key, label, hue in MODELS:
        rows = tables[key]
        for harness in HARNESS:
            got = [r for (t, h), r in rows.items() if h == harness]
            if not got:
                continue
            passed = [r for r in got if r["passed"]]
            avg = statistics.mean(r["seconds"] for r in passed) if passed else None
            points.append((label, hue, HARNESS_LABEL[harness], len(passed), len(got), avg))

    for label, hue, harness, ok, total, avg in points:
        if avg is None:
            ax.scatter(
                [0.4],
                [0],
                s=90,
                facecolors="white",
                edgecolors=LINE,
                linewidths=1.4,
                zorder=3,
            )
            ax.annotate(
                f"{harness} + {label.split('-')[0]}（0/{total}）",
                (0.4, 0),
                textcoords="offset points",
                xytext=(10, -2),
                fontsize=8.6,
                color=FAINT,
                va="center",
            )
            continue
        ax.scatter([avg], [ok], s=150, color=hue, alpha=0.9, zorder=4, edgecolors="white", linewidths=1.2)
        ax.annotate(
            f"{harness} + {label.split('-')[0]}",
            (avg, ok),
            textcoords="offset points",
            xytext=(9, 4),
            fontsize=9.0,
            color=INK,
        )

    ax.set_xlabel("通过项平均耗时（秒）", fontsize=10.5, color=MUTED)
    ax.set_ylabel("12 项中通过数", fontsize=10.5, color=MUTED)
    ax.set_ylim(-0.8, 12.8)
    ax.set_xlim(0, max([p[5] for p in points if p[5]] or [60]) * 1.25)
    ax.grid(axis="y", color=LINE, lw=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.set_title(title, loc="left", fontsize=15, color=INK, pad=26, fontweight="bold")
    ax.text(
        0.0,
        1.045,
        subtitle,
        transform=ax.transAxes,
        fontsize=9.2,
        color=MUTED,
        va="bottom",
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    print(f"saved {out_path} ({out_path.stat().st_size // 1024} KB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spark", type=pathlib.Path, required=True)
    parser.add_argument("--lfm3", type=pathlib.Path, required=True)
    parser.add_argument("--out-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()

    tables = {"spark": load(args.spark), "lfm3": load(args.lfm3)}
    grid(
        args.out_dir / "sota-matrix.png",
        tables,
        "十二项任务 · 四个智能体工具 · 两个 1.7B 模型",
        "每个组合独立目录、独立种子文件、120 秒墙钟上限；结果只看文件系统，不看模型自述。",
    )
    scatter(
        args.out_dir / "sota-score-speed.png",
        tables,
        "通过数 vs 通过项平均耗时",
        "左上更好：做得对，还做得快。空心点表示一项都没过。",
    )


if __name__ == "__main__":
    main()
