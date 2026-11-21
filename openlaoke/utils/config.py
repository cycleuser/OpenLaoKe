"""Configuration management."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.types.permissions import HyperAutoConfig
from openlaoke.types.providers import MultiProviderConfig, PlanConfig, ProviderConfig, ProviderType
from openlaoke.utils.theme import Theme, get_theme, get_theme_names

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".openlaoke"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _provider_from_saved(name: str, pdata: dict[str, Any]) -> ProviderConfig:
    """Rebuild a provider that is not in the built-in defaults.

    Presets supply their own type/base URL/model list, so a provider added by
    ``/model add cycleuser-llm`` survives the next load. Unknown custom
    providers fall back to an OpenAI-compatible config.
    """
    from openlaoke.core.provider_presets import PRESETS_BY_KEY

    preset = PRESETS_BY_KEY.get(name)
    if preset is not None:
        return preset.build(str(pdata.get("api_key") or ""))

    raw_type = pdata.get("provider_type") or ProviderType.OPENAI_COMPATIBLE.value
    try:
        provider_type = ProviderType(raw_type)
    except ValueError:
        provider_type = ProviderType.OPENAI_COMPATIBLE
    return ProviderConfig(
        provider_type=provider_type,
        api_key=str(pdata.get("api_key") or ""),
        base_url=str(pdata.get("base_url") or ""),
        default_model=str(pdata.get("default_model") or ""),
        models=list(pdata.get("models") or []),
        model_labels=dict(pdata.get("model_labels") or {}),
        enabled=bool(pdata.get("enabled", True)),
        is_local=bool(pdata.get("is_local", False)),
    )


@dataclass
class AppConfig:
    """User configuration for OpenLaoKe."""

    providers: MultiProviderConfig = field(default_factory=MultiProviderConfig.defaults)
    plans: PlanConfig = field(default_factory=PlanConfig.defaults)
    hyperauto_config: HyperAutoConfig = field(default_factory=HyperAutoConfig)
    max_tokens: int = 8192
    temperature: float = 1.0
    thinking_budget: int = 0
    # How hard a reasoning-capable model should think: "low", "medium",
    # "high", or "" to leave it to the provider. Low matches what Jcode and
    # pi use for coding turns and is the default here.
    reasoning_effort: str = "low"
    # Harness temperament: "balanced", "pi", "jcode", or "opencode".
    # The mode supplies default effort, step budget, tool profile, and
    # system-prompt directives; see core/harness_modes.py.
    mode: str = "balanced"
    local_n_ctx: int = 8192
    context_cap_tokens: int = 0
    permission_mode: str = "auto"
    auto_approve_all: bool = False
    auto_accept_tools: list[str] = field(default_factory=list)
    always_deny_tools: list[str] = field(default_factory=list)
    theme: str = "dark"
    show_token_budget: bool = True
    show_cost: bool = True
    max_output_lines: int = 500
    enable_mcp: bool = True
    enable_batch: bool = False
    enable_scheduler: bool = False
    enable_browser: bool = False
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    custom_system_prompt: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    working_directory: str = ""
    session_timeout_minutes: int = 0
    enable_telemetry: bool = False
    proxy_mode: str = "none"
    proxy_url: str = ""
    first_run: bool = True
    language: str = "en"

    def is_configured(self) -> bool:
        return self.providers.is_configured()

    def get_active_provider_name(self) -> str:
        return self.providers.active_provider

    def get_active_model(self) -> str:
        return self.providers.get_active_model()

    def get_theme(self) -> Theme:
        return get_theme(self.theme)

    def validate_theme(self) -> bool:
        return self.theme in get_theme_names()

    def get_available_themes(self) -> list[str]:
        return get_theme_names()


def load_config() -> AppConfig:
    """Load configuration from disk."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)

            providers = MultiProviderConfig.defaults()
            if "providers" in data:
                providers_data = data["providers"]
                providers.active_provider = providers_data.get("active_provider", "ollama")
                providers.active_model = providers_data.get("active_model", "")
                providers.local_n_ctx = providers_data.get("local_n_ctx", 262144)
                providers.local_repetition_penalty = providers_data.get(
                    "local_repetition_penalty", 1.1
                )
                providers.local_temperature = providers_data.get("local_temperature", 0.3)
                if "providers" in providers_data:
                    for name, pdata in providers_data.get("providers", {}).items():
                        p = providers.providers.get(name)
                        is_builtin = p is not None
                        if p is None:
                            p = _provider_from_saved(name, pdata)
                            providers.providers[name] = p
                        p.api_key = pdata.get("api_key", p.api_key)
                        p.base_url = pdata.get("base_url", p.base_url)
                        if not is_builtin:
                            p.default_model = pdata.get("default_model", p.default_model)
                        p.enabled = pdata.get("enabled", True)
                        if "models" in pdata and not is_builtin:
                            p.models = list(pdata.get("models") or [])
                        if "model_labels" in pdata:
                            p.model_labels = dict(pdata.get("model_labels") or {})
                        if "provider_type" in pdata:
                            with contextlib.suppress(ValueError):
                                p.provider_type = ProviderType(pdata["provider_type"])
                        if "is_local" in pdata:
                            p.is_local = bool(pdata["is_local"])
                        # Preserve is_local from defaults
                        if name in ("ollama", "lm_studio"):
                            p.is_local = True

            plans = PlanConfig.defaults()
            if "plans" in data:
                plans_data = data["plans"]
                plans.active_plan = plans_data.get("active_plan", "default")

            hyperauto_config = HyperAutoConfig()
            if "hyperauto_config" in data:
                ha_data = data["hyperauto_config"]
                hyperauto_config.enabled = ha_data.get("enabled", False)
                hyperauto_config.max_iterations = ha_data.get("max_iterations", 100)
                hyperauto_config.timeout_seconds = ha_data.get("timeout_seconds", 300)
                hyperauto_config.auto_save = ha_data.get("auto_save", True)
                hyperauto_config.learning_enabled = ha_data.get("learning_enabled", False)
                hyperauto_config.history_limit = ha_data.get("history_limit", 50)
                if "mode" in ha_data:
                    from openlaoke.types.core_types import HyperAutoMode

                    with contextlib.suppress(ValueError):
                        hyperauto_config.mode = HyperAutoMode(ha_data["mode"])

            config = AppConfig(
                providers=providers,
                plans=plans,
                hyperauto_config=hyperauto_config,
                max_tokens=data.get("max_tokens", 8192),
                temperature=data.get("temperature", 1.0),
                thinking_budget=data.get("thinking_budget", 0),
                reasoning_effort=data.get("reasoning_effort", "low"),
                mode=data.get("mode", "balanced"),
                local_n_ctx=data.get("local_n_ctx", 8192),
                context_cap_tokens=data.get("context_cap_tokens", 0),
                permission_mode=data.get("permission_mode", "auto"),
                auto_approve_all=data.get("auto_approve_all", False),
                theme=data.get("theme", "dark")
                if data.get("theme", "dark") in get_theme_names()
                else "dark",
                show_token_budget=data.get("show_token_budget", True),
                show_cost=data.get("show_cost", True),
                max_output_lines=data.get("max_output_lines", 500),
                enable_mcp=data.get("enable_mcp", True),
                enable_batch=bool(data.get("enable_batch", False)),
                enable_scheduler=bool(data.get("enable_scheduler", False)),
                enable_browser=bool(data.get("enable_browser", False)),
                mcp_servers=data.get("mcp_servers", {}),
                custom_system_prompt=data.get("custom_system_prompt", ""),
                env_vars=data.get("env_vars", {}),
                working_directory=data.get("working_directory", ""),
                proxy_mode=data.get("proxy_mode", "none"),
                proxy_url=data.get("proxy_url", ""),
                first_run=data.get("first_run", True),
                language=data.get("language", "en"),
            )
            return config
        except Exception:
            logger.warning(
                "Failed to load config from %s, using defaults", CONFIG_PATH, exc_info=True
            )
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "providers": {
            "active_provider": config.providers.active_provider,
            "active_model": config.providers.active_model,
            "local_n_ctx": config.providers.local_n_ctx,
            "local_repetition_penalty": config.providers.local_repetition_penalty,
            "local_temperature": config.providers.local_temperature,
            "providers": {
                name: {
                    "provider_type": p.provider_type.value,
                    "api_key": p.api_key,
                    "base_url": p.base_url,
                    "default_model": p.default_model,
                    "models": p.models,
                    "model_labels": p.model_labels,
                    "is_local": p.is_local,
                    "enabled": p.enabled,
                }
                for name, p in config.providers.providers.items()
            },
        },
        "plans": {
            "active_plan": config.plans.active_plan,
        },
        "hyperauto_config": {
            "mode": config.hyperauto_config.mode.value,
            "enabled": config.hyperauto_config.enabled,
            "max_iterations": config.hyperauto_config.max_iterations,
            "timeout_seconds": config.hyperauto_config.timeout_seconds,
            "auto_save": config.hyperauto_config.auto_save,
            "learning_enabled": config.hyperauto_config.learning_enabled,
            "history_limit": config.hyperauto_config.history_limit,
        },
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "thinking_budget": config.thinking_budget,
        "reasoning_effort": config.reasoning_effort,
        "mode": config.mode,
        "local_n_ctx": config.local_n_ctx,
        "context_cap_tokens": config.context_cap_tokens,
        "permission_mode": config.permission_mode,
        "auto_approve_all": config.auto_approve_all,
        "theme": config.theme,
        "show_token_budget": config.show_token_budget,
        "show_cost": config.show_cost,
        "max_output_lines": config.max_output_lines,
        "enable_mcp": config.enable_mcp,
        "enable_batch": config.enable_batch,
        "enable_scheduler": config.enable_scheduler,
        "enable_browser": config.enable_browser,
        "mcp_servers": config.mcp_servers,
        "custom_system_prompt": config.custom_system_prompt,
        "env_vars": config.env_vars,
        "working_directory": config.working_directory,
        "proxy_mode": config.proxy_mode,
        "proxy_url": config.proxy_url,
        "first_run": config.first_run,
        "language": config.language,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=CONFIG_DIR, delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(data, tmp, indent=2)
        tmp_path = tmp.name

    os.replace(tmp_path, CONFIG_PATH)
    with contextlib.suppress(OSError):
        os.chmod(CONFIG_PATH, 0o600)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single config value."""
    config = load_config()
    return getattr(config, key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a single config value and persist."""
    config = load_config()
    if hasattr(config, key):
        setattr(config, key, value)
        save_config(config)


def mark_first_run_complete() -> None:
    """Mark that the user has completed the first-run wizard."""
    config = load_config()
    config.first_run = False
    save_config(config)
