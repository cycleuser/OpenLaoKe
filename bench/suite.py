#!/usr/bin/env python
"""Shared runner for the task suites.

``sota_matrix.py`` (coding tasks) and ``daily_matrix.py`` (everyday chores) judge
the same way: an isolated directory, a seeded starting state, one prompt, one
wall-clock budget, and a verifier that reads the filesystem afterwards. This
module holds that machinery once, plus the self-test that proves a verifier
accepts a reference solution and rejects an empty directory.

A suite is just a mapping of key to :class:`Task` and a mapping of verifier name
to callable, so adding tasks never means touching the runner.
"""

from __future__ import annotations

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
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from harness_matrix import DEV_PYTHON, MODELS, SCRATCH, build_command  # noqa: E402

LOG_ROOT = pathlib.Path.home() / ".jcode" / "sota_logs"

Verdict = tuple[bool, bool, str]


@dataclass(frozen=True)
class Task:
    key: str
    prompt: str
    verifier: str
    seed: Callable[[pathlib.Path], None] | None = None
    reference: Callable[[pathlib.Path], None] | None = None
    note: str = ""
    label: str = ""

    @property
    def title(self) -> str:
        return self.label or self.key


@dataclass
class Result:
    harness: str
    model: str
    task: str
    passed: bool
    verified: bool
    timed_out: bool
    exit_code: int | None
    seconds: float
    detail: str
    log_path: str = ""
    log_tail: str = ""
    rep: int = 0


def prepare(task: Task) -> pathlib.Path:
    """One run gets a private parent holding nothing but its own work dir.

    Flat directories let a later agent grep out of its workspace and read the
    file a previous run wrote; jcode did exactly that once and "solved" a task by
    copying a sibling's answer.
    """
    base = pathlib.Path(tempfile.mkdtemp(prefix="suite_run_", dir=SCRATCH))
    run_dir = base / "work"
    run_dir.mkdir()
    if task.seed is not None:
        task.seed(run_dir)
    return run_dir


def run_one(
    harness: str,
    model: str,
    task: Task,
    verifier: Callable[[pathlib.Path, Task], Verdict],
    timeout: float,
    max_steps: int,
    keep: bool,
) -> Result:
    run_dir = prepare(task)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = LOG_ROOT / f"{run_dir.parent.name}_{harness}_{task.key}.log"
    cmd = build_command(harness, model, task, "off", max_steps, str(run_dir))  # type: ignore[arg-type]

    env = dict(os.environ)
    env.setdefault("LOCAL_LLM_KEY", "local")
    env["PWD"] = str(run_dir)
    env.pop("OLDPWD", None)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
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

    try:
        verified, _created, detail = verifier(run_dir, task)
    except Exception as exc:  # noqa: BLE001 - one broken verifier must not stop the suite
        verified, detail = False, f"verifier raised: {exc}"
    try:
        log_tail = log_path.read_text(errors="replace")[-900:]
    except OSError:
        log_tail = "<run directory disappeared before the log could be read>"

    result = Result(
        harness=harness,
        model=model,
        task=task.key,
        # `verified` is the product; `passed` is the product delivered in time.
        # A model that writes the right file and then never exits has not solved
        # the task for a user, but pretending the file is not there is also wrong.
        passed=bool(verified and not timed_out),
        verified=bool(verified),
        timed_out=timed_out,
        exit_code=exit_code,
        seconds=round(seconds, 1),
        detail=detail,
        log_path=str(run_dir),
        log_tail=log_tail,
    )
    if not keep:
        shutil.rmtree(run_dir.parent, ignore_errors=True)
    return result


def selftest(tasks: dict[str, Task], verifiers: dict[str, Callable[[pathlib.Path, Task], Verdict]]) -> int:
    """Every verifier must accept its reference solution and reject an empty dir."""
    failures = 0
    for key, task in tasks.items():
        empty = prepare(task)
        ok_empty, _c, detail_empty = verifiers[task.verifier](empty, task)
        shutil.rmtree(empty.parent, ignore_errors=True)
        solved = prepare(task)
        if task.reference is None:
            print(f"FAIL {key}: no reference solution")
            failures += 1
            shutil.rmtree(solved.parent, ignore_errors=True)
            continue
        try:
            task.reference(solved)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {key}: reference solution raised {exc}")
            failures += 1
            shutil.rmtree(solved.parent, ignore_errors=True)
            continue
        ok, _c, detail = verifiers[task.verifier](solved, task)
        shutil.rmtree(solved.parent, ignore_errors=True)
        good = ok and not ok_empty
        failures += 0 if good else 1
        print(
            f"{'ok  ' if good else 'FAIL'} {key:13} reference={ok} empty_dir={ok_empty} "
            f"detail={detail[:70]!r} empty={detail_empty[:50]!r}"
        )
    print(f"\n{len(tasks) - failures}/{len(tasks)} verifiers behave")
    return 0 if failures == 0 else 1


