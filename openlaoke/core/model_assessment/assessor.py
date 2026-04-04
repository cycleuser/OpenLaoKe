"""Model capability assessor."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from openlaoke.core.model_assessment.types import (
    KNOWN_MODEL_TIERS,
    TIER_GRANULARITIES,
    CapabilityCategory,
    CapabilityScore,
    ModelBenchmark,
    ModelTier,
    TaskGranularity,
)

if TYPE_CHECKING:
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.types.providers import MultiProviderConfig


class ModelAssessor:
    """Assess model capabilities and determine task strategies."""

    def __init__(self, config: MultiProviderConfig):
        self.config = config
        self.benchmarks_dir = Path.home() / ".openlaoke" / "model_benchmarks"
        self.benchmarks_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, ModelBenchmark] = {}

    def get_tier(self, model: str) -> ModelTier:
        model_lower = model.lower()
        for known, tier in KNOWN_MODEL_TIERS.items():
            if known.lower() in model_lower:
                return tier
        return ModelTier.TIER_3_MODERATE

    def get_granularity(self, model: str) -> TaskGranularity:
        return TIER_GRANULARITIES[self.get_tier(model)]

    async def assess_model(
        self, api: MultiProviderClient, model: str, provider: str, quick: bool = False
    ) -> ModelBenchmark:
        start = time.time()
        caps = await self._run_tests(api, model, quick)
        overall = sum(c.score for c in caps.values()) / len(caps) if caps else 0.0

        if overall >= 8.5:
            tier = ModelTier.TIER_1_ADVANCED
        elif overall >= 7.0:
            tier = ModelTier.TIER_2_CAPABLE
        elif overall >= 5.5:
            tier = ModelTier.TIER_3_MODERATE
        elif overall >= 4.0:
            tier = ModelTier.TIER_4_BASIC
        else:
            tier = ModelTier.TIER_5_LIMITED

        recs = self._gen_recs(tier, caps)
        bench = ModelBenchmark(
            provider=provider,
            model=model,
            overall_score=overall,
            tier=tier,
            capabilities=caps,
            tested_at=time.time(),
            test_duration=time.time() - start,
            recommendations=recs,
        )
        self._save(bench)
        return bench

    async def _run_tests(
        self, api: MultiProviderClient, model: str, quick: bool
    ) -> dict[str, CapabilityScore]:
        caps = {}
        caps[CapabilityCategory.BASIC_CHAT.value] = await self._test_chat(api, model)
        if not quick:
            caps[CapabilityCategory.TOOL_CALLING.value] = await self._test_tools(api, model)
            caps[CapabilityCategory.CODE_GENERATION.value] = await self._test_code(api, model)
            caps[CapabilityCategory.MULTI_TURN.value] = await self._test_multiturn(api, model)
        return caps

    async def _test_chat(self, api: MultiProviderClient, model: str) -> CapabilityScore:
        tests = [("What is 2+2?", "4"), ("Capital of France?", "Paris")]
        passed = 0
        for q, exp in tests:
            try:
                r, _, _ = await api.send_message(
                    "You are helpful.", [{"role": "user", "content": q}], None, model
                )
                if exp.lower() in r.content.lower():
                    passed += 1
            except Exception:
                pass
        return CapabilityScore(
            CapabilityCategory.BASIC_CHAT, (passed / len(tests)) * 10, passed, len(tests)
        )

    async def _test_tools(self, api: MultiProviderClient, model: str) -> CapabilityScore:
        tool = {
            "name": "test",
            "description": "Test",
            "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        }
        passed = 0
        try:
            r, _, _ = await api.send_message(
                "Use tools.",
                [{"role": "user", "content": "Call test with x='hello'"}],
                [tool],
                model,
            )
            if r.tool_uses and r.tool_uses[0].name == "test":
                passed += 1
        except Exception:
            pass
        return CapabilityScore(CapabilityCategory.TOOL_CALLING, passed * 10, passed, 1)

    async def _test_code(self, api: MultiProviderClient, model: str) -> CapabilityScore:
        try:
            r, _, _ = await api.send_message(
                "Write code.",
                [{"role": "user", "content": "Python function to add two numbers"}],
                None,
                model,
            )
            score = 10.0 if "def" in r.content and "return" in r.content else 5.0
            return CapabilityScore(
                CapabilityCategory.CODE_GENERATION, score, 1 if score > 5 else 0, 1
            )
        except Exception:
            return CapabilityScore(CapabilityCategory.CODE_GENERATION, 0, 0, 1)

    async def _test_multiturn(self, api: MultiProviderClient, model: str) -> CapabilityScore:
        try:
            msgs = [{"role": "user", "content": "My name is Bob"}]
            r1, _, _ = await api.send_message("Remember.", msgs, None, model)
            msgs.append({"role": "assistant", "content": r1.content})
            msgs.append({"role": "user", "content": "What's my name?"})
            r2, _, _ = await api.send_message("Remember.", msgs, None, model)
            score = 10.0 if "bob" in r2.content.lower() else 5.0
            return CapabilityScore(CapabilityCategory.MULTI_TURN, score, 1 if score > 5 else 0, 1)
        except Exception:
            return CapabilityScore(CapabilityCategory.MULTI_TURN, 0, 0, 1)

    def _gen_recs(self, tier: ModelTier, caps: dict[str, CapabilityScore]) -> list[str]:
        recs = []
        if tier in [ModelTier.TIER_5_LIMITED, ModelTier.TIER_4_BASIC]:
            recs = ["Break tasks into atomic steps", "Verify each step", "Use simple instructions"]
        elif tier == ModelTier.TIER_3_MODERATE:
            recs = ["Limit to 10 subtasks", "Check intermediate results"]
        elif tier == ModelTier.TIER_2_CAPABLE:
            recs = ["Can handle moderate complexity", "Verify critical operations"]
        else:
            recs = ["Can handle complex tasks directly"]
        return recs

    def _save(self, bench: ModelBenchmark) -> None:
        path = self.benchmarks_dir / f"{bench.provider}_{bench.model.replace('/', '_')}.json"
        with open(path, "w") as f:
            json.dump(bench.to_dict(), f, indent=2)

    def load(self, provider: str, model: str) -> ModelBenchmark | None:
        path = self.benchmarks_dir / f"{provider}_{model.replace('/', '_')}.json"
        if path.exists():
            with open(path) as f:
                return ModelBenchmark.from_dict(json.load(f))
        return None

    def list_all(self) -> list[ModelBenchmark]:
        result = []
        for p in self.benchmarks_dir.glob("*.json"):
            with open(p) as f:
                result.append(ModelBenchmark.from_dict(json.load(f)))
        return sorted(result, key=lambda b: b.overall_score, reverse=True)


class TaskDecomposer:
    """Decompose tasks based on model tier."""

    def __init__(self, gran: TaskGranularity):
        self.gran = gran

    def decompose(self, task: str) -> list[str]:
        if not self.gran.requires_explicit_steps:
            return [task]
        parts = task.replace(" and ", "|").replace(" then ", "|").split("|")
        return [p.strip() for p in parts if p.strip()][: self.gran.max_subtasks]

    def should_verify(self, step: int) -> bool:
        freq = self.gran.verification_frequency
        if freq == "every_step":
            return True
        elif freq == "frequent":
            return step % 2 == 0
        elif freq == "moderate":
            return step % 3 == 0
        return False

    def get_timeout(self, base: float) -> float:
        return base * self.gran.timeout_multiplier
