#!/usr/bin/env python3
"""SOTA code ability evaluation for small models (0.8B Qwen3.5 vs baseline).

Compares:
1. Direct LLM output (no tooling)
2. LLM + OpenLaoKe CodeRunner (static analysis + sandbox + iterative refinement)
3. Tests across Python, C, Rust at 3 difficulty levels
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

# ── model config ──────────────────────────────────────────
MODEL_NAME = "huihui_ai/qwen3.5-abliterated:0.8B"
OLLAMA_API = "http://localhost:11434"
TIMEOUT = 120

# ── test cases ────────────────────────────────────────────
@dataclass
class TestCase:
    id: str
    language: str
    description: str
    prompt: str
    difficulty: str  # "easy", "medium", "hard"
    expected_output: str | None = None
    expected_keywords: list[str] = field(default_factory=list)


TEST_CASES = [
    # ─── Python ─────────────────────────────────────────
    TestCase(
        id="py_e1",
        language="python",
        description="Fibonacci function",
        prompt="Write a Python function fib(n) that returns the n-th Fibonacci number. Include a main block that prints fib(10).",
        difficulty="easy",
        expected_keywords=["def fib", "return", "print", "55"],
    ),
    TestCase(
        id="py_e2", 
        language="python",
        description="List comprehension filter",
        prompt="Write Python code that takes a list of numbers and returns only the even numbers squared. Print the result for [1,2,3,4,5,6].",
        difficulty="easy",
        expected_keywords=["def", "return", "print", "4", "16", "36"],
    ),
    TestCase(
        id="py_m1",
        language="python",
        description="Word frequency counter",
        prompt="""Write a Python function word_frequency(text) that:
1. Splits text into words
2. Counts frequency of each word (case-insensitive)
3. Returns dict sorted by frequency descending
Test with: "the cat and the dog and the mouse"
Expected: {"the": 3, "and": 2, "cat": 1, "dog": 1, "mouse": 1}""",
        difficulty="medium",
        expected_keywords=["def word_frequency", "split", "lower", "sorted", "3", "the"],
    ),
    TestCase(
        id="py_h1",
        language="python",
        description="Binary search tree",
        prompt="""Write a Python class BST with:
