"""Permission system for tool execution control.

Evaluation order is **deny > ask > allow > approved > default** — a stored
"Always allow" can never override an explicit deny rule (deny-first).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import StrEnum

from openlaoke.types.core_types import HyperAutoMode, PermissionMode, PermissionResult


class ClassifierMode(StrEnum):
    """Classifier operation modes for intelligent permission decisions."""

    FAST = "fast"
    AI = "ai"
    HYBRID = "hybrid"


class ConfidenceLevel(StrEnum):
    """Confidence levels for classification decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ClassifierResult:
    """Result from the permission classifier."""

    decision: PermissionResult
    confidence: ConfidenceLevel
    reason: str
    safety_level: str | None = None
    matched_pattern: str | None = None
    ai_analysis: str | None = None


@dataclass
class PermissionRule:
    """A single permission rule matching tool names or patterns."""

    pattern: str
    action: PermissionResult
    description: str = ""

    def matches(self, tool_name: str) -> bool:
        return fnmatch.fnmatch(tool_name, self.pattern)


def _rule_subject(pattern: str, tool_name: str) -> str:
    """Extract the parenthesised subject from a ``Tool(subject)`` pattern."""
    if pattern.startswith(tool_name + "(") and pattern.endswith(")"):
        return pattern[len(tool_name) + 1 : -1]
    return ""


@dataclass
class HyperAutoConfig:
    """Configuration for HyperAuto mode."""

    mode: HyperAutoMode = HyperAutoMode.SEMI_AUTO
    enabled: bool = False
    max_iterations: int = 100
    timeout_seconds: int = 300
    auto_save: bool = True
    learning_enabled: bool = False
    history_limit: int = 50


@dataclass
class PermissionConfig:
    """Configuration for the permission system."""

    mode: PermissionMode = PermissionMode.DEFAULT
    always_allow_rules: list[PermissionRule] = field(default_factory=list)
    always_deny_rules: list[PermissionRule] = field(default_factory=list)
    always_ask_rules: list[PermissionRule] = field(default_factory=list)
    approved_tools: list[str] = field(default_factory=list)
    approved_subjects: dict[str, list[str]] = field(default_factory=dict)
    """Tool name -> list of approved subject strings (e.g. command prefixes).

    "Always allow" recorded from the permission prompt stores a narrow
    subject (command base + first argument for Bash) instead of whitelisting
    the whole tool, so approving ``git status`` never auto-allows ``rm -rf``.
    """
    hyperauto_config: HyperAutoConfig = field(default_factory=HyperAutoConfig)

    @classmethod
    def defaults(cls) -> PermissionConfig:
        return cls(
            always_allow_rules=[
                PermissionRule("Read", PermissionResult.ALLOW, "Read-only file access"),
                PermissionRule("Glob", PermissionResult.ALLOW, "File pattern matching"),
                PermissionRule("Grep", PermissionResult.ALLOW, "Content search"),
                PermissionRule("ListDirectory", PermissionResult.ALLOW, "Directory listing"),
                PermissionRule("ToolSearch", PermissionResult.ALLOW, "Tool discovery"),
            ],
            always_deny_rules=[],
            always_ask_rules=[
                PermissionRule("Bash", PermissionResult.ASK, "Shell command execution"),
                PermissionRule("Write", PermissionResult.ASK, "File write operations"),
                PermissionRule("Edit", PermissionResult.ASK, "File edit operations"),
                PermissionRule("Agent", PermissionResult.ASK, "Sub-agent spawning"),
                PermissionRule("WebBrowser", PermissionResult.ASK, "Browser automation"),
            ],
        )

    # -- core check ---------------------------------------------------------

    def check_tool(self, tool_name: str) -> PermissionResult:
        if self.mode == PermissionMode.BYPASS:
            return PermissionResult.ALLOW

        if self.mode == PermissionMode.AUTO:
            return PermissionResult.ALLOW

        for rule in self.always_deny_rules:
            if rule.matches(tool_name):
                return PermissionResult.DENY

        if tool_name in self.approved_tools:
            return PermissionResult.ALLOW

        for rule in self.always_allow_rules:
            if rule.matches(tool_name):
                return PermissionResult.ALLOW

        for rule in self.always_ask_rules:
            if rule.matches(tool_name):
                return PermissionResult.ASK

        return PermissionResult.ASK

    def check_tool_subject(self, tool_name: str, subject: str | None) -> PermissionResult:
        """Check permission for a tool invocation with a narrow subject.

        ``subject`` is a specific invocation descriptor (e.g. the base command
        of a Bash line).  Subject-level approvals only match the same subject;
        tool-level approvals still match every invocation of that tool.
        Deny rules always win regardless of any stored approval.
        """
        if self.mode in (PermissionMode.BYPASS, PermissionMode.AUTO):
            return PermissionResult.ALLOW

        for rule in self.always_deny_rules:
            if rule.matches(tool_name):
                return PermissionResult.DENY
            rule_subject = _rule_subject(rule.pattern, tool_name)
            if subject and rule_subject and fnmatch.fnmatch(subject, rule_subject):
                return PermissionResult.DENY

        if subject and subject in self.approved_subjects.get(tool_name, []):
            return PermissionResult.ALLOW

        return self.check_tool(tool_name)

    # -- approval memory ----------------------------------------------------

    def approve_tool(self, tool_name: str, remember: bool = False) -> None:
        if remember and tool_name not in self.approved_tools:
            self.approved_tools.append(tool_name)

    def approve_subject(self, tool_name: str, subject: str, remember: bool = True) -> None:
        """Remember an "Always allow" at subject granularity (narrow)."""
        if not remember:
            return
        subjects = self.approved_subjects.setdefault(tool_name, [])
        if subject and subject not in subjects:
            subjects.append(subject)
        elif not subject:
            self.approve_tool(tool_name, remember=True)

    def deny_tool(self, tool_name: str) -> None:
        """Add a permanent deny rule for this tool (and drop its approvals)."""
        self.approved_tools = [t for t in self.approved_tools if t != tool_name]
        self.approved_subjects.pop(tool_name, None)
        if tool_name not in (r.pattern for r in self.always_deny_rules):
            self.always_deny_rules.append(
                PermissionRule(tool_name, PermissionResult.DENY, "Denied via session prompt")
            )

    def deny_subject(self, tool_name: str, subject: str) -> None:
        """Add a permanent deny rule scoped to one subject."""
        pattern = f"{tool_name}({subject})" if subject else tool_name
        if pattern not in (r.pattern for r in self.always_deny_rules):
            self.always_deny_rules.append(
                PermissionRule(pattern, PermissionResult.DENY, "Denied via session prompt")
            )
        subjects = self.approved_subjects.get(tool_name, [])
        self.approved_subjects[tool_name] = [s for s in subjects if s != subject]
