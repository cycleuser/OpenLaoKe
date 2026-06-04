"""Permission decision and rule list."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Decision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass
class Rule:
    """A single declarative permission rule.

    Format: ``ToolName`` or ``ToolName(glob)``.

    The glob is matched against the *subject* of the tool call —
    the file path, command, pattern, etc. depending on the tool.
    """

    raw: str
    decision: Decision
    tool_name: str = ""
    subject_glob: str = ""

    def __post_init__(self) -> None:
        if not self.tool_name:
            self._parse(self.raw)

    def _parse(self, raw: str) -> None:
        if "(" in raw and raw.endswith(")"):
            self.tool_name, rest = raw.split("(", 1)
            self.subject_glob = rest[:-1].strip()
        else:
            self.tool_name = raw.strip()
            self.subject_glob = ""


@dataclass
class Policy:
    """Permission policy: ordered list of rules and a default decision."""

    mode: str = "ask"
    allow: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._allow_rules = [Rule(r, Decision.ALLOW) for r in self.allow]
        self._ask_rules = [Rule(r, Decision.ASK) for r in self.ask]
        self._deny_rules = [Rule(r, Decision.DENY) for r in self.deny]

    def subject(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        """Extract the human-meaningful subject of a tool call."""
        for key in ("file_path", "path", "command", "pattern", "query", "url"):
            value = tool_args.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def match(self, tool_name: str, tool_args: dict[str, Any]) -> Decision:
        """Resolve a tool call to ALLOW/ASK/DENY.

        Resolution order: deny > ask > allow > fallback mode.
        """
        subject = self.subject(tool_name, tool_args)
        if not subject:
            short_name = tool_name.split(".")[-1] if "." in tool_name else tool_name
            for rule in self._deny_rules:
                if self._matches_rule(rule, short_name, subject):
                    return Decision.DENY
            for rule in self._ask_rules:
                if self._matches_rule(rule, short_name, subject):
                    return Decision.ASK
            for rule in self._allow_rules:
                if self._matches_rule(rule, short_name, subject):
                    return Decision.ALLOW
            return self._fallback(short_name)

        for rule in self._deny_rules:
            if self._matches_rule(rule, tool_name, subject):
                return Decision.DENY
        for rule in self._ask_rules:
            if self._matches_rule(rule, tool_name, subject):
                return Decision.ASK
        for rule in self._allow_rules:
            if self._matches_rule(rule, tool_name, subject):
                return Decision.ALLOW
        return self._fallback(tool_name)

    def _matches_rule(self, rule: Rule, tool_name: str, subject: str) -> bool:
        if rule.tool_name != tool_name and rule.tool_name != "*":
            return False
        if not rule.subject_glob:
            return True
        if not subject:
            return False
        return fnmatch.fnmatch(subject, rule.subject_glob)

    def _match_rules(self, tool_name: str, tool_args: dict[str, Any], target: Decision) -> Decision | None:
        """Check if any rule of the given decision type matches.

        Returns the decision if matched, None otherwise.
        """
        subject = self.subject(tool_name, tool_args)
        short_name = tool_name.split(".")[-1] if "." in tool_name else tool_name
        rules = (
            self._deny_rules if target == Decision.DENY
            else self._allow_rules if target == Decision.ALLOW
            else self._ask_rules
        )
        for rule in rules:
            if self._matches_rule(rule, short_name, subject):
                return target
            if subject and self._matches_rule(rule, tool_name, subject):
                return target
        return None

    def _fallback(self, tool_name: str) -> Decision:
        if self.mode == "allow":
            return Decision.ALLOW
        if self.mode == "deny":
            return Decision.DENY
        return Decision.ASK


SAFE_BASH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*ls\b"),
    re.compile(r"^\s*pwd\b"),
    re.compile(r"^\s*cat\b"),
    re.compile(r"^\s*head\b"),
    re.compile(r"^\s*tail\b"),
    re.compile(r"^\s*wc\b"),
    re.compile(r"^\s*grep\b"),
    re.compile(r"^\s*find\b"),
    re.compile(r"^\s*rg\b"),
    re.compile(r"^\s*echo\b"),
    re.compile(r"^\s*printf\b"),
    re.compile(r"^\s*git\s+status\b"),
    re.compile(r"^\s*git\s+log\b"),
    re.compile(r"^\s*git\s+diff\b"),
    re.compile(r"^\s*git\s+branch\b"),
    re.compile(r"^\s*test\b"),
    re.compile(r"^\s*pytest\b"),
    re.compile(r"^\s*python\s+-m\s+pytest\b"),
)


def is_readonly_bash_subject(command: str) -> bool:
    """Reclassify a writer bash call as read-only when it matches safe patterns.

    Used by the gate to avoid prompting the user for ``git status`` or ``ls``.
    """
    if not command:
        return False
    if any(ch in command for ch in (">", ">>", "|", ";", "&", "`", "$(")):
        return False
    return any(p.match(command) for p in SAFE_BASH_PATTERNS)
