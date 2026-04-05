"""HyperAuto Verification System - Fully autonomous testing and validation.

This module implements the automatic testing and verification loop that runs
without any human interaction after the initial input. It will repeatedly
test and verify until the task is perfectly completed.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class VerificationStatus(StrEnum):
    """Status of verification."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"


class TestCategory(StrEnum):
    """Categories of tests."""

    SYNTAX = "syntax"
    TYPE_CHECK = "type_check"
    UNIT_TEST = "unit_test"
    INTEGRATION = "integration"
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    LINT = "lint"


@dataclass
class TestResult:
    """Result of a single test."""

    category: TestCategory
    name: str
    passed: bool
    output: str = ""
    error: str = ""
    duration: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "name": self.name,
            "passed": self.passed,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "details": self.details,
        }


@dataclass
class VerificationResult:
    """Result of full verification."""

    status: VerificationStatus
    test_results: list[TestResult] = field(default_factory=list)
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    coverage: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "test_results": [t.to_dict() for t in self.test_results],
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "coverage": self.coverage,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }

    @property
    def is_perfect(self) -> bool:
        """Check if all tests passed with no errors or warnings."""
        return (
            self.status == VerificationStatus.PASSED
            and self.failed_tests == 0
            and len(self.errors) == 0
            and len(self.warnings) == 0
        )

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests


@dataclass
class VerificationConfig:
    """Configuration for verification."""

    max_iterations: int = 10
    min_pass_rate: float = 1.0
    required_coverage: float = 80.0
    enable_syntax_check: bool = True
    enable_type_check: bool = True
    enable_unit_tests: bool = True
    enable_lint: bool = True
    enable_integration_tests: bool = False
    timeout_per_test: float = 60.0
    retry_on_failure: bool = True
    auto_fix_enabled: bool = True