def run_cli(
    argv: list[str] | None,
    tasks: dict[str, Task],
    verifiers: dict[str, Callable[[pathlib.Path, Task], Verdict]],
    description: str,
) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--model", default="spark-1.7b-q4", choices=sorted(MODELS))
    parser.add_argument("--task", default="all", choices=[*tasks, "all"])
    parser.add_argument(
        "--harness",
        nargs="+",
        default=["openlaoke", "pi", "jcode", "opencode"],
        choices=["openlaoke", "pi", "jcode", "opencode"],
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument(
        "--reps",
        type=int,
        default=1,
        help="Repeat each (harness, model, task) cell N times and report k/N pass rate and median seconds.",
    )
    parser.add_argument("--json", type=pathlib.Path, default=None)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest(tasks, verifiers)

    SCRATCH.mkdir(parents=True, exist_ok=True)
    chosen = list(tasks.values()) if args.task == "all" else [tasks[args.task]]
    results: list[Result] = []
    reps = max(1, int(args.reps))

    def summarize_cells(rows: list[Result]) -> dict[str, dict[str, Any]]:
        """Per (harness, task) cell over all reps: k/N pass, median seconds, stability."""
        import statistics
        groups: dict[tuple[str, str], list[Result]] = {}
        for r in rows:
            groups.setdefault((r.harness, r.task), []).append(r)
        out: dict[str, dict[str, Any]] = {}
        for (h, t), rs in groups.items():
            n = len(rs)
            k = sum(1 for r in rs if r.passed)
            kv = sum(1 for r in rs if getattr(r, "verified", False))
            med = statistics.median(r.seconds for r in rs)
            stability = "stable-pass" if k == n else ("stable-fail" if k == 0 else "unstable")
            out[f"{h}|{t}"] = {
                "harness": h,
                "task": t,
                "reps": n,
                "pass_k": k,
                "verified_k": kv,
                "median_seconds": round(float(med), 1),
                "times": [round(float(r.seconds), 1) for r in rs],
                "stability": stability,
            }
        return out

    def flush() -> None:
        if not args.json:
            return
        cells = summarize_cells(results)
        stable_pass = sum(1 for c in cells.values() if c["stability"] == "stable-pass")
        stable_fail = sum(1 for c in cells.values() if c["stability"] == "stable-fail")
        unstable = sum(1 for c in cells.values() if c["stability"] == "unstable")
        payload: dict[str, Any] = {
            "model": args.model,
            "timeout": args.timeout,
            "max_steps": args.max_steps,
            "reps": reps,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cells": cells,
            "results": [asdict(r) for r in results],
            "summary": {
                "pass": sum(1 for r in results if r.passed),
                "verified": sum(1 for r in results if getattr(r, "verified", False)),
                "total": len(results),
                "cells_stable_pass": stable_pass,
                "cells_stable_fail": stable_fail,
                "cells_unstable": unstable,
                "by_harness": {
                    h: {
                        "pass": sum(1 for r in results if r.harness == h and r.passed),
                        "total": sum(1 for r in results if r.harness == h),
                    }
                    for h in args.harness
                },
            },
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    for task in chosen:
        for harness in args.harness:
            for rep in range(1, reps + 1):
                tag = f" [rep {rep}/{reps}]" if reps > 1 else ""
                print(f"== {harness} / {args.model} / {task.key}{tag}", flush=True)
                try:
                    result = run_one(
                        harness,
                        args.model,
                        task,
                        verifiers[task.verifier],
                        args.timeout,
                        args.max_steps,
                        args.keep,
                    )
                except Exception as exc:  # noqa: BLE001
                    result = Result(
                        harness=harness,
                        model=args.model,
                        task=task.key,
                        passed=False,
                        verified=False,
                        timed_out=False,
                        exit_code=None,
                        seconds=0.0,
                        detail=f"runner raised: {exc}",
                    )
                result.rep = rep
                results.append(result)
                flush()
                mark = "PASS" if result.passed else ("TIME" if result.timed_out else "fail")
                print(f"   {mark:4} {result.seconds:6.1f}s  {result.detail[:150]}", flush=True)
            if reps > 1:
                cell = summarize_cells(results)[f"{harness}|{task.key}"]
                print(
                    f"   -> {cell['pass_k']}/{cell['reps']} pass, median {cell['median_seconds']}s, {cell['stability']}",
                    flush=True,
                )

    passed = sum(1 for r in results if r.passed)
    if args.json:
        print(f"\nwrote {args.json}")
    print(f"\n{args.model}: {passed}/{len(results)}")
    if reps > 1:
        cells = summarize_cells(results)
        sp = sum(1 for c in cells.values() if c["stability"] == "stable-pass")
        sf = sum(1 for c in cells.values() if c["stability"] == "stable-fail")
        un = sum(1 for c in cells.values() if c["stability"] == "unstable")
        print(f"cells: {sp} stable-pass / {un} unstable / {sf} stable-fail (of {len(cells)})")
    return 0


__all__ = ["DEV_PYTHON", "Result", "Task", "Verifier", "run_cli", "run_one", "selftest"]
Verifier = Callable[[pathlib.Path, Task], Verdict]
