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
from openlaoke.types.providers import MultiProviderConfig, PlanConfig
from openlaoke.utils.theme import Theme, get_theme, get_theme_names

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".openlaoke"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _get_local_builtin_model_ids() -> list[str]:
    """Get custom local model IDs from registry only."""
    model_ids = []
    try:
        registry_path = CONFIG_DIR / "models" / "custom_models.json"
        if registry_path.exists():
            with open(registry_path) as f:
                custom_models = json.load(f)
            for model_id in custom_models:
                if model_id not in model_ids:
                    model_ids.append(model_id)
    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        pass
    return model_ids


@dataclass
class AppConfig:
    """User configuration for OpenLaoKe."""

    providers: MultiProviderConfig = field(default_factory=MultiProviderConfig.defaults)
    plans: PlanConfig = field(default_factory=PlanConfig.defaults)
    hyperauto_config: HyperAutoConfig = field(default_factory=HyperAutoConfig)
    max_tokens: int = 8192
    temperature: float = 1.0
    thinking_budget: int = 0
    local_n_ctx: int = 8192
    permission_mode: str = "auto"
    auto_approve_all: bool = False
    auto_accept_tools: list[str] = field(default_factory=list)
    always_deny_tools: list[str] = field(default_factory=list)
    theme: str = "dark"
    show_token_budget: bool = True
    show_cost: bool = True
    max_output_lines: int = 500
    enable_mcp: bool = True
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    custom_system_prompt: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    working_directory: str = ""
    session_timeout_minutes: int = 0
    enable_telemetry: bool = False
    proxy_mode: str = "none"
    proxy_url: str = ""
    first_run: bool = True

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
                        if name in providers.providers:
                            p = providers.providers[name]
                            p.api_key = pdata.get("api_key", p.api_key)
                            p.base_url = pdata.get("base_url", p.base_url)
                            p.default_model = pdata.get("default_model", p.default_model)
                            p.enabled = pdata.get("enabled", True)
                            # Preserve is_local from defaults
                            if name in ("ollama", "lm_studio", "local_builtin"):
                                p.is_local = True
                            # Refresh local_builtin models from registry
                            if name == "local_builtin":
                                p.models = _get_local_builtin_model_ids()

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
                local_n_ctx=data.get("local_n_ctx", 8192),
                permission_mode=data.get("permission_mode", "auto"),
                auto_approve_all=data.get("auto_approve_all", False),
                theme=data.get("theme", "dark")
                if data.get("theme", "dark") in get_theme_names()
                else "dark",
                show_token_budget=data.get("show_token_budget", True),
                show_cost=data.get("show_cost", True),
                max_output_lines=data.get("max_output_lines", 500),
                enable_mcp=data.get("enable_mcp", True),
                mcp_servers=data.get("mcp_servers", {}),
                custom_system_prompt=data.get("custom_system_prompt", ""),
                env_vars=data.get("env_vars", {}),
                working_directory=data.get("working_directory", ""),
                proxy_mode=data.get("proxy_mode", "none"),
                proxy_url=data.get("proxy_url", ""),
                first_run=data.get("first_run", True),
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
                    "api_key": p.api_key,
                    "base_url": p.base_url,
                    "default_model": p.default_model,
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
        "local_n_ctx": config.local_n_ctx,
        "permission_mode": config.permission_mode,
        "auto_approve_all": config.auto_approve_all,
        "theme": config.theme,
        "show_token_budget": config.show_token_budget,
        "show_cost": config.show_cost,
        "max_output_lines": config.max_output_lines,
        "enable_mcp": config.enable_mcp,
        "mcp_servers": config.mcp_servers,
        "custom_system_prompt": config.custom_system_prompt,
        "env_vars": config.env_vars,
        "working_directory": config.working_directory,
        "proxy_mode": config.proxy_mode,
        "proxy_url": config.proxy_url,
        "first_run": config.first_run,
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
