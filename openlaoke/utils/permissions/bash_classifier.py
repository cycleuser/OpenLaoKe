"""Bash command safety classifier for dangerous patterns detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class CommandSafetyLevel(StrEnum):
    """Safety classification levels for bash commands."""

    SAFE = "safe"
    DANGEROUS = "dangerous"
    DESTRUCTIVE = "destructive"


class ConfidenceLevel(StrEnum):
    """Confidence levels for classification decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BashClassificationResult:
    """Result of bash command classification."""

    safety_level: CommandSafetyLevel
    confidence: ConfidenceLevel
    reason: str
    matched_pattern: str | None = None


SAFE_COMMANDS = {
    "ls",
    "cat",
    "grep",
    "find",
    "pwd",
    "echo",
    "head",
    "tail",
    "wc",
    "sort",
    "uniq",
    "cut",
    "tr",
    "sed",
    "awk",
    "diff",
    "tree",
    "file",
    "stat",
    "du",
    "df",
    "which",
    "whereis",
    "type",
    "alias",
    "history",
    "jobs",
    "ps",
    "top",
    "htop",
    "whoami",
    "id",
    "groups",
    "date",
    "cal",
    "uptime",
    "uname",
    "hostname",
    "arch",
    "env",
    "printenv",
    "git",
    "npm",
    "yarn",
    "pnpm",
    "pip",
    "pip3",
    "uv",
    "python",
    "python3",
    "node",
    "ruby",
    "perl",
    "php",
    "cargo",
    "rustc",
    "go",
    "java",
    "javac",
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "tar",
    "zip",
    "unzip",
    "gzip",
    "gunzip",
    "mkdir",
    "touch",
    "cp",
    "mv",
    "ln",
    "chmod",
    "chown",
    "chgrp",
    "less",
    "more",
    "vi",
    "vim",
    "nano",
    "emacs",
    "man",
    "info",
    "help",
    "true",
    "false",
    "yes",
    "no",
    "sleep",
    "xargs",
    "parallel",
    "make",
    "cmake",
    "docker",
    "kubectl",
    "terraform",
    "ansible",
    "pytest",
    "jest",
    "mocha",
    "ruff",
    "mypy",
    "black",
    "rg",
    "fd",
    "fzf",
    "bat",
    "exa",
    "lsd",
}

DANGEROUS_COMMANDS = {
    "rm",
    "rmdir",
    "sudo",
    "su",
    "doas",
    "chmod",
    "chown",
    "chgrp",
    "systemctl",
    "service",
    "initctl",
    "iptables",
    "ip6tables",
    "nft",
    "netstat",
    "ss",
    "ip",
    "kill",
    "killall",
    "pkill",
    "xkill",
    "mkfs",
    "fdisk",
    "parted",
    "gdisk",
    "sfdisk",
    "dd",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "useradd",
    "userdel",
    "usermod",
    "groupadd",
    "groupdel",
    "passwd",
    "chpasswd",
    "crontab",
    "at",
    "batch",
    "ln",
    "unlink",
    "mv",
    "cp",
}

