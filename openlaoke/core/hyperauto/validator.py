"""ResultValidator - Comprehensive validation system for generated artifacts.

This module provides validation capabilities:
1. Code validation - syntax, style, best practices
2. Functionality validation - requirement compliance
3. Performance validation - benchmarks and metrics
4. Security validation - vulnerability scanning
5. Compatibility validation - cross-platform checks
6. Quality scoring - comprehensive quality assessment
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ValidationLevel(StrEnum):
    """Validation severity levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    OK = "ok"


class ValidationCategory(StrEnum):
    """Categories of validation."""

    SYNTAX = "syntax"
    STYLE = "style"
    FUNCTIONALITY = "functionality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    BEST_PRACTICES = "best_practices"
    DOCUMENTATION = "documentation"


class Language(StrEnum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    UNKNOWN = "unknown"


@dataclass
class ValidationIssue:
    """A single validation issue."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    category: ValidationCategory = ValidationCategory.SYNTAX
    level: ValidationLevel = ValidationLevel.WARNING
    message: str = ""
    file_path: Path | None = None
    line_number: int | None = None
    column_number: int | None = None
    rule_id: str = ""
    suggestion: str = ""
    auto_fixable: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "level": self.level.value,
            "message": self.message,
            "file_path": str(self.file_path) if self.file_path else None,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "rule_id": self.rule_id,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
            "context": self.context,
        }


@dataclass
class ValidationResult:
    """Result of a validation check."""

    valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    score: float = 100.0
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: int = 0
    errors: int = 0
    category: ValidationCategory = ValidationCategory.SYNTAX
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [i.to_dict() for i in self.issues],
            "score": self.score,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "category": self.category.value,
            "details": self.details,
        }

    @property
    def has_errors(self) -> bool:
        return self.errors > 0 or any(
            i.level in (ValidationLevel.CRITICAL, ValidationLevel.ERROR) for i in self.issues
        )


@dataclass
class PerformanceResult:
    """Result of performance validation."""

    benchmark_passed: bool = True
    metrics: dict[str, float] = field(default_factory=dict)
    baseline_comparison: dict[str, float] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    issues: list[ValidationIssue] = field(default_factory=list)
    score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_passed": self.benchmark_passed,
            "metrics": self.metrics,
            "baseline_comparison": self.baseline_comparison,
            "execution_time_ms": self.execution_time_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "issues": [i.to_dict() for i in self.issues],
            "score": self.score,
        }


@dataclass
class SecurityReport:
    """Security validation report."""

    secure: bool = True
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)
    risk_level: str = "low"
    issues: list[ValidationIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    score: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "secure": self.secure,
            "vulnerabilities": self.vulnerabilities,
            "risk_level": self.risk_level,
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
            "score": self.score,
        }


@dataclass
class ValidatorQualityScore:
    """Comprehensive quality score."""

    overall: float = 0.0
    syntax: float = 100.0
    style: float = 100.0
    functionality: float = 100.0
    performance: float = 100.0
    security: float = 100.0
    compatibility: float = 100.0
    documentation: float = 100.0
    best_practices: float = 100.0
    breakdown: dict[str, float] = field(default_factory=dict)
    grade: str = "A"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "syntax": self.syntax,
            "style": self.style,
            "functionality": self.functionality,
            "performance": self.performance,
            "security": self.security,
            "compatibility": self.compatibility,
            "documentation": self.documentation,
            "best_practices": self.best_practices,
            "breakdown": self.breakdown,
            "grade": self.grade,
        }

    def calculate_grade(self) -> str:
        if self.overall >= 90:
            return "A"
        elif self.overall >= 80:
            return "B"
        elif self.overall >= 70:
            return "C"
        elif self.overall >= 60:
            return "D"
        else:
            return "F"


@dataclass
class Artifact:
    """An artifact to validate."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    type: str = ""
    name: str = ""
    content: str = ""
    file_path: Path | None = None
    language: Language = Language.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "content": self.content,
            "file_path": str(self.file_path) if self.file_path else None,
            "language": self.language.value,
            "metadata": self.metadata,
        }


@dataclass
class Requirements:
    """Validation requirements."""

    functional_requirements: list[str] = field(default_factory=list)
    performance_requirements: dict[str, float] = field(default_factory=dict)
    security_requirements: list[str] = field(default_factory=list)
    compatibility_targets: list[str] = field(default_factory=list)
    style_guidelines: dict[str, Any] = field(default_factory=dict)
    documentation_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "functional_requirements": self.functional_requirements,
            "performance_requirements": self.performance_requirements,
            "security_requirements": self.security_requirements,
            "compatibility_targets": self.compatibility_targets,
            "style_guidelines": self.style_guidelines,
            "documentation_requirements": self.documentation_requirements,
        }


