"""Heuristic + classifier-driven auto-plan detection.

Score 0..6 based on user input shape. Borderline scores (1-2) consult a
cheap-model classifier for confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_COMPLEX_TERMS = (
    "implement",
    "build",
    "create",
    "design",
    "refactor",
    "migrate",
    "redesign",
    "rewrite",
    "convert",
    "integrate",
    "port",
    "restructure",
    "optimize",
    "deploy",
)

_MULTI_SURFACE_TERMS = (
    "api",
    "frontend",
    "backend",
    "database",
    "tests",
    "ci",
    "docs",
    "config",
    "infrastructure",
    "infra",
    "service",
    "schema",
    "migration",
    "pipeline",
)

_DOC_TERMS = (
    "spec",
    "specification",
    "rfc",
    "design doc",
    "readme",
    "issue",
    "ticket",
)


@dataclass
class PlanHeuristic:
    """Heuristic scorer: returns 0..6."""

    text: str
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def evaluate(self) -> PlanHeuristic:
        text = self.text or ""
        reasons: list[str] = []

        if len(text) >= 160:
            self.score += 1
            reasons.append("length>=160")

        numbered = len(re.findall(r"^\s*\d+[\.)]\s+", text, re.MULTILINE))
        if numbered >= 2:
            self.score += 1
            reasons.append("numbered-list")

        if text.count("\n") >= 2:
            self.score += 1
            reasons.append("multi-line")

        if any(t in text.lower() for t in _COMPLEX_TERMS):
            self.score += 1
            reasons.append("complex-intent")

        if any(t in text.lower() for t in _MULTI_SURFACE_TERMS):
            self.score += 1
            reasons.append("multi-surface")

        if any(t in text.lower() for t in _DOC_TERMS):
            self.score += 1
            reasons.append("doc/issue")

        if len(re.findall(r"[@/]\w+", text)) >= 2 or len(re.findall(r"\.\w{1,4}\b", text)) >= 2:
            self.score += 1
            reasons.append("references")

        self.reasons = reasons
        return self


def should_auto_plan(
    text: str,
    mode: str = "ask",
    classifier: Any = None,
) -> bool:
    """Return True if the user input warrants plan mode.

    ``mode`` is one of ``off``, ``ask``, ``on``. ``classifier`` is an
    async callable for borderline cases (score 1-2). If the classifier
    is not provided, the heuristic alone is used.
    """
    if mode == "off":
        return False
    if mode == "on":
        return True
    score = PlanHeuristic(text).evaluate()
    if score.score >= 3:
        return True
    if score.score in (1, 2) and classifier is not None:
        try:
            decision = classifier(text)
            if hasattr(decision, "__await__"):
                return False
            return bool(decision)
        except Exception:
            return False
    return False
