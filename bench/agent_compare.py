"""Compare coding agents (openlaoke / jcode / opencode) on the same tasks and model.

Fair-comparison rules:
- identical task prompt, seeded files, verifier, and isolated temp dir per (agent, task)
- identical model for every agent (default: halogen on llm.cycleuser.com)
- filesystem verification only (never trust self-reported success)
- hard wall-clock timeout per task

Usage:
    python bench/agent_compare.py --agents openlaoke,jcode,opencode --tasks all
    python bench/agent_compare.py --tasks edit,debug --timeout 300
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from bench.harness import TaskVerifier  # noqa: E402

HALOGEN_KEY = os.environ.get("OPENLAOKE_BENCH_API_KEY", "")
HALOGEN_URL = os.environ.get("OPENLAOKE_BENCH_BASE_URL", "https://llm.cycleuser.com/v1")
HALOGEN_MODEL = os.environ.get("OPENLAOKE_BENCH_MODEL", "halogen")

if not HALOGEN_KEY:
    raise SystemExit(
        "Set OPENLAOKE_BENCH_API_KEY (and optionally OPENLAOKE_BENCH_BASE_URL / "
        "OPENLAOKE_BENCH_MODEL) before running the comparison."
    )


@dataclass
class Task:
    id: str
    category: str
    prompt: str
    setup: dict[str, str] = field(default_factory=dict)
    verify: dict = field(default_factory=dict)


TASKS: list[Task] = [
    # --- file creation / generation ---
    Task(
        id="gen-fib",
        category="gen",
        prompt=(
            "Create answer.py with an iterative function fib(n) returning the nth Fibonacci "
            "number, then a __main__ block that prints fib(10)."
        ),
        verify={
            "file_exists": "answer.py",
            "executable": "python answer.py",
            "contains": "def fib",
        },
    ),
    Task(
        id="gen-fizzbuzz",
        category="gen",
        prompt=(
            "Create fizzbuzz.py that prints the numbers 1..15, replacing multiples of 3 with "
            "Fizz, multiples of 5 with Buzz, and multiples of both with FizzBuzz."
        ),
        verify={
            "file_exists": "fizzbuzz.py",
            "executable": "python fizzbuzz.py",
            "contains": "FizzBuzz",
        },
    ),
    # --- precise editing of an existing file ---
    Task(
        id="edit-bug",
        category="edit",
        setup={
            "calc.py": (
                "def add(a, b):\n    return a - b\n\n"
                "def mul(a, b):\n    return a * b\n\n"
                "if __name__ == '__main__':\n    print(add(2, 3))\n"
            )
        },
        prompt="The add function in calc.py has a bug. Fix it so add(2, 3) prints 5.",
        verify={
            "file_exists": "calc.py",
            "executable": "python calc.py",
            "contains": "return a + b",
        },
    ),
    Task(
        id="edit-rename",
        category="edit",
        setup={
            "app.py": (
                "def get_user():\n    return {'name': 'ann'}\n\n"
                "def show():\n    u = get_user()\n    print(u['name'])\n"
            )
        },
        prompt="In app.py rename get_user to fetch_user everywhere (definition and all call sites).",
        verify={
            "file_exists": "app.py",
            "executable": "python app.py",
            "contains": "def fetch_user",
        },
    ),
    Task(
        id="edit-config",
        category="edit",
        setup={"settings.json": '{\n  "debug": false,\n  "port": 8000\n}\n'},
        prompt=(
            'In settings.json set debug to true and add the field "timeout" with value 30. '
            "Keep it valid JSON."
        ),
        verify={
            "file_exists": "settings.json",
            "py_check": (
                "import json;d=json.load(open('settings.json'));"
                "assert d['debug'] is True and d['timeout']==30 and d['port']==8000"
            ),
        },
    ),
    # --- multi-file / cross-file reasoning ---
    Task(
        id="multi-module",
        category="multi",
        prompt=(
            "Create a small package: geometry.py with functions area_circle(r) and area_square(s), "
            "and main.py that imports geometry and prints area_circle(1) rounded to 2 decimals."
        ),
        verify={
            "file_exists": ["geometry.py", "main.py"],
            "executable": "python main.py",
        },
    ),
    Task(
        id="multi-refactor",
        category="multi",
        setup={
            "util.py": "def helper():\n    return 1\n",
            "a.py": "from util import helper\nprint(helper())\n",
            "b.py": "from util import helper\nprint(helper() + 1)\n",
        },
        prompt=(
            "Change helper() in util.py to return 10. Update a.py and b.py only if needed so both "
            "still run without error."
        ),
        verify={
            "file_exists": ["util.py", "a.py", "b.py"],
            "executable": "python a.py",
        },
    ),
    # --- debugging: must run code, read traceback, fix ---
    Task(
        id="debug-traceback",
        category="debug",
        setup={
            "broken.py": (
                "data = [1, 2, 3]\n\n"
                "def total(items):\n"
                "    s = 0\n"
                "    for i in range(len(items) + 1):\n"
                "        s += items[i]\n"
                "    return s\n\n"
                "if __name__ == '__main__':\n"
                "    print(total(data))\n"
            )
        },
        prompt="broken.py crashes with an IndexError. Run it, find the cause, and fix it so it prints 6.",
        verify={"executable": "python broken.py", "contains": "def total"},
    ),
    Task(
        id="debug-import",
        category="debug",
        setup={
            "mymod.py": "def value():\n    return 42\n",
            "runner.py": "import mymod\nprint(mymod.values())\n",
        },
        prompt="runner.py fails because of a wrong function name. Fix runner.py so it prints 42.",
        verify={"executable": "python runner.py", "contains": "value()"},
    ),
    # --- constraint adherence ---
    Task(
        id="constraint-no-libs",
        category="constraint",
        prompt=(
            "Create stats.py implementing mean(nums) and median(nums) using only the Python "
            "standard library (no numpy). Include a __main__ block that prints mean([1,2,3]) "
            "and median([1,2,3,4])."
        ),
        verify={
            "file_exists": "stats.py",
            "executable": "python stats.py",
            "not_contains": "stats.py:numpy",
        },
    ),
    Task(
        id="constraint-exact",
        category="constraint",
        prompt=(
            "Create the file greeting.txt containing exactly one line: Hello, OpenLaoKe! "
            "(no extra text, no trailing blank lines)."
        ),
        verify={"file_exists": "greeting.txt", "contains": "Hello, OpenLaoKe!"},
    ),
    Task(
        id="constraint-structure",
        category="constraint",
        setup={"notes.md": "# Notes\n\nfirst\n"},
        prompt=(
            "Append a new section to notes.md titled '## Todo' followed by a single bullet "
            "'- ship it'. Do not remove existing content."
        ),
        verify={"contains": "notes.md:## Todo", "contains2": "notes.md:- ship it"},
    ),
]


def _verifier_extra(task: Task, work_dir: str) -> tuple[bool, str]:
    checks: list[str] = []
    v = task.verify
    if "py_check" in v:
        import subprocess as _sp

        proc = _sp.run(
            [sys.executable, "-c", v["py_check"]],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=20,
        )
        ok = proc.returncode == 0
        checks.append(f"py_check={'ok' if ok else 'FAILED: ' + (proc.stderr or '')[-200:]}")
        if not ok:
            return False, "; ".join(checks)
    if "contains2" in v:
        spec = v["contains2"]
        fn, text = spec.split(":", 1)
        p = os.path.join(work_dir, fn)
        ok = False
        if os.path.exists(p):
            with open(p) as fh:
                ok = text in fh.read()
        checks.append(f"contains2:{text}={'ok' if ok else 'MISSING'}")
        if not ok:
            return False, "; ".join(checks)
    return True, "; ".join(checks)


INFRA_MARKERS = (
    "API Error",
    "Just a moment",
    "<!DOCTYPE html",
    "Connection error",
    "ReadTimeout",
    "ConnectTimeout",
    "502 Bad Gateway",
    "503 Service",
    "429 Too Many",
)


def _is_infra_failure(result: dict) -> bool:
    if result["exit_code"] == 124:
        return True
    if result["passed"]:
        return False
    blob = result.get("stdout_tail", "") + " " + result.get("error", "")
    return any(marker in blob for marker in INFRA_MARKERS)


def run_task(agent: str, task: Task, timeout: float, max_attempts: int = 2) -> dict:
    for attempt in range(1, max_attempts + 1):
        result = _run_task_once(agent, task, timeout)
        result["attempts"] = attempt
        if result["passed"] or attempt == max_attempts or not _is_infra_failure(result):
            return result
        time.sleep(3)
    return result


def _run_task_once(agent: str, task: Task, timeout: float) -> dict:
    work = tempfile.mkdtemp(prefix=f"cmp_{agent}_{task.id}_")
    for rel, content in task.setup.items():
        p = os.path.join(work, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(rel) else None
        Path(p).write_text(content)

    cmd = build_cmd(agent, task.prompt, work)
    env = {
        **os.environ,
        "NO_COLOR": "1",
        "TERM": "dumb",
        "PWD": work,
        "OLDPWD": work,
        "OPENLAOKE_STATS": "1",
    }
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=work, capture_output=True, text=True, timeout=timeout, env=env
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or "") + (exc.stderr or "")) if isinstance(exc.stdout, str) else ""
        code = 124
    duration = (time.monotonic() - start) * 1000

    tdict = {"id": task.id, "verify": task.verify, "setup": {}}
    ok, score, err = TaskVerifier().verify(tdict, work)
    extra_ok, extra_err = _verifier_extra(task, work)
    if not extra_ok:
        ok, score = False, min(score, 0.5)
        err = (err + "; " + extra_err).strip("; ")

    files = sorted(os.listdir(work))
    shutil.rmtree(work, ignore_errors=True)
    return {
        "task": task.id,
        "category": task.category,
        "agent": agent,
        "passed": ok and code == 0,
        "score": score,
        "duration_ms": round(duration),
        "exit_code": code,
        "error": err,
        "files": files,
        "stdout_tail": out[-1500:],
    }


def build_cmd(agent: str, prompt: str, work: str) -> list[str]:
    if agent == "openlaoke":
        exe = sys.executable
        return [
            exe,
            "-m",
            "openlaoke",
            "-c",
            work,
            "-m",
            HALOGEN_MODEL,
            "--provider",
            "openai_compatible",
            "--base-url",
            HALOGEN_URL,
            "--api-key",
            HALOGEN_KEY,
            "-p",
            "bypass",
            prompt,
        ]
    if agent == "jcode":
        return ["jcode", "run", prompt]
    if agent == "opencode":
        return [
            "opencode",
            "run",
            "--standalone",
            "--model",
            f"cycleuser/{HALOGEN_MODEL}",
            "--auto",
            prompt,
        ]
    raise ValueError(agent)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default="openlaoke,jcode,opencode")
    ap.add_argument("--tasks", default="all", help="comma list of categories or task ids, or 'all'")
    ap.add_argument("--timeout", type=float, default=240)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    selected = TASKS
    if args.tasks != "all":
        wanted = {t.strip() for t in args.tasks.split(",")}
        selected = [t for t in TASKS if t.id in wanted or t.category in wanted]

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        for task in selected:
            futures = {agent: pool.submit(run_task, agent, task, args.timeout) for agent in agents}
            for agent in agents:
                r = futures[agent].result()
                results.append(r)
                flag = "PASS" if r["passed"] else "FAIL"
                print(f"[{task.id:20s}] {agent:10s} {flag} {r['duration_ms']:>7}ms")
            print("-" * 60)

    # summary
    print("\n=== SUMMARY ===")
    summary = {}
    for agent in agents:
        rs = [r for r in results if r["agent"] == agent]
        passed = sum(1 for r in rs if r["passed"])
        avg = sum(r["duration_ms"] for r in rs) / max(1, len(rs))
        score = sum(r["score"] for r in rs) / max(1, len(rs))
        summary[agent] = {
            "passed": passed,
            "total": len(rs),
            "score": round(score, 3),
            "avg_ms": round(avg),
        }
        print(f"{agent:10s} {passed}/{len(rs)}  score={score:.3f}  avg={avg:.0f}ms")

    print("\n=== per-task matrix ===")
    header = f"{'task':20s} " + " ".join(f"{a:>10s}" for a in agents)
    print(header)
    for task in selected:
        cells = []
        for agent in agents:
            r = next(x for x in results if x["task"] == task.id and x["agent"] == agent)
            cells.append(f"{'PASS' if r['passed'] else 'fail':>10s}")
        print(f"{task.id:20s} " + " ".join(cells))

    out = args.out or str(_ROOT / "bench" / "results" / f"agent_compare_{int(time.time())}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"model": HALOGEN_MODEL, "summary": summary, "results": results}, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
