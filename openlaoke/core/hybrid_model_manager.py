"""Advanced model management with CPU/GPU hybrid loading.

This module provides intelligent model loading strategies:
1. Small models (planner/validator) use CPU - always available, no VRAM
2. Large models (executor) use GPU - faster generation
3. Automatic model selection based on available resources
4. Batch operations to minimize model switching

Memory Strategy:
- gemma3:1b (1.4 GB) → CPU (always loaded, ~100MB RAM)
- gemma4:e4b (12 GB) → GPU (loaded on-demand)
- Total VRAM: ~12 GB (vs 13.4 GB with both on GPU)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class DeviceType(StrEnum):
    """Device types for model execution."""

    CPU = "cpu"
    GPU = "gpu"
    AUTO = "auto"


@dataclass
class ModelConfig:
    """Configuration for a model."""

    name: str
    tier: str  # "planner", "executor", "validator"
    device: DeviceType
    keep_alive: str
    max_tokens: int

    size_gb: float = 0.0
    is_loaded: bool = False
    last_used: float = 0.0


@dataclass
class ModelPoolStatus:
    """Status of the model pool."""

    cpu_models: list[ModelConfig] = field(default_factory=list)
    gpu_models: list[ModelConfig] = field(default_factory=list)

    gpu_total_gb: float = 0.0
    gpu_used_gb: float = 0.0
    gpu_free_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_models": [{"name": m.name, "loaded": m.is_loaded} for m in self.cpu_models],
            "gpu_models": [
                {"name": m.name, "loaded": m.is_loaded, "size_gb": m.size_gb}
                for m in self.gpu_models
            ],
            "gpu_memory": {
                "total_gb": self.gpu_total_gb,
                "used_gb": self.gpu_used_gb,
                "free_gb": self.gpu_free_gb,
            },
        }


class HybridModelManager:
    """Manage models with CPU/GPU hybrid strategy."""

    OLLAMA_API = "http://localhost:11434"

    DEFAULT_CONFIGS = {
        "planner": ModelConfig(
            name="gemma3:1b",
            tier="planner",
            device=DeviceType.CPU,
            keep_alive="24h",
            max_tokens=500,
            size_gb=1.4,
        ),
        "executor": ModelConfig(
            name="gemma4:e4b",
            tier="executor",
            device=DeviceType.GPU,
            keep_alive="10m",
            max_tokens=1000,
            size_gb=12.0,
        ),
        "validator": ModelConfig(
            name="gemma3:1b",
            tier="validator",
            device=DeviceType.CPU,
            keep_alive="24h",
            max_tokens=300,
            size_gb=1.4,
        ),
    }

    def __init__(self, app_state: AppState | None = None) -> None:
        self.app_state = app_state
        self.models: dict[str, ModelConfig] = {}
        self._api_client: httpx.AsyncClient | None = None
        self._loaded_models_cache: dict[str, bool] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._api_client is None:
            self._api_client = httpx.AsyncClient(timeout=60.0)
        return self._api_client

    async def initialize(self) -> dict[str, Any]:
        """Initialize model pool with optimal configuration."""

        client = await self._get_client()

        loaded_models = await self._get_loaded_models(client)

        self.models["planner"] = self.DEFAULT_CONFIGS["planner"]
        self.models["validator"] = self.DEFAULT_CONFIGS["validator"]
        self.models["executor"] = self.DEFAULT_CONFIGS["executor"]

        results = {
            "planner": False,
            "validator": False,
            "executor": False,
        }

        for tier, config in self.models.items():
            is_loaded = any(m["name"] == config.name for m in loaded_models)

            if is_loaded:
                config.is_loaded = True
                results[tier] = True
            else:
                success = await self._load_model(client, config)
                config.is_loaded = success
                results[tier] = success

        return {
            "success": all(results.values()),
            "results": results,
            "strategy": "CPU/GPU Hybrid",
        }

    async def _load_model(self, client: httpx.AsyncClient, config: ModelConfig) -> bool:
        """Load a model with specified device preference."""

        try:
            load_options = {
                "model": config.name,
                "prompt": "",
                "keep_alive": config.keep_alive,
                "stream": False,
            }

            if config.device == DeviceType.CPU:
                load_options["options"] = {"num_gpu": 0}

            response = await client.post(
                f"{self.OLLAMA_API}/api/generate",
                json=load_options,
            )

            if response.status_code == 200:
                self._loaded_models_cache[config.name] = True
                return True

        except Exception:
            pass

        return False

    async def _get_loaded_models(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """Get currently loaded models from Ollama."""

        try:
            response = await client.get(f"{self.OLLAMA_API}/api/ps")

            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])

        except Exception:
            pass

        return []

    async def get_status(self) -> ModelPoolStatus:
        """Get current model pool status."""

        client = await self._get_client()
        loaded_models = await self._get_loaded_models(client)

        status = ModelPoolStatus()

        for tier, config in self.models.items():
            config.is_loaded = any(m["name"] == config.name for m in loaded_models)

            if config.device == DeviceType.CPU:
                status.cpu_models.append(config)
            else:
                status.gpu_models.append(config)
                if config.is_loaded:
                    status.gpu_used_gb += config.size_gb

        status.gpu_total_gb = 24.0
        status.gpu_free_gb = status.gpu_total_gb - status.gpu_used_gb

        return status

    async def ensure_model_ready(self, tier: str) -> bool:
        """Ensure a model is loaded and ready."""

        if tier not in self.models:
            return False

        config = self.models[tier]

        if config.is_loaded:
            return True

        client = await self._get_client()
        success = await self._load_model(client, config)
        config.is_loaded = success

        return success

    async def batch_call_planner(self, tasks: list[str]) -> list[str]:
        """Batch call planner model for multiple tasks (minimize switching)."""

        if not await self.ensure_model_ready("planner"):
            return ["Error: Planner model not ready"] * len(tasks)

        client = await self._get_client()
        config = self.models["planner"]

        results = []

        for task in tasks:
            try:
                response = await client.post(
                    f"{self.OLLAMA_API}/api/generate",
                    json={
                        "model": config.name,
                        "prompt": task,
                        "stream": False,
                        "keep_alive": config.keep_alive,
                        "options": {"num_gpu": 0} if config.device == DeviceType.CPU else {},
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    results.append(data.get("response", ""))
                else:
                    results.append(f"Error: HTTP {response.status_code}")

            except Exception as e:
                results.append(f"Error: {str(e)}")

        return results

    async def call_executor(self, prompt: str) -> str:
        """Call executor model for code generation."""

        if not await self.ensure_model_ready("executor"):
            return "Error: Executor model not ready"

        client = await self._get_client()
        config = self.models["executor"]

        try:
            response = await client.post(
                f"{self.OLLAMA_API}/api/generate",
                json={
                    "model": config.name,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": config.keep_alive,
                    "options": {"num_ctx": 8192},
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                return f"Error: HTTP {response.status_code}"

        except Exception as e:
            return f"Error: {str(e)}"

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._api_client:
            await self._api_client.aclose()
            self._api_client = None


def create_hybrid_manager(app_state: AppState | None = None) -> HybridModelManager:
    """Create a hybrid model manager."""
    return HybridModelManager(app_state)
