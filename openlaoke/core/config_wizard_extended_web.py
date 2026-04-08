"""Extended Web configuration in wizard."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.prompt import Confirm, Prompt

from .extended_web.config_integration import extract_cookie_in_wizard
from .extended_web import BrowserAuthManager

console = Console()


async def configure_extended_web(config, provider, key: str) -> bool:
    """Configure Extended Web provider in wizard.

    Args:
        config: AppConfig
        provider: ProviderConfig
        key: Provider key

    Returns:
        True if configured successfully
    """
    console.print("[bold cyan]🌐 Extended Web Configuration[/bold cyan]")
    console.print()
    console.print("[dim]Extended Web uses browser-based authentication.[/dim]")
    console.print()

    # Check for existing authentication
    auth_manager = BrowserAuthManager()
    saved_auths = auth_manager.list_saved_auths()

    # Validate that saved auths have real cookies (not placeholders)
    valid_auths = []
    for auth_name in saved_auths:
        auth_data = auth_manager.load_auth(auth_name)
        if auth_data:
            cookie = auth_data.get("cookie", "")
            # Skip if cookie is a placeholder
            if cookie and cookie != "placeholder_need_manual_extraction" and len(cookie) > 20:
                valid_auths.append(auth_name)

    if valid_auths:
        console.print(f"[green]✓ Found {len(valid_auths)} authenticated service(s):[/green]")
        for auth in valid_auths:
            console.print(f"  • {auth}")
        console.print()

        # Show ALL available models, mark authenticated ones
        console.print("[bold]All available web services:[/bold]")
        for i, model in enumerate(provider.models, 1):
            is_authed = " [green]✓ authenticated[/green]" if model in valid_auths else ""
            console.print(f"  [{i}] {model}{is_authed}")

        console.print()
        console.print("[bold]Select which service to configure as default:[/bold]")
        choices = [str(i) for i in range(1, len(provider.models) + 1)]
        selection = Prompt.ask(
            "Select service",
            choices=choices,
            default="1",
        )
        provider.default_model = provider.models[int(selection) - 1]

        # Check if selected model is authenticated (with real cookies)
        is_selected_authed = provider.default_model in valid_auths

        if is_selected_authed:
            console.print()
            console.print(f"[green]✓ {provider.default_model} is already authenticated![/green]")
            provider.enabled = True
            config.providers[key] = provider
            return True

    else:
        console.print("[yellow]⚠ No authenticated services found.[/yellow]")
        console.print()

        # Show ALL available models
        console.print("[bold]Available web services:[/bold]")
        for i, model in enumerate(provider.models, 1):
            console.print(f"  [{i}] {model}")

        console.print()
        selection = Prompt.ask(
            "Select default model",
            choices=[str(i) for i in range(1, len(provider.models) + 1)],
            default="1",
        )
        provider.default_model = provider.models[int(selection) - 1]

        is_selected_authed = False

    provider.enabled = True
    config.providers[key] = provider

    console.print(f"\n[green]✓ Configured {key} with model {provider.default_model}[/green]")

    # If not authenticated, MUST authenticate now
    if not is_selected_authed:
        console.print()
        console.print("[bold red]⚠ Authentication Required![/bold red]")
        console.print(
            f"[dim]The service {provider.default_model} requires browser authentication.[/dim]"
        )
        console.print()

        # Always authenticate - no skip option
        console.print("[bold]Starting automatic authentication...[/bold]")
        console.print()
        console.print("[dim]This will:[/dim]")
        console.print("  [dim]1. Open your default browser automatically[/dim]")
        console.print("  [dim]2. Navigate to the login page[/dim]")
        console.print("  [dim]3. Wait for you to login[/dim]")
        console.print("  [dim]4. Extract cookies automatically[/dim]")
        console.print()

        if not Confirm.ask("  Continue with authentication?", default=True):
            console.print("[yellow]⚠ Authentication cancelled[/yellow]")
            return False

        # Run async authentication
        auth_success = await extract_cookie_in_wizard(provider.default_model)

        if not auth_success:
            console.print()
            console.print("[yellow]⚠ Authentication was not completed.[/yellow]")
            console.print("[dim]You can authenticate later by running:[/dim]")
            console.print(f"  python3 -m openlaoke.core.extended_web.auto_cookie_extractor")
            return False

    # Save the extended_web provider config
    provider.enabled = True
    config.providers[key] = provider

    return True
