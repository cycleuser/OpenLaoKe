"""Curated provider presets for the setup wizard and `/model add`.

The wizard used to offer 25 providers and a separate prompt branch for each.
Most users only need a local server or one cloud endpoint, so this module keeps
a short, honest list: the common providers plus the CycleUser OpenAI-compatible
endpoints that opencode already uses.

API keys are never stored here. Each preset names an environment variable; the
wizard and `/model add` read it if present and otherwise ask the user.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openlaoke.types.providers import ProviderConfig, ProviderType


@dataclass(frozen=True)
class ProviderPreset:
    key: str
    label: str
    provider_type: ProviderType
    base_url: str = ""
    models: tuple[str, ...] = ()
    default_model: str = ""
    env_var: str = ""
    is_local: bool = False
    hint: str = ""

    def build(self, api_key: str = "") -> ProviderConfig:
        key = api_key or os.environ.get(self.env_var, "")
        models = list(self.models)
        default = self.default_model or (models[0] if models else "")
        return ProviderConfig(
            provider_type=self.provider_type,
            api_key=key,
            base_url=self.base_url,
            default_model=default,
            models=models,
            is_local=self.is_local,
        )


PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="ollama",
        label="Ollama (local)",
        provider_type=ProviderType.OLLAMA,
        base_url="http://localhost:11434/v1",
        models=("qwen3.5:2b", "gemma3:1b"),
        default_model="qwen3.5:2b",
        is_local=True,
        hint="Runs on this machine; no API key.",
    ),
    ProviderPreset(
        key="lm_studio",
        label="LM Studio (local)",
        provider_type=ProviderType.LM_STUDIO,
        base_url="http://localhost:1234/v1",
        models=("local-model",),
        default_model="local-model",
        is_local=True,
        hint="Runs on this machine; no API key.",
    ),
    ProviderPreset(
        key="deepseek",
        label="DeepSeek",
        provider_type=ProviderType.DEEPSEEK,
        base_url="https://api.deepseek.com/v1",
        models=("deepseek-flash", "deepseek-v4-pro"),
        default_model="deepseek-flash",
        env_var="DEEPSEEK_API_KEY",
    ),
    ProviderPreset(
        key="openai",
        label="OpenAI",
        provider_type=ProviderType.OPENAI,
        base_url="https://api.openai.com/v1",
        models=("gpt-4o", "gpt-4o-mini"),
        default_model="gpt-4o",
        env_var="OPENAI_API_KEY",
    ),
    ProviderPreset(
        key="anthropic",
        label="Anthropic (Claude)",
        provider_type=ProviderType.ANTHROPIC,
        base_url="https://api.anthropic.com",
        models=("claude-sonnet-4-20250514",),
        default_model="claude-sonnet-4-20250514",
        env_var="ANTHROPIC_API_KEY",
    ),
    ProviderPreset(
        key="google",
        label="Google Gemini",
        provider_type=ProviderType.GOOGLE,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        models=("gemini-2.0-flash",),
        default_model="gemini-2.0-flash",
        env_var="GOOGLE_API_KEY",
    ),
    ProviderPreset(
        key="openrouter",
        label="OpenRouter",
        provider_type=ProviderType.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        models=("anthropic/claude-3.5-sonnet",),
        default_model="anthropic/claude-3.5-sonnet",
        env_var="OPENROUTER_API_KEY",
    ),
    ProviderPreset(
        key="opencode",
        label="OpenCode Zen",
        provider_type=ProviderType.OPENCODE,
        base_url="https://opencode.ai/zen/v1",
        models=("big-pickle",),
        default_model="big-pickle",
        env_var="OPENCODE_API_KEY",
        hint="Free tier may work without a key.",
    ),
    # The endpoints opencode is already configured with. Same model families
    # jcode and the OpenLaoKe benchmark use.
    ProviderPreset(
        key="cycleuser-llm",
        label="CycleUser LLM (halogen)",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        base_url="https://llm.cycleuser.com/v1",
        models=("halogen", "halogen-master"),
        default_model="halogen",
        env_var="CYCLEUSER_LLM_API_KEY",
        hint="262k-context reasoning model used by jcode.",
    ),
    ProviderPreset(
        key="cycleuser-ai",
        label="CycleUser AI (strata)",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        base_url="https://ai.cycleuser.com/v1",
        models=("strata-iq2-xs", "ornith-1.5-35b-a3b-apex-i-compact"),
        default_model="strata-iq2-xs",
        env_var="CYCLEUSER_AI_API_KEY",
    ),
    ProviderPreset(
        key="cycleuser-work",
        label="CycleUser Work",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        base_url="https://work.cycleuser.com/v1",
        models=("strata-qwen3.8-V100",),
        default_model="strata-qwen3.8-V100",
        env_var="CYCLEUSER_WORK_API_KEY",
    ),
    ProviderPreset(
        key="cycleuser-try",
        label="CycleUser Try",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        base_url="https://try.cycleuser.com/v1",
        models=("polystrata-gemma4-P100",),
        default_model="polystrata-gemma4-P100",
        env_var="CYCLEUSER_TRY_API_KEY",
    ),
)

PRESETS_BY_KEY: dict[str, ProviderPreset] = {p.key: p for p in PRESETS}

# The wizard shows this short list, not all 25 provider types.
WIZARD_ORDER: tuple[str, ...] = (
    "ollama",
    "lm_studio",
    "deepseek",
    "openai",
    "anthropic",
    "google",
    "openrouter",
    "opencode",
    "cycleuser-llm",
    "cycleuser-ai",
    "cycleuser-work",
    "cycleuser-try",
)


def get_preset(key: str) -> ProviderPreset | None:
    return PRESETS_BY_KEY.get(key)


def wizard_presets() -> list[ProviderPreset]:
    return [PRESETS_BY_KEY[k] for k in WIZARD_ORDER]


def custom_preset(key: str, base_url: str, model: str = "") -> ProviderPreset:
    """Build an ad-hoc OpenAI-compatible preset for `/model add`."""
    models = (model,) if model else ()
    return ProviderPreset(
        key=key,
        label=key,
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        base_url=base_url,
        models=models,
        default_model=model,
        env_var="",
    )
