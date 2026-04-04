"""Interactive configuration wizard for first-time setup."""

from __future__ import annotations

import os
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType
from openlaoke.utils.config import AppConfig


console = Console(force_terminal=True)


def run_config_wizard(config: AppConfig | None = None) -> AppConfig:
    """Run the interactive configuration wizard."""
    config = config or AppConfig()

    console.clear()
    console.print(Panel.fit(
        "[bold cyan]OpenLaoKe Configuration Wizard[/bold cyan]\n"
        "[dim]Let's set up your AI coding assistant[/dim]",
        border_style="cyan",
    ))
    console.print()

    # Step 1: Configure provider
    while True:
        console.print("[bold]Step 1: Choose your AI provider[/bold]")
        console.print()
        
        table = Table(show_header=False, box=None)
        table.add_column("Option", style="cyan")
        table.add_column("Provider", style="bold")
        table.add_column("Status", style="dim")
        
        providers = [
            ("1", "Anthropic", "anthropic", "cloud"),
            ("2", "OpenAI (GPT-4)", "openai", "cloud"),
            ("3", "MiniMax", "minimax", "cloud"),
            ("4", "Aliyun Coding Plan", "aliyun_coding_plan", "cloud"),
            ("5", "Ollama (Local)", "ollama", "local"),
            ("6", "LM Studio (Local)", "lm_studio", "local"),
            ("7", "OpenAI-Compatible (Custom)", "openai_compatible", "custom"),
            ("8", "Skip (configure later)", "", ""),
        ]
        
        for opt, name, key, ptype in providers:
            if key and key in config.providers.providers:
                provider = config.providers.providers[key]
                status = _get_provider_status(provider)
                table.add_row(f"  [{opt}]", name, status)
            elif key == "":
                table.add_row(f"  [{opt}]", name, "")
            else:
                table.add_row(f"  [{opt}]", name, "[dim]not configured[/dim]")
        
        console.print(table)
        console.print()

        choice = Prompt.ask(
            "Select provider",
            choices=["1", "2", "3", "4", "5", "6", "7", "8"],
            default="5",
        )

        provider_map = {
            "1": "anthropic",
            "2": "openai",
            "3": "minimax",
            "4": "aliyun_coding_plan",
            "5": "ollama",
            "6": "lm_studio",
            "7": "openai_compatible",
        }

        if choice == "8":
            console.print("\n[yellow]You can configure later by running:[/yellow]")
            console.print("  openlaoke --config")
            console.print()
            return config

        provider_key = provider_map[choice]
        config.providers = _configure_provider(config.providers, provider_key)

        if _check_provider_ready(config.providers, provider_key):
            set_as_default = Confirm.ask(
                f"\nSet {provider_key} as your default provider?",
                default=True,
            )
            if set_as_default:
                config.providers.active_provider = provider_key
                console.print(f"[green]✓[/green] Active provider set to: {provider_key}")
                break
        else:
            console.print("\n[yellow]Provider not fully configured. Try again?[/yellow]")
            if not Confirm.ask("Continue setup?", default=True):
                break

    # Step 2: Configure proxy
    console.print()
    config = _configure_proxy(config)

    # Done
    console.print()
    console.print("[bold green]Configuration complete![/bold green]")
    console.print(f"\nActive provider: [cyan]{config.providers.active_provider}[/cyan]")
    console.print(f"Active model: [cyan]{config.providers.get_active_model()}[/cyan]")
    console.print(f"Proxy: [cyan]{_get_proxy_display(config)}[/cyan]")
    console.print()

    config.first_run = False
    return config


def _get_proxy_display(config: AppConfig) -> str:
    if config.proxy_mode == "none":
        return "disabled"
    elif config.proxy_mode == "system":
        return "use system proxy"
    elif config.proxy_mode == "custom":
        return config.proxy_url or "(not set)"
    return "unknown"


def _get_provider_status(provider: ProviderConfig) -> str:
    if provider.is_local:
        return "[green]✓ local[/green]"
    if provider.api_key:
        return "[green]✓ configured[/green]"
    env_key = ""
    if provider.provider_type == ProviderType.ANTHROPIC:
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    elif provider.provider_type == ProviderType.OPENAI:
        env_key = os.environ.get("OPENAI_API_KEY", "")
    if env_key:
        return "[green]✓ env var[/green]"
    return "[yellow]needs setup[/yellow]"


