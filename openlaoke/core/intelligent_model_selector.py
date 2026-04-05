"""Intelligent model selector based on available resources.

This module automatically selects optimal models based on:
1. Available GPU memory
2. Task complexity
3. Cost optimization
4. Performance requirements

Selection Strategy:
- < 8 GB VRAM: gemma3:1b (CPU) + qwen2.5:0.5b (GPU)
- 8-16 GB VRAM: gemma3:1b (CPU) + gemma4:e2b (GPU)
- > 16 GB VRAM: gemma3:1b (CPU) + gemma4:e4b (GPU)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class ModelCombination:
    """A combination of models for dual-model workflow."""

    name: str
    planner_model: str
    executor_model: str
    validator_model: str

    planner_device: str
    executor_device: str
    validator_device: str

    total_vram_gb: float
    quality_score: float  # 1-10
    cost_factor: float  # relative cost (1.0 = baseline)

    recommended_for: list[str]  # VRAM ranges


class IntelligentModelSelector:
    """Select optimal models based on system resources."""

    MODEL_COMBINATIONS = [
        ModelCombination(
            name="ultra_light",
            planner_model="gemma3:1b",
            executor_model="qwen2.5:0.5b",
            validator_model="gemma3:1b",
            planner_device="cpu",
            executor_device="gpu",
            validator_device="cpu",
            total_vram_gb=0.5,
            quality_score=5.0,
            cost_factor=0.3,
            recommended_for=["< 4 GB"],
        ),
        ModelCombination(
            name="light",
            planner_model="gemma3:1b",
            executor_model="gemma4:e2b",
            validator_model="gemma3:1b",
            planner_device="cpu",
            executor_device="gpu",
            validator_device="cpu",
            total_vram_gb=7.2,
            quality_score=7.0,
            cost_factor=0.5,
            recommended_for=["4-8 GB", "8-12 GB"],
        ),
        ModelCombination(
            name="balanced",
            planner_model="gemma3:1b",
            executor_model="gemma4:e4b",
            validator_model="gemma3:1b",
            planner_device="cpu",
            executor_device="gpu",
            validator_device="cpu",
            total_vram_gb=12.0,
            quality_score=8.5,
            cost_factor=1.0,
            recommended_for=["12-16 GB", "16-24 GB"],
        ),
        ModelCombination(
            name="high_quality",
            planner_model="gemma4:e2b",
            executor_model="gemma4:e4b",
            validator_model="gemma4:e2b",
            planner_device="cpu",
            executor_device="gpu",
            validator_device="cpu",
            total_vram_gb=12.0,
            quality_score=9.0,
            cost_factor=1.5,
            recommended_for=["> 24 GB"],
        ),
        ModelCombination(
            name="premium",
            planner_model="gemma4:e4b",
            executor_model="gemma4:e12b",
            validator_model="gemma4:e4b",
            planner_device="cpu",
            executor_device="gpu",
            validator_device="cpu",
            total_vram_gb=20.0,
            quality_score=10.0,
            cost_factor=3.0,
            recommended_for=["> 32 GB"],
        ),
    ]

    def __init__(self, app_state: AppState | None = None) -> None:
        self.app_state = app_state
        self._available_vram_gb: float | None = None

    async def detect_available_vram(self) -> float:
        """Detect available GPU memory."""

        if self._available_vram_gb is not None:
            return self._available_vram_gb

        import subprocess

        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                output = result.stdout

                import re

                vram_matches = re.findall(r"VRAM \(Total\): (\d+) MB", output)

                if vram_matches:
                    total_mb = sum(int(m) for m in vram_matches)
                    self._available_vram_gb = total_mb / 1024
                    return self._available_vram_gb

        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "AdapterRAM"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                import re

                vram_matches = re.findall(r"(\d+)", result.stdout)

                if vram_matches:
                    total_bytes = sum(int(m) for m in vram_matches if int(m) > 1000000000)
                    self._available_vram_gb = total_bytes / (1024**3)
                    return self._available_vram_gb

        except Exception:
            pass

        self._available_vram_gb = 8.0
        return self._available_vram_gb

    async def select_optimal_combination(self, preference: str = "balanced") -> ModelCombination:
        """Select optimal model combination based on available resources.

        Args:
            preference: "cost" (optimize for cost), "quality" (optimize for quality),
                       "balanced" (balance cost and quality)

        Returns:
            Optimal ModelCombination
        """

        available_vram = await self.detect_available_vram()

        suitable_combinations = [
            combo
            for combo in self.MODEL_COMBINATIONS
            if combo.total_vram_gb <= available_vram * 0.9
        ]

        if not suitable_combinations:
            return self.MODEL_COMBINATIONS[0]

        if preference == "cost":
            suitable_combinations.sort(key=lambda c: c.cost_factor)
            return suitable_combinations[0]

        elif preference == "quality":
            suitable_combinations.sort(key=lambda c: c.quality_score, reverse=True)
            return suitable_combinations[0]

        else:
            suitable_combinations.sort(key=lambda c: c.quality_score / c.cost_factor, reverse=True)
            return suitable_combinations[0]

    async def get_recommendation_report(self) -> dict[str, Any]:
        """Get a detailed recommendation report."""

        available_vram = await self.detect_available_vram()
        optimal = await self.select_optimal_combination()

        return {
            "detected_vram_gb": available_vram,
            "recommended_combination": {
                "name": optimal.name,
                "planner": f"{optimal.planner_model} ({optimal.planner_device})",
                "executor": f"{optimal.executor_model} ({optimal.executor_device})",
                "validator": f"{optimal.validator_model} ({optimal.validator_device})",
            },
            "estimated": {
                "vram_usage_gb": optimal.total_vram_gb,
                "quality_score": optimal.quality_score,
                "cost_factor": optimal.cost_factor,
            },
            "all_suitable_combinations": [
                {
                    "name": c.name,
                    "vram_gb": c.total_vram_gb,
                    "quality": c.quality_score,
                    "cost": c.cost_factor,
                }
                for c in self.MODEL_COMBINATIONS
                if c.total_vram_gb <= available_vram * 0.9
            ],
        }


async def get_optimal_models(app_state: AppState | None = None) -> dict[str, str]:
    """Convenience function to get optimal models."""

    selector = IntelligentModelSelector(app_state)
    combination = await selector.select_optimal_combination()

    return {
        "planner": combination.planner_model,
        "executor": combination.executor_model,
        "validator": combination.validator_model,
        "planner_device": combination.planner_device,
        "executor_device": combination.executor_device,
        "validator_device": combination.validator_device,
    }
