"""Flexible model configuration for dual-model workflow.

This module allows users to configure:
1. Planner model (local/online)
2. Executor model (local/online)
3. Validator model (local/online)

Each model can be:
- Local (Ollama, LM Studio, etc.)
- Online (OpenAI, Anthropic, Google, etc.)
- Custom provider

Example configurations:
1. Local + Local:
   planner: gemma3:1b (Ollama, CPU)
   executor: gemma4:e4b (Ollama, GPU)

2. Local + Online:
   planner: gemma3:1b (Ollama, CPU)
   executor: gpt-4 (OpenAI)

3. Online + Online:
   planner: gpt-3.5-turbo (OpenAI)
   executor: claude-3-opus (Anthropic)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


class ModelProvider(StrEnum):
    """Model providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"


class ModelDevice(StrEnum):
    """Device for model execution."""

    CPU = "cpu"
    GPU = "gpu"
    AUTO = "auto"


@dataclass
class ModelEndpoint:
    """Model endpoint configuration."""

    provider: ModelProvider
    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    device: ModelDevice = ModelDevice.AUTO
    max_tokens: int = 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "api_base": self.api_base,
            "has_api_key": self.api_key is not None,
            "device": self.device.value,
            "max_tokens": self.max_tokens,
        }


@dataclass
class DualModelConfig:
    """Configuration for dual-model workflow."""

    name: str = "default"
    planner: ModelEndpoint | None = None
    executor: ModelEndpoint | None = None
    validator: ModelEndpoint | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "planner": self.planner.to_dict() if self.planner else None,
            "executor": self.executor.to_dict() if self.executor else None,
            "validator": self.validator.to_dict() if self.validator else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DualModelConfig:
        """Create from dictionary."""
        config = cls(name=data.get("name", "default"))

        if "planner" in data and data["planner"]:
            p = data["planner"]
            config.planner = ModelEndpoint(
                provider=ModelProvider(p.get("provider", "ollama")),
                model_name=p.get("model_name", "gemma3:1b"),
                api_base=p.get("api_base"),
                api_key=p.get("api_key"),
                device=ModelDevice(p.get("device", "cpu")),
                max_tokens=p.get("max_tokens", 500),
            )

        if "executor" in data and data["executor"]:
            e = data["executor"]
            config.executor = ModelEndpoint(
                provider=ModelProvider(e.get("provider", "ollama")),
                model_name=e.get("model_name", "gemma4:e4b"),
                api_base=e.get("api_base"),
                api_key=e.get("api_key"),
                device=ModelDevice(e.get("device", "gpu")),
                max_tokens=e.get("max_tokens", 1000),
            )

        if "validator" in data and data["validator"]:
            v = data["validator"]
            config.validator = ModelEndpoint(
                provider=ModelProvider(v.get("provider", "ollama")),
                model_name=v.get("model_name", "gemma3:1b"),
                api_base=v.get("api_base"),
                api_key=v.get("api_key"),
                device=ModelDevice(v.get("device", "cpu")),
                max_tokens=v.get("max_tokens", 300),
            )

        return config