DESTRUCTIVE_PATTERNS = [
    (r"rm\s+-rf\s+/$", "rm -rf / - destroys entire filesystem"),
    (r"rm\s+-rf\s+/\s*$", "rm -rf / - destroys entire filesystem"),
    (r"rm\s+-rf\s+\*", "rm -rf * - destroys all files in current directory"),
    (r"rm\s+-rf\s+~", "rm -rf ~ - destroys home directory"),
    (r"rm\s+-rf\s+\$HOME", "rm -rf $HOME - destroys home directory"),
    (r"rm\s+-rf\s+/\*", "rm -rf /* - destroys entire filesystem"),
    (r"mkfs(\.\w+)?\s+", "mkfs - formats filesystem"),
    (r"mkfs\.ext[234]\s+", "mkfs.ext2/3/4 - formats filesystem"),
    (r"mkfs\.xfs\s+", "mkfs.xfs - formats filesystem"),
    (r"mkfs\.btrfs\s+", "mkfs.btrfs - formats filesystem"),
    (r"dd\s+.*of=/dev/[sh]d[a-z]", "dd writing to disk - destroys disk data"),
    (r"dd\s+.*of=/dev/nvme", "dd writing to NVMe - destroys disk data"),
    (r"dd\s+.*of=/dev/mmcblk", "dd writing to MMC - destroys disk data"),
    (r":()\s*{\s*:\s*|:\s*&\s*};\s*:", "fork bomb - crashes system"),
    (r">\s*/dev/sd[a-z]", "redirect to disk device - destroys data"),
    (r">\s*/dev/hd[a-z]", "redirect to disk device - destroys data"),
    (r">\s*/dev/nvme", "redirect to NVMe device - destroys data"),
    (r"shutdown\s+-h\s+now", "immediate shutdown"),
    (r"reboot\s+--force", "forced reboot"),
    (r"halt\s+--force", "forced halt"),
    (r"poweroff\s+--force", "forced poweroff"),
    (r"systemctl\s+stop\s+systemd", "stopping systemd - dangerous"),
    (r"kill\s+-9\s+-1", "kill all processes"),
    (r"kill\s+-9\s+1$", "kill init process"),
    (r"kill\s+-KILL\s+1$", "kill init process"),
    (r"killall\s+-9\s*$", "kill all processes"),
    (r"pkill\s+-9\s*$", "kill all processes"),
]

DANGEROUS_PATTERNS = [
    (r"rm\s+-[rf]+", "rm with recursive/force flags"),
    (r"rm\s+.*\*\s*$", "rm ending with wildcard"),
    (r"sudo\s+rm", "sudo rm - elevated deletion"),
    (r"sudo\s+chmod", "sudo chmod - elevated permission change"),
    (r"sudo\s+chown", "sudo chown - elevated ownership change"),
    (r"sudo\s+dd", "sudo dd - elevated disk operations"),
    (r"sudo\s+mkfs", "sudo mkfs - elevated filesystem formatting"),
    (r"sudo\s+fdisk", "sudo fdisk - elevated disk partitioning"),
    (r"chmod\s+[0-7]*777", "chmod 777 - overly permissive"),
    (r"chmod\s+-R", "chmod recursive"),
    (r"chown\s+-R", "chown recursive"),
    (r"kill\s+-9", "kill -9 (SIGKILL) - force kill"),
    (r"kill\s+-KILL", "kill -KILL - force kill"),
    (r">\s*/etc/", "redirect to system config directory"),
    (r">\s*/boot/", "redirect to boot directory"),
    (r">\s*/usr/", "redirect to usr directory"),
    (r">\s*/bin/", "redirect to bin directory"),
    (r">\s*/sbin/", "redirect to sbin directory"),
    (r"curl\s+.*\|\s*(ba)?sh", "curl piped to shell - remote code execution"),
    (r"wget\s+.*\|\s*(ba)?sh", "wget piped to shell - remote code execution"),
    (r"eval\s+", "eval - dynamic code execution"),
    (r"exec\s+", "exec - replaces process"),
    (r"source\s+.*http", "source from remote URL"),
    (r"\.\s+.*http", "source from remote URL"),
]

SAFE_PATTERNS = [
    (r"^ls\s", "ls - listing directory"),
    (r"^cat\s", "cat - reading file"),
    (r"^grep\s", "grep - searching content"),
    (r"^find\s", "find - searching files"),
    (r"^pwd\s*$", "pwd - print working directory"),
    (r"^echo\s", "echo - printing text"),
    (r"^head\s", "head - reading file start"),
    (r"^tail\s", "tail - reading file end"),
    (r"^wc\s", "wc - counting lines/words"),
    (r"^sort\s", "sort - sorting lines"),
    (r"^git\s+(status|log|diff|branch|show)", "git read operations"),
    (r"^npm\s+(list|view|search|info)", "npm read operations"),
    (r"^pip\s+(list|show|freeze)", "pip read operations"),
    (r"^python\s+-c\s+['\"]print", "python print statement"),
    (r"^pytest\s+", "pytest - running tests"),
    (r"^ruff\s+check", "ruff linting"),
    (r"^mypy\s+", "mypy type checking"),
    (r"^black\s+--check", "black format check"),
]


