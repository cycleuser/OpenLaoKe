"""AutoTestRunner - Automated test detection, execution, and analysis.

This module provides comprehensive automated testing capabilities:
1. Test framework detection (pytest, jest, go test, cargo test, junit)
2. Test discovery and collection
3. Test execution with result capture
4. Coverage analysis
5. Failure diagnosis and auto-fix suggestions
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from uuid import uuid4


class TestFramework(StrEnum):
    """Supported test frameworks."""

    PYTEST = "pytest"
    JEST = "jest"
    MOCHA = "mocha"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"
    JUNIT = "junit"
    UNKNOWN = "unknown"


class TestStatus(StrEnum):
    """Status of a test."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    PENDING = "pending"
    RUNNING = "running"


class TestSeverity(StrEnum):
    """Severity of test failure."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    COSMETIC = "cosmetic"


@dataclass
class TestInfo:
    """Information about a single test."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    file_path: Path | None = None
    framework: TestFramework = TestFramework.UNKNOWN
    status: TestStatus = TestStatus.PENDING
    duration_ms: float = 0.0
    message: str = ""
    traceback: str = ""
    markers: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "file_path": str(self.file_path) if self.file_path else None,
            "framework": self.framework.value,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "traceback": self.traceback,
            "markers": self.markers,
            "dependencies": self.dependencies,
        }


@dataclass
class TestFailure:
    """Detailed information about a test failure."""

    test_id: str
    test_name: str
    file_path: Path | None = None
    error_type: str = ""
    error_message: str = ""
    traceback: str = ""
    line_number: int | None = None
    expected: str = ""
    actual: str = ""
    severity: TestSeverity = TestSeverity.MEDIUM
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "file_path": str(self.file_path) if self.file_path else None,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "traceback": self.traceback,
            "line_number": self.line_number,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity.value,
            "context": self.context,
        }


@dataclass
class TestResults:
    """Results from running a test suite."""

    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    tests: list[TestInfo] = field(default_factory=list)
    failures: list[TestFailure] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    framework: TestFramework = TestFramework.UNKNOWN
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "tests": [t.to_dict() for t in self.tests],
            "failures": [f.to_dict() for f in self.failures],
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "framework": self.framework.value,
            "timestamp": self.timestamp,
        }

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests * 100

    @property
    def is_success(self) -> bool:
        return self.failed == 0 and self.errors == 0


@dataclass
class TestAnalysis:
    """Analysis of test results."""

    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    slow_tests: list[TestInfo] = field(default_factory=list)
    flaky_tests: list[TestInfo] = field(default_factory=list)
    failure_patterns: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    coverage_percentage: float = 0.0
    quality_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "slow_tests": [t.to_dict() for t in self.slow_tests],
            "flaky_tests": [t.to_dict() for t in self.flaky_tests],
            "failure_patterns": self.failure_patterns,
            "recommendations": self.recommendations,
            "coverage_percentage": self.coverage_percentage,
            "quality_score": self.quality_score,
        }


@dataclass
class CoverageReport:
    """Coverage report data."""

    total_lines: int = 0
    covered_lines: int = 0
    percentage: float = 0.0
    files: dict[str, dict[str, Any]] = field(default_factory=dict)
    uncovered_files: list[str] = field(default_factory=list)
    branch_coverage: float = 0.0
    function_coverage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_lines": self.total_lines,
            "covered_lines": self.covered_lines,
            "percentage": self.percentage,
            "files": self.files,
            "uncovered_files": self.uncovered_files,
            "branch_coverage": self.branch_coverage,
            "function_coverage": self.function_coverage,
        }


@dataclass
class Diagnosis:
    """Diagnosis of a test failure."""

    failure_id: str
    root_cause: str = ""
    confidence: float = 0.0
    suggested_fix: str = ""
    fix_type: str = ""
    affected_files: list[Path] = field(default_factory=list)
    fix_commands: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    auto_fixable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "suggested_fix": self.suggested_fix,
            "fix_type": self.fix_type,
            "affected_files": [str(f) for f in self.affected_files],
            "fix_commands": self.fix_commands,
            "references": self.references,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class TestCycleResult:
    """Result of a full test cycle."""

    success: bool
    framework: TestFramework
    results: TestResults | None = None
    analysis: TestAnalysis | None = None
    coverage: CoverageReport | None = None
    diagnoses: list[Diagnosis] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)
    iterations: int = 0
    total_duration_ms: float = 0.0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "framework": self.framework.value,
            "results": self.results.to_dict() if self.results else None,
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "fixes_applied": self.fixes_applied,
            "iterations": self.iterations,
            "total_duration_ms": self.total_duration_ms,
            "message": self.message,
        }


