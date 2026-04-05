"""Interactive configuration wizard for first-time setup."""

from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType
from openlaoke.utils.config import AppConfig

console = Console(force_terminal=True)


def run_config_wizard(config: AppConfig | None = None) -> AppConfig:
    """Run the interactive configuration wizard."""
    config = config or AppConfig()

    console.clear()
    console.print(
        Panel.fit(
            "[bold cyan]OpenLaoKe Configuration Wizard[/bold cyan]\n"
            "[dim]Let's set up your AI coding assistant[/dim]",
            border_style="cyan",
        )
    )
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
            ("5", "Azure OpenAI", "azure_openai", "cloud"),
            ("6", "Google AI (Gemini)", "google", "cloud"),
            ("7", "Google Vertex AI", "google_vertex", "cloud"),
            ("8", "AWS Bedrock", "aws_bedrock", "cloud"),
            ("9", "xAI Grok", "xai", "cloud"),
            ("10", "Mistral AI", "mistral", "cloud"),
            ("11", "Groq", "groq", "cloud"),
            ("12", "Cerebras", "cerebras", "cloud"),
            ("13", "Cohere", "cohere", "cloud"),
            ("14", "DeepInfra", "deepinfra", "cloud"),
            ("15", "Together AI", "togetherai", "cloud"),
            ("16", "Perplexity", "perplexity", "cloud"),
            ("17", "OpenRouter", "openrouter", "cloud"),
            ("18", "GitHub Copilot", "github_copilot", "cloud"),
            ("19", "Ollama (Local)", "ollama", "local"),
            ("20", "LM Studio (Local)", "lm_studio", "local"),
            ("21", "OpenAI-Compatible (Custom)", "openai_compatible", "custom"),
            ("22", "Skip (configure later)", "", ""),
        ]

        for opt, name, key, _ptype in providers:
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
            choices=[str(i) for i in range(1, 23)],
            default="19",
        )

        provider_map = {
            "1": "anthropic",
            "2": "openai",
            "3": "minimax",
            "4": "aliyun_coding_plan",
            "5": "azure_openai",
            "6": "google",
            "7": "google_vertex",
            "8": "aws_bedrock",
            "9": "xai",
            "10": "mistral",
            "11": "groq",
            "12": "cerebras",
            "13": "cohere",
            "14": "deepinfra",
            "15": "togetherai",
            "16": "perplexity",
            "17": "openrouter",
            "18": "github_copilot",
            "19": "ollama",
            "20": "lm_studio",
            "21": "openai_compatible",
        }

        if choice == "22":
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


def _get_env_var_name(provider_type: ProviderType) -> str:
    """Get environment variable name for a provider type."""
    env_map = {
        ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
        ProviderType.OPENAI: "OPENAI_API_KEY",
        ProviderType.MINIMAX: "MINIMAX_API_KEY",
        ProviderType.ALIYUN_CODING_PLAN: "ALIYUN_API_KEY",
        ProviderType.AZURE_OPENAI: "AZURE_OPENAI_API_KEY",
        ProviderType.GOOGLE: "GOOGLE_API_KEY",
        ProviderType.GOOGLE_VERTEX: "GOOGLE_APPLICATION_CREDENTIALS",
        ProviderType.AWS_BEDROCK: "AWS_ACCESS_KEY_ID",
        ProviderType.XAI: "XAI_API_KEY",
        ProviderType.MISTRAL: "MISTRAL_API_KEY",
        ProviderType.GROQ: "GROQ_API_KEY",
        ProviderType.CEREBRAS: "CEREBRAS_API_KEY",
        ProviderType.COHERE: "COHERE_API_KEY",
        ProviderType.DEEPINFRA: "DEEPINFRA_API_KEY",
        ProviderType.TOGETHERAI: "TOGETHERAI_API_KEY",
        ProviderType.PERPLEXITY: "PERPLEXITY_API_KEY",
        ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
        ProviderType.GITHUB_COPILOT: "GITHUB_TOKEN",
        ProviderType.OPENAI_COMPATIBLE: "OPENAI_API_KEY",
    }
    return env_map.get(provider_type, "")