def extract_base_command(command: str) -> str:
    """Extract the base command from a potentially complex command string."""
    command = command.strip()

    if command.startswith("sudo ") or command.startswith("doas "):
        command = command[5:].strip()

    parts = command.split()
    if not parts:
        return ""

    base = parts[0]
    if base.startswith("./") or base.startswith("/"):
        return ""

    return base


def check_patterns(command: str, patterns: list[tuple[str, str]]) -> tuple[bool, str | None]:
    """Check if command matches any pattern in the list."""
    for pattern, description in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True, description
    return False, None


def classify_bash_command(command: str) -> BashClassificationResult:
    """Classify a bash command into safety levels.

    Args:
        command: The bash command to classify

    Returns:
        BashClassificationResult with safety level, confidence, and reason
    """
    if not command or not command.strip():
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.SAFE,
            confidence=ConfidenceLevel.HIGH,
            reason="Empty command",
        )

    command = command.strip()

    matched, description = check_patterns(command, DESTRUCTIVE_PATTERNS)
    if matched:
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.DESTRUCTIVE,
            confidence=ConfidenceLevel.HIGH,
            reason=description or "Matches destructive pattern",
            matched_pattern=description,
        )

    matched, description = check_patterns(command, DANGEROUS_PATTERNS)
    if matched:
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.DANGEROUS,
            confidence=ConfidenceLevel.HIGH,
            reason=description or "Matches dangerous pattern",
            matched_pattern=description,
        )

    base_cmd = extract_base_command(command)

    if base_cmd in DANGEROUS_COMMANDS:
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.DANGEROUS,
            confidence=ConfidenceLevel.HIGH,
            reason=f"Base command '{base_cmd}' is classified as dangerous",
            matched_pattern=base_cmd,
        )

    if base_cmd in SAFE_COMMANDS:
        matched_safe, safe_desc = check_patterns(command, SAFE_PATTERNS)
        if matched_safe:
            return BashClassificationResult(
                safety_level=CommandSafetyLevel.SAFE,
                confidence=ConfidenceLevel.HIGH,
                reason=safe_desc or f"Command '{base_cmd}' is known safe",
                matched_pattern=safe_desc,
            )

        return BashClassificationResult(
            safety_level=CommandSafetyLevel.SAFE,
            confidence=ConfidenceLevel.MEDIUM,
            reason=f"Base command '{base_cmd}' is generally safe, but check arguments",
        )

    matched, description = check_patterns(command, SAFE_PATTERNS)
    if matched:
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.SAFE,
            confidence=ConfidenceLevel.HIGH,
            reason=description or "Matches safe pattern",
            matched_pattern=description,
        )

    return BashClassificationResult(
        safety_level=CommandSafetyLevel.DANGEROUS,
        confidence=ConfidenceLevel.LOW,
        reason=f"Unknown command '{base_cmd}', treating as potentially dangerous",
    )


def is_safe_command(command: str) -> bool:
    """Quick check if a command is safe to auto-execute."""
    result = classify_bash_command(command)
    return result.safety_level == CommandSafetyLevel.SAFE


def is_destructive_command(command: str) -> bool:
    """Check if a command is destructive and should always be blocked."""
    result = classify_bash_command(command)
    return result.safety_level == CommandSafetyLevel.DESTRUCTIVE


def is_dangerous_command(command: str) -> bool:
    """Check if a command is dangerous and needs confirmation."""
    result = classify_bash_command(command)
    return result.safety_level == CommandSafetyLevel.DANGEROUS