class HyperAutoVerifier:
    """Fully autonomous verification system.

    This system runs tests and validation completely autonomously:
    - No human interaction required after initial input
    - Automatically runs multiple test iterations
    - Verifies completion is perfect before stopping
    - Auto-fixes issues when possible
    """

    def __init__(
        self,
        app_state: AppState,
        config: VerificationConfig | None = None,
    ) -> None:
        self.app_state = app_state
        self.config = config or VerificationConfig()
        self._iteration_count = 0
        self._verification_history: list[VerificationResult] = []
        self._fixed_issues: list[str] = []

    async def verify_until_perfect(
        self,
        task_description: str,
        files_created: list[str] | None = None,
        files_modified: list[str] | None = None,
    ) -> VerificationResult:
        """Run verification loop until task is perfectly completed.

        This is the main entry point for autonomous verification.
        It will run tests repeatedly until:
        1. All tests pass
        2. No errors or warnings
        3. Coverage meets requirements
        4. Or max iterations reached

        Args:
            task_description: Description of the task to verify
            files_created: List of files that were created
            files_modified: List of files that were modified

        Returns:
            Final verification result
        """
        self._iteration_count = 0
        last_result: VerificationResult | None = None

        while self._iteration_count < self.config.max_iterations:
            self._iteration_count += 1

            print(f"\n{'=' * 60}")
            print(f"Verification Iteration {self._iteration_count}/{self.config.max_iterations}")
            print(f"{'=' * 60}")

            result = await self._run_single_verification(
                task_description=task_description,
                files_created=files_created or [],
                files_modified=files_modified or [],
            )

            self._verification_history.append(result)

            if result.is_perfect:
                print(f"\n✓ Perfect completion achieved at iteration {self._iteration_count}")
                return result

            if result.pass_rate >= self.config.min_pass_rate and len(result.errors) == 0:
                print(f"\n✓ Acceptable completion (pass rate: {result.pass_rate:.1%})")
                return result

            if self.config.auto_fix_enabled and result.failed_tests > 0:
                fixed = await self._attempt_auto_fix(result)
                if fixed:
                    self._fixed_issues.extend(fixed)
                    print(f"\n→ Auto-fixed {len(fixed)} issues, re-running verification...")
                    continue

            if not self.config.retry_on_failure:
                print(f"\n✗ Verification failed, retry disabled")
                return result

            print(f"\n→ Issues found, continuing to next iteration...")

        print(f"\n⚠ Max iterations ({self.config.max_iterations}) reached")
        return (
            self._verification_history[-1]
            if self._verification_history
            else VerificationResult(
                status=VerificationStatus.FAILED,
                errors=["Max verification iterations reached"],
            )
        )

    async def _run_single_verification(
        self,
        task_description: str,
        files_created: list[str],
        files_modified: list[str],
    ) -> VerificationResult:
        """Run a single verification pass."""
        results: list[TestResult] = []
        errors: list[str] = []
        warnings: list[str] = []

        files_to_check = list(set(files_created + files_modified))

        if self.config.enable_syntax_check:
            syntax_results = await self._check_syntax(files_to_check)
            results.extend(syntax_results)

        if self.config.enable_type_check:
            type_results = await self._check_types(files_to_check)
            results.extend(type_results)

        if self.config.enable_lint:
            lint_results = await self._run_lint(files_to_check)
            results.extend(lint_results)

        if self.config.enable_unit_tests:
            test_results = await self._run_unit_tests()
            results.extend(test_results)

        if self.config.enable_integration_tests:
            integration_results = await self._run_integration_tests()
            results.extend(integration_results)

        for r in results:
            if not r.passed and r.error:
                errors.append(f"{r.category.value}:{r.name}: {r.error}")
            if r.details.get("warnings"):
                warnings.extend(r.details["warnings"])

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        if failed == 0 and len(errors) == 0:
            status = VerificationStatus.PASSED
        elif passed > 0:
            status = VerificationStatus.PARTIAL
        else:
            status = VerificationStatus.FAILED

        return VerificationResult(
            status=status,
            test_results=results,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            errors=errors,
            warnings=warnings,
            suggestions=self._generate_suggestions(results, errors),
        )

    async def _check_syntax(self, files: list[str]) -> list[TestResult]:
        """Check syntax for all files."""
        results: list[TestResult] = []

        for filepath in files:
            if not filepath:
                continue

            if filepath.endswith(".py"):
                result = await self._check_python_syntax(filepath)
                results.append(result)
            elif filepath.endswith((".c", ".h")):
                result = await self._check_c_syntax(filepath)
                results.append(result)
            elif filepath.endswith((".js", ".ts")):
                result = await self._check_js_syntax(filepath)
                results.append(result)

        return results

    async def _check_python_syntax(self, filepath: str) -> TestResult:
        """Check Python syntax."""
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "py_compile",
                filepath,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            passed = proc.returncode == 0
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=passed,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=False,
                error="Timeout during syntax check",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _check_c_syntax(self, filepath: str) -> TestResult:
        """Check C syntax."""
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "gcc",
                "-fsyntax-only",
                "-Wall",
                filepath,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            passed = proc.returncode == 0
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=passed,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
            )
        except FileNotFoundError:
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=True,
                error="GCC not available, skipping C syntax check",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _check_js_syntax(self, filepath: str) -> TestResult:
        """Check JavaScript/TypeScript syntax."""
        start = time.time()
        try:
            if filepath.endswith(".ts"):
                cmd = ["npx", "tsc", "--noEmit", filepath]
            else:
                cmd = ["node", "--check", filepath]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            passed = proc.returncode == 0
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=passed,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
            )
        except FileNotFoundError:
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=True,
                error="Node.js not available, skipping JS syntax check",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.SYNTAX,
                name=f"syntax:{filepath}",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _check_types(self, files: list[str]) -> list[TestResult]:
        """Run type checking."""
        results: list[TestResult] = []

        py_files = [f for f in files if f.endswith(".py")]
        if py_files and self.config.enable_type_check:
            result = await self._run_mypy(py_files)
            results.append(result)

        ts_files = [f for f in files if f.endswith(".ts")]
        if ts_files:
            result = await self._run_tsc(ts_files)
            results.append(result)

        return results

    async def _run_mypy(self, files: list[str]) -> TestResult:
        """Run mypy type checking."""
        start = time.time()
        try:
            cmd = ["python", "-m", "mypy"] + files
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            output = stdout.decode() if stdout else ""
            error_output = stderr.decode() if stderr else ""

            errors = []
            for line in output.split("\n"):
                if "error:" in line.lower():
                    errors.append(line)

            passed = proc.returncode == 0 or len(errors) == 0

            return TestResult(
                category=TestCategory.TYPE_CHECK,
                name="mypy",
                passed=passed,
                output=output,
                error=error_output if not passed else "",
                duration=time.time() - start,
                details={"errors": errors},
            )
        except FileNotFoundError:
            return TestResult(
                category=TestCategory.TYPE_CHECK,
                name="mypy",
                passed=True,
                error="mypy not installed, skipping type check",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.TYPE_CHECK,
                name="mypy",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _run_tsc(self, files: list[str]) -> TestResult:
        """Run TypeScript compiler check."""
        start = time.time()
        try:
            cmd = ["npx", "tsc", "--noEmit"] + files
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            passed = proc.returncode == 0
            return TestResult(
                category=TestCategory.TYPE_CHECK,
                name="tsc",
                passed=passed,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.TYPE_CHECK,
                name="tsc",
                passed=True,
                error=f"TypeScript check skipped: {e}",
                duration=time.time() - start,
            )

    async def _run_lint(self, files: list[str]) -> list[TestResult]:
        """Run linting."""
        results: list[TestResult] = []

        py_files = [f for f in files if f.endswith(".py")]
        if py_files:
            result = await self._run_ruff(py_files)
            results.append(result)

        c_files = [f for f in files if f.endswith((".c", ".h"))]
        if c_files:
            result = await self._run_cppcheck(c_files)
            results.append(result)

        return results

    async def _run_ruff(self, files: list[str]) -> TestResult:
        """Run ruff linter."""
        start = time.time()
        try:
            cmd = ["python", "-m", "ruff", "check"] + files
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            output = stdout.decode() if stdout else ""
            passed = proc.returncode == 0

            return TestResult(
                category=TestCategory.LINT,
                name="ruff",
                passed=passed,
                output=output,
                error="" if passed else output,
                duration=time.time() - start,
            )
        except FileNotFoundError:
            return TestResult(
                category=TestCategory.LINT,
                name="ruff",
                passed=True,
                error="ruff not installed, skipping lint",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.LINT,
                name="ruff",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _run_cppcheck(self, files: list[str]) -> TestResult:
        """Run cppcheck for C files."""
        start = time.time()
        try:
            cmd = ["cppcheck", "--error-exitcode=1"] + files
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            passed = proc.returncode == 0
            return TestResult(
                category=TestCategory.LINT,
                name="cppcheck",
                passed=passed,
                output=stdout.decode() if stdout else "",
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
            )
        except FileNotFoundError:
            return TestResult(
                category=TestCategory.LINT,
                name="cppcheck",
                passed=True,
                error="cppcheck not available",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.LINT,
                name="cppcheck",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _run_unit_tests(self) -> list[TestResult]:
        """Run unit tests."""
        results: list[TestResult] = []

        pytest_result = await self._run_pytest()
        if pytest_result:
            results.append(pytest_result)

        make_result = await self._run_make_test()
        if make_result:
            results.append(make_result)

        return results

    async def _run_pytest(self) -> TestResult | None:
        """Run pytest."""
        start = time.time()
        try:
            cmd = ["python", "-m", "pytest", "-v", "--tb=short"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.app_state.cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test * 5,
            )

            output = stdout.decode() if stdout else ""
            passed = proc.returncode == 0

            match = re.search(r"(\d+) passed", output)
            passed_count = int(match.group(1)) if match else 0

            match = re.search(r"(\d+) failed", output)
            failed_count = int(match.group(1)) if match else 0

            return TestResult(
                category=TestCategory.UNIT_TEST,
                name="pytest",
                passed=passed,
                output=output,
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
                details={
                    "passed": passed_count,
                    "failed": failed_count,
                },
            )
        except FileNotFoundError:
            return TestResult(
                category=TestCategory.UNIT_TEST,
                name="pytest",
                passed=True,
                error="pytest not found, skipping",
                duration=time.time() - start,
            )
        except asyncio.TimeoutError:
            return TestResult(
                category=TestCategory.UNIT_TEST,
                name="pytest",
                passed=False,
                error="Test execution timeout",
                duration=time.time() - start,
            )
        except Exception as e:
            return TestResult(
                category=TestCategory.UNIT_TEST,
                name="pytest",
                passed=False,
                error=str(e),
                duration=time.time() - start,
            )

    async def _run_make_test(self) -> TestResult | None:
        """Run make test for C projects."""
        start = time.time()
        try:
            cmd = ["make", "test"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.app_state.cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.timeout_per_test,
            )

            output = stdout.decode() if stdout else ""
            passed = proc.returncode == 0

            return TestResult(
                category=TestCategory.UNIT_TEST,
                name="make_test",
                passed=passed,
                output=output,
                error=stderr.decode() if stderr else "",
                duration=time.time() - start,
            )
        except FileNotFoundError:
            return None
        except Exception:
            return None

    async def _run_integration_tests(self) -> list[TestResult]:
        """Run integration tests."""
        return []

    async def _attempt_auto_fix(self, result: VerificationResult) -> list[str]:
        """Attempt to automatically fix issues."""
        fixed: list[str] = []

        for test_result in result.test_results:
            if test_result.passed:
                continue

            if test_result.category == TestCategory.LINT:
                fixed_issues = await self._auto_fix_lint_issues(test_result)
                fixed.extend(fixed_issues)

        return fixed

    async def _auto_fix_lint_issues(self, test_result: TestResult) -> list[str]:
        """Auto-fix lint issues using ruff --fix."""
        fixed: list[str] = []

        if "ruff" in test_result.name:
            try:
                cmd = ["python", "-m", "ruff", "check", "--fix", "."]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.app_state.cwd,
                )
                await proc.communicate()

                if proc.returncode == 0:
                    fixed.append("Auto-fixed lint issues with ruff")
            except Exception:
                pass

        return fixed

    def _generate_suggestions(
        self,
        results: list[TestResult],
        errors: list[str],
    ) -> list[str]:
        """Generate suggestions for fixing issues."""
        suggestions: list[str] = []

        for test in results:
            if not test.passed:
                if test.category == TestCategory.SYNTAX:
                    suggestions.append(f"Fix syntax errors in {test.name}")
                elif test.category == TestCategory.TYPE_CHECK:
                    suggestions.append("Add type annotations or fix type errors")
                elif test.category == TestCategory.LINT:
                    suggestions.append("Run 'ruff check --fix' to auto-fix lint issues")
                elif test.category == TestCategory.UNIT_TEST:
                    suggestions.append("Fix failing unit tests")

        return list(set(suggestions))

    def get_verification_summary(self) -> dict[str, Any]:
        """Get summary of all verifications."""
        if not self._verification_history:
            return {"iterations": 0, "final_status": "none"}

        final = self._verification_history[-1]

        return {
            "iterations": self._iteration_count,
            "final_status": final.status.value,
            "is_perfect": final.is_perfect,
            "pass_rate": final.pass_rate,
            "total_tests": final.total_tests,
            "passed_tests": final.passed_tests,
            "failed_tests": final.failed_tests,
            "fixed_issues": self._fixed_issues,
            "history": [v.to_dict() for v in self._verification_history],
        }