- insert(val) method
- search(val) method that returns True/False  
- inorder() method that returns sorted list
Test with: insert 5,3,7,1,4; then search(4) and inorder()""",
        difficulty="hard",
        expected_keywords=["class", "insert", "search", "inorder", "True"],
    ),

    # ─── C ─────────────────────────────────────────────
    TestCase(
        id="c_e1",
        language="c",
        description="Hello + sum",
        prompt="Write a C program with a main() that prints 'Hello from C' then computes and prints the sum of 1 to 100.",
        difficulty="easy",
        expected_keywords=["#include", "int main", "printf", "5050"],
    ),
    TestCase(
        id="c_m1",
        language="c",
        description="String reverse",
        prompt="Write a C function void reverse_string(char* s) that reverses a string in-place. Include a main() that tests it with 'hello' and prints the result.",
        difficulty="medium",
        expected_keywords=["include", "string", "reverse", "strlen", "temp"],
    ),

    # ─── Rust ───────────────────────────────────────────
    TestCase(
        id="rs_e1",
        language="rust",
        description="Hello + vector sum",
        prompt="Write a Rust program with fn main() that creates a Vec<i32> with [1,2,3,4,5] and prints the sum using .iter().sum().",
        difficulty="easy",
        expected_keywords=["fn main", "Vec", "iter", "sum", "println"],
    ),
]


@dataclass
class TestResult:
    test_id: str
    passed: bool
    language: str
    difficulty: str
    mode: str  # "direct" or "tooled"
    output: str = ""
    code: str = ""
    exec_result: str = ""
    analysis: str = ""
    duration_ms: float = 0.0


# ── baseline: direct LLM call ────────────────────────────
async def test_direct(test: TestCase) -> TestResult:
    start = time.time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
        response = await client.post(
            f"{OLLAMA_API}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": f"You are a {test.language.upper()} expert. {test.prompt}\nOnly output the code, no explanation.",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512},
            },
        )
        data = response.json()
        code = data.get("response", "").strip()
        code = _extract_code(code, test.language)

    duration = (time.time() - start) * 1000
    return TestResult(
        test_id=test.id,
        passed=_check_keywords(code, test.expected_keywords),
        language=test.language,
        difficulty=test.difficulty,
        mode="direct",
        code=code,
        duration_ms=duration,
    )


# ── tooled: LLM + CodeRunner ─────────────────────────────
async def test_tooled(test: TestCase) -> TestResult:
    start = time.time()
    code = ""
    exec_output = ""
    analysis_output = ""

    # Step 1: Get code from LLM
    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
        response = await client.post(
            f"{OLLAMA_API}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": (
                    f"You are a {test.language.upper()} expert. {test.prompt}\n"
                    "Output ONLY the code inside ``` markers. No explanation."
                ),
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512},
            },
        )
        data = response.json()
        code = _extract_code(data.get("response", ""), test.language)

    # Step 2: Static analysis + sandbox execution
    if test.language == "python":
        exec_output, analysis_output = _run_python(code, test.expected_keywords)
    elif test.language == "c":
        exec_output, analysis_output = _run_c(code)
    elif test.language == "rust":
        exec_output, analysis_output = _run_rust(code)

    # Step 3: If failed, iterative refinement (max 2 more rounds)
    for round_num in range(1, 3):
        passed = _check_keywords(
            code, test.expected_keywords
        ) and "error" not in exec_output.lower()[:200]
        if passed:
            break

        # Feed error back to LLM
        feedback = f"Your {test.language} code failed. Error:\n{exec_output}"
        if analysis_output:
            feedback += f"\nStatic analysis:\n{analysis_output}"
        feedback += "\nFix the code. Output ONLY corrected code in ``` markers."

        async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
            response = await client.post(
                f"{OLLAMA_API}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": f"Original code:\n```\n{code}\n```\n\n{feedback}",
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512},
                },
            )
            data2 = response.json()
            new_code = _extract_code(data2.get("response", ""), test.language)
            if new_code and new_code != code:
                code = new_code
                if test.language == "python":
                    exec_output, analysis_output = _run_python(code, test.expected_keywords)
                elif test.language == "c":
                    exec_output, analysis_output = _run_c(code)
                elif test.language == "rust":
                    exec_output, analysis_output = _run_rust(code)

    duration = (time.time() - start) * 1000
    passed = _check_keywords(code, test.expected_keywords) or _check_exec_success(code, test.language)
    return TestResult(
        test_id=test.id,
        passed=passed,
        language=test.language,
        difficulty=test.difficulty,
        mode="tooled",
        code=code,
        exec_result=exec_output,
        analysis=analysis_output,
        duration_ms=duration,
    )


def _extract_code(text: str, language: str) -> str:
    import re

    m = re.search(r"```(?:\w*\n)?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _check_exec_success(code: str, language: str) -> bool:
    from openlaoke.core.langs.python_sandbox import PythonSandbox
    from openlaoke.core.langs.c_sandbox import CSandbox
    try:
        if language == 'python':
            sb = PythonSandbox()
            result = sb.run(code=code, timeout_ms=5000)
            return result.success and bool(result.stdout.strip())
        elif language == 'c':
            sb = CSandbox()
            result = sb.run(code=code, timeout_ms=5000)
            return result.success
        return False
    except Exception:
        return False

def _check_keywords(code: str, keywords: list[str]) -> bool:
    if not keywords:
        return bool(code.strip())
    code_lower = code.lower() + "\n"
    return all(kw.lower() in code_lower for kw in keywords)


def _run_python(code: str, expected: list[str]) -> tuple[str, str]:
    from openlaoke.core.langs.python_sandbox import PythonSandbox

    sb = PythonSandbox()
    result = sb.run(code=code, timeout_ms=10000, run_static_analysis=True)

    exec_out = result.stdout or ""
    if result.stderr:
        exec_out += "\n[stderr]\n" + result.stderr[:1000]

    analysis_out = ""
    if result.analysis:
        analysis_out = "\n".join(
            f"[{a.tool}/{a.severity}] {a.message}" for a in result.analysis[:10]
        )

    return exec_out, analysis_out


def _run_c(code: str) -> tuple[str, str]:
    from openlaoke.core.langs.c_sandbox import CSandbox

    sb = CSandbox()
    result = sb.run(code=code, timeout_ms=10000)

    exec_out = result.stdout or ""
    if result.stderr:
        exec_out += "\n[stderr]\n" + result.stderr[:1000]
    if result.compile_messages:
        exec_out += "\n[compiler]\n" + "\n".join(
            f"[{m.severity}] {m.message}" for m in result.compile_messages[:10]
        )

    return exec_out, ""


def _run_rust(code: str) -> tuple[str, str]:
    from openlaoke.core.langs.rust_sandbox import RustSandbox

    sb = RustSandbox()
    result = sb.run(code=code, timeout_ms=30000)

    exec_out = result.stdout or ""
    if result.stderr:
        exec_out += "\n[stderr]\n" + result.stderr[:1000]
    if result.diagnostics:
        exec_out += "\n[diagnostics]\n" + "\n".join(
            f"[{d.severity}] {d.message}" for d in result.diagnostics[:10]
        )

    return exec_out, ""


async def main() -> None:
    print("=" * 70)
    print(f"SOTA Code Ability Evaluation")
    print(f"Model: {MODEL_NAME}")
    print(f"Test cases: {len(TEST_CASES)}")
    print("=" * 70)

    results: list[TestResult] = []

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {test.id} ({test.language}/{test.difficulty})")
        print(f"  Task: {test.description}")

        # Direct mode
        print("  [direct] Running...", end=" ", flush=True)
        try:
            r_direct = await test_direct(test)
            results.append(r_direct)
            print(f"{'PASS' if r_direct.passed else 'FAIL'} ({r_direct.duration_ms:.0f}ms)")
        except Exception as e:
            print(f"ERROR: {e}")

        # Tooled mode
        print("  [tooled] Running...", end=" ", flush=True)
        try:
            r_tooled = await test_tooled(test)
            results.append(r_tooled)
            print(f"{'PASS' if r_tooled.passed else 'FAIL'} ({r_tooled.duration_ms:.0f}ms)")
        except Exception as e:
            print(f"ERROR: {e}")

    # ── summary ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for mode in ["direct", "tooled"]:
        mode_results = [r for r in results if r.mode == mode]
        total = len(mode_results)
        passed = sum(1 for r in mode_results if r.passed)
        langs = {}
        for r in mode_results:
            langs.setdefault(r.language, {"total": 0, "passed": 0})
            langs[r.language]["total"] += 1
            langs[r.language]["passed"] += int(r.passed)
        diffs = {}
        for r in mode_results:
            diffs.setdefault(r.difficulty, {"total": 0, "passed": 0})
            diffs[r.difficulty]["total"] += 1
            diffs[r.difficulty]["passed"] += int(r.passed)

        print(f"\n[{mode.upper()}] Overall: {passed}/{total} ({100*passed//total}%) pass")
        for lang, stats in langs.items():
            print(f"  {lang}: {stats['passed']}/{stats['total']}")
        for d, stats in diffs.items():
            print(f"  {d}: {stats['passed']}/{stats['total']}")

    # ── comparison ───────────────────────────────────
    direct_pass = sum(1 for r in results if r.mode == "direct" and r.passed)
    tooled_pass = sum(1 for r in results if r.mode == "tooled" and r.passed)
    n = len(TEST_CASES)
    print(f"\nComparison: direct={direct_pass}/{n} vs tooled={tooled_pass}/{n}")
    if tooled_pass > direct_pass:
        print(f"Tooled IMPROVEMENT: +{tooled_pass - direct_pass} more passes")
    elif tooled_pass == direct_pass:
        print("No difference detected (model may be too small)")
    else:
        print(f"WARNING: Tooled is worse ({tooled_pass - direct_pass}) — check refinement logic")

    # ── export JSON ──────────────────────────────────
    export = {
        "model": MODEL_NAME,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": [
            {
                "id": r.test_id,
                "passed": r.passed,
                "lang": r.language,
                "diff": r.difficulty,
                "mode": r.mode,
                "code": r.code[:500],
                "exec_result": r.exec_result[:500],
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
    }
    path = os.path.expanduser("~/.openlaoke/eval_results.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(export, f, indent=2)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    asyncio.run(main())
