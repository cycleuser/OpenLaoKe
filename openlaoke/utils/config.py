"""Configuration management."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.types.providers import MultiProviderConfig, PlanConfig


CONFIG_DIR = Path.home() / ".openlaoke"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """User configuration for OpenLaoKe."""
    providers: MultiProviderConfig = field(default_factory=MultiProviderConfig.defaults)
    plans: PlanConfig = field(default_factory=PlanConfig.defaults)
    max_tokens: int = 8192
    temperature: float = 1.0
    thinking_budget: int = 0
    permission_mode: str = "auto"
    auto_approve_all: bool = True
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
                if "providers" in providers_data:
                    for name, pdata in providers_data.get("providers", {}).items():
                        if name in providers.providers:
                            p = providers.providers[name]
                            p.api_key = pdata.get("api_key", p.api_key)
                            p.base_url = pdata.get("base_url", p.base_url)
                            p.default_model = pdata.get("default_model", p.default_model)
                            p.enabled = pdata.get("enabled", True)
                            # Preserve is_local from defaults
                            if name in ("ollama", "lm_studio"):
                                p.is_local = True

            plans = PlanConfig.defaults()
            if "plans" in data:
                plans_data = data["plans"]
                plans.active_plan = plans_data.get("active_plan", "default")

            config = AppConfig(
                providers=providers,
                plans=plans,
                max_tokens=data.get("max_tokens", 8192),
                temperature=data.get("temperature", 1.0),
                thinking_budget=data.get("thinking_budget", 0),
                permission_mode=data.get("permission_mode", "auto"),
                auto_approve_all=data.get("auto_approve_all", True),
                theme=data.get("theme", "dark"),
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
            pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "providers": {
            "active_provider": config.providers.active_provider,
            "active_model": config.providers.active_model,
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
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "thinking_budget": config.thinking_budget,
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

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


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