def _check_provider_ready(config: MultiProviderConfig, key: str) -> bool:
    provider = config.providers.get(key)
    if not provider:
        return False
    return provider.is_configured()


def _configure_proxy(config: AppConfig) -> AppConfig:
    """Configure proxy settings."""
    console.print("[bold]Step 2: Proxy Configuration[/bold]")
    console.print("[dim]Configure network proxy for API requests[/dim]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Option", style="cyan")
    table.add_column("Mode", style="bold")
    table.add_column("Description", style="dim")
    
    table.add_row("  [1]", "No proxy", "Direct connection (default)")
    table.add_row("  [2]", "System proxy", "Use system HTTP/HTTPS proxy settings")
    table.add_row("  [3]", "Custom proxy", "Specify a custom proxy URL")
    
    console.print(table)
    console.print()

    choice = Prompt.ask(
        "Select proxy mode",
        choices=["1", "2", "3"],
        default="1",
    )

    if choice == "1":
        config.proxy_mode = "none"
        config.proxy_url = ""
        console.print("[green]✓[/green] Proxy disabled")
    elif choice == "2":
        config.proxy_mode = "system"
        config.proxy_url = ""
        system_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or ""
        if system_proxy:
            console.print(f"[green]✓[/green] Will use system proxy: {system_proxy}")
        else:
            console.print("[green]✓[/green] Will use system proxy (none detected)")
    elif choice == "3":
        config.proxy_mode = "custom"
        default_url = config.proxy_url or "http://127.0.0.1:7890"
        proxy_url = Prompt.ask(
            "Enter proxy URL",
            default=default_url,
        )
        config.proxy_url = proxy_url
        console.print(f"[green]✓[/green] Custom proxy set: {proxy_url}")

    return config


def _configure_provider(config: MultiProviderConfig, key: str) -> MultiProviderConfig:
    """Configure a specific provider."""
    provider = config.providers.get(key)
    if not provider:
        return config

    console.print(f"\n[bold]Configuring {key}[/bold]")
    console.print("[dim]Press Enter to use default value[/dim]\n")

    if provider.is_local:
        base_url = Prompt.ask(
            "API URL",
            default=provider.base_url,
        )
        provider.base_url = base_url

        if key == "ollama":
            models = _detect_ollama_models(base_url)
            if models:
                provider.models = models
                provider.default_model = _select_model_from_list(models, provider.default_model)
            else:
                console.print("[yellow]No models detected. Using default list.[/yellow]")
                provider.default_model = _select_model_from_list(provider.models, provider.default_model)
        else:
            provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.OPENAI_COMPATIBLE:
        console.print("[dim]Enter your custom OpenAI-compatible API details[/dim]")
        
        base_url = Prompt.ask(
            "API Base URL",
            default=provider.base_url or "http://localhost:8000/v1",
        )
        provider.base_url = base_url

        # Check for API key in environment
        env_key = os.environ.get("OPENAI_API_KEY", "")
        if env_key:
            console.print(f"[green]✓ Found OPENAI_API_KEY in environment[/green]")
            use_env = Confirm.ask("Use this key?", default=True)
            if use_env:
                provider.api_key = env_key
            else:
                api_key = Prompt.ask(
                    "API Key (required for this provider)",
                    password=True,
                )
                provider.api_key = api_key
        else:
            api_key = Prompt.ask(
                "API Key (required for this provider)",
                password=True,
            )
            provider.api_key = api_key

        if not provider.api_key:
            console.print("[bold red]Warning: No API key provided. API calls may fail.[/bold red]")

        default_model = Prompt.ask(
            "Model name",
            default=provider.default_model or provider.models[0] if provider.models else "default",
        )
        provider.default_model = default_model

    elif provider.provider_type == ProviderType.MINIMAX:
        env_key = os.environ.get("MINIMAX_API_KEY", "")
        if env_key:
            console.print(f"[green]✓ Found MINIMAX_API_KEY in environment[/green]")
            use_env = Confirm.ask("Use this key?", default=True)
            if use_env:
                provider.api_key = env_key
            else:
                provider.api_key = Prompt.ask("Enter MiniMax API Key", password=True)
        else:
            provider.api_key = Prompt.ask("Enter MiniMax API Key", password=True)

        base_url = Prompt.ask(
            "API Base URL (press Enter for default)",
            default=provider.base_url,
        )
        provider.base_url = base_url
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.ALIYUN_CODING_PLAN:
        env_key = os.environ.get("ALIYUN_API_KEY", "")
        if env_key:
            console.print(f"[green]✓ Found ALIYUN_API_KEY in environment[/green]")
            use_env = Confirm.ask("Use this key?", default=True)
            if use_env:
                provider.api_key = env_key
            else:
                provider.api_key = Prompt.ask("Enter Aliyun Coding Plan API Key (format: sk-sp-xxxxx)", password=True)
        else:
            provider.api_key = Prompt.ask("Enter Aliyun Coding Plan API Key (format: sk-sp-xxxxx)", password=True)

        base_url = Prompt.ask(
            "API Base URL (press Enter for default)",
            default=provider.base_url,
        )
        provider.base_url = base_url
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    else:
        env_var = "ANTHROPIC_API_KEY" if key == "anthropic" else "OPENAI_API_KEY"
        env_value = os.environ.get(env_var, "")

        if env_value:
            console.print(f"[green]✓ Found {env_var} in environment[/green]")
            use_env = Confirm.ask("Use this key?", default=True)
            if use_env:
                provider.api_key = env_value
            else:
                api_key = Prompt.ask(
                    f"Enter {key} API Key",
                    password=True,
                )
                provider.api_key = api_key
        else:
            api_key = Prompt.ask(
                f"Enter your {key} API Key",
                password=True,
            )
            provider.api_key = api_key

        if key == "anthropic":
            base_url = Prompt.ask(
                "API Base URL (press Enter for default)",
                default=provider.base_url,
            )
        else:
            base_url = Prompt.ask(
                "API Base URL (press Enter for default)",
                default=provider.base_url,
            )
        provider.base_url = base_url

        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    provider.enabled = True
    config.providers[key] = provider

    return config


