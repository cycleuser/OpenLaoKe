"""Provider types and configurations for multiple LLM backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderType(str, Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    MINIMAX = "minimax"
    ALIYUN_CODING_PLAN = "aliyun_coding_plan"
    CUSTOM = "custom"


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    provider_type: ProviderType
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    models: list[str] = field(default_factory=list)
    enabled: bool = True
    is_local: bool = False

    def is_configured(self) -> bool:
        if self.is_local:
            return True
        return bool(self.api_key and self.api_key != "none")

    def get_default_model(self) -> str:
        if self.default_model:
            return self.default_model
        return self.models[0] if self.models else ""


@dataclass
class MultiProviderConfig:
    """Configuration for all providers."""
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    active_provider: str = "ollama"
    active_model: str = ""

    def get_active_provider(self) -> ProviderConfig | None:
        return self.providers.get(self.active_provider)

    def get_active_model(self) -> str:
        if self.active_model:
            return self.active_model
        provider = self.get_active_provider()
        if provider:
            return provider.get_default_model()
        return ""

    def is_configured(self) -> bool:
        provider = self.get_active_provider()
        return provider is not None and provider.is_configured()

    def set_active_provider(self, name: str) -> bool:
        if name in self.providers:
            self.active_provider = name
            return True
        return False

    def list_available_providers(self) -> list[str]:
        return [name for name, p in self.providers.items() if p.is_configured()]

    @classmethod
    def defaults(cls) -> MultiProviderConfig:
        return cls(
            providers={
                "ollama": ProviderConfig(
                    provider_type=ProviderType.OLLAMA,
                    base_url="http://localhost:11434/v1",
                    default_model="gemma4:e2b",
                    models=[
                        "gemma4:e2b",
                        "gemma4:e4b",
                        "gemma3:1b",
                        "llama3.2",
                        "llama3.1",
                        "codellama",
                        "deepseek-coder-v2",
                        "qwen2.5-coder",
                    ],
                    is_local=True,
                ),
                "lm_studio": ProviderConfig(
                    provider_type=ProviderType.LM_STUDIO,
                    base_url="http://localhost:1234/v1",
                    default_model="local-model",
                    models=["local-model"],
                    is_local=True,
                ),
                "anthropic": ProviderConfig(
                    provider_type=ProviderType.ANTHROPIC,
                    base_url="https://api.anthropic.com",
                    default_model="claude-sonnet-4-20250514",
                    models=[
                        "claude-sonnet-4-20250514",
                        "claude-opus-4-20250514",
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-20241022",
                    ],
                ),
                "openai": ProviderConfig(
                    provider_type=ProviderType.OPENAI,
                    base_url="https://api.openai.com/v1",
                    default_model="gpt-4o",
                    models=[
                        "gpt-4o",
                        "gpt-4o-mini",
                        "gpt-4-turbo",
                        "o1-preview",
                        "o1-mini",
                    ],
                ),
                "minimax": ProviderConfig(
                    provider_type=ProviderType.MINIMAX,
                    base_url="https://api.minimaxi.com/v1",
                    default_model="MiniMax-M2.7-highspeed",
                    models=[
                        "MiniMax-M2.7-highspeed",
                        "MiniMax-M2.7",
                        "MiniMax-M2.5-highspeed",
                        "MiniMax-M2.5",
                        "MiniMax-M2.1-highspeed",
                        "MiniMax-M2.1",
                        "MiniMax-M2",
                    ],
                ),
                "aliyun_coding_plan": ProviderConfig(
                    provider_type=ProviderType.ALIYUN_CODING_PLAN,
                    base_url="https://coding.dashscope.aliyuncs.com/v1",
                    default_model="qwen3.5-plus",
                    models=[
                        "qwen3.5-plus",
                        "kimi-k2.5",
                        "glm-5",
                        "MiniMax-M2.5",
                        "qwen3-max-2026-01-23",
                        "qwen3-coder-next",
                        "qwen3-coder-plus",
                        "glm-4.7",
                    ],
                ),
                "openai_compatible": ProviderConfig(
                    provider_type=ProviderType.OPENAI_COMPATIBLE,
                    base_url="",
                    default_model="",
                    models=[],
                ),
            },
            active_provider="ollama",
        )


@dataclass
class CodingPlan:
    """Coding plan configuration for opencode-style plans."""
    name: str
    description: str
    enabled: bool = True
    max_iterations: int = 50
    auto_approve: bool = False
    tools: list[str] = field(default_factory=list)


@dataclass
class PlanConfig:
    """Configuration for coding plans."""
    plans: dict[str, CodingPlan] = field(default_factory=dict)
    active_plan: str = "default"

    @classmethod
    def defaults(cls) -> PlanConfig:
        return cls(
            plans={
                "default": CodingPlan(
                    name="default",
                    description="Standard coding assistant mode",
                    max_iterations=50,
                    tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent"],
                ),
                "quick": CodingPlan(
                    name="quick",
                    description="Quick mode with auto-approve for fast iterations",
                    max_iterations=20,
                    auto_approve=True,
                    tools=["Read", "Write", "Edit", "Bash"],
                ),
                "explorer": CodingPlan(
                    name="explorer",
                    description="Read-only exploration mode",
                    max_iterations=30,
                    tools=["Read", "Glob", "Grep", "Bash"],
                ),
                "architect": CodingPlan(
                    name="architect",
                    description="Architecture planning mode",
                    max_iterations=100,
                    tools=["Read", "Glob", "Grep", "Agent"],
                ),
            },
            active_plan="default",
        )

    def get_active_plan(self) -> CodingPlan:
        return self.plans.get(self.active_plan, self.plans["default"])