"""Model capability types and constants."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CapabilityCategory(StrEnum):
    BASIC_CHAT = "basic_chat"
    TOOL_CALLING = "tool_calling"
    CODE_GENERATION = "code_generation"
    MULTI_TURN = "multi_turn"
    ERROR_RECOVERY = "error_recovery"
    INSTRUCTION_FOLLOWING = "instruction_following"


class ModelTier(StrEnum):
    TIER_1_ADVANCED = "tier_1_advanced"
    TIER_2_CAPABLE = "tier_2_capable"
    TIER_3_MODERATE = "tier_3_moderate"
    TIER_4_BASIC = "tier_4_basic"
    TIER_5_LIMITED = "tier_5_limited"


@dataclass
class CapabilityScore:
    category: CapabilityCategory
    score: float
    max_score: float = 10.0
    tests_passed: int = 0
    tests_total: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score) * 100

    @property
    def pass_rate(self) -> float:
        if self.tests_total == 0:
            return 0.0
        return (self.tests_passed / self.tests_total) * 100


@dataclass
class ModelBenchmark:
    provider: str
    model: str
    overall_score: float
    tier: ModelTier
    capabilities: dict[str, CapabilityScore]
    tested_at: float
    test_duration: float
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "overall_score": self.overall_score,
            "tier": self.tier.value,
            "capabilities": {
                k: {
                    "score": v.score,
                    "max_score": v.max_score,
                    "tests_passed": v.tests_passed,
                    "tests_total": v.tests_total,
                    "percentage": v.percentage,
                    "pass_rate": v.pass_rate,
                    "details": v.details,
                }
                for k, v in self.capabilities.items()
            },
            "tested_at": self.tested_at,
            "test_duration": self.test_duration,
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelBenchmark:
        capabilities = {}
        for k, v in data["capabilities"].items():
            capabilities[k] = CapabilityScore(
                category=CapabilityCategory(k),
                score=v["score"],
                max_score=v.get("max_score", 10.0),
                tests_passed=v.get("tests_passed", 0),
                tests_total=v.get("tests_total", 0),
                details=v.get("details", {}),
            )
        return cls(
            provider=data["provider"],
            model=data["model"],
            overall_score=data["overall_score"],
            tier=ModelTier(data["tier"]),
            capabilities=capabilities,
            tested_at=data["tested_at"],
            test_duration=data["test_duration"],
            recommendations=data.get("recommendations", []),
        )


@dataclass
class TaskGranularity:
    max_subtasks: int
    subtask_complexity_limit: str
    verification_frequency: str
    retry_limit: int
    timeout_multiplier: float
    tool_call_limit: int
    requires_explicit_steps: bool
    min_confidence_threshold: float


_SIZE_RE = re.compile(r"(\d+\.?\d*)\s*b", re.IGNORECASE)

_TIER1_PREFIXES = (
    "claude-",
    "gpt-4o",
    "gpt-4.5",
    "gpt-5",
    "o1",
    "o3",
    "o4",
    "gemini-2.5",
    "grok-3",
)
_TIER2_PREFIXES = (
    "deepseek",
    "llama-3.3",
    "llama-4",
    "mistral-large",
    "gemini-2.0",
    "claude-haiku",
)


def classify_model_tier(model_name: str) -> ModelTier:
    """Determine model tier using rule-based heuristics (not hardcoded names).

    Priority order:
    1. Known premium models → TIER_1
    2. Known capable models → TIER_2
    3. Size: >50B → TIER_2, >20B → TIER_3, >5B → TIER_4, ≤5B → TIER_5
    4. Name hints: large/pro/ultra → TIER_2, medium → TIER_3, small/mini → TIER_4
    5. Fallback → TIER_3
    """
    lower = model_name.lower()

    for prefix in _TIER1_PREFIXES:
        if prefix in lower:
            return ModelTier.TIER_1_ADVANCED

    for prefix in _TIER2_PREFIXES:
        if prefix in lower:
            return ModelTier.TIER_2_CAPABLE

    m = _SIZE_RE.search(lower)
    if m:
        size = float(m.group(1))
        if size > 50:
            return ModelTier.TIER_2_CAPABLE
        if size > 20:
            return ModelTier.TIER_3_MODERATE
        if size > 5:
            return ModelTier.TIER_4_BASIC
        return ModelTier.TIER_5_LIMITED

    if "large" in lower or "pro" in lower or "ultra" in lower:
        return ModelTier.TIER_2_CAPABLE
    if "medium" in lower:
        return ModelTier.TIER_3_MODERATE
    if "small" in lower or "mini" in lower or "nano" in lower or "tiny" in lower:
        return ModelTier.TIER_4_BASIC

    return ModelTier.TIER_3_MODERATE


TIER_GRANULARITIES: dict[ModelTier, TaskGranularity] = {
    ModelTier.TIER_1_ADVANCED: TaskGranularity(
        max_subtasks=20,
        subtask_complexity_limit="high",
        verification_frequency="minimal",
        retry_limit=3,
        timeout_multiplier=1.0,
        tool_call_limit=50,
        requires_explicit_steps=False,
        min_confidence_threshold=0.6,
    ),
    ModelTier.TIER_2_CAPABLE: TaskGranularity(
        max_subtasks=15,
        subtask_complexity_limit="medium",
        verification_frequency="moderate",
        retry_limit=4,
        timeout_multiplier=1.2,
        tool_call_limit=35,
        requires_explicit_steps=False,
        min_confidence_threshold=0.7,
    ),
    ModelTier.TIER_3_MODERATE: TaskGranularity(
        max_subtasks=10,
        subtask_complexity_limit="low",
        verification_frequency="frequent",
        retry_limit=5,
        timeout_multiplier=1.5,
        tool_call_limit=25,
        requires_explicit_steps=True,
        min_confidence_threshold=0.8,
    ),
    ModelTier.TIER_4_BASIC: TaskGranularity(
        max_subtasks=6,
        subtask_complexity_limit="minimal",
        verification_frequency="every_step",
        retry_limit=6,
        timeout_multiplier=2.0,
        tool_call_limit=15,
        requires_explicit_steps=True,
        min_confidence_threshold=0.85,
    ),
    ModelTier.TIER_5_LIMITED: TaskGranularity(
        max_subtasks=4,
        subtask_complexity_limit="atomic",
        verification_frequency="every_step",
        retry_limit=8,
        timeout_multiplier=3.0,
        tool_call_limit=10,
        requires_explicit_steps=True,
        min_confidence_threshold=0.9,
    ),
}
