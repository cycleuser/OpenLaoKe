"""Concrete local-task benchmark for small models, through OpenLaoKe and pi.

5 tasks x 2 models x 2 harnesses x {zh, en}. Each run gets its own directory
under ~/Downloads/openlaoke-pi-small-models/, keeps the harness output in
run.log, and leaves any generated artifacts in place for manual inspection.

Usage:
    python /tmp/bench_concrete_tasks.py
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = "/Users/fred/Documents/GitHub/cycleuser/OpenLaoKe"
DEV = sys.executable  # run with the conda dev environment
BASE_URL = "http://127.0.0.1:11434/v1"
OUT_ROOT = Path.home() / "Downloads" / "pi-small-model-tasks"
RESULTS = OUT_ROOT / "results.jsonl"

MODELS = ["qwen3.5:2b", "LiquidAI-dev/lfm2.5-2.6b:latest"]
LANGS = ["zh", "en"]
HARNESSES = ["openlaoke", "pi"]

BUGGY = "def average(nums):\n    return sum(nums) / len(nums) + 1\n\nprint(average([2, 4, 6]))\n"
DATA = "3\n14\n15\n92\n65\n35\n"

PROMPTS = {
    "T1_write_exact": {
        "zh": "在当前目录创建文件 hello.txt，内容正好是：hello small model",
        "en": "Create a file hello.txt in the current directory containing exactly: hello small model",
    },
    "T2_read_sum": {
        "zh": "读取当前目录的 data.txt（每行一个整数），计算所有数字之和，并把结果告诉我。",
        "en": "Read data.txt in the current directory (one integer per line), compute the sum of all numbers, and tell me the result.",
    },
    "T3_fib_run": {
        "zh": "在当前目录写一个 fib.py，打印前 10 个斐波那契数（从 0 和 1 开始），然后用 python3 运行它，把输出告诉我。",
        "en": "Write fib.py in the current directory that prints the first 10 Fibonacci numbers (starting 0 and 1), then run it with python3 and tell me the output.",
    },
    "T4_report_md": {
        "zh": "在当前目录写一个 report.md：标题为「本地小模型」，下面用三条要点列出本地小模型的三个优点。",
        "en": "Write report.md in the current directory: title 'Local Small Models', then list three advantages of local small models as three bullet points.",
    },
    "T5_fix_bug": {
        "zh": "当前目录的 buggy.py 计算平均值的结果不对，请找出并修复 bug，然后运行 python3 buggy.py 把输出告诉我。",
        "en": "The average computed by buggy.py in the current directory is wrong. Find and fix the bug, then run python3 buggy.py and tell me the output.",
    },
}

INPUTS = {"T2_read_sum": {"data.txt": DATA}, "T5_fix_bug": {"buggy.py": BUGGY}}


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def run_one(harness: str, model: str, lang: str, task: str) -> dict:
    work = OUT_ROOT / harness / slug(model) / lang / task
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for name, content in INPUTS.get(task, {}).items():
        (work / name).write_text(content, encoding="utf-8")

    prompt = PROMPTS[task][lang]
    if harness == "openlaoke":
        cmd = [DEV, "-m", "openlaoke", "--provider", "openai_compatible", "--base-url", BASE_URL,
               "--api-key", "not-needed", "--model", model, "--max-tokens", "2000", "--yes",
               "--cwd", str(work), prompt]
        cwd = REPO
    else:
        cmd = ["pi", "-p", "--provider", "ollama-local", "--model", model,
               "--no-skills", "--no-context-files", "--no-extensions",
               "--no-prompt-templates", "--no-themes", prompt]
        cwd = str(work)
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600, check=False)
        out, err = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        out, err = "", "TIMEOUT"
    elapsed = round(time.time() - start, 1)
    (work / "run.log").write_text(f"$ {' '.join(cmd)}\n\n--- stdout ---\n{out}\n--- stderr ---\n{err}\n", encoding="utf-8")

    return {
        "harness": harness, "model": model, "lang": lang, "task": task,
        "seconds": elapsed, "workdir": str(work), "stdout": out[:4000],
        "artifacts": sorted(p.name for p in work.iterdir() if p.name != "run.log"),
    }


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text("", encoding="utf-8")
    total = len(HARNESSES) * len(MODELS) * len(LANGS) * len(PROMPTS)
    n = 0
    for harness in HARNESSES:
        for model in MODELS:
            for lang in LANGS:
                for task in PROMPTS:
                    n += 1
                    r = run_one(harness, model, lang, task)
                    with RESULTS.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                    print(f"[{n}/{total}] {harness:9} {model:32} {lang} {task:16} "
                          f"{r['seconds']:6.1f}s  artifacts={r['artifacts']}", flush=True)
    print(f"\nDone. Artifacts under {OUT_ROOT}")


if __name__ == "__main__":
    main()
