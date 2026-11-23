#!/usr/bin/env python
"""Draw the 4-harness x 2-model agent matrix as one publication-quality figure.

Data comes straight from the merged result files in bench/results/, so the picture
cannot drift away from the numbers in the article.

Usage:
    /Users/fred/miniconda3/envs/dev/bin/python bench/make_matrix_chart.py \
        --out ../blog/微信公众号草稿/images/agent-matrix-17b.png
"""

from __future__ import annotations

import argparse
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = [
    (HERE / "results/final-spark-17b-q4.json", "Spark-1.7B", "#C2410C"),
    (HERE / "results/final-lfm3-17b-q4.json", "LFM3-1.7B", "#1D4ED8"),
]

TASKS = ["fib", "merge", "docx", "xlsx", "ip", "weather", "download"]
HARNESS_ORDER = ["jcode", "openlaoke", "pi", "opencode"]
HARNESS_LABEL = {"jcode": "Jcode", "openlaoke": "OpenLaoKe", "pi": "pi", "opencode": "OpenCode"}

INK = "#111827"
MUTED = "#6B7280"
FAINT = "#9CA3AF"
LINE = "#E5E7EB"
FAIL = "#DC2626"
PAPER = "#FCFCFD"

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False


def load():
    table = {}
    totals = {}
    for path, label, _hue in RESULTS:
        data = json.loads(path.read_text())
        cells = {}
        for rec in data["results"]:
            cells[(rec["harness"], rec["task"])] = (
                rec["passed"],
                rec["seconds"],
                rec["timed_out"],
            )
        table[label] = cells
        totals[label] = (data["summary"]["pass"], data["summary"]["total"])
    return table, totals


def tick(ax, cx, cy, s, color, lw=2.4):
    ax.plot([cx - 0.20 * s, cx - 0.05 * s, cx + 0.22 * s],
            [cy + 0.00 * s, cy - 0.16 * s, cy + 0.20 * s],
            color=color, lw=lw, solid_capstyle="round", solid_joinstyle="round", zorder=5)


def cross(ax, cx, cy, s, color, lw=2.0):
    for dx in (1, -1):
        ax.plot([cx - 0.13 * s * dx, cx + 0.13 * s * dx],
                [cy - 0.13 * s, cy + 0.13 * s],
                color=color, lw=lw, solid_capstyle="round", zorder=5)


