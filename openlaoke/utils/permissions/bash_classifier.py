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
    # read-only system inspection (macOS / Linux)
    "lscpu",
    "lsmem",
    "lsblk",
    "blkid",
    "free",
    "vm_stat",
    "sysctl",
    "system_profiler",
    "sw_vers",
    "ioreg",
    "hostinfo",
    "nproc",
    "getconf",
    "locale",
    "lsof",
    "w",
    "who",
    "users",
    "last",
    "ifconfig",
    "ipconfig",
    "networksetup",
    "scutil",
    "pmset",
    "iostat",
    "mdls",
    "mdfind",
    "hdiutil",
    "defaults",
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

# Interpreter wrappers whose arguments can smuggle arbitrary code.  A command
# like `python3 -c "import os; os.system('rm -rf ~')"` must not be classified
# by its interpreter name alone.
INTERPRETER_COMMANDS = {
    "python",
    "python3",
    "node",
    "ruby",
    "perl",
    "php",
    "bash",
    "sh",
    "zsh",
    "fish",
    "powershell",
    "pwsh",
    "lua",
    "tclsh",
    "osascript",
    "awk",
    "sed",
    "eval",
    "xargs",
}

# Interpreter inline-code flags: `<interp> -c/-e/-f/-x <code>` runs the next
# argument as code, so the whole invocation is treated as DANGEROUS (ask).
_INTERPRETER_CODE_RE = re.compile(
    r"(?:^|;|\|\||&&|\|)\s*(?:sudo\s+|doas\s+)?(?:env\s+\S+=\S+\s+)?"
    r"(python3?|node|ruby|perl|php|bash|sh|zsh|fish|powershell|pwsh|lua|tclsh|osascript)\s+"
    r"(?:-\w+\s+)*-[cefx]\b",
)

# Commands that spawn further programs: their inner payload is opaque.
_NESTED_SHELL_RE = re.compile(r"(?:^|;|\|\||&&|\|)\s*(?:sudo\s+)?(bash|sh|zsh|fish)\s+-c\b")

# Redirect targets that write files anywhere outside /tmp or /dev/null.
_REDIRECT_RE = re.compile(r"\d{0,2}>{1,2}\s*([^\s;&|]+)")
_APPEND_RE = re.compile(r">>")
_SAFE_REDIRECT_RE = re.compile(r"^/dev/null$|^/tmp/|^&\d$|^\d*$|^&1$")

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
    # Network access patterns (from sekrun)
    (r"git\s+push", "git push - pushes changes to remote"),
    (r"git\s+pull", "git pull - pulls from remote"),
    (r"git\s+fetch", "git fetch - fetches from remote"),
    (r"npm\s+(install|i)\s", "npm install - installs packages"),
    (r"pnpm\s+(install|add)\s", "pnpm install - installs packages"),
    (r"yarn\s+add\s", "yarn add - installs packages"),
    (r"pip\s+install\s", "pip install - installs packages"),
    (r"pip3\s+install\s", "pip3 install - installs packages"),
    (r"uv\s+pip\s+install", "uv pip install - installs packages"),
    (r"cargo\s+install\s", "cargo install - installs packages"),
    (r"go\s+install\s", "go install - installs packages"),
    (r"gem\s+install\s", "gem install - installs packages"),
    # Network connections (from sekrun)
    (r"nc\s", "nc/netcat - network tool"),
    (r"ncat\s", "ncat - network tool"),
    (r"ssh\s", "ssh - remote connection"),
    (r"scp\s", "scp - remote file copy"),
    (r"rsync\s+.*:", "rsync to/from remote"),
    (r"ftp\s", "ftp - file transfer"),
    (r"sftp\s", "sftp - file transfer"),
    (r"telnet\s", "telnet - remote connection"),
    (r"wget\s+(?!.*\|\s*(ba)?sh)", "wget - downloads content"),
    (r"curl\s+(?!.*\|\s*(ba)?sh)", "curl - downloads content"),
    # Path traversal
    (r"\.\.\/", "path traversal (../)"),
    (r"\.\.\\\\", "path traversal (..\\)"),
    # Invoke-WebRequest (PowerShell)
    (r"invoke-webrequest", "Invoke-WebRequest - downloads content"),
    (r"iwr\s", "iwr (Invoke-WebRequest) - downloads content"),
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


