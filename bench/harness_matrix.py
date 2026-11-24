#!/usr/bin/env python
"""Run the same coding task through OpenLaoKe, pi, Jcode, and OpenCode.

The point is a fair-ish harness comparison on one local model: each harness gets
the same prompt in a fresh directory, the same wall-clock budget, and the result
is judged by executing the file it was asked to create. Nothing is taken from
the agent's own claim of success.

Usage:
    python bench/harness_matrix.py --model lfm3-gguf --thinking on --task fib
    python bench/harness_matrix.py --model qwen-mlx --thinking off --harness pi jcode
    python bench/harness_matrix.py --model lfm3-gguf --task all --json result.json

Thinking mode is mostly server-side for local models. The flag is recorded in
the result and forwarded where the harness has a real knob (pi, OpenLaoKe).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Any

DEV_PYTHON = "/Users/fred/miniconda3/envs/dev/bin/python"
SCRATCH = pathlib.Path.home() / ".jcode" / "scratch"


@dataclass(frozen=True)
class Task:
    key: str
    prompt: str
    filename: str
    expected: str
    verifier: str = "output"  # "output" or a key in CUSTOM_VERIFIERS


import re

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")


def _looks_like_ip(text: str) -> bool:
    return bool(_IPV4.search(text) or _IPV6.search(text))


def _read_docx(path):
    import docx

    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _read_xlsx(path):
    import openpyxl

    wb = openpyxl.load_workbook(str(path))
    parts = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            parts.append(" ".join("" if c is None else str(c) for c in row))
    return "\n".join(parts)


def _v_file_only(cwd, task):
    target = cwd / task.filename
    if not target.exists() or target.stat().st_size == 0:
        return False, target.exists(), ""
    text = target.read_text(errors="replace")
    return task.expected.lower() in text.lower(), True, text[-200:]


def _v_docx(cwd, task):
    target = cwd / task.filename
    if not target.exists():
        return False, False, ""
    try:
        text = _read_docx(target)
    except Exception as exc:
        return False, True, f"docx read error: {exc}"
    return task.expected.lower() in text.lower(), True, text[-200:]


def _v_xlsx(cwd, task):
    target = cwd / task.filename
    if not target.exists():
        return False, False, ""
    try:
        text = _read_xlsx(target)
    except Exception as exc:
        return False, True, f"xlsx read error: {exc}"
    return task.expected.lower() in text.lower(), True, text[-200:]


def _v_ipv4(cwd, task):
    target = cwd / task.filename
    if not target.exists():
        return False, False, ""
    try:
        proc = subprocess.run(
            [DEV_PYTHON, str(target)], cwd=cwd, capture_output=True, text=True, timeout=40
        )
    except subprocess.TimeoutExpired:
        return False, True, "<run timed out>"
    out = (proc.stdout + proc.stderr).strip()
    return _looks_like_ip(out), True, out[-200:]


def _v_temp(cwd, task):
    target = cwd / task.filename
    if not target.exists():
        return False, False, ""
    try:
        proc = subprocess.run(
            [DEV_PYTHON, str(target)], cwd=cwd, capture_output=True, text=True, timeout=40
        )
    except subprocess.TimeoutExpired:
        return False, True, "<run timed out>"
    out = (proc.stdout + proc.stderr).strip()
    return bool(re.search(r"\d+\s*°", out)) or bool(re.search(r"\d+\s*C", out, re.I)), True, out[-200:]


CUSTOM_VERIFIERS = {
    "docx": _v_docx,
    "xlsx": _v_xlsx,
    "ipv4": _v_ipv4,
    "temp": _v_temp,
    "file": _v_file_only,
}


TASKS: dict[str, Task] = {
    "fib": Task(
        key="fib",
        prompt=(
            "Create answer.py with an iterative fib(n) and a __main__ block that prints fib(10). "
            "Run it to verify."
        ),
        filename="answer.py",
        expected="55",
    ),
    "merge": Task(
        key="merge",
        prompt=(
            "Create merge_sort.py implementing merge sort and a __main__ block that sorts "
            "[5, 3, 1, 4, 2] and prints the result. Run it to verify."
        ),
        filename="merge_sort.py",
        expected="[1, 2, 3, 4, 5]",
    ),
    "docx": Task(
        key="docx",
        prompt=(
            "Use python-docx to create report.docx containing a heading 'Monthly Report' and a "
            "paragraph that says exactly: Revenue grew by 20 percent. Run a short script to "
            "verify the file opens."
        ),
        filename="report.docx",
        expected="Revenue grew by 20 percent",
        verifier="docx",
    ),
    "xlsx": Task(
        key="xlsx",
        prompt=(
            "Use openpyxl to create budget.xlsx with a header row Name and Cost, and one data "
            "row: Server and 120. Run a short script to verify the file opens and contains 120."
        ),
        filename="budget.xlsx",
        expected="120",
        verifier="xlsx",
    ),
    "ip": Task(
        key="ip",
        prompt=(
            "Create ip.py that uses urllib (no proxy) to fetch https://icanhazip.com and prints "
            "the public IP address it returns. Run it to verify."
        ),
        filename="ip.py",
        expected="",
        verifier="ipv4",
    ),
    "weather": Task(
        key="weather",
        prompt=(
            "Create weather.py that fetches the current temperature for Beijing from "
            "https://wttr.in/Beijing?format=3 (using urllib, no proxy) and prints the result. "
            "It must include a number with a degree sign or C. Run it to verify."
        ),
        filename="weather.py",
        expected="",
        verifier="temp",
    ),
    "download": Task(
        key="download",
        prompt=(
            "Create a file named page.html by downloading https://example.com (using curl or "
            "urllib, no proxy). The file must contain the words Example Domain. Verify the file "
            "exists and is non-empty."
        ),
        filename="page.html",
        expected="Example Domain",
        verifier="file",
    ),
}

MODELS: dict[str, dict[str, str]] = {
    # Q4 GGUF only. No Q8, no MLX. llama.cpp serves all of these.
    "lfm3-1.7b-q4": {
        "ol_provider": "lfm3_1_7b_q4_gguf",
        "ol_model": "lfm3-1.7b-q4",
        "pi": "lfm3-gguf-q4",
        "pi_model": "lfm3-1.7b-q4",
        "jcode": "lfm3-gguf-q4",
        "jcode_model": "lfm3-1.7b-q4",
        "opencode": "lfm3-gguf-q4/lfm3-1.7b-q4",
    },
    "lfm3-omni-2b-q4": {
        "ol_provider": "lfm3_omni_q4_gguf",
        "ol_model": "lfm3-omni-q4",
        "pi": "lfm3-omni-q4",
        "pi_model": "lfm3-omni-q4",
        "jcode": "lfm3-omni-q4",
        "jcode_model": "lfm3-omni-q4",
        "opencode": "lfm3-omni-q4/lfm3-omni-q4",
    },
    "spark-4b-q4": {
        "ol_provider": "spark_q4_gguf",
        "ol_model": "spark-q4",
        "pi": "spark-q4",
        "pi_model": "spark-q4",
        "jcode": "spark-q4",
        "jcode_model": "spark-q4",
        "opencode": "spark-q4/spark-q4",
    },
    "spark-1.7b-q4": {
        "ol_provider": "spark_1_7b_q4_gguf",
        "ol_model": "spark-1.7b-q4",
        "pi": "spark-1.7b-q4",
        "pi_model": "spark-1.7b-q4",
        "jcode": "spark-17b-q4",
        "jcode_model": "spark-1.7b-q4",
        "opencode": "spark-1.7b-q4/spark-1.7b-q4",
    },
    "spark-2.6-1.7b-q4": {
        "ol_provider": "spark_2_6_1_7b_q4_gguf",
        "ol_model": "spark-2.6-1.7b-q4",
        "pi": "spark-2.6-1.7b-q4",
        "pi_model": "spark-2.6-1.7b-q4",
        "jcode": "spark-26-17b-q4",
        "jcode_model": "spark-2.6-1.7b-q4",
        "opencode": "spark-2.6-1.7b-q4/spark-2.6-1.7b-q4",
    },
}


@dataclass
class RunResult:
    harness: str
    model: str
    thinking: str
    task: str
    passed: bool = False
    timed_out: bool = False
    exit_code: int | None = None
    seconds: float = 0.0
    artifact_seconds: float | None = None
    file_created: bool = False
    output: str = ""
    log_path: str = ""
    log_tail: str = ""
    error: str = ""


@dataclass
class Matrix:
    model: str
    thinking: str
    timeout: float
    max_steps: int
    started: str = ""
    results: list[RunResult] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, Any]:
        by_task: dict[str, dict[str, Any]] = {}
        for task in TASKS:
            rows = [r for r in self.results if r.task == task]
            if not rows:
                continue
            by_task[task] = {
                "pass": sum(1 for r in rows if r.passed),
                "total": len(rows),
                "fastest_pass": min((r.seconds for r in rows if r.passed), default=None),
            }
        return {
            "model": self.model,
            "thinking": self.thinking,
            "pass": sum(1 for r in self.results if r.passed),
            "total": len(self.results),
            "by_task": by_task,
        }


def build_command(
    harness: str, model_key: str, task: Task, thinking: str, max_steps: int, cwd: str
) -> list[str]:
    m = MODELS[model_key]
    if harness == "openlaoke":
        effort = "high" if thinking == "on" else "low"
        return [
            DEV_PYTHON,
            "-m",
            "openlaoke",
            "--provider",
            m["ol_provider"],
            "--model",
            m["ol_model"],
            "--local",
            "-p",
            "bypass",
            "--max-tokens",
            "4096",
            "--max-steps",
            str(max_steps),
            "--reasoning-effort",
            effort,
            "-c",
            cwd,
            task.prompt,
        ]
    if harness == "pi":
        cmd = [
            "pi",
            "--print",
            "--no-session",
            "--provider",
            m["pi"],
            "--model",
            m["pi_model"],
            "--thinking",
            "high" if thinking == "on" else "off",
            task.prompt,
        ]
        return cmd
    if harness == "jcode":
        return [
            "jcode",
            "--provider-profile",
            m["jcode"],
            "--model",
            m["jcode_model"],
            "run",
            task.prompt,
        ]
    if harness == "opencode":
        return [
            "opencode",
            "run",
            "--standalone",
            "--model",
            m["opencode"],
            "--auto",
            task.prompt,
        ]
    raise ValueError(f"unknown harness: {harness}")


def verify(cwd: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    if task.verifier != "output":
        return CUSTOM_VERIFIERS[task.verifier](cwd, task)
    target = cwd / task.filename
    if not target.exists():
        return False, False, ""
    try:
        proc = subprocess.run(
            [DEV_PYTHON, str(target)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return False, True, "<verification timed out>"
    output = (proc.stdout + proc.stderr).strip()
    return task.expected in output, True, output[-800:]


def run_one(
    harness: str,
    model_key: str,
    task: Task,
    thinking: str,
    timeout: float,
    max_steps: int,
) -> RunResult:
    run_dir = pathlib.Path(tempfile.mkdtemp(prefix=f"matrix_{model_key}_{harness}_", dir=SCRATCH))
    log_path = run_dir / "run.log"
    cmd = build_command(harness, model_key, task, thinking, max_steps, str(run_dir))
    env = dict(os.environ)
    env.setdefault("LOCAL_LLM_KEY", "local")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["PWD"] = str(run_dir)
    env.pop("OLDPWD", None)
    # local probes need direct network (proxy would break ip/weather/download tasks)
    for pk in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy",
               "https_proxy", "all_proxy"):
        env.pop(pk, None)
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"

    started = time.time()
    timed_out = False
    exit_code: int | None = None
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=run_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    seconds = time.time() - started

    ok, created, output = verify(run_dir, task)
    artifact = run_dir / task.filename
    artifact_seconds = round(artifact.stat().st_mtime - started, 1) if artifact.exists() else None
    log_tail = log_path.read_text(errors="replace")[-1200:]
    return RunResult(
        harness=harness,
        model=model_key,
        thinking=thinking,
        task=task.key,
        passed=bool(ok and not timed_out),
        timed_out=timed_out,
        exit_code=exit_code,
        seconds=round(seconds, 1),
        artifact_seconds=artifact_seconds,
        file_created=created,
        output=output,
        log_path=str(run_dir),
        log_tail=log_tail,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="lfm3-gguf", choices=sorted(MODELS))
    parser.add_argument("--thinking", default="off", choices=["on", "off"])
    parser.add_argument("--task", default="fib", choices=[*TASKS, "all"])
    parser.add_argument(
        "--harness",
        nargs="+",
        default=["openlaoke", "pi", "jcode", "opencode"],
        choices=["openlaoke", "pi", "jcode", "opencode"],
    )
    parser.add_argument("--timeout", type=float, default=180.0, help="Seconds per run")
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    parser.add_argument("--keep", action="store_true", help="Keep run directories")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tasks = list(TASKS.values()) if args.task == "all" else [TASKS[args.task]]
    matrix = Matrix(
        model=args.model,
        thinking=args.thinking,
        timeout=args.timeout,
        max_steps=args.max_steps,
        started=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    for task in tasks:
        for harness in args.harness:
            print(
                f"== {harness} / {args.model} / thinking={args.thinking} / {task.key}", flush=True
            )
            result = run_one(
                harness,
                args.model,
                task,
                args.thinking,
                args.timeout,
                args.max_steps,
            )
            matrix.results.append(result)
            print(
                f"   pass={result.passed} timeout={result.timed_out} "
                f"exit={result.exit_code} sec={result.seconds} "
                f"artifact={result.artifact_seconds} file={result.file_created} out={result.output!r}",
                flush=True,
            )

    payload = {**asdict(matrix), "summary": matrix.summary}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n")
        print(f"\nwrote {args.json}", flush=True)
    print("\n" + json.dumps(matrix.summary, ensure_ascii=False), flush=True)

    if not args.keep:
        for result in matrix.results:
            shutil.rmtree(result.log_path, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
