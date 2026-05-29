"""Model escalation - cloud fallback when local model hard-fails.

When the local model exhausts all retries and decomposition strategies,
optionally fires one call to a stronger cloud model (Anthropic/OpenAI/DeepSeek).
Requires configured API key. Session-limited to prevent runaway costs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum


class EscalationProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


PROVIDER_ENV_KEYS: dict[EscalationProvider, str] = {
    EscalationProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    EscalationProvider.OPENAI: "OPENAI_API_KEY",
    EscalationProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
}

PROVIDER_PRIORITY: list[EscalationProvider] = [
    EscalationProvider.ANTHROPIC,
    EscalationProvider.OPENAI,
    EscalationProvider.DEEPSEEK,
]


@dataclass
class EscalationEngine:
    max_per_session: int = 5
    _session_count: int = 0
    _available_providers: list[EscalationProvider] = field(default_factory=list)
    _enabled: bool = True

    def __post_init__(self) -> None:
        self._detect_providers()

    def _detect_providers(self) -> None:
        self._available_providers = []
        for provider in PROVIDER_PRIORITY:
            env_key = PROVIDER_ENV_KEYS[provider]
            if os.environ.get(env_key):
                self._available_providers.append(provider)

    def can_escalate(self) -> bool:
        if not self._enabled:
            return False
        if not self._available_providers:
            return False
        return self._session_count < self.max_per_session

    def get_next_provider(self) -> EscalationProvider | None:
        if not self.can_escalate():
            return None
        # Prefer highest priority that hasn't been used too many times
        for provider in PROVIDER_PRIORITY:
            if provider in self._available_providers:
                return provider
        return None

    def record_escalation(self, provider: EscalationProvider) -> None:
        self._session_count += 1

    def get_escalation_system_message(self) -> str:
        return (
            "A smaller local model failed to complete this task. "
            "Please fix it in as few tool calls as possible."
        )

    @property
    def session_count(self) -> int:
        return self._session_count

    @property
    def available_providers(self) -> list[str]:
        return [p.value for p in self._available_providers]

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