def _select_model_from_list(models: list[str], default: str) -> str:
    """Show a numbered list of models and let user select one."""
    if not models:
        return default
    
    if len(models) == 1:
        console.print(f"[green]Using model: {models[0]}[/green]")
        return models[0]

    # Find preferred default
    preferred_defaults = ["gemma3:1b", "gemma4:e4b", "llama3.2", "gpt-4o", "claude-sonnet-4-20250514"]
    actual_default = default
    for pref in preferred_defaults:
        if pref in models:
            actual_default = pref
            break
    
    console.print("\n[bold]Available models:[/bold]")
    for i, model in enumerate(models, 1):
        marker = " [cyan](default)[/cyan]" if model == actual_default else ""
        console.print(f"  [{i}] {model}{marker}")
    
    default_idx = models.index(actual_default) + 1 if actual_default in models else 1
    
    choices = [str(i) for i in range(1, len(models) + 1)]
    selection = Prompt.ask(
        "\nSelect model",
        choices=choices,
        default=str(default_idx),
    )
    
    return models[int(selection) - 1]


def _detect_ollama_models(base_url: str) -> list[str]:
    """Try to detect available Ollama models."""
    try:
        import httpx
        url = base_url.replace("/v1", "/api/tags")
        # Don't use proxy for local Ollama
        with httpx.Client(timeout=5.0, proxy=None) as client:
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


def show_current_config(config: AppConfig) -> None:
    """Display current configuration."""
    console.print("\n[bold]Current Configuration[/bold]\n")

    # Providers table
    table = Table(title="Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Active", style="magenta")

    for name, provider in config.providers.providers.items():
        status = _get_provider_status(provider)
        active = "✓" if name == config.providers.active_provider else ""
        model = provider.default_model
        table.add_row(name, model, status, active)

    console.print(table)
    
    # Proxy info
    console.print(f"\n[bold]Proxy:[/bold] {_get_proxy_display(config)}")
    console.print()


def quick_setup(provider: str, api_key: str, model: str = "") -> AppConfig:
    """Quick setup for a single provider (non-interactive)."""
    config = AppConfig()

    if provider in config.providers.providers:
        config.providers.providers[provider].api_key = api_key
        if model:
            config.providers.providers[provider].default_model = model
        config.providers.active_provider = provider
        config.first_run = False

    return config


def get_proxy_url(config: AppConfig) -> str | None:
    """Get the effective proxy URL from config."""
    if config.proxy_mode == "none":
        return None
    elif config.proxy_mode == "system":
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or None
        return proxy if proxy and proxy != "" else None
    elif config.proxy_mode == "custom":
        return config.proxy_url if config.proxy_url else None
    return None