def _get_provider_status(provider: ProviderConfig) -> str:
    if provider.is_local:
        return "[green]✓ local[/green]"
    if provider.api_key:
        return "[green]✓ stored[/green]"
    env_key = ""
    if provider.provider_type == ProviderType.ANTHROPIC:
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    elif provider.provider_type == ProviderType.OPENAI:
        env_key = os.environ.get("OPENAI_API_KEY", "")
    elif provider.provider_type == ProviderType.MINIMAX:
        env_key = os.environ.get("MINIMAX_API_KEY", "")
    elif provider.provider_type == ProviderType.ALIYUN_CODING_PLAN:
        env_key = os.environ.get("ALIYUN_API_KEY", "")
    elif provider.provider_type == ProviderType.AZURE_OPENAI:
        env_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    elif provider.provider_type == ProviderType.GOOGLE:
        env_key = os.environ.get("GOOGLE_API_KEY", "")
    elif provider.provider_type == ProviderType.GOOGLE_VERTEX:
        env_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    elif provider.provider_type == ProviderType.AWS_BEDROCK:
        env_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    elif provider.provider_type == ProviderType.XAI:
        env_key = os.environ.get("XAI_API_KEY", "")
    elif provider.provider_type == ProviderType.MISTRAL:
        env_key = os.environ.get("MISTRAL_API_KEY", "")
    elif provider.provider_type == ProviderType.GROQ:
        env_key = os.environ.get("GROQ_API_KEY", "")
    elif provider.provider_type == ProviderType.CEREBRAS:
        env_key = os.environ.get("CEREBRAS_API_KEY", "")
    elif provider.provider_type == ProviderType.COHERE:
        env_key = os.environ.get("COHERE_API_KEY", "")
    elif provider.provider_type == ProviderType.DEEPINFRA:
        env_key = os.environ.get("DEEPINFRA_API_KEY", "")
    elif provider.provider_type == ProviderType.TOGETHERAI:
        env_key = os.environ.get("TOGETHERAI_API_KEY", "")
    elif provider.provider_type == ProviderType.PERPLEXITY:
        env_key = os.environ.get("PERPLEXITY_API_KEY", "")
    elif provider.provider_type == ProviderType.OPENROUTER:
        env_key = os.environ.get("OPENROUTER_API_KEY", "")
    elif provider.provider_type == ProviderType.GITHUB_COPILOT:
        env_key = os.environ.get("GITHUB_TOKEN", "")
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

    # Check available configurations
    stored_key = provider.api_key
    env_var_name = _get_env_var_name(provider.provider_type)
    env_key = os.environ.get(env_var_name, "")

    # Show configuration options
    if stored_key or env_key:
        console.print()
        table = Table(show_header=False, box=None)
        table.add_column("Option", style="cyan")
        table.add_column("Source", style="bold")
        table.add_column("Details", style="dim")

        options = []
        default_choice = "1"

        if stored_key:
            masked_key = (
                f"{stored_key[:8]}...{stored_key[-4:]}" if len(stored_key) > 12 else stored_key
            )
            table.add_row(
                "  [1]", "Stored config", f"Key: {masked_key}, Model: {provider.default_model}"
            )
            options.append("1")
            default_choice = "1"

        if env_key:
            masked_env = f"{env_key[:8]}...{env_key[-4:]}" if len(env_key) > 12 else env_key
            option_num = str(len(options) + 1)
            table.add_row(f"  [{option_num}]", "Environment var", f"{env_var_name}={masked_env}")
            options.append(option_num)
            if not stored_key:
                default_choice = option_num

        option_num = str(len(options) + 1)
        table.add_row(f"  [{option_num}]", "Reconfigure", "Enter new API key and settings")
        options.append(option_num)

        console.print(table)
        console.print()

        choice = Prompt.ask(
            "Select configuration source",
            choices=options,
            default=default_choice,
        )

        # Use stored configuration (complete config, can return)
        if choice == "1" and stored_key:
            console.print(f"[green]✓ Using stored configuration for {key}[/green]")
            return config

        # Use environment variable (need to continue config for model selection)
        if env_key:
            env_option_idx = 2 if stored_key else 1
            if choice == str(env_option_idx):
                provider.api_key = env_key
                console.print(f"[green]✓ Using {env_var_name} from environment[/green]")
                console.print("[dim]Continue with model selection...[/dim]\n")
            elif choice == options[-1]:
                # Reconfigure - will ask for new API key below
                console.print("\n[yellow]Reconfiguring...[/yellow]")
        elif choice == options[-1]:
            console.print("\n[yellow]Reconfiguring...[/yellow]")

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
                console.print(f"[green]✓ Detected {len(models)} models from Ollama[/green]")
                provider.models = models
                provider.default_model = _select_model_from_list(models, provider.default_model)
            else:
                console.print("\n[yellow]⚠ Could not detect models from Ollama.[/yellow]")
                console.print("[dim]Make sure Ollama is running: ollama serve[/dim]")
                console.print("[dim]Or pull some models: ollama pull gemma3:1b[/dim]\n")
                console.print("[bold]Using default model list (you can change this later):[/bold]")
                provider.default_model = _select_model_from_list(
                    provider.models, provider.default_model
                )
        else:
            provider.default_model = _select_model_from_list(
                provider.models, provider.default_model
            )

    elif provider.provider_type == ProviderType.OPENAI_COMPATIBLE:
        console.print("[dim]Enter your custom OpenAI-compatible API details[/dim]")

        base_url = Prompt.ask(
            "API Base URL",
            default=provider.base_url or "http://localhost:8000/v1",
        )
        provider.base_url = base_url

        # Ask for API key if not already set
        if not provider.api_key:
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
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter MiniMax API Key", password=True)

        base_url = Prompt.ask(
            "API Base URL (press Enter for default)",
            default=provider.base_url,
        )
        provider.base_url = base_url
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.ALIYUN_CODING_PLAN:
        if not provider.api_key:
            provider.api_key = Prompt.ask(
                "Enter Aliyun Coding Plan API Key (format: sk-sp-xxxxx)", password=True
            )

        base_url = Prompt.ask(
            "API Base URL (press Enter for default)",
            default=provider.base_url,
        )
        provider.base_url = base_url
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.AZURE_OPENAI:
        console.print("[dim]Azure OpenAI requires endpoint and API key[/dim]")

        # Endpoint configuration
        env_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        if env_endpoint and not provider.base_url:
            console.print("[green]✓ Found AZURE_OPENAI_ENDPOINT in environment[/green]")
            use_env = Confirm.ask("Use this endpoint?", default=True)
            if use_env:
                provider.base_url = env_endpoint

        if not provider.base_url:
            provider.base_url = Prompt.ask(
                "Enter Azure OpenAI Endpoint (e.g., https://your-resource.openai.azure.com)"
            )

        # API key configuration
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Azure OpenAI API Key", password=True)

        console.print(
            f"\n[dim]Available models (deployment names): {', '.join(provider.models)}[/dim]"
        )
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.GOOGLE:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Google AI API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.GOOGLE_VERTEX:
        console.print("[dim]Google Vertex AI uses GCP Application Default Credentials[/dim]")
        env_project = os.environ.get("GOOGLE_VERTEX_PROJECT", "")
        if env_project:
            console.print("[green]✓ Found GOOGLE_VERTEX_PROJECT in environment[/green]")
        else:
            project_id = Prompt.ask("Enter GCP Project ID")
            os.environ["GOOGLE_VERTEX_PROJECT"] = project_id
        env_location = os.environ.get("GOOGLE_VERTEX_LOCATION", "")
        if env_location:
            console.print("[green]✓ Found GOOGLE_VERTEX_LOCATION in environment[/green]")
        else:
            location = Prompt.ask("Enter GCP Location (e.g., us-central1)", default="us-central1")
            os.environ["GOOGLE_VERTEX_LOCATION"] = location
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.AWS_BEDROCK:
        console.print("[dim]AWS Bedrock uses AWS credentials from environment[/dim]")
        env_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        if env_key:
            console.print("[green]✓ Found AWS_ACCESS_KEY_ID in environment[/green]")
        else:
            console.print(
                "[yellow]AWS credentials not found. Configure with AWS CLI or set environment variables[/yellow]"
            )
        env_region = os.environ.get("AWS_REGION", "")
        if env_region:
            console.print("[green]✓ Found AWS_REGION in environment[/green]")
        else:
            region = Prompt.ask("Enter AWS Region (e.g., us-east-1)", default="us-east-1")
            os.environ["AWS_REGION"] = region
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.XAI:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter xAI API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.MISTRAL:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Mistral API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.GROQ:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Groq API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.CEREBRAS:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Cerebras API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.COHERE:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Cohere API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.DEEPINFRA:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter DeepInfra API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.TOGETHERAI:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Together AI API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.PERPLEXITY:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter Perplexity API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.OPENROUTER:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter OpenRouter API Key", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    elif provider.provider_type == ProviderType.GITHUB_COPILOT:
        if not provider.api_key:
            provider.api_key = Prompt.ask("Enter GitHub Personal Access Token", password=True)
        console.print(f"\n[dim]Available models: {', '.join(provider.models)}[/dim]")
        provider.default_model = _select_model_from_list(provider.models, provider.default_model)

    else:
        if not provider.api_key:
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
    preferred_defaults = [
        "gemma3:1b",
        "gemma4:e4b",
        "llama3.2",
        "gpt-4o",
        "claude-sonnet-4-20250514",
    ]
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

        with httpx.Client(timeout=5.0, proxy=None) as client:
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                all_models = [m["name"] for m in data.get("models", [])]

                embedding_keywords = [
                    "embed",
                    "embedding",
                    "rerank",
                    "reranker",
                    "minilm",
                    "arctic-embed",
                    "bge-",
                    "nomic-embed",
                    "paraphrase",
                    "granite-embedding",
                ]

                generation_models = []
                for model in all_models:
                    model_lower = model.lower()
                    is_embedding = any(kw in model_lower for kw in embedding_keywords)

                    if not is_embedding:
                        generation_models.append(model)

                return generation_models if generation_models else all_models
    except Exception as e:
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