class AutoTestRunner:
    """Automated test detection, execution, and analysis system."""

    FRAMEWORK_CONFIGS: dict[TestFramework, dict[str, Any]] = {
        TestFramework.PYTEST: {
            "detect_files": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
            "test_patterns": ["test_*.py", "*_test.py", "tests/*.py"],
            "run_command": ["pytest", "-v", "--tb=short"],
            "coverage_command": ["pytest", "--cov=.", "--cov-report=json"],
            "result_parser": "pytest",
        },
        TestFramework.JEST: {
            "detect_files": ["jest.config.js", "jest.config.ts", "package.json"],
            "test_patterns": ["*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"],
            "run_command": ["npm", "test", "--", "--verbose"],
            "coverage_command": ["npm", "test", "--", "--coverage", "--json"],
            "result_parser": "jest",
        },
        TestFramework.MOCHA: {
            "detect_files": ["mocha.opts", ".mocharc.json", ".mocharc.js", "package.json"],
            "test_patterns": ["*.test.js", "*.spec.js", "test/*.js"],
            "run_command": ["npm", "test"],
            "coverage_command": ["npx", "nyc", "--reporter=json", "npm", "test"],
            "result_parser": "mocha",
        },
        TestFramework.GO_TEST: {
            "detect_files": ["go.mod", "*_test.go"],
            "test_patterns": ["*_test.go"],
            "run_command": ["go", "test", "-v", "./..."],
            "coverage_command": ["go", "test", "-coverprofile=coverage.out", "./..."],
            "result_parser": "go",
        },
        TestFramework.CARGO_TEST: {
            "detect_files": ["Cargo.toml"],
            "test_patterns": ["tests/*.rs", "*_test.rs"],
            "run_command": ["cargo", "test", "--", "--nocapture"],
            "coverage_command": ["cargo", "tarpaulin", "--out", "Json"],
            "result_parser": "cargo",
        },
        TestFramework.JUNIT: {
            "detect_files": ["pom.xml", "build.gradle", "build.gradle.kts"],
            "test_patterns": ["*Test.java", "*Tests.java", "Test*.java"],
            "run_command": ["mvn", "test"],
            "coverage_command": ["mvn", "jacoco:report"],
            "result_parser": "junit",
        },
    }

    FAILURE_PATTERNS: dict[str, dict[str, Any]] = {
        "assertion_error": {
            "patterns": ["AssertionError", "assert", "expected", "actual"],
            "fix_type": "assertion",
            "auto_fixable": True,
        },
        "import_error": {
            "patterns": ["ImportError", "ModuleNotFoundError", "cannot find module"],
            "fix_type": "dependency",
            "auto_fixable": True,
        },
        "attribute_error": {
            "patterns": ["AttributeError", "has no attribute", "undefined"],
            "fix_type": "implementation",
            "auto_fixable": True,
        },
        "type_error": {
            "patterns": ["TypeError", "type mismatch", "wrong type"],
            "fix_type": "type_fix",
            "auto_fixable": True,
        },
        "value_error": {
            "patterns": ["ValueError", "invalid value", "invalid argument"],
            "fix_type": "value_fix",
            "auto_fixable": False,
        },
        "syntax_error": {
            "patterns": ["SyntaxError", "syntax error", "parse error"],
            "fix_type": "syntax",
            "auto_fixable": True,
        },
        "timeout_error": {
            "patterns": ["TimeoutError", "timeout", "timed out"],
            "fix_type": "performance",
            "auto_fixable": False,
        },
        "null_reference": {
            "patterns": ["NullPointerException", "NoneType", "null pointer", "undefined"],
            "fix_type": "null_check",
            "auto_fixable": True,
        },
    }

    def detect_test_framework(self, project_path: Path) -> TestFramework:
        """Detect the test framework used in a project."""
        if not project_path.exists() or not project_path.is_dir():
            return TestFramework.UNKNOWN

        files = set(os.listdir(project_path))

        for framework, config in self.FRAMEWORK_CONFIGS.items():
            if framework == TestFramework.UNKNOWN:
                continue
            detect_files = config.get("detect_files", [])
            for detect_file in detect_files:
                if detect_file in files:
                    if detect_file == "package.json":
                        return self._detect_js_framework(project_path / detect_file)
                    if detect_file in ("pom.xml", "build.gradle", "build.gradle.kts"):
                        return TestFramework.JUNIT
                    return framework

        for framework, config in self.FRAMEWORK_CONFIGS.items():
            if framework == TestFramework.UNKNOWN:
                continue
            test_patterns = config.get("test_patterns", [])
            for pattern in test_patterns:
                matches = list(project_path.glob(pattern))
                if matches:
                    return framework

        return TestFramework.UNKNOWN

    def _detect_js_framework(self, package_json: Path) -> TestFramework:
        """Detect JavaScript test framework from package.json."""
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            dev_deps = data.get("devDependencies", {})
            deps = data.get("dependencies", {})

            all_deps = {**deps, **dev_deps}

            if "jest" in all_deps:
                return TestFramework.JEST
            if "mocha" in all_deps:
                return TestFramework.MOCHA

            scripts = data.get("scripts", {})
            test_script = scripts.get("test", "")
            if "jest" in test_script:
                return TestFramework.JEST
            if "mocha" in test_script:
                return TestFramework.MOCHA

        except Exception:
            pass

        return TestFramework.UNKNOWN

    def discover_tests(self, project_path: Path) -> list[TestInfo]:
        """Discover all tests in a project."""
        framework = self.detect_test_framework(project_path)
        if framework == TestFramework.UNKNOWN:
            return []

        config = self.FRAMEWORK_CONFIGS.get(framework, {})
        test_patterns = config.get("test_patterns", [])
        tests: list[TestInfo] = []

        for pattern in test_patterns:
            for test_file in project_path.glob(pattern):
                if test_file.is_file():
                    file_tests = self._extract_tests_from_file(test_file, framework)
                    tests.extend(file_tests)

        return tests

    def _extract_tests_from_file(self, file_path: Path, framework: TestFramework) -> list[TestInfo]:
        """Extract individual tests from a test file."""
        tests: list[TestInfo] = []

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return tests

        if framework == TestFramework.PYTEST:
            tests.extend(self._extract_pytest_tests(file_path, content))
        elif framework in (TestFramework.JEST, TestFramework.MOCHA):
            tests.extend(self._extract_js_tests(file_path, content))
        elif framework == TestFramework.GO_TEST:
            tests.extend(self._extract_go_tests(file_path, content))
        elif framework == TestFramework.CARGO_TEST:
            tests.extend(self._extract_rust_tests(file_path, content))
        elif framework == TestFramework.JUNIT:
            tests.extend(self._extract_java_tests(file_path, content))

        return tests

    def _extract_pytest_tests(self, file_path: Path, content: str) -> list[TestInfo]:
        """Extract pytest test functions."""
        tests: list[TestInfo] = []

        class_pattern = re.compile(r"class\s+(\w+(?:Test|Tests)\w*)\s*[:\(]")
        func_pattern = re.compile(r"def\s+(test_\w+)\s*\(")

        classes = class_pattern.findall(content)
        funcs = func_pattern.findall(content)

        for func in funcs:
            test = TestInfo(
                name=func,
                file_path=file_path,
                framework=TestFramework.PYTEST,
                status=TestStatus.PENDING,
            )
            tests.append(test)

        for cls in classes:
            class_content = self._extract_class_content(content, cls)
            class_funcs = func_pattern.findall(class_content)
            for func in class_funcs:
                test = TestInfo(
                    name=f"{cls}.{func}",
                    file_path=file_path,
                    framework=TestFramework.PYTEST,
                    status=TestStatus.PENDING,
                )
                tests.append(test)

        return tests

    def _extract_class_content(self, content: str, class_name: str) -> str:
        """Extract content of a specific class."""
        pattern = re.compile(rf"class\s+{class_name}\s*[:\(].*?(?=class\s+\w|\Z)", re.DOTALL)
        match = pattern.search(content)
        return match.group(0) if match else ""

    def _extract_js_tests(self, file_path: Path, content: str) -> list[TestInfo]:
        """Extract JavaScript test definitions."""
        tests: list[TestInfo] = []

        patterns = [
            re.compile(r"(?:test|it)\s*\(\s*['\"]([^'\"]+)['\"]"),
            re.compile(r"describe\s*\(\s*['\"]([^'\"]+)['\"]"),
        ]

        for pattern in patterns:
            matches = pattern.findall(content)
            for match in matches:
                test = TestInfo(
                    name=match,
                    file_path=file_path,
                    framework=TestFramework.JEST,
                    status=TestStatus.PENDING,
                )
                tests.append(test)

        return tests

    def _extract_go_tests(self, file_path: Path, content: str) -> list[TestInfo]:
        """Extract Go test functions."""
        tests: list[TestInfo] = []

        pattern = re.compile(r"func\s+(Test\w+)\s*\(")
        matches = pattern.findall(content)

        for match in matches:
            test = TestInfo(
                name=match,
                file_path=file_path,
                framework=TestFramework.GO_TEST,
                status=TestStatus.PENDING,
            )
            tests.append(test)

        return tests

    def _extract_rust_tests(self, file_path: Path, content: str) -> list[TestInfo]:
        """Extract Rust test functions."""
        tests: list[TestInfo] = []

        patterns = [
            re.compile(r"#\[test\]\s*fn\s+(\w+)"),
            re.compile(r"#\[cfg\(test\)\]\s*mod\s+tests\s*\{([^}]+)\}"),
        ]

        for pattern in patterns:
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                test = TestInfo(
                    name=match,
                    file_path=file_path,
                    framework=TestFramework.CARGO_TEST,
                    status=TestStatus.PENDING,
                )
                tests.append(test)

        return tests

    def _extract_java_tests(self, file_path: Path, content: str) -> list[TestInfo]:
        """Extract Java test methods."""
        tests: list[TestInfo] = []

        patterns = [
            re.compile(r"@Test\s*public\s+void\s+(\w+)\s*\("),
            re.compile(r"public\s+void\s+(test\w+)\s*\("),
        ]

        for pattern in patterns:
            matches = pattern.findall(content)
            for match in matches:
                test = TestInfo(
                    name=match,
                    file_path=file_path,
                    framework=TestFramework.JUNIT,
                    status=TestStatus.PENDING,
                )
                tests.append(test)

        return tests

    def run_tests(self, tests: list[TestInfo], project_path: Path) -> TestResults:
        """Run discovered tests and collect results."""
        if not tests:
            return TestResults(framework=TestFramework.UNKNOWN)

        framework = self._get_common_framework(tests)
        config = self.FRAMEWORK_CONFIGS.get(framework, {})

        command = config.get("run_command", [])
        if not command:
            return TestResults(framework=framework)

        try:
            result = subprocess.run(
                command,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=600,
            )

            parsed_results = self._parse_test_results(result.stdout, result.stderr, framework)

            parsed_results.exit_code = result.returncode
            parsed_results.stdout = result.stdout
            parsed_results.stderr = result.stderr
            parsed_results.framework = framework

            return parsed_results

        except subprocess.TimeoutExpired:
            return TestResults(
                framework=framework,
                stderr="Test execution timed out",
                exit_code=-1,
            )
        except Exception as e:
            return TestResults(
                framework=framework,
                stderr=str(e),
                exit_code=-1,
            )

    def _get_common_framework(self, tests: list[TestInfo]) -> TestFramework:
        """Get the common framework from tests."""
        if not tests:
            return TestFramework.UNKNOWN
        return tests[0].framework

    def _parse_test_results(
        self, stdout: str, stderr: str, framework: TestFramework
    ) -> TestResults:
        """Parse test results from output."""
        if framework == TestFramework.PYTEST:
            return self._parse_pytest_results(stdout, stderr)
        elif framework in (TestFramework.JEST, TestFramework.MOCHA):
            return self._parse_js_results(stdout, stderr)
        elif framework == TestFramework.GO_TEST:
            return self._parse_go_results(stdout, stderr)
        elif framework == TestFramework.CARGO_TEST:
            return self._parse_cargo_results(stdout, stderr)
        elif framework == TestFramework.JUNIT:
            return self._parse_junit_results(stdout, stderr)

        return TestResults(framework=framework)

    def _parse_pytest_results(self, stdout: str, stderr: str) -> TestResults:
        """Parse pytest output."""
        results = TestResults(framework=TestFramework.PYTEST)

        passed_pattern = re.compile(r"(\d+)\s+passed")
        failed_pattern = re.compile(r"(\d+)\s+failed")
        skipped_pattern = re.compile(r"(\d+)\s+skipped")
        error_pattern = re.compile(r"(\d+)\s+error")

        passed_match = passed_pattern.search(stdout)
        failed_match = failed_pattern.search(stdout)
        skipped_match = skipped_pattern.search(stdout)
        error_match = error_pattern.search(stdout)

        if passed_match:
            results.passed = int(passed_match.group(1))
        if failed_match:
            results.failed = int(failed_match.group(1))
        if skipped_match:
            results.skipped = int(skipped_match.group(1))
        if error_match:
            results.errors = int(error_match.group(1))

        results.total_tests = results.passed + results.failed + results.skipped + results.errors

        failure_pattern = re.compile(r"FAILED\s+([^\s]+)\s*-")
        for match in failure_pattern.finditer(stdout):
            failure = TestFailure(
                test_id=uuid4().hex[:8],
                test_name=match.group(1),
                severity=TestSeverity.HIGH,
            )
            results.failures.append(failure)

        duration_pattern = re.compile(r"in\s+([\d.]+)\s*s")
        duration_match = duration_pattern.search(stdout)
        if duration_match:
            results.duration_ms = float(duration_match.group(1)) * 1000

        return results

    def _parse_js_results(self, stdout: str, stderr: str) -> TestResults:
        """Parse Jest/Mocha output."""
        results = TestResults(framework=TestFramework.JEST)

        passed_pattern = re.compile(r"(\d+)\s+passing")
        failed_pattern = re.compile(r"(\d+)\s+failing")
        skipped_pattern = re.compile(r"(\d+)\s+skipped")

        passed_match = passed_pattern.search(stdout + stderr)
        failed_match = failed_pattern.search(stdout + stderr)
        skipped_match = skipped_pattern.search(stdout + stderr)

        if passed_match:
            results.passed = int(passed_match.group(1))
        if failed_match:
            results.failed = int(failed_match.group(1))
        if skipped_match:
            results.skipped = int(skipped_match.group(1))

        results.total_tests = results.passed + results.failed + results.skipped

        return results

    def _parse_go_results(self, stdout: str, stderr: str) -> TestResults:
        """Parse go test output."""
        results = TestResults(framework=TestFramework.GO_TEST)

        output = stdout + stderr

        lines = output.splitlines()
        for line in lines:
            if "PASS" in line:
                results.passed += 1
            elif "FAIL" in line:
                results.failed += 1
            elif "SKIP" in line:
                results.skipped += 1

        results.total_tests = results.passed + results.failed + results.skipped

        return results

    def _parse_cargo_results(self, stdout: str, stderr: str) -> TestResults:
        """Parse cargo test output."""
        results = TestResults(framework=TestFramework.CARGO_TEST)

        output = stdout + stderr

        passed_pattern = re.compile(r"test result: ok\. (\d+) passed")
        failed_pattern = re.compile(r"test result: FAILED\. (\d+) failed")

        passed_match = passed_pattern.search(output)
        failed_match = failed_pattern.search(output)

        if passed_match:
            results.passed = int(passed_match.group(1))
        if failed_match:
            results.failed = int(failed_match.group(1))

        results.total_tests = results.passed + results.failed

        return results

    def _parse_junit_results(self, stdout: str, stderr: str) -> TestResults:
        """Parse Maven/Gradle test output."""
        results = TestResults(framework=TestFramework.JUNIT)

        output = stdout + stderr

        tests_pattern = re.compile(r"Tests run:\s*(\d+)")
        failures_pattern = re.compile(r"Failures:\s*(\d+)")
        errors_pattern = re.compile(r"Errors:\s*(\d+)")
        skipped_pattern = re.compile(r"Skipped:\s*(\d+)")

        tests_match = tests_pattern.search(output)
        failures_match = failures_pattern.search(output)
        errors_match = errors_pattern.search(output)
        skipped_match = skipped_pattern.search(output)

        if tests_match:
            results.total_tests = int(tests_match.group(1))
        if failures_match:
            results.failed = int(failures_match.group(1))
        if errors_match:
            results.errors = int(errors_match.group(1))
        if skipped_match:
            results.skipped = int(skipped_match.group(1))

        if results.total_tests == 0:
            results.passed = results.total_tests - results.failed - results.errors - results.skipped

        return results

    def analyze_results(self, results: TestResults) -> TestAnalysis:
        """Analyze test results and generate insights."""
        analysis = TestAnalysis()

        analysis.success_rate = results.success_rate

        if results.tests:
            total_duration = sum(t.duration_ms for t in results.tests)
            analysis.avg_duration_ms = total_duration / len(results.tests)

            threshold = analysis.avg_duration_ms * 3
            analysis.slow_tests = [t for t in results.tests if t.duration_ms > threshold]

        analysis.failure_patterns = self._identify_failure_patterns(results.failures)

        analysis.recommendations = self._generate_recommendations(results, analysis)

        analysis.quality_score = self._calculate_quality_score(results, analysis)

        return analysis

    def _identify_failure_patterns(self, failures: list[TestFailure]) -> list[str]:
        """Identify common patterns in failures."""
        patterns: list[str] = []

        error_types: dict[str, int] = {}
        for failure in failures:
            error_type = failure.error_type or "unknown"
            error_types[error_type] = error_types.get(error_type, 0) + 1

        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            if count > 1:
                patterns.append(f"{error_type}: {count} occurrences")

        return patterns

    def _generate_recommendations(self, results: TestResults, analysis: TestAnalysis) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations: list[str] = []

        if results.failed > 0:
            recommendations.append("Fix failing tests before proceeding")

        if analysis.slow_tests:
            recommendations.append(f"Optimize {len(analysis.slow_tests)} slow tests")

        if results.skipped > results.total_tests * 0.1:
            recommendations.append("Reduce number of skipped tests")

        if analysis.success_rate < 80:
            recommendations.append("Test success rate is below 80%, investigate failures")

        if analysis.failure_patterns:
            recommendations.append(
                f"Address common failure patterns: {analysis.failure_patterns[0]}"
            )

        if analysis.coverage_percentage < 70:
            recommendations.append("Increase test coverage to at least 70%")

        return recommendations

    def _calculate_quality_score(self, results: TestResults, analysis: TestAnalysis) -> float:
        """Calculate overall quality score."""
        score = 0.0

        success_weight = 0.4
        coverage_weight = 0.3
        speed_weight = 0.2
        stability_weight = 0.1

        score += analysis.success_rate * success_weight

        coverage = results.coverage_percentage if hasattr(results, "coverage_percentage") else 0
        score += coverage * coverage_weight

        if analysis.avg_duration_ms > 0:
            speed_score = min(100, 1000 / analysis.avg_duration_ms * 10)
            score += speed_score * speed_weight

        stability_score = 100 if not analysis.flaky_tests else 100 - len(analysis.flaky_tests) * 10
        score += stability_score * stability_weight

        return min(100, max(0, score))

    def check_coverage(self, project_path: Path) -> CoverageReport:
        """Check test coverage for a project."""
        framework = self.detect_test_framework(project_path)
        if framework == TestFramework.UNKNOWN:
            return CoverageReport()

        config = self.FRAMEWORK_CONFIGS.get(framework, {})
        coverage_command = config.get("coverage_command", [])

        if not coverage_command:
            return CoverageReport()

        try:
            result = subprocess.run(
                coverage_command,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=300,
            )

            return self._parse_coverage_results(
                result.stdout, result.stderr, framework, project_path
            )

        except Exception:
            return CoverageReport()

    def _parse_coverage_results(
        self, stdout: str, stderr: str, framework: TestFramework, project_path: Path
    ) -> CoverageReport:
        """Parse coverage results."""
        report = CoverageReport()

        if framework == TestFramework.PYTEST:
            coverage_file = project_path / "coverage.json"
            if coverage_file.exists():
                try:
                    data = json.loads(coverage_file.read_text(encoding="utf-8"))
                    report.total_lines = data.get("totals", {}).get("num_statements", 0)
                    report.covered_lines = data.get("totals", {}).get("covered_lines", 0)
                    report.percentage = data.get("totals", {}).get("percent_covered", 0.0)
                    report.files = data.get("files", {})
                except Exception:
                    pass

        elif framework == TestFramework.GO_TEST:
            coverage_file = project_path / "coverage.out"
            if coverage_file.exists():
                try:
                    content = coverage_file.read_text(encoding="utf-8")
                    lines = content.splitlines()
                    total = 0
                    covered = 0
                    for line in lines:
                        if line.startswith("mode:"):
                            continue
                        parts = line.split()
                        if len(parts) >= 3:
                            count = int(parts[-1])
                            total += 1
                            if count > 0:
                                covered += 1
                    report.total_lines = total
                    report.covered_lines = covered
                    report.percentage = (covered / total * 100) if total > 0 else 0.0
                except Exception:
                    pass

        elif framework == TestFramework.JUNIT:
            jacoco_file = project_path / "target" / "site" / "jacoco" / "jacoco.xml"
            if not jacoco_file.exists():
                jacoco_file = project_path / "build" / "reports" / "jacoco" / "jacoco.xml"
            if jacoco_file.exists():
                try:
                    content = jacoco_file.read_text(encoding="utf-8")
                    covered_pattern = re.compile(r'covered="(\d+)"')
                    missed_pattern = re.compile(r'missed="(\d+)"')
                    covered_matches = covered_pattern.findall(content)
                    missed_matches = missed_pattern.findall(content)
                    covered = sum(int(m) for m in covered_matches)
                    missed = sum(int(m) for m in missed_matches)
                    report.covered_lines = covered
                    report.total_lines = covered + missed
                    report.percentage = (
                        (covered / report.total_lines * 100) if report.total_lines > 0 else 0.0
                    )
                except Exception:
                    pass

        return report

    def diagnose_failures(self, failures: list[TestFailure]) -> list[Diagnosis]:
        """Diagnose test failures and suggest fixes."""
        diagnoses: list[Diagnosis] = []

        for failure in failures:
            diagnosis = self._diagnose_single_failure(failure)
            diagnoses.append(diagnosis)

        return diagnoses

    def _diagnose_single_failure(self, failure: TestFailure) -> Diagnosis:
        """Diagnose a single test failure."""
        diagnosis = Diagnosis(
            failure_id=failure.test_id,
            confidence=0.0,
        )

        error_text = f"{failure.error_type} {failure.error_message}".lower()

        for pattern_name, pattern_info in self.FAILURE_PATTERNS.items():
            patterns = pattern_info.get("patterns", [])
            matched = any(p.lower() in error_text for p in patterns)

            if matched:
                diagnosis.root_cause = pattern_name
                diagnosis.confidence = 0.8
                diagnosis.fix_type = pattern_info.get("fix_type", "")
                diagnosis.auto_fixable = pattern_info.get("auto_fixable", False)
                diagnosis.suggested_fix = self._generate_fix_suggestion(failure, pattern_name)
                break

        if not diagnosis.root_cause:
            diagnosis.root_cause = "unknown"
            diagnosis.confidence = 0.3
            diagnosis.suggested_fix = "Manual investigation required"

        if failure.file_path:
            diagnosis.affected_files.append(failure.file_path)

        return diagnosis

    def _generate_fix_suggestion(self, failure: TestFailure, pattern_name: str) -> str:
        """Generate fix suggestion based on failure pattern."""
        suggestions: dict[str, str] = {
            "assertion_error": f"Check assertion in {failure.test_name}: expected '{failure.expected}' but got '{failure.actual}'",
            "import_error": f"Install missing dependency or fix import path in {failure.test_name}",
            "attribute_error": f"Add missing attribute or method referenced in {failure.test_name}",
            "type_error": f"Fix type mismatch in {failure.test_name}: check parameter types",
            "value_error": f"Validate input values in {failure.test_name}: check for invalid arguments",
            "syntax_error": f"Fix syntax error in {failure.file_path} at line {failure.line_number or 'unknown'}",
            "timeout_error": f"Optimize {failure.test_name} performance or increase timeout threshold",
            "null_reference": f"Add null check or initialize object before use in {failure.test_name}",
        }

        return suggestions.get(pattern_name, f"Investigate {failure.test_name} failure")

    def auto_fix_tests(self, diagnosis: Diagnosis, project_path: Path) -> bool:
        """Attempt to automatically fix a test issue."""
        if not diagnosis.auto_fixable:
            return False

        if not diagnosis.affected_files:
            return False

        fix_commands = self._generate_fix_commands(diagnosis, project_path)

        for command in fix_commands:
            try:
                result = subprocess.run(
                    command,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    return False
            except Exception:
                return False

        return True

    def _generate_fix_commands(self, diagnosis: Diagnosis, project_path: Path) -> list[list[str]]:
        """Generate commands to fix the diagnosed issue."""
        commands: list[list[str]] = []

        if diagnosis.fix_type == "dependency":
            framework = self.detect_test_framework(project_path)
            if framework == TestFramework.PYTEST:
                commands.append(["pip", "install", "-e", "."])
            elif framework in (TestFramework.JEST, TestFramework.MOCHA):
                commands.append(["npm", "install"])
            elif framework == TestFramework.GO_TEST:
                commands.append(["go", "mod", "download"])
            elif framework == TestFramework.CARGO_TEST:
                commands.append(["cargo", "fetch"])

        return commands

    def run_full_test_cycle(self, project_path: Path, max_iterations: int = 3) -> TestCycleResult:
        """Run a complete test cycle: discover → run → analyze → diagnose → fix."""
        import time

        start_time = time.time()
        iterations = 0
        fixes_applied: list[str] = []

        framework = self.detect_test_framework(project_path)

        for _iteration in range(max_iterations):
            iterations += 1

            tests = self.discover_tests(project_path)
            if not tests:
                return TestCycleResult(
                    success=False,
                    framework=framework,
                    message="No tests discovered",
                    iterations=iterations,
                    total_duration_ms=(time.time() - start_time) * 1000,
                )

            results = self.run_tests(tests, project_path)

            if results.is_success:
                analysis = self.analyze_results(results)
                coverage = self.check_coverage(project_path)

                return TestCycleResult(
                    success=True,
                    framework=framework,
                    results=results,
                    analysis=analysis,
                    coverage=coverage,
                    fixes_applied=fixes_applied,
                    iterations=iterations,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    message="All tests passed",
                )

            diagnoses = self.diagnose_failures(results.failures)

            auto_fixable_count = sum(1 for d in diagnoses if d.auto_fixable)
            if auto_fixable_count == 0:
                return TestCycleResult(
                    success=False,
                    framework=framework,
                    results=results,
                    diagnoses=diagnoses,
                    fixes_applied=fixes_applied,
                    iterations=iterations,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    message="No auto-fixable failures found",
                )

            for diagnosis in diagnoses:
                if diagnosis.auto_fixable and self.auto_fix_tests(diagnosis, project_path):
                    fixes_applied.append(diagnosis.failure_id)

        return TestCycleResult(
            success=False,
            framework=framework,
            diagnoses=self.diagnose_failures(results.failures) if results else [],
            fixes_applied=fixes_applied,
            iterations=iterations,
            total_duration_ms=(time.time() - start_time) * 1000,
            message=f"Failed after {max_iterations} iterations",
        )

    async def async_run_tests(self, project_path: Path) -> TestResults:
        """Asynchronously run tests."""
        tests = self.discover_tests(project_path)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run_tests, tests, project_path)

    async def async_run_full_cycle(self, project_path: Path) -> TestCycleResult:
        """Asynchronously run full test cycle."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run_full_test_cycle, project_path)

    def get_test_command(self, framework: TestFramework) -> list[str]:
        """Get the test run command for a framework."""
        config = self.FRAMEWORK_CONFIGS.get(framework, {})
        return cast(list[str], config.get("run_command", []))

    def get_coverage_command(self, framework: TestFramework) -> list[str]:
        """Get the coverage command for a framework."""
        config = self.FRAMEWORK_CONFIGS.get(framework, {})
        return cast(list[str], config.get("coverage_command", []))