@dataclass
class ValidationReport:
    """Complete validation report."""

    valid: bool = True
    artifact_id: str = ""
    overall_score: float = 100.0
    quality_score: ValidatorQualityScore | None = None
    code_validation: ValidationResult | None = None
    functionality_validation: ValidationResult | None = None
    performance_validation: PerformanceResult | None = None
    security_validation: SecurityReport | None = None
    compatibility_validation: ValidationResult | None = None
    total_issues: int = 0
    critical_issues: int = 0
    errors: int = 0
    warnings: int = 0
    recommendations: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "artifact_id": self.artifact_id,
            "overall_score": self.overall_score,
            "quality_score": self.quality_score.to_dict() if self.quality_score else None,
            "code_validation": self.code_validation.to_dict() if self.code_validation else None,
            "functionality_validation": (
                self.functionality_validation.to_dict() if self.functionality_validation else None
            ),
            "performance_validation": (
                self.performance_validation.to_dict() if self.performance_validation else None
            ),
            "security_validation": (
                self.security_validation.to_dict() if self.security_validation else None
            ),
            "compatibility_validation": (
                self.compatibility_validation.to_dict() if self.compatibility_validation else None
            ),
            "total_issues": self.total_issues,
            "critical_issues": self.critical_issues,
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


class ResultValidator:
    """Comprehensive validation system for generated artifacts."""

    LANGUAGE_CONFIGS: dict[Language, dict[str, Any]] = {
        Language.PYTHON: {
            "syntax_check": ["python", "-m", "py_compile"],
            "lint_tools": ["ruff", "mypy", "flake8", "pylint"],
            "format_tools": ["ruff", "black"],
            "test_framework": "pytest",
            "security_tools": ["bandit"],
            "file_extensions": [".py", ".pyw"],
        },
        Language.JAVASCRIPT: {
            "syntax_check": ["node", "--check"],
            "lint_tools": ["eslint"],
            "format_tools": ["prettier"],
            "test_framework": "jest",
            "security_tools": ["npm audit"],
            "file_extensions": [".js", ".mjs", ".cjs"],
        },
        Language.TYPESCRIPT: {
            "syntax_check": ["tsc", "--noEmit"],
            "lint_tools": ["eslint"],
            "format_tools": ["prettier"],
            "test_framework": "jest",
            "security_tools": ["npm audit"],
            "file_extensions": [".ts", ".tsx"],
        },
        Language.GO: {
            "syntax_check": ["go", "build"],
            "lint_tools": ["golangci-lint"],
            "format_tools": ["gofmt", "goimports"],
            "test_framework": "go test",
            "security_tools": ["gosec"],
            "file_extensions": [".go"],
        },
        Language.RUST: {
            "syntax_check": ["cargo", "check"],
            "lint_tools": ["cargo", "clippy"],
            "format_tools": ["cargo", "fmt", "--check"],
            "test_framework": "cargo test",
            "security_tools": ["cargo audit"],
            "file_extensions": [".rs"],
        },
        Language.JAVA: {
            "syntax_check": ["javac"],
            "lint_tools": ["checkstyle", "spotbugs"],
            "format_tools": ["google-java-format"],
            "test_framework": "junit",
            "security_tools": ["dependency-check"],
            "file_extensions": [".java"],
        },
        Language.C: {
            "syntax_check": ["gcc", "-fsyntax-only"],
            "lint_tools": ["cppcheck"],
            "format_tools": ["clang-format"],
            "test_framework": "custom",
            "security_tools": ["cppcheck"],
            "file_extensions": [".c", ".h"],
        },
        Language.CPP: {
            "syntax_check": ["g++", "-fsyntax-only"],
            "lint_tools": ["cppcheck"],
            "format_tools": ["clang-format"],
            "test_framework": "custom",
            "security_tools": ["cppcheck"],
            "file_extensions": [".cpp", ".cc", ".cxx", ".hpp"],
        },
    }

    SECURITY_PATTERNS: dict[str, dict[str, Any]] = {
        "hardcoded_password": {
            "patterns": ["password.*=.*['\"]", "passwd.*=.*['\"]", "pwd.*=.*['\"]"],
            "level": ValidationLevel.CRITICAL,
            "message": "Hardcoded password detected",
        },
        "hardcoded_secret": {
            "patterns": ["secret.*=.*['\"]", "api_key.*=.*['\"", "token.*=.*['\"]"],
            "level": ValidationLevel.CRITICAL,
            "message": "Hardcoded secret detected",
        },
        "sql_injection": {
            "patterns": ["execute\\(.*\\+.*\\)", "query\\(.*\\+.*\\)"],
            "level": ValidationLevel.ERROR,
            "message": "Potential SQL injection vulnerability",
        },
        "command_injection": {
            "patterns": ["exec\\(.*\\+.*\\)", "system\\(.*\\+.*\\)", "eval\\(.*\\+.*\\)"],
            "level": ValidationLevel.ERROR,
            "message": "Potential command injection vulnerability",
        },
        "unsafe_deserialization": {
            "patterns": ["pickle\\.loads", "yaml\\.load\\(.*\\)"],
            "level": ValidationLevel.WARNING,
            "message": "Unsafe deserialization",
        },
        "debug_code": {
            "patterns": ["print\\(", "console\\.log\\(", "debugger"],
            "level": ValidationLevel.INFO,
            "message": "Debug code detected",
        },
        "weak_crypto": {
            "patterns": ["md5\\(", "sha1\\(", "random\\.random"],
            "level": ValidationLevel.WARNING,
            "message": "Weak cryptographic function",
        },
    }

    BEST_PRACTICE_PATTERNS: dict[str, dict[str, Any]] = {
        "missing_error_handling": {
            "patterns": ["try\\s*\\{[^}]*\\}\\s*catch", "try:\\s*[^except]"],
            "level": ValidationLevel.WARNING,
            "message": "Missing proper error handling",
        },
        "magic_numbers": {
            "patterns": ["[=\\(\\[],\\s*\\d{2,}\\s*[\\)\\];,]"],
            "level": ValidationLevel.INFO,
            "message": "Magic number detected",
        },
        "long_function": {
            "check": "line_count",
            "threshold": 50,
            "level": ValidationLevel.WARNING,
            "message": "Function exceeds recommended length",
        },
        "deep_nesting": {
            "check": "nesting_depth",
            "threshold": 4,
            "level": ValidationLevel.WARNING,
            "message": "Deep nesting detected",
        },
        "duplicate_code": {
            "check": "similarity",
            "threshold": 0.8,
            "level": ValidationLevel.WARNING,
            "message": "Potential duplicate code",
        },
    }

    def detect_language(self, code: str, file_path: Path | None = None) -> Language:
        """Detect the programming language of code."""
        if file_path:
            extension = file_path.suffix.lower()
            for language, config in self.LANGUAGE_CONFIGS.items():
                if language == Language.UNKNOWN:
                    continue
                extensions = config.get("file_extensions", [])
                if extension in extensions:
                    return language

        python_indicators = ["def ", "import ", "from ", "class ", "__", "self.", "elif "]
        js_indicators = ["function ", "const ", "let ", "var ", "=>", "require(", "export "]
        ts_indicators = ["interface ", "type ", ": string", ": number", ": boolean"]
        go_indicators = ["func ", "package ", 'import "', "go ", "chan ", "defer "]
        rust_indicators = ["fn ", "let mut", "impl ", "pub fn", "use ", "::<", "crate::"]
        java_indicators = ["public class", "private ", "void ", "static ", "new ", "extends "]
        c_indicators = ["#include", "int main", "void ", "struct ", "typedef ", "sizeof"]
        cpp_indicators = ["#include", "class ", "namespace ", "template<", "std::", "new "]

        indicators = {
            Language.PYTHON: python_indicators,
            Language.JAVASCRIPT: js_indicators,
            Language.TYPESCRIPT: ts_indicators,
            Language.GO: go_indicators,
            Language.RUST: rust_indicators,
            Language.JAVA: java_indicators,
            Language.C: c_indicators,
            Language.CPP: cpp_indicators,
        }

        scores: dict[Language, int] = {}
        for language, lang_indicators in indicators.items():
            score = sum(1 for ind in lang_indicators if ind in code)
            scores[language] = score

        max_score = max(scores.values())
        if max_score == 0:
            return Language.UNKNOWN

        for language, score in scores.items():
            if score == max_score:
                return language

        return Language.UNKNOWN

    def validate_code(
        self, code: str, language: str | Language = Language.UNKNOWN
    ) -> ValidationResult:
        """Validate code for syntax and style."""
        if isinstance(language, str):
            language = self._str_to_language(language)

        if language == Language.UNKNOWN:
            language = self.detect_language(code)

        result = ValidationResult(category=ValidationCategory.SYNTAX)

        syntax_result = self._check_syntax(code, language)
        result.issues.extend(syntax_result.issues)

        style_result = self._check_style(code, language)
        result.issues.extend(style_result.issues)

        best_practice_result = self._check_best_practices(code, language)
        result.issues.extend(best_practice_result.issues)

        result.errors = sum(
            1 for i in result.issues if i.level in (ValidationLevel.CRITICAL, ValidationLevel.ERROR)
        )
        result.warnings = sum(1 for i in result.issues if i.level == ValidationLevel.WARNING)
        result.passed_checks = sum(
            1 for i in result.issues if i.level in (ValidationLevel.OK, ValidationLevel.INFO)
        )
        result.failed_checks = result.errors + result.warnings
        result.valid = result.errors == 0
        result.score = self._calculate_validation_score(result)

        return result

    def _str_to_language(self, language_str: str) -> Language:
        """Convert string to Language enum."""
        mapping = {
            "python": Language.PYTHON,
            "javascript": Language.JAVASCRIPT,
            "js": Language.JAVASCRIPT,
            "typescript": Language.TYPESCRIPT,
            "ts": Language.TYPESCRIPT,
            "go": Language.GO,
            "rust": Language.RUST,
            "java": Language.JAVA,
            "c": Language.C,
            "cpp": Language.CPP,
            "c++": Language.CPP,
        }
        return mapping.get(language_str.lower(), Language.UNKNOWN)

    def _check_syntax(self, code: str, language: Language) -> ValidationResult:
        """Check code syntax."""
        result = ValidationResult(category=ValidationCategory.SYNTAX)

        if language == Language.UNKNOWN:
            return result

        config = self.LANGUAGE_CONFIGS.get(language, {})
        syntax_check = config.get("syntax_check", [])

        if not syntax_check:
            return result

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=config.get("file_extensions", [""])[0], delete=False
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            check_result = subprocess.run(
                syntax_check + [temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if check_result.returncode != 0:
                errors = self._parse_syntax_errors(check_result.stderr, language)
                result.issues.extend(errors)

        except subprocess.TimeoutExpired:
            result.issues.append(
                ValidationIssue(
                    category=ValidationCategory.SYNTAX,
                    level=ValidationLevel.ERROR,
                    message="Syntax check timed out",
                )
            )
        except FileNotFoundError:
            pass
        except Exception as e:
            result.issues.append(
                ValidationIssue(
                    category=ValidationCategory.SYNTAX,
                    level=ValidationLevel.ERROR,
                    message=f"Syntax check failed: {e}",
                )
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

        return result

    def _parse_syntax_errors(self, error_output: str, language: Language) -> list[ValidationIssue]:
        """Parse syntax errors from tool output."""
        issues: list[ValidationIssue] = []

        if language in (Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT):
            pattern = re.compile(r"SyntaxError: (.+)")
            for match in pattern.finditer(error_output):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.SYNTAX,
                        level=ValidationLevel.ERROR,
                        message=f"Syntax error: {match.group(1)}",
                        auto_fixable=True,
                    )
                )

        elif language == Language.GO:
            pattern = re.compile(r"(.+):(\d+):(\d+): (.+)")
            for match in pattern.finditer(error_output):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.SYNTAX,
                        level=ValidationLevel.ERROR,
                        message=match.group(4),
                        line_number=int(match.group(2)),
                        column_number=int(match.group(3)),
                        auto_fixable=True,
                    )
                )

        elif language == Language.RUST:
            pattern = re.compile(r"error\[E\d+\]: (.+)")
            for match in pattern.finditer(error_output):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.SYNTAX,
                        level=ValidationLevel.ERROR,
                        message=match.group(1),
                        auto_fixable=True,
                    )
                )

        elif language == Language.JAVA:
            pattern = re.compile(r"error: (.+)")
            for match in pattern.finditer(error_output):
                issues.append(
                    ValidationIssue(
                        category=ValidationCategory.SYNTAX,
                        level=ValidationLevel.ERROR,
                        message=match.group(1),
                        auto_fixable=True,
                    )
                )

        return issues

    def _check_style(self, code: str, language: Language) -> ValidationResult:
        """Check code style."""
        result = ValidationResult(category=ValidationCategory.STYLE)

        lines = code.splitlines()

        for i, line in enumerate(lines, 1):
            if len(line) > 100:
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.STYLE,
                        level=ValidationLevel.INFO,
                        message=f"Line exceeds 100 characters ({len(line)} chars)",
                        line_number=i,
                        rule_id="line-length",
                        suggestion="Break line into multiple lines",
                        auto_fixable=True,
                    )
                )

            if line.strip() == "":
                continue

            if (
                language == Language.PYTHON
                and not line.startswith("#")
                and "    " not in line[:4]
                and line[0] == " "
            ):
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.STYLE,
                        level=ValidationLevel.WARNING,
                        message="Inconsistent indentation",
                        line_number=i,
                        rule_id="indentation",
                        suggestion="Use 4 spaces for indentation",
                        auto_fixable=True,
                    )
                )

        return result

    def _check_best_practices(self, code: str, language: Language) -> ValidationResult:
        """Check best practices."""
        result = ValidationResult(category=ValidationCategory.BEST_PRACTICES)

        functions = self._extract_functions(code, language)
        for func_name, start_line, end_line in functions:
            func_lines = end_line - start_line + 1
            if func_lines > 50:
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.BEST_PRACTICES,
                        level=ValidationLevel.WARNING,
                        message=f"Function '{func_name}' is too long ({func_lines} lines)",
                        line_number=start_line,
                        rule_id="long-function",
                        suggestion="Break into smaller functions",
                        auto_fixable=False,
                    )
                )

        for pattern_name, pattern_info in self.BEST_PRACTICE_PATTERNS.items():
            patterns = pattern_info.get("patterns", [])
            level = pattern_info.get("level", ValidationLevel.WARNING)
            message = pattern_info.get("message", "")

            for pattern in patterns:
                try:
                    regex = re.compile(pattern)
                    for match in regex.finditer(code):
                        line_num = code[: match.start()].count("\n") + 1
                        result.issues.append(
                            ValidationIssue(
                                category=ValidationCategory.BEST_PRACTICES,
                                level=level,
                                message=message,
                                line_number=line_num,
                                rule_id=pattern_name,
                                auto_fixable=False,
                            )
                        )
                except re.error:
                    pass

        return result

    def _extract_functions(self, code: str, language: Language) -> list[tuple[str, int, int]]:
        """Extract function definitions with line numbers."""
        functions: list[tuple[str, int, int]] = []

        lines = code.splitlines()

        if language == Language.PYTHON:
            pattern = re.compile(r"def\s+(\w+)\s*\(")
            for i, line in enumerate(lines, 1):
                match = pattern.search(line)
                if match:
                    func_name = match.group(1)
                    end_line = self._find_function_end(lines, i - 1, language)
                    functions.append((func_name, i, end_line))

        elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            patterns = [
                re.compile(r"function\s+(\w+)\s*\("),
                re.compile(r"const\s+(\w+)\s*=\s*(?:async\s*)?\("),
            ]
            for i, line in enumerate(lines, 1):
                for pattern in patterns:
                    match = pattern.search(line)
                    if match:
                        func_name = match.group(1)
                        end_line = self._find_function_end(lines, i - 1, language)
                        functions.append((func_name, i, end_line))

        elif language == Language.GO:
            pattern = re.compile(r"func\s+(?:\(\w+\)\s*)?(\w+)\s*\(")
            for i, line in enumerate(lines, 1):
                match = pattern.search(line)
                if match:
                    func_name = match.group(1)
                    end_line = self._find_function_end(lines, i - 1, language)
                    functions.append((func_name, i, end_line))

        elif language == Language.RUST:
            pattern = re.compile(r"fn\s+(\w+)\s*\(")
            for i, line in enumerate(lines, 1):
                match = pattern.search(line)
                if match:
                    func_name = match.group(1)
                    end_line = self._find_function_end(lines, i - 1, language)
                    functions.append((func_name, i, end_line))

        elif language == Language.JAVA:
            pattern = re.compile(r"(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(")
            for i, line in enumerate(lines, 1):
                match = pattern.search(line)
                if match:
                    func_name = match.group(1)
                    end_line = self._find_function_end(lines, i - 1, language)
                    functions.append((func_name, i, end_line))

        return functions

    def _find_function_end(self, lines: list[str], start: int, language: Language) -> int:
        """Find the end line of a function."""
        if language == Language.PYTHON:
            indent = len(lines[start]) - len(lines[start].lstrip())
            for i in range(start + 1, len(lines)):
                if lines[i].strip() == "":
                    continue
                current_indent = len(lines[i]) - len(lines[i].lstrip())
                if current_indent <= indent and not lines[i].strip().startswith("#"):
                    return i
            return len(lines)

        elif language in (
            Language.JAVASCRIPT,
            Language.TYPESCRIPT,
            Language.JAVA,
            Language.CPP,
            Language.GO,
            Language.RUST,
        ):
            brace_count = 0
            started = False
            for i in range(start, len(lines)):
                for char in lines[i]:
                    if char == "{":
                        brace_count += 1
                        started = True
                    elif char == "}":
                        brace_count -= 1
                        if started and brace_count == 0:
                            return i + 1
            return len(lines)

        return len(lines)

    def validate_functionality(
        self, implementation: str, requirements: list[str], language: Language = Language.UNKNOWN
    ) -> ValidationResult:
        """Validate that implementation meets requirements."""
        result = ValidationResult(category=ValidationCategory.FUNCTIONALITY)

        if language == Language.UNKNOWN:
            language = self.detect_language(implementation)

        for req in requirements:
            keywords = self._extract_keywords(req)
            matched = sum(1 for kw in keywords if kw.lower() in implementation.lower())

            coverage = matched / len(keywords) if keywords else 0

            if coverage < 0.5:
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.FUNCTIONALITY,
                        level=ValidationLevel.WARNING,
                        message=f"Requirement not fully addressed: '{req}'",
                        suggestion=f"Ensure implementation addresses: {req}",
                        auto_fixable=False,
                    )
                )
            elif coverage < 1.0:
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.FUNCTIONALITY,
                        level=ValidationLevel.INFO,
                        message=f"Requirement partially addressed: '{req}'",
                        suggestion=f"Complete implementation for: {req}",
                        auto_fixable=False,
                    )
                )

        result.warnings = sum(1 for i in result.issues if i.level == ValidationLevel.WARNING)
        result.valid = all(i.level != ValidationLevel.ERROR for i in result.issues)
        result.score = self._calculate_validation_score(result)

        return result

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract important keywords from text."""
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "if",
            "or",
            "because",
            "until",
            "while",
            "although",
            "though",
            "that",
            "which",
            "who",
            "whom",
            "this",
            "these",
            "those",
            "am",
            "it",
        }

        words = re.findall(r"\b\w+\b", text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords

    def validate_performance(
        self, code: str, benchmarks: dict[str, float], language: Language = Language.UNKNOWN
    ) -> PerformanceResult:
        """Validate performance against benchmarks."""
        result = PerformanceResult()

        if language == Language.UNKNOWN:
            language = self.detect_language(code)

        result.execution_time_ms = self._estimate_execution_time(code, language)
        result.memory_usage_mb = self._estimate_memory_usage(code)

        if "max_execution_time_ms" in benchmarks:
            max_time = benchmarks["max_execution_time_ms"]
            if result.execution_time_ms > max_time:
                result.benchmark_passed = False
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.PERFORMANCE,
                        level=ValidationLevel.WARNING,
                        message=f"Execution time ({result.execution_time_ms}ms) exceeds benchmark ({max_time}ms)",
                        suggestion="Optimize code for better performance",
                        auto_fixable=False,
                    )
                )

        if "max_memory_mb" in benchmarks:
            max_memory = benchmarks["max_memory_mb"]
            if result.memory_usage_mb > max_memory:
                result.benchmark_passed = False
                result.issues.append(
                    ValidationIssue(
                        category=ValidationCategory.PERFORMANCE,
                        level=ValidationLevel.WARNING,
                        message=f"Memory usage ({result.memory_usage_mb}MB) exceeds benchmark ({max_memory}MB)",
                        suggestion="Reduce memory allocations",
                        auto_fixable=False,
                    )
                )

        for metric, threshold in benchmarks.items():
            result.baseline_comparison[metric] = threshold
            result.metrics[metric] = getattr(result, metric.replace("max_", ""), 0.0)

        result.score = self._calculate_performance_score(result, benchmarks)

        return result

    def _estimate_execution_time(self, code: str, language: Language) -> float:
        """Estimate execution time in milliseconds."""
        complexity_indicators = {
            "loops": len(re.findall(r"(for|while|loop)", code, re.IGNORECASE)),
            "nested_loops": len(re.findall(r"(for|while).*?(for|while)", code, re.IGNORECASE)),
            "recursion": len(re.findall(r"def\s+\w+.*\w+\(", code)),
            "io_operations": len(
                re.findall(r"(read|write|open|fetch|request)", code, re.IGNORECASE)
            ),
            "sorting": len(re.findall(r"(sort|sorted|order)", code, re.IGNORECASE)),
        }

        base_time = 10.0

        for indicator, count in complexity_indicators.items():
            if indicator == "nested_loops":
                base_time += count * 100.0
            elif indicator == "loops":
                base_time += count * 20.0
            elif indicator == "recursion":
                base_time += count * 50.0
            elif indicator == "io_operations":
                base_time += count * 100.0
            elif indicator == "sorting":
                base_time += count * 30.0

        return base_time

    def _estimate_memory_usage(self, code: str) -> float:
        """Estimate memory usage in megabytes."""
        allocations = len(
            re.findall(r"(new|malloc|allocate|list|dict|array|Map)", code, re.IGNORECASE)
        )
        large_data = len(re.findall(r"(buffer|cache|store|data)", code, re.IGNORECASE))

        base_memory = 1.0
        base_memory += allocations * 0.5
        base_memory += large_data * 2.0

        return base_memory

    def _calculate_performance_score(
        self, result: PerformanceResult, benchmarks: dict[str, float]
    ) -> float:
        """Calculate performance score."""
        score = 100.0

        for metric, threshold in benchmarks.items():
            actual = result.metrics.get(metric.replace("max_", ""), 0.0)
            if actual > threshold:
                ratio = actual / threshold
                penalty = min(50, (ratio - 1) * 100)
                score -= penalty

        return max(0, score)

    def validate_security(self, code: str, language: Language = Language.UNKNOWN) -> SecurityReport:
        """Validate code for security vulnerabilities."""
        report = SecurityReport()

        if language == Language.UNKNOWN:
            language = self.detect_language(code)

        for pattern_name, pattern_info in self.SECURITY_PATTERNS.items():
            patterns = pattern_info.get("patterns", [])
            level = pattern_info.get("level", ValidationLevel.WARNING)
            message = pattern_info.get("message", "")

            for pattern in patterns:
                try:
                    regex = re.compile(pattern, re.IGNORECASE)
                    for match in regex.finditer(code):
                        line_num = code[: match.start()].count("\n") + 1

                        vulnerability = {
                            "type": pattern_name,
                            "line": line_num,
                            "message": message,
                            "severity": level.value,
                            "match": match.group(0),
                        }
                        report.vulnerabilities.append(vulnerability)

                        report.issues.append(
                            ValidationIssue(
                                category=ValidationCategory.SECURITY,
                                level=level,
                                message=message,
                                line_number=line_num,
                                rule_id=pattern_name,
                                suggestion=self._get_security_fix_suggestion(pattern_name),
                                auto_fixable=False,
                            )
                        )
                except re.error:
                    pass

        critical_count = sum(1 for v in report.vulnerabilities if v["severity"] == "critical")
        error_count = sum(1 for v in report.vulnerabilities if v["severity"] == "error")
        warning_count = sum(1 for v in report.vulnerabilities if v["severity"] == "warning")

        if critical_count > 0:
            report.risk_level = "critical"
            report.secure = False
        elif error_count > 0:
            report.risk_level = "high"
            report.secure = False
        elif warning_count > 3:
            report.risk_level = "medium"
        elif warning_count > 0:
            report.risk_level = "low"
        else:
            report.risk_level = "none"

        report.recommendations = self._generate_security_recommendations(report)

        report.score = self._calculate_security_score(report)

        return report

    def _get_security_fix_suggestion(self, pattern_name: str) -> str:
        """Get fix suggestion for security issue."""
        suggestions = {
            "hardcoded_password": "Use environment variables or secure config for passwords",
            "hardcoded_secret": "Use environment variables or secure vault for secrets",
            "sql_injection": "Use parameterized queries or prepared statements",
            "command_injection": "Sanitize inputs and avoid shell execution",
            "unsafe_deserialization": "Use safe deserialization with validation",
            "debug_code": "Remove debug statements before production",
            "weak_crypto": "Use strong cryptographic algorithms (SHA-256, AES)",
        }
        return suggestions.get(pattern_name, "Review and fix security vulnerability")

    def _generate_security_recommendations(self, report: SecurityReport) -> list[str]:
        """Generate security recommendations."""
        recommendations: list[str] = []

        if report.vulnerabilities:
            types = set(v["type"] for v in report.vulnerabilities)

            for vuln_type in types:
                if vuln_type in ("hardcoded_password", "hardcoded_secret"):
                    recommendations.append("Use environment variables for secrets")
                elif vuln_type in ("sql_injection", "command_injection"):
                    recommendations.append("Implement input validation and sanitization")
                elif vuln_type == "unsafe_deserialization":
                    recommendations.append("Use safe deserialization methods")
                elif vuln_type == "weak_crypto":
                    recommendations.append("Upgrade to modern cryptographic algorithms")

        if report.risk_level in ("critical", "high"):
            recommendations.append("Immediate remediation required before deployment")
        elif report.risk_level == "medium":
            recommendations.append("Address vulnerabilities before release")

        return recommendations

    def _calculate_security_score(self, report: SecurityReport) -> float:
        """Calculate security score."""
        score = 100.0

        for vuln in report.vulnerabilities:
            severity = vuln["severity"]
            if severity == "critical":
                score -= 30
            elif severity == "error":
                score -= 20
            elif severity == "warning":
                score -= 10
            else:
                score -= 5

        return max(0, score)

    def validate_compatibility(
        self, code: str, target: str, language: Language = Language.UNKNOWN
    ) -> ValidationResult:
        """Validate compatibility with target platform/version."""
        result = ValidationResult(category=ValidationCategory.COMPATIBILITY)

        if language == Language.UNKNOWN:
            language = self.detect_language(code)

        target_lower = target.lower()

        if language == Language.PYTHON:
            version_match = re.search(r"python\s*(\d+\.?\d*)", target_lower)
            if version_match:
                target_version = float(version_match.group(1))
                features: dict[str, float] = self._detect_python_features(code)
                for feature, min_version in features.items():
                    if min_version > target_version:
                        result.issues.append(
                            ValidationIssue(
                                category=ValidationCategory.COMPATIBILITY,
                                level=ValidationLevel.ERROR,
                                message=f"Feature '{feature}' requires Python {min_version}, target is {target_version}",
                                suggestion=f"Remove or replace feature for Python {target_version} compatibility",
                                auto_fixable=False,
                            )
                        )

        elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            if "node" in target_lower:
                version_match = re.search(r"node\s*(\d+)", target_lower)
                if version_match:
                    target_version = int(version_match.group(1))
                    js_features: dict[str, int] = self._detect_js_features(code)
                    for feature, min_version in js_features.items():
                        if min_version > target_version:
                            result.issues.append(
                                ValidationIssue(
                                    category=ValidationCategory.COMPATIBILITY,
                                    level=ValidationLevel.WARNING,
                                    message=f"Feature '{feature}' may not be available in Node {target_version}",
                                    suggestion=f"Use polyfill or alternative for Node {target_version}",
                                    auto_fixable=False,
                                )
                            )

            if "browser" in target_lower:
                browser_features = ["require(", "module.exports", "process.", "__dirname"]
                for feature in browser_features:
                    if feature in code:
                        result.issues.append(
                            ValidationIssue(
                                category=ValidationCategory.COMPATIBILITY,
                                level=ValidationLevel.ERROR,
                                message=f"Node.js-specific feature '{feature}' not available in browser",
                                suggestion="Use browser-compatible alternatives",
                                auto_fixable=False,
                            )
                        )

        elif language == Language.GO:
            go_features = self._detect_go_features(code)
            for feature, info in go_features.items():
                if info.get("experimental"):
                    result.issues.append(
                        ValidationIssue(
                            category=ValidationCategory.COMPATIBILITY,
                            level=ValidationLevel.WARNING,
                            message=f"Experimental feature '{feature}' may not be stable",
                            auto_fixable=False,
                        )
                    )

        result.errors = sum(
            1 for i in result.issues if i.level in (ValidationLevel.CRITICAL, ValidationLevel.ERROR)
        )
        result.warnings = sum(1 for i in result.issues if i.level == ValidationLevel.WARNING)
        result.valid = result.errors == 0
        result.score = self._calculate_validation_score(result)

        return result

    def _detect_python_features(self, code: str) -> dict[str, float]:
        """Detect Python features and their minimum version requirements."""
        features: dict[str, float] = {}

        if "match " in code and "case " in code:
            features["match_case"] = 3.10
        if "| " in code and "None" in code:
            features["union_types"] = 3.10
        if "async def" in code:
            features["async"] = 3.5
        if 'f"' in code or "f'" in code:
            features["f_strings"] = 3.6
        if ": " in code and "-> " in code:
            features["type_hints"] = 3.5
        if "@dataclass" in code:
            features["dataclasses"] = 3.7

        return features

    def _detect_js_features(self, code: str) -> dict[str, int]:
        """Detect JavaScript features and their minimum Node version."""
        features: dict[str, int] = {}

        if "async " in code or "await " in code:
            features["async_await"] = 8
        if "=>" in code:
            features["arrow_functions"] = 6
        if "class " in code:
            features["classes"] = 6
        if "let " in code or "const " in code:
            features["let_const"] = 6
        if "`" in code:
            features["template_literals"] = 6
        if "..." in code:
            features["spread_operator"] = 6
        if "import " in code and "from " in code:
            features["es_modules"] = 14

        return features

    def _detect_go_features(self, code: str) -> dict[str, dict[str, Any]]:
        """Detect Go features."""
        features: dict[str, dict[str, Any]] = {}

        if "go " in code and "chan" in code:
            features["goroutines"] = {"stable": True}
        if "defer " in code:
            features["defer"] = {"stable": True}
        if "interface{}" in code or "any" in code:
            features["generics_prep"] = {"experimental": "any" in code}

        return features

    def calculate_quality_score(self, results: dict[str, Any]) -> ValidatorQualityScore:
        """Calculate comprehensive quality score from validation results."""
        score = ValidatorQualityScore()

        weights = {
            "syntax": 0.15,
            "style": 0.10,
            "functionality": 0.25,
            "performance": 0.15,
            "security": 0.20,
            "compatibility": 0.10,
            "documentation": 0.05,
        }

        for category, _weight in weights.items():
            category_result = results.get(category)
            if category_result:
                if hasattr(category_result, "score"):
                    setattr(score, category, category_result.score)
                elif isinstance(category_result, dict):
                    setattr(score, category, category_result.get("score", 100.0))

        score.overall = sum(getattr(score, cat) * weight for cat, weight in weights.items())

        score.breakdown = {cat: getattr(score, cat) for cat in weights}

        score.grade = score.calculate_grade()

        return score

    def _calculate_validation_score(self, result: ValidationResult) -> float:
        """Calculate validation score from result."""
        total_checks = result.passed_checks + result.failed_checks
        if total_checks == 0:
            return 100.0

        base_score = 100.0

        for issue in result.issues:
            if issue.level == ValidationLevel.CRITICAL:
                base_score -= 30
            elif issue.level == ValidationLevel.ERROR:
                base_score -= 20
            elif issue.level == ValidationLevel.WARNING:
                base_score -= 10
            elif issue.level == ValidationLevel.INFO:
                base_score -= 5

        return max(0, min(100, base_score))

    def full_validation(
        self, artifact: Artifact, requirements: Requirements | None = None
    ) -> ValidationReport:
        """Perform full validation on an artifact."""
        import time

        report = ValidationReport(
            artifact_id=artifact.id,
            timestamp=time.time(),
        )

        language = artifact.language
        if language == Language.UNKNOWN:
            language = self.detect_language(artifact.content, artifact.file_path)

        code_result = self.validate_code(artifact.content, language)
        report.code_validation = code_result

        if requirements and requirements.functional_requirements:
            func_result = self.validate_functionality(
                artifact.content, requirements.functional_requirements, language
            )
            report.functionality_validation = func_result

        if requirements and requirements.performance_requirements:
            perf_result = self.validate_performance(
                artifact.content, requirements.performance_requirements, language
            )
            report.performance_validation = perf_result

        security_result = self.validate_security(artifact.content, language)
        report.security_validation = security_result

        if requirements and requirements.compatibility_targets:
            compat_results: list[ValidationResult] = []
            for target in requirements.compatibility_targets:
                compat_result = self.validate_compatibility(artifact.content, target, language)
                compat_results.append(compat_result)
            if compat_results:
                report.compatibility_validation = compat_results[0]

        results = {
            "syntax": code_result,
            "style": code_result,
            "functionality": report.functionality_validation,
            "performance": report.performance_validation,
            "security": security_result,
            "compatibility": report.compatibility_validation,
        }

        report.quality_score = self.calculate_quality_score(results)

        total = 0
        for r in results.values():
            if r is not None and hasattr(r, "issues"):
                total += len(r.issues)
        report.total_issues = total

        critical = 0
        for r in results.values():
            if r is not None and hasattr(r, "issues"):
                for i in r.issues:
                    if hasattr(i, "level") and i.level == ValidationLevel.CRITICAL:
                        critical += 1
        report.critical_issues = critical

        errors = 0
        for r in results.values():
            if r is not None and hasattr(r, "issues"):
                for i in r.issues:
                    if hasattr(i, "level") and i.level == ValidationLevel.ERROR:
                        errors += 1
        report.errors = errors

        warnings = 0
        for r in results.values():
            if r is not None and hasattr(r, "issues"):
                for i in r.issues:
                    if hasattr(i, "level") and i.level == ValidationLevel.WARNING:
                        warnings += 1
        report.warnings = warnings

        report.overall_score = report.quality_score.overall if report.quality_score else 100.0

        report.valid = (
            report.critical_issues == 0 and report.errors == 0 and report.overall_score >= 60
        )

        report.recommendations = self._generate_recommendations(report)

        return report

    def _generate_recommendations(self, report: ValidationReport) -> list[str]:
        """Generate recommendations from validation report."""
        recommendations: list[str] = []

        if report.code_validation and report.code_validation.has_errors:
            recommendations.append("Fix syntax and code errors")

        if report.security_validation and not report.security_validation.secure:
            recommendations.append("Address security vulnerabilities")

        if report.performance_validation and not report.performance_validation.benchmark_passed:
            recommendations.append("Optimize performance to meet benchmarks")

        if report.quality_score and report.quality_score.overall < 80:
            recommendations.append(
                f"Improve overall quality score (current: {report.quality_score.overall:.1f})"
            )

        if report.functionality_validation and report.functionality_validation.warnings > 0:
            recommendations.append("Complete implementation of all requirements")

        if report.compatibility_validation and report.compatibility_validation.has_errors:
            recommendations.append("Ensure compatibility with target platforms")

        if report.warnings > 5:
            recommendations.append(f"Address {report.warnings} warning issues")

        return recommendations

    async def async_validate_code(self, code: str, language: str = "python") -> ValidationResult:
        """Asynchronously validate code."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.validate_code, code, language)

    async def async_full_validation(
        self, artifact: Artifact, requirements: Requirements | None = None
    ) -> ValidationReport:
        """Asynchronously perform full validation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.full_validation, artifact, requirements)

    def quick_validate(self, code: str, language: str = "python") -> tuple[bool, float]:
        """Quick validation returning pass/fail and score."""
        lang = self._str_to_language(language)
        result = self.validate_code(code, lang)
        return result.valid, result.score

    def get_validation_summary(self, report: ValidationReport) -> str:
        """Get a summary string of validation results."""
        if report.valid:
            return f"Validation PASSED with score {report.overall_score:.1f} (Grade: {report.quality_score.grade if report.quality_score else 'N/A'})"
        else:
            return f"Validation FAILED with {report.critical_issues} critical, {report.errors} errors, score {report.overall_score:.1f}"
