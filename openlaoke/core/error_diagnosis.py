"""Error diagnosis for bash command failures.

When bash exits non-zero, makes a quick LLM call to classify error type and
emit a structured hint with file/line location and fix suggestion.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

ERROR_PATTERNS: dict[str, list[str]] = {
    "syntax": [
        r"SyntaxError",
        r"(?i)syntax error",
        r"(?i)unexpected token",
        r"(?i)unexpected end",
    ],
    "runtime": [
        r"(?i)runtime error",
        r"(?i)RuntimeError",
        r"(?i)exception",
        r"Traceback",
        r"(?i)segmentation fault",
        r"(?i)out of memory",
    ],
    "permission": [
        r"(?i)permission denied",
        r"(?i)EACCES",
        r"(?i)not permitted",
        r"(?i)access denied",
    ],
    "notfound": [
        r"(?i)not found",
        r"(?i)No such file",
        r"(?i)command not found",
        r"(?i)cannot find",
        r"(?i)ENOENT",
        r"(?i)does not exist",
        r"(?i)ModuleNotFound",
        r"(?i)ImportError",
        r"(?i)no module",
        r"(?i)No matching distribution",
        r"(?i)could not find",
        r"(?i)unable to locate",
    ],
    "timeout": [
        r"(?i)timed?[\s-]out",
        r"(?i)ETIMEDOUT",
        r"(?i)connection refused",
        r"(?i)too slow",
    ],
}

FILE_LINE_PATTERNS: list[str] = [
    r'File "([^"]+)", line (\d+)',
    r"([^\s:]+):(\d+):\d+",
    r"at (.+?):(\d+)",
    r"([^\s]+\.\w+):(\d+)(?::|$)",
]


@dataclass
class ErrorDiagnosis:
    error_type: str = "unknown"
    file_path: str = ""
    line_number: int | None = None
    fix_suggestion: str = ""

    def format_for_prompt(self) -> str:
        parts = [f"[ERROR-DIAGNOSIS] type={self.error_type}"]
        if self.file_path:
            loc = f"line {self.line_number}" if self.line_number else ""
            parts.append(f"file={self.file_path} {loc}".strip())
        if self.fix_suggestion:
            parts.append(f"suggestion={self.fix_suggestion}")
        return " | ".join(parts)


@dataclass
class ErrorDiagnoser:
    cache_ttl: int = 300
    _cache: dict[str, tuple[ErrorDiagnosis, float]] = field(default_factory=dict)

    def diagnose(
        self,
        command: str,
        stderr: str,
        exit_code: int,
        work_dir: str = "",
    ) -> ErrorDiagnosis:
        cache_key = f"{command}|{stderr[:200]}|{exit_code}"
        if cache_key in self._cache:
            diag, ts = self._cache[cache_key]
            if time.time() - ts < self.cache_ttl:
                return diag

        diag = self._regex_diagnose(command, stderr, exit_code)
        self._cache[cache_key] = (diag, time.time())
        return diag

    def _regex_diagnose(self, command: str, stderr: str, exit_code: int) -> ErrorDiagnosis:
        combined = f"{stderr}\n{command}"

        error_type = self._classify_error(combined)
        file_path, line_number = self._extract_file_line(combined)
        fix_suggestion = self._suggest_fix(error_type, command, stderr)

        return ErrorDiagnosis(
            error_type=error_type,
            file_path=file_path,
            line_number=line_number,
            fix_suggestion=fix_suggestion,
        )

    def _classify_error(self, text: str) -> str:
        for error_type, patterns in ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return error_type
        return "unknown"

    @staticmethod
    def _extract_file_line(text: str) -> tuple[str, int | None]:
        for pattern in FILE_LINE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    return match.group(1), int(match.group(2))
                except (IndexError, ValueError):
                    pass
        return "", None

    @staticmethod
    def _suggest_fix(error_type: str, command: str, stderr: str) -> str:
        suggestions = {
            "syntax": "Check syntax: missing quotes, brackets, or indentation",
            "runtime": "Runtime error. Check variable types, null values, or edge cases",
            "permission": "Permission denied. Try with elevated privileges or check file ownership",
            "notfound": "File/command not found. Check path spelling or install the dependency",
            "timeout": "Operation timed out. Check network connectivity or increase timeout",
        }
        base = suggestions.get(error_type, "Unknown error - check output for details")
        parts = [base]
        if "pip install" in command:
            parts.append("Try: pip install --user <package> or use a virtual environment")
        if "npm install" in command:
            parts.append("Try: npm install --legacy-peer-deps or clear node_modules")
        if pytest_search := re.search(r"pytest\s+([^\s]+)", command):
            parts.append(f"Check test path: {pytest_search.group(1)}")
        return "; ".join(parts)

    def clear_cache(self) -> None:
        self._cache.clear()
