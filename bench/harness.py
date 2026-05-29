"""Benchmark harness for evaluating model performance on coding tasks.

Three suites: smoke (5 simple tasks), polyglot (19 multi-language tasks),
tool-use (10 multi-step tool tasks). Results persisted to bench/results/.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

SMOKE_TASKS = [
    {
        "id": "smoke-hello",
        "prompt": "Create a file hello.py that prints 'Hello, World!'",
        "verify": {"file_exists": "hello.py", "contains": "Hello, World!"},
    },
    {
        "id": "smoke-counter",
        "prompt": "Create a file counter.py with a function that returns 42",
        "verify": {"file_exists": "counter.py", "contains": "42"},
    },
    {
        "id": "smoke-readme",
        "prompt": "Create a README.md with the title '# Test Project'",
        "verify": {"file_exists": "README.md", "contains": "# Test Project"},
    },
    {
        "id": "smoke-json",
        "prompt": 'Create a config.json with {"version": "1.0"}',
        "verify": {"file_exists": "config.json", "contains": '"version"'},
    },
    {
        "id": "smoke-python-syntax",
        "prompt": "Create a file valid.py with: x = [1, 2, 3]; print(sum(x))",
        "verify": {"file_exists": "valid.py", "executable": "python valid.py"},
    },
]

POLYGLOT_TASKS = [
    {
        "id": "poly-py-function",
        "prompt": "Write a Python function add(a, b) that returns a + b in math.py",
        "verify": {"file_exists": "math.py", "contains": "def add"},
    },
    {
        "id": "poly-py-class",
        "prompt": "Write a Python class Dog with method bark() returning 'woof' in dog.py",
        "verify": {"file_exists": "dog.py", "contains": "class Dog"},
    },
    {
        "id": "poly-js-function",
        "prompt": "Write a JavaScript function multiply(a, b) that returns a * b in math.js",
        "verify": {"file_exists": "math.js", "contains": "function multiply"},
    },
    {
        "id": "poly-js-arrow",
        "prompt": "Write a JavaScript arrow function square = (n) => n * n in square.js",
        "verify": {"file_exists": "square.js", "contains": "=>"},
    },
    {
        "id": "poly-ts-interface",
        "prompt": "Write a TypeScript interface User with name: string and age: number in types.ts",
        "verify": {"file_exists": "types.ts", "contains": "interface User"},
    },
    {
        "id": "poly-bash-script",
        "prompt": "Write a bash script greet.sh that prints 'Hello from bash'",
        "verify": {"file_exists": "greet.sh", "contains": "Hello from bash"},
    },
    {
        "id": "poly-md-table",
        "prompt": "Create a markdown file table.md with a table: |Name|Age|",
        "verify": {"file_exists": "table.md", "contains": "|Name|Age|"},
    },
    {
        "id": "poly-json-config",
        "prompt": 'Create settings.json with {"debug": true, "port": 8080}',
        "verify": {"file_exists": "settings.json", "contains": '"debug"'},
    },
    {
        "id": "poly-py-listcomp",
        "prompt": "Write a Python list comprehension squares = [x*x for x in range(10)] in squares.py",
        "verify": {"file_exists": "squares.py", "contains": "x*x"},
    },
    {
        "id": "poly-js-array",
        "prompt": "Write JS code in numbers.js creating const nums = [1,2,3,4,5]",
        "verify": {"file_exists": "numbers.js", "contains": "1,2,3,4,5"},
    },
    {
        "id": "poly-css-style",
        "prompt": "Create a CSS file style.css with body { margin: 0; padding: 0; }",
        "verify": {"file_exists": "style.css", "contains": "body"},
    },
    {
        "id": "poly-yaml-config",
        "prompt": "Create a YAML file config.yaml with name: test and version: 1",
        "verify": {"file_exists": "config.yaml", "contains": "name:"},
    },
    {
        "id": "poly-toml-config",
        "prompt": "Create a TOML file data.toml with [owner] and name = 'admin'",
        "verify": {"file_exists": "data.toml", "contains": "[owner]"},
    },
    {
        "id": "poly-html-page",
        "prompt": "Create an HTML file page.html with <title>Test</title>",
        "verify": {"file_exists": "page.html", "contains": "<title>"},
    },
    {
        "id": "poly-py-decorator",
        "prompt": "Write a Python decorator @timer that prints execution time in timer.py",
        "verify": {"file_exists": "timer.py", "contains": "def timer"},
    },
    {
        "id": "poly-js-class",
        "prompt": "Write a JS class Car with constructor(make, model) in car.js",
        "verify": {"file_exists": "car.js", "contains": "class Car"},
    },
    {
        "id": "poly-py-import",
        "prompt": "Create main.py that imports print('done') and utils.py with def helper(): pass",
        "verify": {"file_exists": ["main.py", "utils.py"]},
    },
    {
        "id": "poly-rust-fn",
        "prompt": 'Create main.rs with fn main() { println!("rust"); }',
        "verify": {"file_exists": "main.rs", "contains": "fn main"},
    },
    {
        "id": "poly-go-fn",
        "prompt": 'Create main.go with package main; func main() { println("go") }',
        "verify": {"file_exists": "main.go", "contains": "package main"},
    },
]

TOOL_USE_TASKS = [
    {
        "id": "tool-read-write",
        "prompt": "Read data.txt and write its content to output.txt",
        "setup": {"write": {"data.txt": "sample data content"}},
        "verify": {"file_exists": "output.txt", "contains": "sample data content"},
    },
    {
        "id": "tool-multi-file",
        "prompt": "Create a.py with x=1, b.py with y=2, and c.py importing both",
        "verify": {"file_exists": ["a.py", "b.py", "c.py"]},
    },
    {
        "id": "tool-search-replace",
        "prompt": "In the file source.txt, replace all occurrences of 'old' with 'new'",
        "setup": {"write": {"source.txt": "old value\nold config\nkeep this\nold stuff"}},
        "verify": {"not_contains": "source.txt:old"},
    },
    {
        "id": "tool-grep-find",
        "prompt": "Create a file with TODO items, then search for all TODOs",
        "setup": {"write": {"tasks.txt": "TODO: fix bug\nDONE: deploy\nTODO: refactor"}},
        "verify": {"file_exists": "tasks.txt"},
    },
    {
        "id": "tool-directory",
        "prompt": "Create directories a/b/c and a file deep.txt inside c",
        "verify": {"file_exists": "a/b/c/deep.txt"},
    },
    {
        "id": "tool-json-edit",
        "prompt": "Read data.json and add a field 'new_field': true",
        "setup": {"write": {"data.json": '{"name": "test", "value": 1}'}},
        "verify": {"contains": "data.json:new_field"},
    },
    {
        "id": "tool-markdown-edit",
        "prompt": "Append '## Section 2' to the end of doc.md",
        "setup": {"write": {"doc.md": "# Title\nContent here."}},
        "verify": {"contains": "doc.md:## Section 2"},
    },
    {
        "id": "tool-git-init",
        "prompt": "Initialize a git repo and create .gitignore with *.pyc",
        "verify": {"file_exists": ".gitignore", "contains": "*.pyc"},
    },
    {
        "id": "tool-error-handle",
        "prompt": "Try to read nonexistent.txt, then create it with 'recovered'",
        "verify": {"file_exists": "nonexistent.txt"},
    },
    {
        "id": "tool-batch-ops",
        "prompt": "Create three files x.txt, y.txt, z.txt each containing their name",
        "verify": {"file_exists": ["x.txt", "y.txt", "z.txt"]},
    },
]


@dataclass
class TaskResult:
    task_id: str
    suite: str
    passed: bool
    score: float
    tool_calls: int = 0
    duration_ms: float = 0.0
    error: str = ""


@dataclass
class SuiteResult:
    suite: str
    total: int
    passed: int
    failed: int
    score: float
    results: list[TaskResult] = field(default_factory=list)
    duration_ms: float = 0.0
    tool_calls: int = 0


@dataclass
class HarnessResult:
    suites: list[SuiteResult] = field(default_factory=list)
    overall_score: float = 0.0
    total_tasks: int = 0
    total_passed: int = 0
    total_duration_ms: float = 0.0
    total_tool_calls: int = 0

    def to_dict(self) -> dict:
        return {
            "suites": [
                {
                    "suite": s.suite,
                    "total": s.total,
                    "passed": s.passed,
                    "failed": s.failed,
                    "score": s.score,
                    "duration_ms": s.duration_ms,
                    "tool_calls": s.tool_calls,
                    "results": [
                        {
                            "task_id": r.task_id,
                            "passed": r.passed,
                            "score": r.score,
                            "tool_calls": r.tool_calls,
                            "duration_ms": r.duration_ms,
                            "error": r.error,
                        }
                        for r in s.results
                    ],
                }
                for s in self.suites
            ],
            "overall_score": self.overall_score,
            "total_tasks": self.total_tasks,
            "total_passed": self.total_passed,
            "total_duration_ms": self.total_duration_ms,
            "total_tool_calls": self.total_tool_calls,
        }


def get_smoke_tasks() -> list[dict]:
    return SMOKE_TASKS


def get_polyglot_tasks() -> list[dict]:
    return POLYGLOT_TASKS


def get_tooluse_tasks() -> list[dict]:
    return TOOL_USE_TASKS


@dataclass
class TaskVerifier:
    def verify(self, task: dict, work_dir: str) -> tuple[bool, float, str]:
        verify = task.get("verify", {})
        checks: list[tuple[bool, float, str]] = []

        file_exists = verify.get("file_exists")
        if isinstance(file_exists, str):
            path = os.path.join(work_dir, file_exists)
            checks.append((os.path.exists(path), 1.0, f"file_exists: {file_exists}"))
        elif isinstance(file_exists, list):
            for fp in file_exists:
                path = os.path.join(work_dir, fp)
                checks.append((os.path.exists(path), 1.0, f"file_exists: {fp}"))

        contains = verify.get("contains")
        if isinstance(contains, str):
            parts = contains.split(":", 1)
            if len(parts) == 2:
                fn, text = parts
                path = os.path.join(work_dir, fn)
                if os.path.exists(path):
                    try:
                        with open(path) as f:
                            content = f.read()
                        checks.append((text in content, 1.0, f"contains: {contains}"))
                    except Exception as e:
                        checks.append((False, 0.0, f"read error: {e}"))
                else:
                    checks.append((False, 0.0, f"file not found: {fn}"))
            else:
                for root, _, files in os.walk(work_dir):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        try:
                            with open(fp) as f:
                                if contains in f.read():
                                    checks.append((True, 1.0, f"contains in {fn}: {contains}"))
                                    break
                        except Exception:
                            continue
                    else:
                        continue
                    break
                else:
                    checks.append((False, 0.0, f"contains no file: {contains}"))

        not_contains = verify.get("not_contains")
        if isinstance(not_contains, str):
            parts = not_contains.split(":", 1)
            if len(parts) == 2:
                fn, text = parts
                path = os.path.join(work_dir, fn)
                if os.path.exists(path):
                    try:
                        with open(path) as f:
                            content = f.read()
                        checks.append((text not in content, 1.0, f"not_contains: {not_contains}"))
                    except Exception as e:
                        checks.append((False, 0.0, f"read error: {e}"))

        executable = verify.get("executable")
        if isinstance(executable, str):
            import subprocess

            try:
                result = subprocess.run(
                    executable.split(), cwd=work_dir, capture_output=True, text=True, timeout=10
                )
                checks.append((result.returncode == 0, 1.0, f"executable: {executable}"))
            except Exception as e:
                checks.append((False, 0.0, f"exec error: {e}"))

        if not checks:
            return (False, 0.0, "no verification criteria")
        total_score = sum(s for _, s, _ in checks) / len(checks)
        all_passed = all(p for p, _, _ in checks)
        errors = "; ".join(e for p, _, e in checks if not p)
        return (all_passed, total_score, errors)


@dataclass
class HarnessRunner:
    results_dir: str = ""
    task_verifier: TaskVerifier = field(default_factory=TaskVerifier)

    def get_results_dir(self) -> str:
        if self.results_dir:
            return self.results_dir
        return os.path.join(os.getcwd(), "bench", "results")

    async def run_suite(
        self,
        suite_name: str,
        tasks: list[dict],
        agent_callable,
        work_dir: str,
    ) -> SuiteResult:
        results = []
        passed = 0
        failed = 0
        total_score = 0.0
        total_duration = 0.0
        total_tool_calls = 0

        for task in tasks:
            start = time.time()
            try:
                await agent_callable(task["prompt"])
                calls = 0
                ok, score, error = self.task_verifier.verify(task, work_dir)
                duration = (time.time() - start) * 1000

                if ok:
                    passed += 1
                else:
                    failed += 1
                total_score += score
                total_duration += duration
                total_tool_calls += calls
                results.append(
                    TaskResult(
                        task_id=task["id"],
                        suite=suite_name,
                        passed=ok,
                        score=score,
                        tool_calls=calls,
                        duration_ms=duration,
                        error=error,
                    )
                )
            except Exception as e:
                failed += 1
                duration = (time.time() - start) * 1000
                total_duration += duration
                results.append(
                    TaskResult(
                        task_id=task["id"],
                        suite=suite_name,
                        passed=False,
                        score=0.0,
                        duration_ms=duration,
                        error=str(e),
                    )
                )

        return SuiteResult(
            suite=suite_name,
            total=len(tasks),
            passed=passed,
            failed=failed,
            score=total_score / max(len(tasks), 1),
            results=results,
            duration_ms=total_duration,
            tool_calls=total_tool_calls,
        )

    def save_result(self, result: HarnessResult, run_id: str = "") -> str:
        d = self.get_results_dir()
        os.makedirs(d, exist_ok=True)
        if not run_id:
            run_id = time.strftime("%Y%m%d-%H%M%S")
        fp = os.path.join(d, f"{run_id}.json")
        with open(fp, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        return fp
