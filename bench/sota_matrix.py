#!/usr/bin/env python
"""A harder, more representative task suite for small local models.

The first matrix (``harness_matrix.py``) proved four tools can create one file.
This one asks for what coding agents are actually measured on: repair a failing
test suite, implement a written spec, split a module into a package, drive a
CLI, join JSON into CSV, write SQL against a seeded database, extract fields
from a log, commit to git, build a Word table, and run work concurrently.

Everything is judged from the filesystem after the run, never from what the
agent says it did. Two easy anchors (``merge``, ``download``) stay in the set so
a zero on the hard tasks cannot be confused with a broken harness.

Usage:
    python bench/sota_matrix.py --selftest                # every verifier must pass its own reference solution
    python bench/sota_matrix.py --model spark-1.7b-q4 --task all --timeout 120
    python bench/sota_matrix.py --model lfm3-1.7b-q4 --task fix_tests --harness jcode
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
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

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness_matrix import DEV_PYTHON, MODELS, SCRATCH, build_command  # noqa: E402

# --------------------------------------------------------------------------
# task model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Task:
    key: str
    prompt: str
    verifier: str

    # files the task starts with, written before the agent runs
    seed: Callable[[pathlib.Path], None] | None = None
    # an honest solution, used only by --selftest
    reference: Callable[[pathlib.Path], None] | None = None
    note: str = ""


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(cwd: pathlib.Path, args: list[str], stdin: str = "", timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": str(cwd), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _py(cwd: pathlib.Path, code: str, timeout: float = 60) -> subprocess.CompletedProcess:
    return _run(cwd, [DEV_PYTHON, "-c", code], timeout=timeout)


# --------------------------------------------------------------------------
# seeds
# --------------------------------------------------------------------------

CALC_BUGGY = '''"""Small arithmetic helpers."""


def add(a, b):
    return a - b


def mean(values):
    total = 0
    for value in values:
        total += value
    return total / (len(values) + 1)


def clamp(value, low, high):
    if value < low:
        return high
    if value > high:
        return low
    return value
'''

CALC_TESTS = '''from calc import add, clamp, mean


def test_add():
    assert add(2, 3) == 5


def test_mean():
    assert mean([2, 4, 6]) == 4


def test_clamp():
    assert clamp(5, 1, 10) == 5
    assert clamp(-3, 1, 10) == 1
    assert clamp(99, 1, 10) == 10
'''

CALC_FIXED = '''"""Small arithmetic helpers."""


def add(a, b):
    return a + b


def mean(values):
    if not values:
        raise ValueError("mean of empty sequence")
    return sum(values) / len(values)


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value
'''

SPEC_MD = '''# textutil.slugify

Implement `slugify(text: str) -> str` in `textutil.py` following these rules, in
this order:

1. Lowercase the text.
2. Replace every character that is not an ASCII letter or digit with a dash.
3. Collapse runs of dashes into a single dash.
4. Strip leading and trailing dashes.

Examples:

| input | output |
|---|---|
| `Hello, World!` | `hello-world` |
| `  Multiple   Spaces  ` | `multiple-spaces` |
| `A--B__C` | `a-b-c` |
| `!!!` | `` (empty string) |
| `Model 1.7B Q4` | `model-1-7b-q4` |

Keep it dependency free: standard library only. Do not change the file name.
'''

APP_MONOLITH = '''"""Tiny report tool kept in one file."""


def load_rows():
    return [("north", 10), ("south", 6), ("north", 4)]


def total(rows):
    return sum(amount for _region, amount in rows)


def by_region(rows):
    result = {}
    for region, amount in rows:
        result[region] = result.get(region, 0) + amount
    return result


def render():
    rows = load_rows()
    parts = [f"total: {total(rows)}"]
    for region in sorted(by_region(rows)):
        parts.append(f"{region}: {by_region(rows)[region]}")
    return "\\n".join(parts)


if __name__ == "__main__":
    print(render())
'''

ORDERS_JSON = json.dumps(
    {
        "orders": [
            {"region": "north", "amount": 120.5},
            {"region": "south", "amount": 80},
            {"region": "north", "amount": 30},
            {"region": "east", "amount": 200.25},
        ]
    },
    indent=2,
)

ACCESS_LOG = """2026-03-01 10:00:01 INFO signup alice@example.com from 10.0.0.4
2026-03-01 10:00:07 INFO login  bob.smith+news@mail.example.org from 10.0.0.9
2026-03-01 10:01:12 WARN  retry  alice@example.com from 10.0.0.4
2026-03-01 10:02:44 ERROR bounce carol@sub.example.net. from 10.0.0.11
2026-03-01 10:03:01 INFO login  dave@example.io from 10.0.0.12
2026-03-01 10:03:02 INFO health check ok
"""


def seed_fix_tests(d: pathlib.Path) -> None:
    _write(d / "calc.py", CALC_BUGGY)
    _write(d / "test_calc.py", CALC_TESTS)


def seed_spec_impl(d: pathlib.Path) -> None:
    _write(d / "SPEC.md", SPEC_MD)


def seed_refactor(d: pathlib.Path) -> None:
    _write(d / "app.py", APP_MONOLITH)


def seed_datatrans(d: pathlib.Path) -> None:
    _write(d / "orders.json", ORDERS_JSON)


def seed_sqlite(d: pathlib.Path) -> None:
    import sqlite3

    db = d / "shop.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount INTEGER);
        INSERT INTO customers (id, name) VALUES (1, 'Ada'), (2, 'Bo'), (3, 'Cy'), (4, 'Dana');
        INSERT INTO orders (customer_id, amount) VALUES
          (1, 100), (2, 300), (2, 50), (3, 120), (3, 80), (4, 500), (4, 20), (1, 40);
        """
    )
    con.commit()
    con.close()


