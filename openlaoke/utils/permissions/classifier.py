"""Permission classifier module for intelligent command classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from openlaoke.types.core_types import PermissionResult
from openlaoke.utils.permissions.bash_classifier import (
    CommandSafetyLevel,
    ConfidenceLevel,
    classify_bash_command,
)

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class ClassifierMode(StrEnum):
    """Classifier operation modes."""

    FAST = "fast"
    AI = "ai"
    HYBRID = "hybrid"


@dataclass
class ClassifierResult:
    """Result from the permission classifier."""

    decision: PermissionResult
    confidence: ConfidenceLevel
    reason: str
    safety_level: CommandSafetyLevel | None = None
    matched_pattern: str | None = None
    ai_analysis: str | None = None


def fast_classify_bash(command: str) -> ClassifierResult:
    """Fast rule-based classification of bash commands.

    Uses pattern matching and command lists for quick classification.

    Args:
        command: The bash command to classify

    Returns:
        ClassifierResult with decision and confidence
    """
    bash_result = classify_bash_command(command)

    if bash_result.safety_level == CommandSafetyLevel.SAFE:
        return ClassifierResult(
            decision=PermissionResult.ALLOW,
            confidence=bash_result.confidence,
            reason=bash_result.reason,
            safety_level=bash_result.safety_level,
            matched_pattern=bash_result.matched_pattern,
        )

    if bash_result.safety_level == CommandSafetyLevel.DESTRUCTIVE:
        return ClassifierResult(
            decision=PermissionResult.DENY,
            confidence=bash_result.confidence,
            reason=bash_result.reason,
            safety_level=bash_result.safety_level,
            matched_pattern=bash_result.matched_pattern,
        )

    return ClassifierResult(
        decision=PermissionResult.ASK,
        confidence=bash_result.confidence,
        reason=bash_result.reason,
        safety_level=bash_result.safety_level,
        matched_pattern=bash_result.matched_pattern,
    )


async def ai_classify_bash(
    command: str,
    app_state: AppState,
    context: str = "",
) -> ClassifierResult:
    """AI-based classification for complex or ambiguous commands.

    Uses the AI model to analyze command intent and context.

    Args:
        command: The bash command to classify
        app_state: Application state for accessing AI client
        context: Additional context about command purpose

    Returns:
        ClassifierResult with AI-based decision
    """
    fast_result = fast_classify_bash(command)

    if fast_result.confidence == ConfidenceLevel.HIGH:
        return fast_result

    if fast_result.safety_level == CommandSafetyLevel.DESTRUCTIVE:
        return fast_result

    prompt = f"""Analyze this bash command for safety:

Command: {command}
Context: {context}

Classify as one of:
- SAFE: Read-only operations, harmless commands
- DANGEROUS: Commands that could modify files, permissions, or system state
- DESTRUCTIVE: Commands that could cause irreversible damage

Provide your classification and a brief reason."""

    try:
        if not hasattr(app_state, "get_client"):
            return fast_result

        client = app_state.get_client()
        if client is None:
            return fast_result

        if not hasattr(client, "create_message"):
            return fast_result

        response = await client.create_message(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )

        content = ""
        if response.content:
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

        ai_decision = PermissionResult.ASK
        if "SAFE" in content.upper():
            ai_decision = PermissionResult.ALLOW
        elif "DESTRUCTIVE" in content.upper():
            ai_decision = PermissionResult.DENY

        return ClassifierResult(
            decision=ai_decision,
            confidence=ConfidenceLevel.MEDIUM,
            reason=f"AI analysis: {content[:100]}",
            safety_level=fast_result.safety_level,
            ai_analysis=content,
        )

    except Exception:
        return fast_result


async def hybrid_classify_bash(
    command: str,
    app_state: AppState,
    context: str = "",
) -> ClassifierResult:
    """Hybrid classification combining fast rules and AI analysis.

    Uses fast classification first, then AI for low-confidence cases.

    Args:
        command: The bash command to classify
        app_state: Application state for accessing AI client
        context: Additional context about command purpose

    Returns:
        ClassifierResult with combined decision
    """
    fast_result = fast_classify_bash(command)

    if fast_result.confidence == ConfidenceLevel.HIGH:
        return fast_result

    if fast_result.safety_level == CommandSafetyLevel.DESTRUCTIVE:
        return fast_result

    return await ai_classify_bash(command, app_state, context)


async def classify_bash(
    command: str,
    app_state: AppState,
    mode: ClassifierMode = ClassifierMode.FAST,
    context: str = "",
) -> ClassifierResult:
    """Classify a bash command using specified classifier mode.

    Args:
        command: The bash command to classify
        app_state: Application state
        mode: Classifier mode (fast, ai, or hybrid)
        context: Additional context about command purpose

    Returns:
        ClassifierResult with final decision
    """
    if mode == ClassifierMode.FAST:
        return fast_classify_bash(command)

    if mode == ClassifierMode.AI:
        return await ai_classify_bash(command, app_state, context)

    return await hybrid_classify_bash(command, app_state, context)


def classify_tool(tool_name: str, tool_input: dict) -> ClassifierResult:
    """Classify a general tool call for permission requirements.

    Args:
        tool_name: Name of the tool being called
        tool_input: Input parameters for the tool

    Returns:
        ClassifierResult with classification decision
    """
    safe_tools = {"Read", "Glob", "Grep", "WebFetch"}

    if tool_name in safe_tools:
        return ClassifierResult(
            decision=PermissionResult.ALLOW,
            confidence=ConfidenceLevel.HIGH,
            reason=f"Tool '{tool_name}' is classified as safe/read-only",
        )

    dangerous_tools = {"Write", "Edit", "Bash"}

    if tool_name in dangerous_tools:
        if tool_name == "Bash" and "command" in tool_input:
            return fast_classify_bash(tool_input["command"])

        return ClassifierResult(
            decision=PermissionResult.ASK,
            confidence=ConfidenceLevel.MEDIUM,
            reason=f"Tool '{tool_name}' may modify files or system state",
        )

    return ClassifierResult(
        decision=PermissionResult.ASK,
        confidence=ConfidenceLevel.LOW,
        reason=f"Unknown tool '{tool_name}', requiring confirmation",
    )
