"""Model capability types and constants."""

from __future__ import annotations

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


KNOWN_MODEL_TIERS: dict[str, ModelTier] = {
    "claude-sonnet-4": ModelTier.TIER_1_ADVANCED,
    "claude-opus-4": ModelTier.TIER_1_ADVANCED,
    "claude-3-5-sonnet": ModelTier.TIER_1_ADVANCED,
    "gpt-4o": ModelTier.TIER_1_ADVANCED,
    "gpt-4-turbo": ModelTier.TIER_1_ADVANCED,
    "o1-preview": ModelTier.TIER_1_ADVANCED,
    "claude-3-5-haiku": ModelTier.TIER_2_CAPABLE,
    "gpt-4o-mini": ModelTier.TIER_2_CAPABLE,
    "gemma3:27b": ModelTier.TIER_2_CAPABLE,
    "llama3.1:70b": ModelTier.TIER_2_CAPABLE,
    "qwen2.5:72b": ModelTier.TIER_2_CAPABLE,
    "mistral-large": ModelTier.TIER_2_CAPABLE,
    "gemma3:12b": ModelTier.TIER_3_MODERATE,
    "llama3.1:8b": ModelTier.TIER_3_MODERATE,
    "qwen2.5:14b": ModelTier.TIER_3_MODERATE,
    "mistral-small": ModelTier.TIER_3_MODERATE,
    "gemma3:4b": ModelTier.TIER_4_BASIC,
    "llama3.2:3b": ModelTier.TIER_4_BASIC,
    "qwen2.5:7b": ModelTier.TIER_4_BASIC,
    "phi3:mini": ModelTier.TIER_4_BASIC,
    "gemma3:1b": ModelTier.TIER_5_LIMITED,
    "llama3.2:1b": ModelTier.TIER_5_LIMITED,
    "qwen2.5:1.5b": ModelTier.TIER_5_LIMITED,
    "phi3:tiny": ModelTier.TIER_5_LIMITED,
}

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
