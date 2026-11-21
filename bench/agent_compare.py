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
LOCAL_MODEL = os.environ.get("OPENLAOKE_BENCH_LOCAL_MODEL", "/Users/fred/models/qwen3.5-2b-mlx4")

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
    fixtures: dict[str, str] = field(default_factory=dict)
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
    # --- tasks that need more reasoning than pattern matching ---
    Task(
        id="hard-expr-eval",
        category="hard",
        prompt=(
            "Create calc.py with eval_expr(text) that evaluates an arithmetic expression "
            "containing integers or decimals, +, -, *, /, parentheses, and unary minus, "
            "with normal precedence. Raise ValueError on malformed input. Do not use "
            "Python's eval()."
        ),
        verify={
            "file_exists": "calc.py",
            "py_check": (
                "import ast\n"
                "tree = ast.parse(open('calc.py').read())\n"
                "assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) "
                "and isinstance(n.func, ast.Name) and n.func.id == 'eval'], "
                "'eval() is not allowed'\n"
                "from calc import eval_expr\n"
                "cases = {'1+2*3': 7, '(1+2)*3': 9, '-2*3': -6, '8/2-1': 3, "
                "'2*(3+4)-5': 9, '10/4': 2.5}\n"
                "for text, want in cases.items():\n"
                "    got = eval_expr(text)\n"
                "    assert abs(got - want) < 1e-9, (text, got, want)\n"
                "for bad in ['1+', '(1+2', '1//2', '']:\n"
                "    try:\n"
                "        eval_expr(bad)\n"
                "    except ValueError:\n"
                "        pass\n"
                "    else:\n"
                "        raise AssertionError('expected ValueError for ' + repr(bad))\n"
            ),
        },
    ),
    Task(
        id="hard-csv-parse",
        category="hard",
        prompt=(
            "Create csvparse.py with parse_csv(text) returning a list of rows, each row a "
            "list of string fields. Support commas, quoted fields, doubled quotes inside "
            'quotes (""), and newlines inside quoted fields. Drop one trailing newline. '
            "Do not use Python's csv module."
        ),
        verify={
            "file_exists": "csvparse.py",
            "py_check": (
                "import ast\n"
                "tree = ast.parse(open('csvparse.py').read())\n"
                "mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) "
                "for a in n.names}\n"
                "mods |= {str(n.module or '') for n in ast.walk(tree) "
                "if isinstance(n, ast.ImportFrom)}\n"
                "assert 'csv' not in mods, 'csv module is not allowed'\n"
                "from csvparse import parse_csv\n"
                "assert parse_csv('a,b\\n1,2\\n') == [['a', 'b'], ['1', '2']]\n"
                "assert parse_csv('a,\"b,c\",d\\n') == [['a', 'b,c', 'd']]\n"
                "assert parse_csv('a,\"b\"\"c\"\\n') == [['a', 'b\"c']]\n"
                "assert parse_csv('a,\"line1\\nline2\",b\\n') == "
                "[['a', 'line1\\nline2', 'b']]\n"
                "assert parse_csv('') == []\n"
            ),
        },
    ),
    Task(
        id="hard-lru-cache",
        category="hard",
        prompt=(
            "Create lru.py with class LRUCache(capacity) supporting get(key, default=None), "
            "put(key, value), and len(cache). put() and a successful get() refresh recency. "
            "When full, put() evicts the least-recently-used key."
        ),
        verify={
            "file_exists": "lru.py",
            "py_check": (
                "from lru import LRUCache\n"
                "cache = LRUCache(2)\n"
                "cache.put('a', 1)\n"
                "cache.put('b', 2)\n"
                "assert cache.get('a') == 1\n"
                "cache.put('c', 3)\n"
                "assert cache.get('b') is None\n"
                "assert cache.get('a') == 1\n"
                "assert cache.get('c') == 3\n"
                "cache.put('a', 9)\n"
                "assert cache.get('a') == 9\n"
                "assert len(cache) == 2\n"
                "assert cache.get('missing', 'd') == 'd'\n"
            ),
        },
    ),
    Task(
        id="hard-debug-median",
        category="hard",
        setup={
            "stats.py": (
                "def mean(values):\n"
                "    return sum(values) / len(values)\n"
                "\n"
                "\n"
                "def median(values):\n"
                "    values = values.sort()\n"
                "    n = len(values)\n"
                "    if n % 2:\n"
                "        return values[n // 2]\n"
                "    return (values[n // 2 - 1] + values[n // 2]) / 2\n"
            )
        },
        prompt=(
            "Fix the bug in stats.py so median() works for odd and even length lists, "
            "including unsorted input, without mutating the caller's list. mean([]) must "
            "raise ValueError. Keep the function names and signatures."
        ),
        verify={
            "file_exists": "stats.py",
            "py_check": (
                "from stats import mean, median\n"
                "xs = [3, 1, 2]\n"
                "assert median(xs) == 2, median(xs)\n"
                "assert xs == [3, 1, 2], 'median must not mutate input'\n"
                "assert median([4, 1, 3, 2]) == 2.5\n"
                "assert mean([2, 4, 6]) == 4\n"
                "try:\n"
                "    mean([])\n"
                "except ValueError:\n"
                "    pass\n"
                "else:\n"
                "    raise AssertionError('mean([]) must raise ValueError')\n"
            ),
        },
    ),
    # --- document tool use: docx, xlsx, pdf -> markdown, python + files ---
    Task(
        id="doc-docx-edit",
        category="docs",
        fixtures={
            "report.docx": ("# Quarterly Report\nRevenue grew 12% in Q1.\nCosts stayed flat.")
        },
        prompt=(
            "Edit the existing report.docx in the current directory. Append a heading "
            "'Approved' and a paragraph 'Reviewed by QA.' at the end. Keep the original "
            "title and paragraphs unchanged. Save it as report.docx."
        ),
        verify={
            "file_exists": "report.docx",
            "py_check": (
                "from docx import Document\n"
                "d = Document('report.docx')\n"
                "joined = '\\n'.join(p.text for p in d.paragraphs)\n"
                "assert 'Quarterly Report' in joined\n"
                "assert 'Revenue grew 12% in Q1.' in joined\n"
                "assert 'Costs stayed flat.' in joined\n"
                "assert 'Approved' in joined\n"
                "assert 'Reviewed by QA.' in joined\n"
            ),
        },
    ),
    Task(
        id="doc-xlsx-summary",
        category="docs",
        fixtures={"budget.xlsx": ("Q1|Item|Amount\nQ1|Widgets|100\nQ1|Gadgets|250\nQ1|Gizmos|400")},
        prompt=(
            "Edit budget.xlsx. Create a new worksheet named 'Summary'. In Summary A1 put "
            "'Total' and in B1 put a formula that sums Q1!B2:B4. Keep the Q1 sheet "
            "unchanged. Save the workbook."
        ),
        verify={
            "file_exists": "budget.xlsx",
            "py_check": (
                "import openpyxl\n"
                "wb = openpyxl.load_workbook('budget.xlsx', data_only=False)\n"
                "assert 'Q1' in wb.sheetnames and 'Summary' in wb.sheetnames\n"
                "s = wb['Summary']\n"
                "assert str(s['A1'].value).strip() == 'Total'\n"
                "formula = str(s['B1'].value).replace(' ', '').upper()\n"
                "assert formula.startswith('=SUM('), formula\n"
                "assert 'Q1' in formula and 'B2:B4' in formula, formula\n"
                "q = wb['Q1']\n"
                "assert q['B2'].value == 100 and q['B4'].value == 400\n"
            ),
        },
    ),
    Task(
        id="doc-pdf-to-md",
        category="docs",
        fixtures={
            "manual.pdf": (
                "# User Manual\n"
                "## Installation\n"
                "Run the installer and follow the prompts.\n"
                "## Configuration\n"
                "TABLE\n"
                "| Setting | Value |\n"
                "| Theme | Dark |\n"
                "| Port | 8080 |"
            )
        },
        prompt=(
            "Convert manual.pdf into manual.md. Preserve the title as '# User Manual', "
            "the section headings as '## Installation' and '## Configuration', the "
            "paragraph text, and the table as a Markdown table with the same rows. Do "
            "not invent content."
        ),
        verify={
            "file_exists": "manual.md",
            "py_check": (
                "from pathlib import Path\n"
                "md = Path('manual.md').read_text(encoding='utf-8').lower()\n"
                "assert '# user manual' in md\n"
                "assert '## installation' in md\n"
                "assert '## configuration' in md\n"
                "assert 'run the installer' in md\n"
                "assert 'theme' in md and 'dark' in md and '8080' in md\n"
                "rows = [l for l in md.splitlines() if l.strip().startswith('|')]\n"
                "assert len(rows) >= 4, rows\n"
            ),
        },
    ),
    Task(
        id="doc-script-docx",
        category="docs",
        prompt=(
            "Create make_report.py that uses python-docx to build report.docx with a "
            "level-1 heading 'Sales Report', a paragraph 'Generated by script.', and a "
            "table with header row Item, Amount and one data row Widgets, 100. Run the "
            "script so report.docx exists. Leave both files."
        ),
        verify={
            "file_exists": ["make_report.py", "report.docx"],
            "py_check": (
                "from docx import Document\n"
                "d = Document('report.docx')\n"
                "texts = [p.text for p in d.paragraphs]\n"
                "assert 'Sales Report' in texts\n"
                "assert 'Generated by script.' in texts\n"
                "assert d.tables, 'missing table'\n"
                "t = d.tables[0]\n"
                "assert len(t.rows) >= 2\n"
                "assert t.cell(0, 0).text.strip() == 'Item'\n"
                "assert t.cell(1, 0).text.strip() == 'Widgets'\n"
                "assert t.cell(1, 1).text.strip() == '100'\n"
            ),
        },
    ),
    Task(
        id="doc-py-csv",
        category="docs",
        fixtures={"sales.csv": "item,amount\nwidgets,100\ngadgets,250\ngizmos,400\n"},
        prompt=(
            "Create analyze.py that reads sales.csv, sums the amount column, and writes "
            "summary.json with integer keys total and items. Run it. Leave all three files."
        ),
        verify={
            "file_exists": ["analyze.py", "summary.json"],
            "py_check": (
                "import json\n"
                "with open('summary.json') as f:\n"
                "    data = json.load(f)\n"
                "assert data == {'total': 750, 'items': 3}, data\n"
            ),
        },
    ),
]