def draw(out_path: pathlib.Path, title: str, subtitle: str) -> None:
    table, totals = load()

    groups = []
    for _path, label, hue in RESULTS:
        cells = table[label]
        present = [h for h in HARNESS_ORDER if any(k[0] == h for k in cells)]
        present.sort(key=lambda h: (-sum(1 for t in TASKS if cells.get((h, t), (False,))[0]),
                                    HARNESS_ORDER.index(h)))
        groups.append((label, hue, present, cells))

    cw, ch = 1.0, 0.92
    ox = 0.45                    # left margin inside the canvas
    left_pad = 2.25
    right_pad = 1.25
    head_band = 2.05
    group_band = 0.66
    group_gap = 0.34
    foot_band = 1.3

    n_rows = sum(len(g[2]) for g in groups)
    width = ox + left_pad + len(TASKS) * cw + right_pad
    height = (head_band + foot_band + n_rows * ch
              + len(groups) * group_band + (len(groups) - 1) * group_gap)

    fig_w = 12.4
    fig = plt.figure(figsize=(fig_w, fig_w * height / width), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # ---- title block (top) ----
    ax.text(ox, height - 0.5, title, fontsize=18, color=INK, va="top", fontweight="bold")
    ax.text(ox, height - 1.0, subtitle, fontsize=9.8, color=MUTED, va="top")

    # ---- column headers ----
    head_y = height - head_band
    gx = left_pad + len(TASKS) * cw + right_pad / 2 - 0.1 + ox
    for j, task in enumerate(TASKS):
        ax.text(ox + left_pad + j * cw + cw / 2, head_y + 0.28, task,
                ha="center", va="center", fontsize=11.5, color=INK)
    ax.text(gx, head_y + 0.28, "通过", ha="center", va="center", fontsize=11.5, color=INK)
    ax.plot([ox, width], [head_y - 0.12, head_y - 0.12], color=LINE, lw=1.1)

    # ---- rows ----
    y = head_y - 0.14
    for gi, (label, hue, present, cells) in enumerate(groups):
        # group header
        y -= group_band * 0.55
        passed, total = totals[label]
        ax.text(ox, y - 0.05, label, fontsize=12.5, color=hue, va="center", fontweight="bold")
        ax.text(ox + 1.62, y - 0.05,
                f"{passed}/{total} 通过 · {100 * passed / total:.0f}%",
                fontsize=10.5, color=MUTED, va="center")
        y -= group_band * 0.45

        for harness in present:
            ax.text(ox + left_pad - 0.28, y - ch / 2, HARNESS_LABEL[harness],
                    ha="right", va="center", fontsize=12, color=INK)
            row_pass = 0
            for j, task in enumerate(TASKS):
                ok, secs, timed_out = cells.get((harness, task), (False, 0.0, False))
                row_pass += bool(ok)
                x0 = ox + left_pad + j * cw + 0.05
                y0 = y - ch + 0.05
                w = cw - 0.10
                h = ch - 0.10
                cx, cy = x0 + w / 2, y0 + h / 2
                if ok:
                    ax.add_patch(FancyBboxPatch(
                        (x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10",
                        linewidth=0.0, facecolor=hue, alpha=0.10, zorder=1))
                    ax.add_patch(FancyBboxPatch(
                        (x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10",
                        linewidth=0.9, facecolor="none", edgecolor=hue, alpha=0.45, zorder=2))
                    tick(ax, cx, cy + 0.12, 0.9, hue, lw=2.1)
                    ax.text(cx, cy - 0.24, f"{secs:.0f}s", ha="center", va="center",
                            fontsize=8.6, color=MUTED, zorder=5)
                else:
                    ax.add_patch(FancyBboxPatch(
                        (x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10",
                        linewidth=0.9, facecolor=PAPER, edgecolor=LINE,
                        linestyle=(0, (2.2, 1.9)) if timed_out else "solid", zorder=2))
                    cross(ax, cx, cy + 0.12, 0.9, FAIL, lw=1.9)
                    ax.text(cx, cy - 0.24, "超时" if timed_out else f"{secs:.0f}s",
                            ha="center", va="center", fontsize=8.6, color=FAINT, zorder=5)
            ax.text(gx, y - ch / 2,
                    f"{row_pass}/7", ha="center", va="center", fontsize=12,
                    color=INK if row_pass >= 6 else MUTED)
            y -= ch
        if gi < len(groups) - 1:
            y -= group_gap

    # ---- footer legend ----
    ly = 0.72
    sw, shh = 0.36, 0.26
    items = [
        ("pass", 0.0, "通过（格子里的数字是耗时）"),
        ("fail", 3.45, "未通过"),
        ("timeout", 5.35, "撞上 150 秒上限"),
    ]
    for kind, dx, text in items:
        lx = ox + dx
        dash = (0, (2.2, 1.9)) if kind == "timeout" else "solid"
        ax.add_patch(FancyBboxPatch((lx, ly - shh / 2), sw, shh,
                                    boxstyle="round,pad=0,rounding_size=0.06",
                                    linewidth=0.9, facecolor=PAPER, edgecolor=LINE,
                                    linestyle=dash))
        if kind == "pass":
            ax.add_patch(FancyBboxPatch((lx, ly - shh / 2), sw, shh,
                                        boxstyle="round,pad=0,rounding_size=0.06",
                                        linewidth=0.9, facecolor="#1D4ED8", alpha=0.10))
            ax.add_patch(FancyBboxPatch((lx, ly - shh / 2), sw, shh,
                                        boxstyle="round,pad=0,rounding_size=0.06",
                                        linewidth=0.9, facecolor="none", edgecolor="#1D4ED8",
                                        alpha=0.45))
            tick(ax, lx + sw / 2, ly + 0.015, 0.52, "#1D4ED8", lw=1.8)
        elif kind == "fail":
            cross(ax, lx + sw / 2, ly + 0.015, 0.52, FAIL, lw=1.6)
        ax.text(lx + sw + 0.16, ly - 0.005, text, fontsize=9.6, color=MUTED, va="center")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    print(f"saved {out_path} ({out_path.stat().st_size // 1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "agent_matrix_17b.png"))
    ap.add_argument("--title", default="四个智能体工具 × 两个 1.7B 模型：七项任务")
    ap.add_argument("--subtitle", default=(
        "同一提示词、独立目录、150 秒墙钟上限，结果只认文件内容，不认模型自述。"
    ))
    args = ap.parse_args()
    draw(pathlib.Path(args.out).expanduser(), args.title, args.subtitle)


if __name__ == "__main__":
    main()
