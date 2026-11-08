"""Startup cost gate.

There is no CI workflow in this repository, so this script is the gate: it
measures the two numbers a slow harness is felt through - time to import the
entry module in a cold interpreter, and the resident memory that import leaves
behind - and exits non-zero when either goes over budget.

Budgets are deliberately loose enough not to flap on a laptop and tight enough
to catch a regression that adds a heavyweight import to the startup path.  Both
can be overridden, which is what makes it usable in a comparison run:

    python scripts/bench_startup.py
    python scripts/bench_startup.py --max-ms 900 --max-mb 90
    python scripts/bench_startup.py --runs 5 --json

Run it before tagging a release, or after touching anything at import time.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys

DEFAULT_MODULE = "openlaoke.entrypoints.cli"
DEFAULT_MAX_MS = 1200.0
DEFAULT_MAX_MB = 120.0

PROBE = """
import json, os, resource, sys, time
started = time.perf_counter()
import {module}
elapsed = (time.perf_counter() - started) * 1000.0
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
# ru_maxrss is bytes on macOS and kilobytes on Linux.
if sys.platform != "darwin":
    peak *= 1024
heavy = []
for name, loaded in list(sys.modules.items()):
    path = getattr(loaded, "__file__", None)
    if not path or not path.endswith(".py"):
        continue
    try:
        size = os.path.getsize(path)
    except OSError:
        continue
    heavy.append([name, size])
heavy.sort(key=lambda item: item[1], reverse=True)
print(json.dumps({{"ms": elapsed, "rss_bytes": peak, "modules": len(sys.modules),
                  "heavy": heavy[:10]}}))
"""


def _measure(module: str) -> dict[str, float]:
    code = PROBE.format(module=module)
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"could not import {module}:\n{result.stderr.strip()[:2000] or result.stdout[:2000]}"
        )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    return {
        "ms": float(payload["ms"]),
        "mb": float(payload["rss_bytes"]) / (1024 * 1024),
        "modules": int(payload["modules"]),
        "heavy": payload.get("heavy", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default=DEFAULT_MODULE, help="entry module to import")
    parser.add_argument("--max-ms", type=float, default=None, help="import time budget")
    parser.add_argument("--max-mb", type=float, default=None, help="peak RSS budget")
    parser.add_argument("--runs", type=int, default=3, help="subprocesses to average")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    budget_ms = args.max_ms if args.max_ms is not None else DEFAULT_MAX_MS
    budget_mb = args.max_mb if args.max_mb is not None else DEFAULT_MAX_MB

    samples = [_measure(args.module) for _ in range(max(1, args.runs))]
    ms_median = statistics.median(sample["ms"] for sample in samples)
    mb_peak = max(sample["mb"] for sample in samples)
    modules = samples[-1]["modules"]

    failures: list[str] = []
    if ms_median > budget_ms:
        failures.append(f"import took {ms_median:.0f}ms, budget {budget_ms:.0f}ms")
    if mb_peak > budget_mb:
        failures.append(f"import peaked at {mb_peak:.0f}MB RSS, budget {budget_mb:.0f}MB")

    if args.json:
        print(
            json.dumps(
                {
                    "module": args.module,
                    "median_ms": round(ms_median, 1),
                    "peak_mb": round(mb_peak, 1),
                    "modules": modules,
                    "budget_ms": budget_ms,
                    "budget_mb": budget_mb,
                    "ok": not failures,
                    "failures": failures,
                }
            )
        )
    else:
        print(f"{args.module}: {ms_median:.0f}ms import (budget {budget_ms:.0f}ms)")
        print(f"  peak RSS after import: {mb_peak:.1f}MB (budget {budget_mb:.0f}MB)")
        print(f"  modules loaded: {modules}")
        heavy = samples[-1].get("heavy") or []
        if heavy:
            print("  largest imported modules:")
            for name, size in heavy[:5]:
                print(f"    {size / 1024:6.0f}KB  {name}")
        for failure in failures:
            print(f"  FAIL: {failure}")
        if not failures:
            print("  ok")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