class DualModelConfigManager:
    """Manage dual-model configurations."""

    DEFAULT_CONFIGS = {
        "local_balanced": DualModelConfig(
            name="local_balanced",
            planner=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=500,
            ),
            executor=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma4:e4b",
                api_base="http://localhost:11434",
                device=ModelDevice.GPU,
                max_tokens=1000,
            ),
            validator=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=300,
            ),
        ),
        "local_light": DualModelConfig(
            name="local_light",
            planner=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=500,
            ),
            executor=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma4:e2b",
                api_base="http://localhost:11434",
                device=ModelDevice.GPU,
                max_tokens=1000,
            ),
            validator=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=300,
            ),
        ),
        "hybrid_openai": DualModelConfig(
            name="hybrid_openai",
            planner=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=500,
            ),
            executor=ModelEndpoint(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4-turbo",
                api_base="https://api.openai.com/v1",
                device=ModelDevice.AUTO,
                max_tokens=2000,
            ),
            validator=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=300,
            ),
        ),
        "hybrid_anthropic": DualModelConfig(
            name="hybrid_anthropic",
            planner=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=500,
            ),
            executor=ModelEndpoint(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-opus-20240229",
                api_base="https://api.anthropic.com",
                device=ModelDevice.AUTO,
                max_tokens=2000,
            ),
            validator=ModelEndpoint(
                provider=ModelProvider.OLLAMA,
                model_name="gemma3:1b",
                api_base="http://localhost:11434",
                device=ModelDevice.CPU,
                max_tokens=300,
            ),
        ),
        "online_premium": DualModelConfig(
            name="online_premium",
            planner=ModelEndpoint(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                api_base="https://api.openai.com/v1",
                device=ModelDevice.AUTO,
                max_tokens=500,
            ),
            executor=ModelEndpoint(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-opus-20240229",
                api_base="https://api.anthropic.com",
                device=ModelDevice.AUTO,
                max_tokens=2000,
            ),
            validator=ModelEndpoint(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                api_base="https://api.openai.com/v1",
                device=ModelDevice.AUTO,
                max_tokens=300,
            ),
        ),
    }

    def __init__(self, app_state: AppState | None = None) -> None:
        self.app_state = app_state
        self.configs: dict[str, DualModelConfig] = dict(self.DEFAULT_CONFIGS)
        self.active_config_name: str = "local_balanced"

        self._load_user_configs()

    def _load_user_configs(self) -> None:
        """Load user-defined configurations."""
        config_dir = Path.home() / ".openlaoke" / "dual_model_configs"
        config_file = config_dir / "configs.json"

        if config_file.exists():
            try:
                import json

                with open(config_file) as f:
                    data = json.load(f)

                for name, config_data in data.get("configs", {}).items():
                    self.configs[name] = DualModelConfig.from_dict(config_data)

                if "active_config" in data:
                    self.active_config_name = data["active_config"]

            except Exception:
                pass

    def _save_user_configs(self) -> None:
        """Save user-defined configurations."""
        config_dir = Path.home() / ".openlaoke" / "dual_model_configs"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "configs.json"

        try:
            import json

            data = {
                "configs": {name: config.to_dict() for name, config in self.configs.items()},
                "active_config": self.active_config_name,
            }

            with open(config_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception:
            pass

    def get_config(self, name: str | None = None) -> DualModelConfig | None:
        """Get a configuration by name."""
        if name is None:
            name = self.active_config_name
        return self.configs.get(name)

    def set_active_config(self, name: str) -> bool:
        """Set the active configuration."""
        if name in self.configs:
            self.active_config_name = name
            self._save_user_configs()
            return True
        return False

    def list_configs(self) -> list[str]:
        """List all available configurations."""
        return list(self.configs.keys())

    def create_custom_config(
        self,
        name: str,
        planner_provider: str,
        planner_model: str,
        executor_provider: str,
        executor_model: str,
        validator_provider: str | None = None,
        validator_model: str | None = None,
        planner_api_key: str | None = None,
        executor_api_key: str | None = None,
        validator_api_key: str | None = None,
        planner_device: str = "cpu",
        executor_device: str = "gpu",
        validator_device: str = "cpu",
    ) -> DualModelConfig:
        """Create a custom configuration."""

        if validator_provider is None:
            validator_provider = planner_provider
        if validator_model is None:
            validator_model = planner_model

        def get_api_base(provider: str) -> str | None:
            bases = {
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com",
                "google": "https://generativelanguage.googleapis.com",
                "deepseek": "https://api.deepseek.com",
                "ollama": "http://localhost:11434",
            }
            return bases.get(provider.lower())

        config = DualModelConfig(
            name=name,
            planner=ModelEndpoint(
                provider=ModelProvider(planner_provider.lower()),
                model_name=planner_model,
                api_base=get_api_base(planner_provider),
                api_key=planner_api_key,
                device=ModelDevice(planner_device.lower()),
                max_tokens=500,
            ),
            executor=ModelEndpoint(
                provider=ModelProvider(executor_provider.lower()),
                model_name=executor_model,
                api_base=get_api_base(executor_provider),
                api_key=executor_api_key,
                device=ModelDevice(executor_device.lower()),
                max_tokens=2000,
            ),
            validator=ModelEndpoint(
                provider=ModelProvider(validator_provider.lower()),
                model_name=validator_model,
                api_base=get_api_base(validator_provider),
                api_key=validator_api_key,
                device=ModelDevice(validator_device.lower()),
                max_tokens=300,
            ),
        )

        self.configs[name] = config
        self._save_user_configs()

        return config

    async def check_provider_availability(self, endpoint: ModelEndpoint) -> tuple[bool, str]:
        """Check if a model provider is available."""

        if endpoint.provider == ModelProvider.OLLAMA:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{endpoint.api_base}/api/version")
                    if response.status_code == 200:
                        return True, "Ollama is running"
                    return False, "Ollama returned error"
            except Exception as e:
                return False, f"Ollama not available: {str(e)}"

        elif endpoint.provider in [
            ModelProvider.OPENAI,
            ModelProvider.ANTHROPIC,
            ModelProvider.GOOGLE,
        ]:
            if endpoint.api_key:
                return True, f"{endpoint.provider.value} configured with API key"
            return False, f"{endpoint.provider.value} requires API key"

        return True, f"{endpoint.provider.value} endpoint ready"

    async def check_config_availability(
        self, config_name: str | None = None
    ) -> dict[str, tuple[bool, str]]:
        """Check availability of all models in a configuration."""

        config = self.get_config(config_name)
        if not config:
            return {}

        results = {}

        if config.planner:
            results["planner"] = await self.check_provider_availability(config.planner)

        if config.executor:
            results["executor"] = await self.check_provider_availability(config.executor)

        if config.validator:
            results["validator"] = await self.check_provider_availability(config.validator)

        return results


def create_config_manager(app_state: AppState | None = None) -> DualModelConfigManager:
    """Create a configuration manager."""
    return DualModelConfigManager(app_state)
