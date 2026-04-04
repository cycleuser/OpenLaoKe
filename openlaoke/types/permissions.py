"""Permission system for tool execution control."""

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
    approved_tools: set[str] = field(default_factory=set)
    hyperauto_config: HyperAutoConfig = field(default_factory=HyperAutoConfig)

    @classmethod
    def defaults(cls) -> PermissionConfig:
        return cls(
            always_allow_rules=[
                PermissionRule("Read", PermissionResult.ALLOW, "Read-only file access"),
                PermissionRule("Glob", PermissionResult.ALLOW, "File pattern matching"),
                PermissionRule("Grep", PermissionResult.ALLOW, "Content search"),
                PermissionRule("Bash", PermissionResult.ALLOW, "Shell command execution"),
                PermissionRule("Write", PermissionResult.ALLOW, "File write operations"),
                PermissionRule("Edit", PermissionResult.ALLOW, "File edit operations"),
            ],
            always_deny_rules=[],
            always_ask_rules=[
                PermissionRule("Agent", PermissionResult.ASK, "Sub-agent spawning"),
            ],
        )

    def check_tool(self, tool_name: str) -> PermissionResult:
        if self.mode == PermissionMode.BYPASS:
            return PermissionResult.ALLOW

        if self.mode == PermissionMode.AUTO:
            return PermissionResult.ALLOW

        if tool_name in self.approved_tools:
            return PermissionResult.ALLOW

        for rule in self.always_deny_rules:
            if rule.matches(tool_name):
                return PermissionResult.DENY

        for rule in self.always_allow_rules:
            if rule.matches(tool_name):
                return PermissionResult.ALLOW

        for rule in self.always_ask_rules:
            if rule.matches(tool_name):
                return PermissionResult.ASK

        return PermissionResult.ASK

    def approve_tool(self, tool_name: str, remember: bool = False) -> None:
        if remember:
            self.approved_tools.add(tool_name)

    def deny_tool(self, tool_name: str) -> None:
        self.approved_tools.discard(tool_name)
