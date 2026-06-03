"""Security utilities: path sanitization, credential redaction, ANSI stripping."""

from __future__ import annotations

import os
import re

# Common credential/secret patterns
_CREDENTIAL_PATTERNS: list[tuple[str, str]] = [
    (r"(?:Authorization|X-Api-Key|X-API-Key):\s*[^\n]+", "[header]: [redacted]"),
    (r"Bearer\s+[a-zA-Z0-9\-._~+/]+\s*", "Bearer [redacted]"),
    (
        r'(?:api[_-]?key|apikey|secret|token|password|passwd|auth)\s*[=:]\s*["\']?[^\s"\')\]}]+',
        "[redacted]",
    ),
    (r"sk-[a-zA-Z0-9]{24,}", "[redacted-key]"),
    (r"gh[pousr]_[a-zA-Z0-9]{20,}", "[redacted-token]"),
    (r"AIza[0-9A-Za-z\-_]{20,}", "[redacted-key]"),
    (r"ya29\.[0-9A-Za-z\-_]{20,}", "[redacted-token]"),
    (r"xox[bpras]-[0-9a-zA-Z\-]{10,}", "[redacted-slack]"),
]


def sanitize_path(path: str, cwd: str | None = None) -> str:
    """Resolve and sanitize a file path, preventing traversal outside workspace."""
    cwd = cwd or os.getcwd()
    resolved = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    real_cwd = os.path.realpath(cwd)

    if not _is_within(real_cwd, resolved):
        home = os.path.realpath(os.path.expanduser("~"))
        if _is_within(home, resolved):
            return resolved
        raise ValueError(f"Path '{path}' resolves outside workspace and home directory")
    return resolved


def _is_within(parent: str, child: str) -> bool:
    try:
        rel = os.path.relpath(child, parent)
        return not rel.startswith("..") and not os.path.isabs(rel)
    except ValueError:
        return False


def redact_credentials(text: str) -> str:
    """Redact credentials, API keys, and tokens from text output."""
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\([0-9a-zA-Z]")
    return ansi_pattern.sub("", text)


def sanitize_tool_args(args: dict[str, object]) -> dict[str, object]:
    """Sanitize tool arguments: strip ANSI from all string values."""
    cleaned: dict[str, object] = {}
    for key, value in args.items():
        if isinstance(value, str):
            cleaned[key] = strip_ansi(value)
        else:
            cleaned[key] = value
    return cleaned
