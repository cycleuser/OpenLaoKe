"""Deterministic blast-radius classification for shell commands.

Four tiers, decided offline from the command text alone (modelled on jcode's
``jcode-command-risk``):

* ``safe``          read-only, runs.
* ``low``           destructive but the target is known and inside the working
                    directory, and the damage is bounded: runs, and gets logged.
* ``confirm``       the target cannot be resolved from the text (variables,
                    globs, network writes, package installs) or the command is
                    unrecognised: the model must re-issue with a ``justification``.
* ``catastrophic``  whole filesystem, a device node, credentials, or privilege
                    escalation: refused, and no justification unlocks it.

Biased toward recall: an unfamiliar command is ``confirm``, never ``safe``.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass

CATASTROPHIC = "catastrophic"
CONFIRM = "confirm"
LOW = "low"
SAFE = "safe"

_UNEXPANDABLE = re.compile(r"[$*?~`{}{}]")
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||&|\n")

SAFE_BASES = {
    "awk",
    "basename",
    "builtin",
    "cat",
    "cd",
    "command",
    "date",
    "dirname",
    "du",
    "echo",
    "egrep",
    "env",
    "exit",
    "export",
    "false",
    "fgrep",
    "find",
    "fg",
    "bg",
    "git",
    "grep",
    "head",
    "hostname",
    "jobs",
    "jq",
    "less",
    "ls",
    "md5",
    "md5sum",
    "printf",
    "pwd",
    "read",
    "return",
    "rg",
    "sed",
    "set",
    "sha1sum",
    "sha256sum",
    "sleep",
    "sort",
    "stat",
    "tail",
    "test",
    "true",
    "type",
    "uname",
    "uniq",
    "unset",
    "wait",
    "wc",
    "which",
    "whoami",
}
SAFE_GIT_SUBCOMMANDS = {
    "blame",
    "branch",
    "describe",
    "diff",
    "log",
    "ls-files",
    "remote",
    "show",
    "status",
}
LOW_BASES = {
    "chmod",
    "chown",
    "cp",
    "install",
    "mkdir",
    "mv",
    "rm",
    "rmdir",
    "sed",
    "tee",
    "touch",
    "truncate",
}
CONFIRM_BASES = {
    "anthropic",
    "ansible",
    "aws",
    "brew",
    "bundle",
    "cargo",
    "composer",
    "curl",
    "docker",
    "gem",
    "gh",
    "gcloud",
    "helm",
    "kubectl",
    "make",
    "npm",
    "npx",
    "pip",
    "pip3",
    "pnpm",
    "poetry",
    "npm publish",
    "pipenv",
    "playwright",
    "sudo",
    "terraform",
    "uv",
    "wget",
    "yarn",
    "brew install",
    "systemctl",
    "service",
    "launchctl",
    "open",
}
SAFE_TEST_PREFIXES = ("pytest", "python -m pytest", "mypy", "ruff", "black", "isort", "python -m ")
INTERPRETERS = {
    "bash",
    "bun",
    "deno",
    "node",
    "perl",
    "php",
    "python",
    "python3",
    "python3.12",
    "ruby",
    "sh",
    "zsh",
}
INLINE_CODE_FLAGS = {"-c", "-e", "-p", "--eval", "--print", "-"}

_CATASTROPHIC_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\brm\s+(-[a-z]*\s+)*(/|/\*|~|~/?\$?)\s*$"),
        "recursive removal of the filesystem root",
    ),
    (
        re.compile(r"\brm\s+(-[a-z]*[rf][a-z]*\s+)+(/|~|\$HOME)(\s|$)"),
        "recursive removal rooted at / or $HOME",
    ),
    (
        re.compile(r"\brm\s+-[a-z]*[rf][a-z]*\s+\.\."),
        "recursive removal reaching above the working directory",
    ),
    (
        re.compile(
            r"\brm\s+-[a-z]*[rf][a-z]*\s+/(?:usr|etc|bin|lib|var|System|Users|home)(?:\s|/|$)"
        ),
        "recursive removal of a system directory",
    ),
    (re.compile(r"\b(mkfs|fdisk|diskutil\s+erase)\b"), "disk formatting"),
    (re.compile(r"\bdd\b[^\n]*\bof=/dev/"), "raw write to a device node"),
    (re.compile(r">\s*/dev/(sd|nvme|disk)"), "redirect onto a block device"),
    (re.compile(r"\bchmod\s+(-[a-z]+\s+)*(777|a\+w)\s+/(\s|$)"), "world-writable root"),
    (re.compile(r"\bchown\s+-[a-z]+\s+[^\s]+\s+/(\s|$)"), "recursive ownership change on /"),
    (re.compile(r":\(\)\s*\{.*\};\s*:"), "fork bomb"),
    (
        re.compile(r"\brm\s+-[a-z]*[rf][a-z]*\s+(~/\.ssh|~/\.aws|~/.config\b|\.ssh)(\s|$)"),
        "removal of credential storage",
    ),
)


@dataclass(frozen=True)
class RiskAssessment:
    tier: str
    reason: str
    needs_justification: bool = False
    records: bool = False

    @property
    def blocked(self) -> bool:
        return self.tier == CATASTROPHIC


def _segments(command: str) -> list[str]:
    return [part.strip() for part in _SEGMENT_SPLIT.split(command) if part.strip()]


def _split(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def _is_interpreter(base: str) -> bool:
    return base in INTERPRETERS or base.startswith("python3.")


def _is_local_script(tokens: list[str], workdir: str) -> bool:
    if not tokens:
        return False
    base = os.path.basename(tokens[0])
    if not _is_interpreter(base):
        return False
    args = tokens[1:]
    if not args or any(arg in INLINE_CODE_FLAGS for arg in args):
        return False
    for arg in args:
        if arg.startswith("-"):
            continue
        path = arg if os.path.isabs(arg) else os.path.join(workdir, arg)
        path = os.path.normpath(path)
        if path != workdir and not path.startswith(workdir + os.sep):
            return False
        return os.path.isfile(path)
    return False


def _is_safe_segment(tokens: list[str], workdir: str) -> bool:
    if not tokens:
        return False
    base = os.path.basename(tokens[0])
    if base == "git" and len(tokens) > 1:
        return tokens[1] in SAFE_GIT_SUBCOMMANDS
    if base in SAFE_BASES and base not in {"sed", "find"}:
        return True
    if base in {"sed", "find"} and not any(
        flag in " ".join(tokens) for flag in ("-i", "-delete", "-exec", "-execdir", ">")
    ):
        return True
    if _is_interpreter(base) and len(tokens) > 1:
        joined = " ".join(tokens)
        if joined.startswith(SAFE_TEST_PREFIXES):
            return True
        return _is_local_script(tokens, workdir)
    return base in {"pytest"}


def _targets_within(target: str, cwd: str) -> bool:
    if target.startswith("-"):
        return True
    expanded = os.path.expanduser(target)
    absolute = expanded if os.path.isabs(expanded) else os.path.join(cwd, expanded)
    normalised = os.path.normpath(absolute)
    return normalised == cwd or normalised.startswith(cwd + os.sep)


def assess(command: str, cwd: str | None = None) -> RiskAssessment:
    """Classify one command line. Every segment must pass for the safest verdict."""
    workdir = os.path.abspath(cwd or os.getcwd())
    segments = _segments(command)
    if not segments:
        return RiskAssessment(SAFE, "empty command")

    for pattern, reason in _CATASTROPHIC_PATTERNS:
        if pattern.search(command):
            return RiskAssessment(CATASTROPHIC, reason)

    worst = SAFE
    reasons: list[str] = []

    for segment in segments:
        if any(marker in segment for marker in ("|(", "$(", "`")):
            return RiskAssessment(CONFIRM, "target depends on command substitution")

        tokens = _split(segment)
        if not tokens:
            continue
        base = os.path.basename(tokens[0])

        if base in ("sudo", "doas", "su"):
            return RiskAssessment(CATASTROPHIC, f"{base} escalates privileges")

        if "curl" in command and re.search(r"\|\s*(ba)?sh", command):
            return RiskAssessment(CATASTROPHIC, "remote script piped into a shell")

        if _is_safe_segment(tokens, workdir):
            continue

        if base in LOW_BASES:
            operands = [token for token in tokens[1:] if not token.startswith("-")]
            if _UNEXPANDABLE.search(segment):
                worst = _raise(worst, CONFIRM)
                reasons.append(f"{base} target comes from a glob or variable")
                continue
            outside = [item for item in operands if not _targets_within(item, workdir)]
            if outside:
                worst = _raise(worst, CONFIRM)
                reasons.append(f"{base} touches a path outside the working directory")
                continue
            if base in {"rm", "rmdir", "truncate"}:
                worst = _raise(worst, LOW)
                reasons.append(f"{base} deletes inside the working directory")
            else:
                worst = _raise(worst, LOW)
                reasons.append(f"{base} modifies files inside the working directory")
            continue

        if base in CONFIRM_BASES:
            worst = _raise(worst, CONFIRM)
            reasons.append(f"{base} changes state outside the working directory")
            continue

        worst = _raise(worst, CONFIRM)
        reasons.append(f"unrecognised command '{base}'")

    reason = "; ".join(dict.fromkeys(reasons)) or "read-only command"
    if worst == CONFIRM:
        return RiskAssessment(CONFIRM, reason, needs_justification=True)
    if worst == LOW:
        return RiskAssessment(LOW, reason, records=True)
    return RiskAssessment(SAFE, reason)


def _raise(current: str, candidate: str) -> str:
    order = {SAFE: 0, LOW: 1, CONFIRM: 2, CATASTROPHIC: 3}
    return candidate if order[candidate] > order[current] else current