def seed_regex(d: pathlib.Path) -> None:
    _write(d / "access.log", ACCESS_LOG)


def seed_git(d: pathlib.Path) -> None:
    _write(d / "notes.md", "# Notes\n\n- first entry\n")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "bench",
        "GIT_AUTHOR_EMAIL": "bench@example.com",
        "GIT_COMMITTER_NAME": "bench",
        "GIT_COMMITTER_EMAIL": "bench@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=d, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "chore: seed notes"], cwd=d, env=env, check=True)


# --------------------------------------------------------------------------
# verifiers
# --------------------------------------------------------------------------


def _last(text: str, n: int = 300) -> str:
    return text.strip()[-n:]


def v_merge(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "merge_sort.py"
    if not target.exists():
        return False, False, ""
    try:
        proc = _run(d, [DEV_PYTHON, str(target)], timeout=30)
    except subprocess.TimeoutExpired:
        return False, True, "<timed out>"
    out = proc.stdout + proc.stderr
    return "[1, 2, 3, 4, 5]" in out, True, _last(out)


def v_download(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "page.html"
    if not target.exists() or target.stat().st_size == 0:
        return False, target.exists(), ""
    text = target.read_text(errors="replace")
    return "example domain" in text.lower(), True, _last(text)


def v_fix_tests(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    tests = d / "test_calc.py"
    if not tests.exists() or not (d / "calc.py").exists():
        return False, tests.exists(), ""
    if hashlib.sha256(tests.read_bytes()).hexdigest() != hashlib.sha256(
        CALC_TESTS.encode()
    ).hexdigest():
        return False, True, "test_calc.py was modified"
    try:
        proc = _run(
            d,
            [DEV_PYTHON, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return False, True, "<pytest timed out>"
    out = proc.stdout + proc.stderr
    ok = proc.returncode == 0 and "3 passed" in out
    return ok, True, _last(out)


SLUG_CASES = [
    ("Hello, World!", "hello-world"),
    ("  Multiple   Spaces  ", "multiple-spaces"),
    ("A--B__C", "a-b-c"),
    ("!!!", ""),
    ("Model 1.7B Q4", "model-1-7b-q4"),
]


def v_spec_impl(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "textutil.py"
    if not target.exists():
        return False, False, ""
    if not target.read_text(errors="replace").strip():
        return False, True, "textutil.py is empty"
    probe = d / "_spec_probe.py"
    body = ["from textutil import slugify", "", "cases = ["]
    for src, want in SLUG_CASES:
        body.append(f"    ({src!r}, {want!r}),")
    body += [
        "]",
        "for src, want in cases:",
        "    got = slugify(src)",
        "    print(repr(src), '->', repr(got))",
        "    assert got == want, f'{src!r}: {got!r} != {want!r}'",
        "print('all slug cases ok')",
        "",
    ]
    probe.write_text("\n".join(body), encoding="utf-8")
    try:
        proc = _run(d, [DEV_PYTHON, str(probe)], timeout=60)
    except subprocess.TimeoutExpired:
        return False, True, "<probe timed out>"
    finally:
        with contextlib.suppress(FileNotFoundError):
            probe.unlink()
    out = proc.stdout + proc.stderr
    return "all slug cases ok" in out, True, _last(out)


def v_refactor(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    app = d / "app.py"
    lib = d / "lib"
    if not app.exists():
        return False, False, ""
    modules = sorted(p.name for p in lib.glob("*.py")) if lib.is_dir() else []
    if len(modules) < 2 or "__init__.py" not in modules:
        return False, True, f"lib package modules: {modules}"
    try:
        run = _run(d, [DEV_PYTHON, "app.py"], timeout=45)
        api = _py(
            d,
            "import lib; assert lib.total([('north', 10), ('south', 6)]) == 16; "
            "assert lib.by_region([('a', 1), ('a', 2)])['a'] == 3; print('api ok')",
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return False, True, "<timed out>"
    out = run.stdout
    expected = {"total: 20", "north: 14", "south: 6"}
    ok = expected.issubset({line.strip() for line in out.splitlines()}) and "api ok" in api.stdout
    detail = f"stdout={_last(out, 150)!r} api={_last(api.stdout + api.stderr, 150)!r}"
    return ok, True, detail


def v_cli(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "wc_cli.py"
    if not target.exists():
        return False, False, ""
    try:
        proc = _run(
            d,
            [DEV_PYTHON, str(target), "--sep", "|", "--upper"],
            stdin="alpha beta gamma\n",
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return False, True, "<timed out>"
    out = proc.stdout.strip()
    return out == "ALPHA|BETA|GAMMA", True, _last(proc.stdout + proc.stderr)


def v_datatrans(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "summary.csv"
    if not target.exists() or target.stat().st_size == 0:
        return False, target.exists(), ""
    rows = [line.strip() for line in target.read_text(errors="replace").splitlines() if line.strip()]
    if not rows:
        return False, True, "empty csv"
    if rows[0].replace(" ", "").lower() != "region,total":
        return False, True, f"header is {rows[0]!r}"
    try:
        parsed = [
            (parts[0].strip().lower(), float(parts[1]))
            for parts in (row.split(",") for row in rows[1:])
        ]
    except (ValueError, IndexError) as exc:
        return False, True, f"unparsable row: {exc}"
    expected = [("east", 200.25), ("north", 150.5), ("south", 80.0)]
    ok = len(parsed) == 3 and all(
        got[0] == want[0] and abs(got[1] - want[1]) < 0.01
        for got, want in zip(parsed, expected, strict=False)
    )
    return ok, True, f"rows={parsed}"


def v_sqlite(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    q = d / "q.sql"
    db = d / "shop.db"
    if not q.exists() or not q.read_text(errors="replace").strip():
        return False, q.exists(), ""
    if not db.exists():
        return False, True, "shop.db was deleted"
    try:
        import sqlite3

        con = sqlite3.connect(db)
        try:
            rows = con.execute(q.read_text(encoding="utf-8")).fetchall()
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001 - any SQL error is a fail
        return False, True, f"sql error: {exc}"
    cleaned = [tuple(str(cell).strip() for cell in row) for row in rows]
    expected = [("Dana", "520"), ("Bo", "350"), ("Cy", "200")]
    return cleaned == expected, True, f"rows={cleaned}"


def v_regex(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "emails.txt"
    if not target.exists() or target.stat().st_size == 0:
        return False, target.exists(), ""
    got = [line.strip() for line in target.read_text(errors="replace").splitlines() if line.strip()]
    expected = [
        "alice@example.com",
        "bob.smith+news@mail.example.org",
        "carol@sub.example.net",
        "dave@example.io",
    ]
    return got == expected, True, f"got={got}"


def v_git(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    notes = d / "notes.md"
    if not notes.exists():
        return False, False, ""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "bench",
        "GIT_AUTHOR_EMAIL": "bench@example.com",
        "GIT_COMMITTER_NAME": "bench",
        "GIT_COMMITTER_EMAIL": "bench@example.com",
    }
    try:
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=d, capture_output=True, text=True, env=env
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=d, capture_output=True, text=True, env=env
        ).stdout.strip()
        count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"], cwd=d, capture_output=True, text=True, env=env
        ).stdout.strip()
    except OSError as exc:
        return False, True, f"git failed: {exc}"
    body = notes.read_text(errors="replace")
    ok = (
        subject == "docs: add shipped note"
        and "shipped the fix" in body
        and not status
        and count == "2"
    )
    return ok, True, f"subject={subject!r} commits={count} dirty={bool(status)}"


def v_docx_table(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "report.docx"
    if not target.exists():
        return False, False, ""
    try:
        import docx

        document = docx.Document(str(target))
    except Exception as exc:  # noqa: BLE001
        return False, True, f"cannot open docx: {exc}"
    texts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    flat = " | ".join(texts)
    if "Q3 Report" not in flat:
        return False, True, f"no heading, paragraphs={texts[:4]}"
    if not document.tables:
        return False, True, "no table"
    table = document.tables[0]
    cells = {cell.text.strip() for row in table.rows for cell in row.cells}
    ok = {"Region", "Revenue"}.issubset(cells) and "APAC" in cells and "42" in cells
    return ok, True, f"cells={sorted(cells)[:8]}"


def v_async(d: pathlib.Path, task: Task) -> tuple[bool, bool, str]:
    target = d / "fast.py"
    if not target.exists():
        return False, False, ""
    started = time.time()
    try:
        proc = _run(d, [DEV_PYTHON, str(target)], timeout=30)
    except subprocess.TimeoutExpired:
        return False, True, "<timed out>"
    elapsed = time.time() - started
    out = (proc.stdout + proc.stderr).strip()
    # The prompt asks for a `done 5` line, so a line is what has to exist: a
    # substring match would also accept "done 1" or a stray mention in a traceback.
    lines = {line.strip().lower() for line in out.splitlines() if line.strip()}
    ok = elapsed < 3.0 and "done 5" in lines
    return ok, True, f"{elapsed:.1f}s out={_last(out, 120)!r}"


VERIFIERS: dict[str, Callable[[pathlib.Path, Task], tuple[bool, bool, str]]] = {
    "merge": v_merge,
    "download": v_download,
    "fix_tests": v_fix_tests,
    "spec_impl": v_spec_impl,
    "refactor": v_refactor,
    "cli": v_cli,
    "datatrans": v_datatrans,
    "sqlite": v_sqlite,
    "regex": v_regex,
    "git": v_git,
    "docx_table": v_docx_table,
    "async": v_async,
}


# --------------------------------------------------------------------------
# reference solutions (selftest only)
# --------------------------------------------------------------------------


def ref_merge(d: pathlib.Path) -> None:
    _write(
        d / "merge_sort.py",
        "def merge_sort(items):\n"
        "    if len(items) <= 1:\n"
        "        return list(items)\n"
        "    mid = len(items) // 2\n"
        "    left = merge_sort(items[:mid])\n"
        "    right = merge_sort(items[mid:])\n"
        "    out = []\n"
        "    while left and right:\n"
        "        out.append(left.pop(0) if left[0] <= right[0] else right.pop(0))\n"
        "    return out + left + right\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(merge_sort([5, 3, 1, 4, 2]))\n",
    )


def ref_download(d: pathlib.Path) -> None:
    subprocess.run(
        ["curl", "-sS", "-L", "-o", "page.html", "https://example.com"], cwd=d, check=True
    )


def ref_fix_tests(d: pathlib.Path) -> None:
    _write(d / "calc.py", CALC_FIXED)


def ref_spec_impl(d: pathlib.Path) -> None:
    _write(
        d / "textutil.py",
        "import re\n"
        "\n"
        "\n"
        "def slugify(text: str) -> str:\n"
        "    lowered = text.lower()\n"
        "    dashed = re.sub(r'[^a-z0-9]', '-', lowered)\n"
        "    return re.sub(r'-+', '-', dashed).strip('-')\n",
    )


def ref_refactor(d: pathlib.Path) -> None:
    _write(
        d / "lib" / "__init__.py",
        "from .data import load_rows\n"
        "from .report import by_region, render, total\n"
        "\n"
        "__all__ = ['load_rows', 'total', 'by_region', 'render']\n",
    )
    _write(
        d / "lib" / "data.py",
        "def load_rows():\n"
        "    return [('north', 10), ('south', 6), ('north', 4)]\n",
    )
    _write(
        d / "lib" / "report.py",
        "from .data import load_rows\n"
        "\n"
        "\n"
        "def total(rows):\n"
        "    return sum(amount for _region, amount in rows)\n"
        "\n"
        "\n"
        "def by_region(rows):\n"
        "    result = {}\n"
        "    for region, amount in rows:\n"
        "        result[region] = result.get(region, 0) + amount\n"
        "    return result\n"
        "\n"
        "\n"
        "def render():\n"
        "    rows = load_rows()\n"
        "    parts = [f'total: {total(rows)}']\n"
        "    for region in sorted(by_region(rows)):\n"
        "        parts.append(f'{region}: {by_region(rows)[region]}')\n"
        "    return '\\n'.join(parts)\n",
    )
    _write(
        d / "app.py",
        "from lib import render\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(render())\n",
    )


def ref_cli(d: pathlib.Path) -> None:
    _write(
        d / "wc_cli.py",
        "import argparse\n"
        "import sys\n"
        "\n"
        "\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--sep', default=' ')\n"
        "    parser.add_argument('--upper', action='store_true')\n"
        "    args = parser.parse_args()\n"
        "    words = sys.stdin.read().split()\n"
        "    if args.upper:\n"
        "        words = [word.upper() for word in words]\n"
        "    print(args.sep.join(words))\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
    )


def ref_datatrans(d: pathlib.Path) -> None:
    _write(
        d / "summary.csv",
        "region,total\neast,200.25\nnorth,150.50\nsouth,80.00\n",
    )


def ref_sqlite(d: pathlib.Path) -> None:
    _write(
        d / "q.sql",
        "SELECT c.name AS name, SUM(o.amount) AS revenue\n"
        "FROM customers c JOIN orders o ON o.customer_id = c.id\n"
        "GROUP BY c.id, c.name\n"
        "ORDER BY revenue DESC\n"
        "LIMIT 3;\n",
    )


def ref_regex(d: pathlib.Path) -> None:
    _write(
        d / "emails.txt",
        "alice@example.com\n"
        "bob.smith+news@mail.example.org\n"
        "carol@sub.example.net\n"
        "dave@example.io\n",
    )


def ref_git(d: pathlib.Path) -> None:
    notes = d / "notes.md"
    notes.write_text(notes.read_text() + "- shipped the fix\n", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "bench",
        "GIT_AUTHOR_EMAIL": "bench@example.com",
        "GIT_COMMITTER_NAME": "bench",
        "GIT_COMMITTER_EMAIL": "bench@example.com",
    }
    subprocess.run(["git", "add", "-A"], cwd=d, env=env, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "docs: add shipped note"], cwd=d, env=env, check=True
    )


def ref_docx_table(d: pathlib.Path) -> None:
    import docx

    document = docx.Document()
    document.add_heading("Q3 Report", level=1)
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Revenue"
    table.cell(1, 0).text = "APAC"
    table.cell(1, 1).text = "42"
    document.save(str(d / "report.docx"))


def ref_async(d: pathlib.Path) -> None:
    _write(
        d / "fast.py",
        "import time\n"
        "from concurrent.futures import ThreadPoolExecutor\n"
        "\n"
        "\n"
        "def job(n):\n"
        "    time.sleep(1)\n"
        "    return n\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    with ThreadPoolExecutor(max_workers=5) as pool:\n"
        "        list(pool.map(job, range(5)))\n"
        "    print('done 5')\n",
    )


# --------------------------------------------------------------------------
# task table
# --------------------------------------------------------------------------

TASKS: dict[str, Task] = {
    "merge": Task(
        key="merge",
        prompt=(
            "Create merge_sort.py implementing merge sort and a __main__ block that sorts "
            "[5, 3, 1, 4, 2] and prints the result. Run it to verify."
        ),
        verifier="merge",
        reference=ref_merge,
        note="anchor: one file, one run",
    ),
    "download": Task(
        key="download",
        prompt=(
            "Create a file named page.html by downloading https://example.com (using curl or "
            "urllib, no proxy). The file must contain the words Example Domain. Verify it."
        ),
        verifier="download",
        reference=ref_download,
        note="anchor: network tool use",
    ),
    "fix_tests": Task(
        key="fix_tests",
        prompt=(
            "calc.py has three bugs and test_calc.py describes the expected behavior. Run "
            "`python3 -m pytest -q` to see the failures, fix calc.py, and run the suite again "
            "until all three tests pass. Do not modify test_calc.py."
        ),
        verifier="fix_tests",
        seed=seed_fix_tests,
        reference=ref_fix_tests,
        note="SWE-style repair against a test suite",
    ),
    "spec_impl": Task(
        key="spec_impl",
        prompt=(
            "Read SPEC.md and implement slugify(text) in textutil.py exactly as specified, "
            "including every example in the table. Add a __main__ block that prints the five "
            "example outputs and run it."
        ),
        verifier="spec_impl",
        seed=seed_spec_impl,
        reference=ref_spec_impl,
        note="implement a written spec with edge cases",
    ),
    "refactor": Task(
        key="refactor",
        prompt=(
            "app.py is one flat module. Split it into a package named lib with an __init__.py "
            "that re-exports load_rows, total, by_region and render, and at least one more "
            "module. Keep `python3 app.py` printing exactly what it prints now."
        ),
        verifier="refactor",
        seed=seed_refactor,
        reference=ref_refactor,
        note="multi-file refactor that must not change behavior",
    ),
    "cli": Task(
        key="cli",
        prompt=(
            "Write wc_cli.py: read words from stdin, join them with --sep (default space), and "
            "uppercase them when --upper is passed. Use argparse. "
            "`python3 wc_cli.py --sep '|' --upper` with stdin `alpha beta gamma` must print "
            "`ALPHA|BETA|GAMMA`."
        ),
        verifier="cli",
        reference=ref_cli,
        note="argument parsing driven from the command line",
    ),
    "datatrans": Task(
        key="datatrans",
        prompt=(
            "Read orders.json and write summary.csv with header `region,total`, one row per "
            "region, totals with two decimals, sorted by total descending."
        ),
        verifier="datatrans",
        seed=seed_datatrans,
        reference=ref_datatrans,
        note="JSON to CSV aggregation with an ordering rule",
    ),
    "sqlite": Task(
        key="sqlite",
        prompt=(
            "shop.db has tables customers(id, name) and orders(customer_id, amount). Write "
            "q.sql selecting the top 3 customers by total amount, columns name and revenue, "
            "highest first. Verify it with sqlite3."
        ),
        verifier="sqlite",
        seed=seed_sqlite,
        reference=ref_sqlite,
        note="write SQL against a real database and check the rows",
    ),
    "regex": Task(
        key="regex",
        prompt=(
            "Extract every email address from access.log into emails.txt: one per line, "
            "lowercase, no duplicates, sorted. Trailing punctuation in the log is not part of "
            "the address."
        ),
        verifier="regex",
        seed=seed_regex,
        reference=ref_regex,
        note="extraction with dedupe, sort and a punctuation trap",
    ),
    "git": Task(
        key="git",
        prompt=(
            "Append the line `- shipped the fix` to notes.md and commit it with the message "
            "`docs: add shipped note`. Leave the working tree clean."
        ),
        verifier="git",
        seed=seed_git,
        reference=ref_git,
        note="git commit with an exact message",
    ),
    "docx_table": Task(
        key="docx_table",
        prompt=(
            "Use python-docx to create report.docx with a level-1 heading `Q3 Report` and a "
            "2x2 table whose header is Region | Revenue and whose data row is APAC | 42. Run a "
            "script to verify the file opens."
        ),
        verifier="docx_table",
        reference=ref_docx_table,
        note="structured document artifact",
    ),
    "async": Task(
        key="async",
        prompt=(
            "Write fast.py that runs five jobs of `time.sleep(1)` concurrently with a thread "
            "pool or asyncio, prints `done 5` at the end, and finishes in well under 3 seconds."
        ),
        verifier="async",
        reference=ref_async,
        note="concurrency, judged by wall clock",
    ),
}


# --------------------------------------------------------------------------
# running
# --------------------------------------------------------------------------


@dataclass
class Result:
    harness: str
    model: str
    task: str
    passed: bool
    timed_out: bool
    exit_code: int | None
    seconds: float
    detail: str
    log_path: str = ""
    log_tail: str = ""


def prepare(task: Task) -> pathlib.Path:
    """One run gets one private parent holding nothing but its own work dir.

    Flat ``sota_cli_*`` directories let a later agent grep out of its workspace
    and find the file a previous run wrote; jcode did exactly that once and
    "solved" a task by reading a sibling's answer. Nesting each run under its own
    random parent keeps neighbours out of reach even when run dirs are kept.
    """
    base = pathlib.Path(tempfile.mkdtemp(prefix="sota_run_", dir=SCRATCH))
    run_dir = base / "work"
    run_dir.mkdir()
    if task.seed is not None:
        task.seed(run_dir)
    return run_dir


LOG_ROOT = pathlib.Path.home() / ".jcode" / "sota_logs"


def run_one(
    harness: str, model: str, task: Task, timeout: float, max_steps: int, keep: bool
) -> Result:
    run_dir = prepare(task)
    # The log lives outside the run tree: an agent that runs `rm -rf ..` would
    # otherwise take its own log with it, and a benchmark that cannot read its
    # log is a benchmark that stops in the middle.
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
        passed, _created, detail = VERIFIERS[task.verifier](run_dir, task)
    except Exception as exc:  # noqa: BLE001 - one broken verifier must not stop the matrix
        passed, detail = False, f"verifier raised: {exc}"
    try:
        log_tail = log_path.read_text(errors="replace")[-900:]
    except OSError:
        log_tail = "<run directory disappeared before the log could be read>"
    result = Result(
        harness=harness,
        model=model,
        task=task.key,
        passed=bool(passed and not timed_out),
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


def selftest() -> int:
    """Every verifier must accept its reference solution and reject an empty dir."""
    failures = 0
    for key, task in TASKS.items():
        empty = prepare(task)
        ok_empty, _c, detail_empty = VERIFIERS[task.verifier](empty, task)
        shutil.rmtree(empty, ignore_errors=True)
        solved = prepare(task)
        assert task.reference is not None, key
        try:
            task.reference(solved)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {key}: reference solution raised {exc}")
            failures += 1
            continue
        ok, _c, detail = VERIFIERS[task.verifier](solved, task)
        shutil.rmtree(solved, ignore_errors=True)
        verdict = "ok  " if ok and not ok_empty else "FAIL"
        if not (ok and not ok_empty):
            failures += 1
        print(
            f"{verdict} {key:11} reference={ok} empty_dir={ok_empty} "
            f"detail={detail[:80]!r} empty={detail_empty[:60]!r}"
        )
    print(f"\n{len(TASKS) - failures}/{len(TASKS)} verifiers behave")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="spark-1.7b-q4", choices=sorted(MODELS))
    parser.add_argument("--task", default="all", choices=[*TASKS, "all"])
    parser.add_argument(
        "--harness",
        nargs="+",
        default=["openlaoke", "pi", "jcode", "opencode"],
        choices=["openlaoke", "pi", "jcode", "opencode"],
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    SCRATCH.mkdir(parents=True, exist_ok=True)
    tasks = list(TASKS.values()) if args.task == "all" else [TASKS[args.task]]
    results: list[Result] = []

    def flush_json() -> None:
        if not args.json:
            return
        payload = {
            "model": args.model,
            "timeout": args.timeout,
            "max_steps": args.max_steps,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": [asdict(r) for r in results],
            "summary": {
                "pass": sum(1 for r in results if r.passed),
                "total": len(results),
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

    for task in tasks:
        for harness in args.harness:
            print(f"== {harness} / {args.model} / {task.key}", flush=True)
            try:
                result = run_one(harness, args.model, task, args.timeout, args.max_steps, args.keep)
            except Exception as exc:  # noqa: BLE001
                result = Result(
                    harness=harness,
                    model=args.model,
                    task=task.key,
                    passed=False,
                    timed_out=False,
                    exit_code=None,
                    seconds=0.0,
                    detail=f"harness loop raised: {exc}",
                )
            results.append(result)
            flush_json()
            mark = "PASS" if result.passed else ("TIME" if result.timed_out else "fail")
            print(f"   {mark:4} {result.seconds:6.1f}s  {result.detail[:150]}", flush=True)

    passed = sum(1 for r in results if r.passed)
    if args.json:
        print(f"\nwrote {args.json}")
    print(f"\n{args.model}: {passed}/{len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
