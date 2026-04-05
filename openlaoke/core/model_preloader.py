"""Model preloading and caching for fast switching.

Ollama supports keeping models in memory/VRAM for faster switching.
This module provides utilities to:
1. Preload models before execution
2. Keep models alive in memory
3. Optimize dual-model workflow

Memory requirements:
- gemma3:1b: 815 MB (planner/validator)
- gemma4:e4b: 12 GB (executor)
- Total: ~13 GB VRAM

Strategies:
1. Keep-alive: Keep models in memory between calls
2. Batch calls: Group multiple calls to same model
3. Parallel loading: Load both models upfront
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class ModelLoadStatus:
    """Status of a loaded model."""

    name: str
    is_loaded: bool
    size_gb: float
    processor: str  # "GPU" or "CPU"
    context_length: int
    until: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "is_loaded": self.is_loaded,
            "size_gb": self.size_gb,
            "processor": self.processor,
            "context_length": self.context_length,
            "until": self.until,
        }


class ModelPreloader:
    """Preload and cache models for fast switching."""

    OLLAMA_API = "http://localhost:11434"

    DEFAULT_KEEP_ALIVE = "10m"  # Keep models alive for 10 minutes

    def __init__(self, app_state: AppState | None = None) -> None:
        self.app_state = app_state
        self._loaded_models: dict[str, ModelLoadStatus] = {}

    async def preload_models(self, models: list[str], keep_alive: str = "10m") -> dict[str, bool]:
        """Preload multiple models into memory/VRAM.

        Args:
            models: List of model names to preload
            keep_alive: How long to keep models loaded (e.g., "10m", "1h", "24h")

        Returns:
            Dict of model_name -> success status
        """
        results = {}

        for model in models:
            try:
                success = await self._load_model(model, keep_alive)
                results[model] = success
            except Exception as e:
                results[model] = False

        return results

    async def _load_model(self, model: str, keep_alive: str) -> bool:
        """Load a single model with keep_alive setting."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.OLLAMA_API}/api/generate",
                json={
                    "model": model,
                    "prompt": "",  # Empty prompt to just load the model
                    "keep_alive": keep_alive,
                    "stream": False,
                },
            )

            if response.status_code == 200:
                self._loaded_models[model] = ModelLoadStatus(
                    name=model,
                    is_loaded=True,
                    size_gb=0.0,
                    processor="GPU",
                    context_length=4096,
                    until=None,
                )
                return True

            return False

    async def get_loaded_models(self) -> list[ModelLoadStatus]:
        """Get list of currently loaded models."""

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.OLLAMA_API}/api/ps")

                if response.status_code == 200:
                    data = response.json()

                    models = []
                    for model_data in data.get("models", []):
                        models.append(
                            ModelLoadStatus(
                                name=model_data.get("name", "unknown"),
                                is_loaded=True,
                                size_gb=model_data.get("size", 0) / (1024**3),
                                processor=model_data.get("details", {}).get("processor", "GPU"),
                                context_length=model_data.get("details", {}).get(
                                    "context_length", 4096
                                ),
                                until=model_data.get("expires", None),
                            )
                        )

                    return models

        except Exception:
            pass

        return []

    async def keep_alive(self, model: str, duration: str = "10m") -> bool:
        """Keep a model alive in memory for specified duration.

        Args:
            model: Model name
            duration: Duration string (e.g., "10m", "1h", "24h")

        Returns:
            Success status
        """
        return await self._load_model(model, duration)

    async def unload_model(self, model: str) -> bool:
        """Unload a model from memory.

        Args:
            model: Model name to unload

        Returns:
            Success status
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.OLLAMA_API}/api/generate",
                    json={
                        "model": model,
                        "keep_alive": 0,  # Set to 0 to unload
                        "stream": False,
                    },
                )

                if response.status_code == 200:
                    if model in self._loaded_models:
                        del self._loaded_models[model]
                    return True

        except Exception:
            pass

        return False

    async def check_memory_available(self) -> dict[str, Any]:
        """Check available memory for model loading.

        Returns:
            Dict with memory information
        """
        import subprocess

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                gpus = []

                for line in lines:
                    parts = line.split(", ")
                    if len(parts) == 3:
                        total_mb = int(parts[0].strip())
                        used_mb = int(parts[1].strip())
                        free_mb = int(parts[2].strip())

                        gpus.append(
                            {
                                "total_gb": total_mb / 1024,
                                "used_gb": used_mb / 1024,
                                "free_gb": free_mb / 1024,
                                "usage_percent": (used_mb / total_mb) * 100 if total_mb > 0 else 0,
                            }
                        )

                return {
                    "gpu_available": True,
                    "gpus": gpus,
                }

        except Exception:
            pass

        return {
            "gpu_available": False,
            "gpus": [],
        }

    async def preload_dual_models(self) -> dict[str, Any]:
        """Preload both planner and executor models.

        Returns:
            Status report
        """
        start_time = time.time()

        planner_model = "gemma3:1b"
        executor_model = "gemma4:e4b"

        memory_info = await self.check_memory_available()

        loaded = await self.get_loaded_models()
        loaded_names = [m.name for m in loaded]

        results = {
            "planner": planner_model in loaded_names,
            "executor": executor_model in loaded_names,
        }

        if not results["planner"] or not results["executor"]:
            preload_results = await self.preload_models(
                [planner_model, executor_model],
                keep_alive=self.DEFAULT_KEEP_ALIVE,
            )
            results.update(preload_results)

        loaded_after = await self.get_loaded_models()

        total_time = time.time() - start_time

        return {
            "success": results.get("planner", False) and results.get("executor", False),
            "planner_loaded": results.get("planner", False),
            "executor_loaded": results.get("executor", False),
            "memory_info": memory_info,
            "loaded_models": [m.to_dict() for m in loaded_after],
            "load_time_seconds": total_time,
        }


async def preload_dual_models(app_state: AppState | None = None) -> dict[str, Any]:
    """Convenience function to preload dual models."""
    preloader = ModelPreloader(app_state)
    return await preloader.preload_dual_models()


async def get_model_status() -> list[dict[str, Any]]:
    """Convenience function to get loaded model status."""
    preloader = ModelPreloader()
    models = await preloader.get_loaded_models()
    return [m.to_dict() for m in models]


async def keep_model_alive(model: str, duration: str = "10m") -> bool:
    """Convenience function to keep a model alive."""
    preloader = ModelPreloader()
    return await preloader.keep_alive(model, duration)