def _cell_value(text: str):
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _write_docx(path: str, spec: str) -> None:
    from docx import Document

    doc = Document()
    for line in spec.splitlines():
        if line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.strip():
            doc.add_paragraph(line)
    doc.save(path)


def _write_xlsx(path: str, spec: str) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for line in spec.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        sheet = parts[0].strip()
        if sheet not in wb.sheetnames:
            wb.create_sheet(sheet)
        wb[sheet].append([_cell_value(cell) for cell in parts[1:]])
    wb.save(path)


def _write_pdf(path: str, spec: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    story: list = []
    rows: list[list[str]] = []

    def flush_table() -> None:
        if not rows:
            return
        table = Table(rows, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 8))
        rows.clear()

    for line in spec.splitlines():
        if line.strip() == "TABLE":
            continue
        if line.strip().startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
            continue
        flush_table()
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.strip():
            story.append(Paragraph(line, styles["BodyText"]))
            story.append(Spacer(1, 6))
    flush_table()
    SimpleDocTemplate(path, pagesize=A4).build(story)


def _write_fixture(path: str, spec: str) -> None:
    if path.endswith(".docx"):
        _write_docx(path, spec)
    elif path.endswith(".xlsx"):
        _write_xlsx(path, spec)
    elif path.endswith(".pdf"):
        _write_pdf(path, spec)
    else:
        Path(path).write_text(spec, encoding="utf-8")


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
    "Server disconnected",
    "Server disconnected without sending a response",
    "RemoteProtocolError",
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
        os.makedirs(os.path.dirname(p) or work, exist_ok=True)
        Path(p).write_text(content)
    for rel, spec in task.fixtures.items():
        p = os.path.join(work, rel)
        os.makedirs(os.path.dirname(p) or work, exist_ok=True)
        _write_fixture(p, spec)

    cmd = build_cmd(agent, task.prompt, work)
    env = {
        **os.environ,
        "NO_COLOR": "1",
        "TERM": "dumb",
        "PWD": work,
        "OLDPWD": work,
        "OPENLAOKE_STATS": "1",
        "PATH": os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""),
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
    if agent == "openlaoke" or agent.startswith("openlaoke-"):
        variant = agent.split("-", 1)[1] if "-" in agent else ""
        exe = sys.executable
        if variant == "2b":
            return [
                exe,
                "-m",
                "openlaoke",
                "-c",
                work,
                "-m",
                LOCAL_MODEL,
                "--provider",
                "openai_compatible",
                "--base-url",
                "http://127.0.0.1:11434/v1",
                "--api-key",
                "local",
                "--no-proxy",
                "-p",
                "bypass",
                "--mode",
                "pi",
                "--max-tokens",
                "2048",
                prompt,
            ]
        if variant in ("glm", "cloud"):
            return [
                exe,
                "-m",
                "openlaoke",
                "-c",
                work,
                "-m",
                "glm-5.3",
                "--provider",
                "ollama_cloud",
                "--no-proxy",
                "-p",
                "bypass",
                "--mode",
                "balanced",
                "--max-tokens",
                "4096",
                prompt,
            ]
        cmd = [
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
        ]
        if variant:
            cmd.extend(["--mode", variant])
        cmd.append(prompt)
        return cmd
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
    if agent == "pi":
        provider = os.environ.get("OPENLAOKE_BENCH_PI_PROVIDER", "halogen-proxy")
        return [
            "pi",
            "--print",
            "--no-session",
            "--provider",
            provider,
            "--model",
            HALOGEN_MODEL,
            "--thinking",
            os.environ.get("OPENLAOKE_BENCH_PI_THINKING", "low"),
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
