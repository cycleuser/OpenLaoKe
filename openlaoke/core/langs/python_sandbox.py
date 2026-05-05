"""Enhanced Python sandbox with static analysis and structured output."""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisResult:
    tool: str  # "mypy", "ruff", "pylint"
    severity: str  # "error", "warning", "info"
    line: int | None = None
    column: int | None = None
    message: str = ""
    code: str | None = None


@dataclass
class StructuredResult:
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    exec_ms: float = 0.0
    mem_kb: int | None = None
    analysis: list[AnalysisResult] = field(default_factory=list)
    test_result: dict[str, Any] = field(default_factory=dict)
    retry_suggested: bool = False
    improved_code: str | None = None


class PythonSandbox:
    """Enhanced sandbox with static analysis and structured feedback."""

    STATIC_ANALYZERS = ["mypy", "ruff"]
    TEST_RUNNER = "pytest"

    def run(
        self,
        code: str,
        timeout_ms: int = 30000,
        mem_mb: int = 256,
        workdir: str | None = None,
        run_static_analysis: bool = True,
        run_tests: bool = False,
        test_code: str | None = None,
    ) -> StructuredResult:
        start = time.time()
        tmp_path: str | None = None
        try:
            cleaned = self._clean_code(code)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(cleaned)
                tmp_path = tmp.name

            timeout_sec = timeout_ms / 1000.0
            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=workdir or os.getcwd(),
            )
            elapsed = (time.time() - start) * 1000.0

            analysis: list[AnalysisResult] = []
            if run_static_analysis:
                analysis = self._run_static_analysis(tmp_path, timeout_sec)

            test_info: dict[str, Any] = {}
            if run_tests:
                test_info = self._run_tests(tmp_path, timeout_sec)
            elif test_code:
                test_info = self._run_custom_tests(tmp_path, test_code, timeout_sec)

            return StructuredResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exec_ms=elapsed,
                analysis=analysis,
                test_result=test_info,
                retry_suggested=(
                    result.returncode != 0 or any(a.severity == "error" for a in analysis)
                ),
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start) * 1000.0
            return StructuredResult(
                success=False,
                exit_code=-1,
                stderr=f"Timeout after {timeout_ms}ms",
                exec_ms=elapsed,
                retry_suggested=False,
            )
        except Exception as e:
            return StructuredResult(
                success=False,
                exit_code=-1,
                stderr=str(e),
                exec_ms=0.0,
                retry_suggested=False,
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)

    def _clean_code(self, code: str) -> str:
        code = code.strip()
        code = re.sub(r"^```(?:python|py)?\s*\n", "", code)
        code = re.sub(r"\n```\s*$", "", code)
        return code

    def _run_static_analysis(self, filepath: str, timeout_sec: float) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        cwd = os.path.dirname(filepath) or os.getcwd()

        for tool in self.STATIC_ANALYZERS:
            try:
                if tool == "mypy":
                    r = subprocess.run(
                        ["mypy", "--strict", filepath],
                        capture_output=True,
                        text=True,
                        timeout=timeout_sec,
                        cwd=cwd,
                    )
                    results.extend(self._parse_mypy_output(r.stdout, r.stderr))
                elif tool == "ruff":
                    r = subprocess.run(
                        ["ruff", "check", filepath, "--output-format=json"],
                        capture_output=True,
                        text=True,
                        timeout=timeout_sec,
                        cwd=cwd,
                    )
                    results.extend(self._parse_ruff_output(r.stdout))
            except FileNotFoundError:
                continue
            except Exception:
                continue
        return results

    def _parse_mypy_output(self, stdout: str, stderr: str) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        combined = (stdout or "") + "\n" + (stderr or "")
        for line in combined.splitlines():
            if "error:" in line.lower() or "warning:" in line.lower():
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    try:
                        line_no = int(parts[0].split()[-1])
                    except ValueError:
                        line_no = None
                    severity = "error" if "error" in line.lower() else "warning"
                    results.append(
                        AnalysisResult(
                            tool="mypy",
                            severity=severity,
                            line=line_no,
                            message=parts[2].strip(),
                        )
                    )
        return results

    def _parse_ruff_output(self, stdout: str) -> list[AnalysisResult]:
        results: list[AnalysisResult] = []
        try:
            data = json.loads(stdout) if stdout else []
            if isinstance(data, list):
                for item in data:
                    results.append(
                        AnalysisResult(
                            tool="ruff",
                            severity=item.get("type", "warning"),
                            line=item.get("location", {}).get("row"),
                            column=item.get("location", {}).get("column"),
                            message=item.get("message", ""),
                            code=item.get("code"),
                        )
                    )
        except Exception:
            pass
        return results

    def _run_tests(self, filepath: str, timeout_sec: float) -> dict[str, Any]:
        cwd = os.path.dirname(filepath) or os.getcwd()
        try:
            result = subprocess.run(
                ["pytest", filepath, "-v", "--tb=short", "--maxfail=3"],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=cwd,
            )
            return {
                "passed": result.returncode == 0,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
            }
        except FileNotFoundError:
            return {"passed": False, "error": "pytest not found"}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _run_custom_tests(
        self, filepath: str, test_code: str, timeout_sec: float
    ) -> dict[str, Any]:
        test_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_test.py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(test_code)
                test_path = tmp.name
            result = subprocess.run(
                ["python3", test_path],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            return {
                "passed": result.returncode == 0,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
            }
        except Exception as e:
            return {"passed": False, "error": str(e)}
        finally:
            if test_path and os.path.exists(test_path):
                with contextlib.suppress(OSError):
                    os.unlink(test_path)


SandboxResult = StructuredResult  # alias for backward compat
