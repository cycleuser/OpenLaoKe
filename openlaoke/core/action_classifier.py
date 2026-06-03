"""Message action classifier - determines whether a message needs clarification, action, or is just a response."""

from __future__ import annotations

import re
from dataclasses import dataclass


class ActionKind:
    CLARIFY = "clarify"
    ACTION = "action"
    RESPOND = "respond"
    GREETING = "greeting"
    PRAISE = "praise"


@dataclass
class ActionResult:
    kind: str
    confidence: float
    reason: str = ""


_CLARIFY_PATTERNS = [
    re.compile(r"\?\s*$", re.IGNORECASE),
    re.compile(
        r"^(?:what|how|why|when|where|who|can you explain|explain|tell me about|is it|does it|do you)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:please|pls)\s+(?:explain|clarify|elaborate|help)\b", re.IGNORECASE),
]

_GREETING_PATTERNS = [
    re.compile(
        r"^(?:hi|hey|hello|greetings|good morning|good afternoon|good evening)\b", re.IGNORECASE
    ),
]

_PRAISE_PATTERNS = [
    re.compile(
        r"^(?:thanks|thank you|good job|great|awesome|nice|appreciate|well done)\b", re.IGNORECASE
    ),
]

_ACTION_PATTERNS = [
    re.compile(
        r"\b(?:fix|add|remove|delete|create|modify|update|change|implement|refactor|write|build|install|setup|configure|deploy|test|debug|optimize|migrate|convert|generate)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please|pls|can you|could you|would you)\s+(?:fix|add|remove|create|change|update|write|build|install|implement|refactor|help)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:code|file|script|function|class|module|package|project|app|application|server|api|endpoint|database|db)\b",
        re.IGNORECASE,
    ),
]


def classify_action(message: str) -> ActionResult:
    """Classify a user message to determine the intent.

    Returns ActionKind plus confidence (0-1).
    """
    if not message or not message.strip():
        return ActionResult(kind=ActionKind.CLARIFY, confidence=0.5, reason="empty message")

    msg = message.strip()
    msg_lower = msg.lower()

    # Check clarification patterns
    for pattern in _CLARIFY_PATTERNS:
        if pattern.search(msg_lower):
            return ActionResult(kind=ActionKind.CLARIFY, confidence=0.8, reason="question detected")

    # Check greeting
    for pattern in _GREETING_PATTERNS:
        if pattern.search(msg_lower):
            if any(p.search(msg_lower) for p in _ACTION_PATTERNS):
                break
            return ActionResult(
                kind=ActionKind.GREETING, confidence=0.9, reason="greeting detected"
            )

    # Check praise
    for pattern in _PRAISE_PATTERNS:
        if pattern.search(msg_lower):
            if any(p.search(msg_lower) for p in _ACTION_PATTERNS):
                break
            return ActionResult(
                kind=ActionKind.PRAISE, confidence=0.7, reason="praise/thanks detected"
            )

    # Check action patterns
    action_score = 0
    action_matches = 0
    for pattern in _ACTION_PATTERNS:
        matches = pattern.findall(msg_lower)
        action_matches += len(matches)
    action_score = min(1.0, action_matches * 0.3)

    if action_score >= 0.3:
        return ActionResult(
            kind=ActionKind.ACTION,
            confidence=action_score,
            reason=f"{action_matches} action keywords",
        )

    return ActionResult(kind=ActionKind.RESPOND, confidence=0.5, reason="default response")