def _split_compound_command(command: str) -> list[str]:
    """Split a shell line into segments at ; && || and unquoted pipes.

    Quoted content is protected via a placeholder swap so pipes inside
    strings (e.g. `grep "a|b"`) don't create bogus segments.
    """
    placeholders: list[str] = []

    def _protect(match: re.Match) -> str:
        token = f"\x00{len(placeholders)}\x00"
        placeholders.append(match.group(0))
        return token

    command = re.sub(r"'[^']*'|\"[^\"]*\"", _protect, command)
    segments = re.split(r";|\|\||&&|\|", command)
    out = []
    for seg in segments:
        for i, ph in enumerate(placeholders):
            seg = seg.replace(f"\x00{i}\x00", ph)
        seg = seg.strip()
        if seg:
            out.append(seg)
    return out


def _check_redirect_targets(command: str) -> tuple[bool, str | None]:
    """Flag shell redirects that write to a file path (project-external writes
    such as `echo x > ~/.zshrc` must not be silently auto-executed)."""
    if _APPEND_RE.search(command) or re.search(r"(?<![>])>(?![>\d&])", command) is None:
        # Any plain `>` or `>>` redirect at all → treat as write for safety
        # except when the target is clearly /dev/null, a tmp file, or a
        # file-descriptor dup like 2>&1.
        pass
    for match in _REDIRECT_RE.finditer(command):
        target = match.group(1).strip()
        if not target or _SAFE_REDIRECT_RE.match(target):
            continue
        return True, f"redirect writes to '{target}' - untracked file modification"
    return False, None


def check_patterns(command: str, patterns: list[tuple[str, str]]) -> tuple[bool, str | None]:
    """Check if command matches any pattern in the list."""
    for pattern, description in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True, description
    return False, None


def classify_bash_command(command: str) -> BashClassificationResult:
    """Classify a bash command into safety levels.

    Compound commands (``;``, ``&&``, ``||``, ``|``) are classified per
    segment; the *worst* segment wins.  Interpreter inline-code calls
    (``python3 -c``, ``node -e``, ``bash -c``) and redirects that write files
    are treated as dangerous so they require user approval.

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

    worst = _classify_single(command)
    if worst.safety_level == CommandSafetyLevel.DESTRUCTIVE:
        return worst

    # Compound commands: each segment classified independently; the worst
    # segment's level wins.  This closes the `safe && dangerous` gap.
    segments = _split_compound_command(command)
    if len(segments) > 1:
        for seg in segments:
            seg_result = _classify_single(seg)
            if seg_result.safety_level in (
                CommandSafetyLevel.DESTRUCTIVE,
                CommandSafetyLevel.DANGEROUS,
            ):
                return seg_result
            if (
                seg_result.safety_level == CommandSafetyLevel.SAFE
                and worst.safety_level == CommandSafetyLevel.SAFE
                and seg_result.confidence == ConfidenceLevel.HIGH
                and worst.confidence == ConfidenceLevel.LOW
            ):
                worst = seg_result

    # Redirect target check applies to the whole line (target is a sibling
    # node of the command, not an argument of it).
    redir_bad, redir_reason = _check_redirect_targets(command)
    if redir_bad:
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.DANGEROUS,
            confidence=ConfidenceLevel.HIGH,
            reason=redir_reason or "Redirect target",
            matched_pattern=redir_reason,
        )

    return worst


def _classify_single(command: str) -> BashClassificationResult:
    """Classify a single (non-compound) shell segment."""
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

    # Interpreter inline code: `python3 -c '<code>'`, `node -e`, `bash -c` …
    # The payload is opaque, so require confirmation regardless of the
    # interpreter being on the SAFE list.
    if _INTERPRETER_CODE_RE.search(command):
        return BashClassificationResult(
            safety_level=CommandSafetyLevel.DANGEROUS,
            confidence=ConfidenceLevel.HIGH,
            reason="Interpreter inline code (python -c / node -e / bash -c) — "
            "payload is opaque and requires approval",
            matched_pattern="interpreter-inline-code",
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

        # Bare interpreter/script names without flags stay medium-confidence
        # safe; anything reading inline code was already caught above.
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
