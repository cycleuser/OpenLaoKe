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


# Environment variable names that carry credentials. A shell command started by
# the agent inherits the process environment, so without this a one-line
# `curl -d "$ANTHROPIC_API_KEY" https://…` would export the key. The list is
# matched case-insensitively; ``*`` is a suffix wildcard.
_SECRET_ENV_NAMES = frozenset(
    {
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "KRB5CCNAME",
        "NETRC",
        "DOCKER_AUTH_CONFIG",
        "NPM_TOKEN",
        "PYPI_TOKEN",
        "HF_TOKEN",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "GITLAB_TOKEN",
        "CI_JOB_TOKEN",
        "SLACK_TOKEN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "DASHSCOPE_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "XAI_API_KEY",
        "OPENROUTER_API_KEY",
        "TOGETHER_API_KEY",
    }
)

_SECRET_ENV_PREFIXES = (
    "AWS_",
    "AZURE_",
    "GOOGLE_",
    "OPENAI_",
    "ANTHROPIC_",
    "DEEPSEEK_",
    "MOONSHOT_",
    "DASHSCOPE_",
)

_SECRET_ENV_SUFFIXES = (
    "_API_KEY",
    "_APIKEY",
    "_TOKEN",
    "_SECRET",
    "_SECRET_KEY",
    "_PASSWORD",
    "_PASSWD",
    "_CREDENTIALS",
    "_ACCESS_KEY",
    "_PRIVATE_KEY",
)


def is_secret_env_name(name: str) -> bool:
    """True when an environment variable name looks like it holds a credential."""
    upper = name.upper()
    if upper in _SECRET_ENV_NAMES:
        return True
    if upper.startswith(_SECRET_ENV_PREFIXES):
        return True
    return upper.endswith(_SECRET_ENV_SUFFIXES)


def scrub_environment(env: dict[str, str], allow: set[str] | None = None) -> dict[str, str]:
    """Drop credential-shaped variables before handing an env to a subprocess.

    Names in ``allow`` are kept even when they look like secrets, which is the
    escape hatch for a project whose build genuinely needs one.

    This is hygiene, not a sandbox: it stops the model from reading a key out of
    the inherited environment, and does nothing about a key sitting in a file
    it can already read.
    """
    keep = {name.upper() for name in (allow or set())}
    return {
        name: value
        for name, value in env.items()
        if name.upper() in keep or not is_secret_env_name(name)
    }


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
