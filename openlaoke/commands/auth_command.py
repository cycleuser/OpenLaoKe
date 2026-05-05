"""Extended Web authentication CLI commands."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from openlaoke.core.extended_web import BrowserAuthManager
from openlaoke.core.extended_web.types import WEB_PROVIDERS

console = Console()


@click.group()
def auth() -> None:
    """Authentication management commands."""
    pass


@auth.group("extended-web")
def extended_web() -> None:
    """Extended Web provider authentication."""
    pass


@extended_web.command("login")
@click.argument("provider")
@click.option("--port", default=0, help="Debug port (0 for auto)")
@click.option("--timeout", default=300, help="Login timeout in seconds")
@click.option("--auto", "-a", is_flag=True, help="Auto-launch browser (no manual setup)")
def login(provider: str, port: int, timeout: int, auto: bool) -> None:
    """Authenticate a web provider.

    Examples:
        openlaoke auth extended-web login deepseek-chat
        openlaoke auth extended-web login deepseek-chat --auto
    """
    from openlaoke.core.extended_web.types import WEB_PROVIDERS

    if provider not in WEB_PROVIDERS:
        console.print(f"[red]Error:[/red] Unknown provider: {provider}")
        console.print(f"\n[dim]Available providers: {', '.join(WEB_PROVIDERS.keys())}[/dim]")
        sys.exit(1)

    config = WEB_PROVIDERS[provider]

    console.print(
        Panel.fit(
            f"[bold cyan]Authenticating {config.name}[/bold cyan]\n[dim]{config.base_url}[/dim]",
            border_style="cyan",
        )
    )
    console.print()

    auth_manager = BrowserAuthManager()

    # Check if already authenticated
    saved_auth = auth_manager.load_auth(provider)
    if saved_auth:
        console.print(f"[green]✓ Found existing authentication for {provider}[/green]")
        console.print(f"  Cookie length: {len(saved_auth.get('cookie', ''))}")
        console.print(f"  Saved at: {saved_auth.get('saved_at', 'unknown')}")
        console.print()

        if not Confirm.ask("Re-authenticate?", default=False):
            console.print("\n[dim]Using existing authentication.[/dim]")
            sys.exit(0)

    if auto:
        # Auto-launch browser mode
        console.print("[bold]Auto mode: Launching browser automatically...[/bold]")
        console.print()

        try:
            from openlaoke.core.extended_web.auto_browser import authenticate_with_auto_browser

            auth_data = asyncio.run(
                authenticate_with_auto_browser(
                    provider_type=provider,
                    login_url=config.login_url,
                    timeout=timeout,
                )
            )

            console.print()
            console.print(
                Panel(
                    f"[bold green]✓ Authentication successful![/bold green]\n\n"
                    f"[dim]Provider:[/dim] [cyan]{provider}[/cyan]\n"
                    f"[dim]Cookie length:[/dim] {len(auth_data.get('cookie', ''))}\n"
                    f"[dim]Auth file:[/dim] {auth_manager._get_auth_file(provider)}",
                    border_style="green",
                )
            )

        except Exception as e:
            console.print(f"\n[red]✗ Error:[/red] {e}")
            console.print("\n[dim]Make sure you have Chrome/Edge installed.[/dim]")
            sys.exit(1)
    else:
        # Manual mode (existing behavior)
        console.print("[bold]Manual mode: Please start browser with remote debugging[/bold]")
        console.print()
        console.print("If you haven't already, start Chrome with:")
        console.print()

        if sys.platform == "darwin":
            console.print("  [dim]# macOS[/dim]")
            console.print(
                "  [cyan]/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\[/cyan]"
            )
            console.print(
                f"    [cyan]--remote-debugging-port={port if port != 0 else 9222} \\[/cyan]"
            )
            console.print("    [cyan]--user-data-dir=/tmp/chrome-debug[/cyan]")
        elif sys.platform == "win32":
            console.print("  [dim]# Windows[/dim]")
            console.print(
                f'  [cyan]"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={port if port != 0 else 9222}[/cyan]'
            )
        else:
            console.print("  [dim]# Linux[/dim]")
            console.print(
                f"  [cyan]google-chrome --remote-debugging-port={port if port != 0 else 9222}[/cyan]"
            )

        console.print()

        if not Confirm.ask("Is browser running with remote debugging?", default=True):
            console.print(
                "\n[yellow]Please start browser first, then run this command again.[/yellow]"
            )
            console.print("\n[dim]Or use --auto flag for automatic browser launch.[/dim]")
            sys.exit(0)

        console.print()
        console.print("[bold]Step 2: Login to the service[/bold]")
        console.print()

        # Open login page
        console.print(f"\n[dim]Opening {config.login_url}...[/dim]")
        console.print("[dim]Please complete the login in the browser window.[/dim]")
        console.print()

        try:
            # Run authentication
            auth_data = asyncio.run(
                auth_manager.authenticate_provider(provider, port if port != 0 else 9222, timeout)
            )

            console.print()
            console.print(
                Panel(
                    f"[bold green]✓ Authentication successful![/bold green]\n\n"
                    f"[dim]Provider:[/dim] [cyan]{provider}[/cyan]\n"
                    f"[dim]Cookie length:[/dim] {len(auth_data.get('cookie', ''))}\n"
                    f"[dim]Auth file:[/dim] {auth_manager._get_auth_file(provider)}",
                    border_style="green",
                )
            )

        except ConnectionError as e:
            console.print(f"\n[red]✗ Connection error:[/red] {e}")
            console.print("\n[dim]Make sure browser is running with --remote-debugging-port[/dim]")
            sys.exit(1)
        except TimeoutError as e:
            console.print(f"\n[red]✗ Timeout:[/red] {e}")
            console.print("\n[dim]Please try again.[/dim]")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]✗ Error:[/red] {e}")
            sys.exit(1)

    config = WEB_PROVIDERS[provider]

    console.print(
        Panel.fit(
            f"[bold cyan]Authenticating {config.name}[/bold cyan]\n[dim]{config.base_url}[/dim]",
            border_style="cyan",
        )
    )
    console.print()

    # Check if Chrome is running with remote debugging
    console.print("[bold]Step 1: Start Chrome with remote debugging[/bold]")
    console.print()
    console.print("If you haven't already, start Chrome with:")
    console.print()

    if sys.platform == "darwin":
        console.print("  [dim]# macOS[/dim]")
        console.print(
            "  [cyan]/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\[/cyan]"
        )
        console.print(f"    [cyan]--remote-debugging-port={port} \\[/cyan]")
        console.print("    [cyan]--user-data-dir=/tmp/chrome-debug[/cyan]")
    elif sys.platform == "win32":
        console.print("  [dim]# Windows[/dim]")
        console.print(
            f'  [cyan]"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={port}[/cyan]'
        )
    else:
        console.print("  [dim]# Linux[/dim]")
        console.print(f"  [cyan]google-chrome --remote-debugging-port={port}[/cyan]")

    console.print()

    if not Confirm.ask("Is Chrome running with remote debugging?", default=True):
        console.print("\n[yellow]Please start Chrome first, then run this command again.[/yellow]")
        sys.exit(0)

    # Authenticate
    console.print()
    console.print("[bold]Step 2: Login to the service[/bold]")
    console.print()

    auth_manager = BrowserAuthManager()

    # Check if already authenticated
    saved_auth = auth_manager.load_auth(provider)
    if saved_auth:
        console.print(f"[green]✓ Found existing authentication for {provider}[/green]")
        console.print(f"  Cookie length: {len(saved_auth.get('cookie', ''))}")
        console.print(f"  Saved at: {saved_auth.get('saved_at', 'unknown')}")
        console.print()

        if not Confirm.ask("Re-authenticate?", default=False):
            console.print("\n[dim]Using existing authentication.[/dim]")
            sys.exit(0)

    # Open login page
    console.print(f"\n[dim]Opening {config.login_url}...[/dim]")
    console.print("[dim]Please complete the login in the browser window.[/dim]")
    console.print()

    try:
        # Run authentication
        auth_data = asyncio.run(auth_manager.authenticate_provider(provider, port, timeout))

        console.print()
        console.print(
            Panel(
                f"[bold green]✓ Authentication successful![/bold green]\n\n"
                f"[dim]Provider:[/dim] [cyan]{provider}[/cyan]\n"
                f"[dim]Cookie length:[/dim] {len(auth_data.get('cookie', ''))}\n"
                f"[dim]Auth file:[/dim] {auth_manager._get_auth_file(provider)}",
                border_style="green",
            )
        )

    except ConnectionError as e:
        console.print(f"\n[red]✗ Connection error:[/red] {e}")
        console.print("\n[dim]Make sure Chrome is running with --remote-debugging-port[/dim]")
        sys.exit(1)
    except TimeoutError as e:
        console.print(f"\n[red]✗ Timeout:[/red] {e}")
        console.print("\n[dim]Please try again.[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        sys.exit(1)


@extended_web.command("list")
def list_auth() -> None:
    """List all authenticated providers."""
    auth_manager = BrowserAuthManager()
    auths = auth_manager.list_saved_auths()

    if not auths:
        console.print("[yellow]No authenticated providers found.[/yellow]")
        console.print(
            "\n[dim]Use 'openlaoke auth extended-web login <provider>' to authenticate.[/dim]"
        )
        return

    console.print(f"[bold]Authenticated providers ({len(auths)})[/bold]")
    console.print()

    table = Table(show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Cookie Length", justify="right")

    for provider_type in auths:
        auth_data = auth_manager.load_auth(provider_type)
        config = WEB_PROVIDERS.get(provider_type)
        name = config.name if config else provider_type

        # Check if auth is valid
        cookie = auth_data.get("cookie", "") if auth_data else ""
        status = "[green]✓ Valid[/green]" if len(cookie) > 10 else "[red]✗ Invalid[/red]"

        table.add_row(
            provider_type,
            name,
            status,
            str(len(cookie)),
        )

    console.print(table)


@extended_web.command("remove")
@click.argument("provider")
def remove(provider: str) -> None:
    """Remove authentication for a provider.

    Examples:
        openlaoke auth extended-web remove deepseek-chat
    """
    from openlaoke.core.extended_web.types import WEB_PROVIDERS

    if provider not in WEB_PROVIDERS:
        console.print(f"[red]Error:[/red] Unknown provider: {provider}")
        sys.exit(1)

    auth_manager = BrowserAuthManager()
    auth_file = auth_manager._get_auth_file(provider)

    if not auth_file.exists():
        console.print(f"[yellow]No authentication found for {provider}[/yellow]")
        return

    config = WEB_PROVIDERS[provider]

    console.print(f"[bold]Remove authentication for {config.name}?[/bold]")
    console.print(f"  Auth file: {auth_file}")
    console.print()

    if not Confirm.ask("Are you sure?", default=False):
        console.print("[dim]Cancelled.[/dim]")
        return

    auth_manager.delete_auth(provider)
    console.print(f"[green]✓ Authentication removed for {provider}[/green]")


@extended_web.command("show")
@click.argument("provider")
def show(provider: str) -> None:
    """Show authentication details for a provider."""
    from openlaoke.core.extended_web.types import WEB_PROVIDERS

    if provider not in WEB_PROVIDERS:
        console.print(f"[red]Error:[/red] Unknown provider: {provider}")
        sys.exit(1)

    auth_manager = BrowserAuthManager()
    auth_data = auth_manager.load_auth(provider)

    if not auth_data:
        console.print(f"[yellow]No authentication found for {provider}[/yellow]")
        return

    config = WEB_PROVIDERS[provider]

    console.print(f"[bold]{config.name} Authentication[/bold]")
    console.print()

    # Mask cookie for security
    cookie = auth_data.get("cookie", "")
    masked_cookie = f"{cookie[:10]}...{cookie[-10:]}" if len(cookie) > 20 else "(short cookie)"

    console.print(f"  [dim]Provider:[/dim] {provider}")
    console.print(f"  [dim]Name:[/dim] {config.name}")
    console.print(f"  [dim]Base URL:[/dim] {config.base_url}")
    console.print(f"  [dim]Cookie:[/dim] {masked_cookie}")
    console.print(f"  [dim]Cookie length:[/dim] {len(cookie)}")
    console.print(f"  [dim]User agent:[/dim] {auth_data.get('user_agent', 'N/A')[:50]}...")
    console.print(
        f"  [dim]Has bearer token:[/dim] {'Yes' if auth_data.get('bearer_token') else 'No'}"
    )
    console.print(f"  [dim]Auth file:[/dim] {auth_manager._get_auth_file(provider)}")
    console.print()

    # Show required cookies
    console.print(f"  [dim]Required cookies:[/dim] {', '.join(config.required_cookies)}")

    # Check if all required cookies are present
    has_all = all(req in cookie for req in config.required_cookies)
    status = (
        "[green]✓ All required cookies present[/green]"
        if has_all
        else "[red]✗ Missing required cookies[/red]"
    )
    console.print(f"  [dim]Status:[/dim] {status}")


@extended_web.command("test")
@click.argument("provider")
@click.option("--message", default="你好，请介绍一下你自己", help="Test message")
def test(provider: str, message: str) -> None:
    """Test authentication by making an API call.

    Examples:
        openlaoke auth extended-web test deepseek-chat
    """
    from openlaoke.core.extended_web.types import WEB_PROVIDERS
    from openlaoke.core.extended_web.web_client import WebServiceClient

    if provider not in WEB_PROVIDERS:
        console.print(f"[red]Error:[/red] Unknown provider: {provider}")
        sys.exit(1)

    auth_manager = BrowserAuthManager()
    auth_data = auth_manager.load_auth(provider)

    if not auth_data:
        console.print(f"[red]Error:[/red] No authentication found for {provider}")
        console.print("\n[dim]Run 'openlaoke auth extended-web login {provider}' first.[/dim]")
        sys.exit(1)

    config = WEB_PROVIDERS[provider]

    console.print(f"[bold]Testing {config.name}...[/bold]")
    console.print(f"  Message: {message}")
    console.print()

    async def run_test() -> None:
        client = WebServiceClient(
            provider_type=provider,
            cookie=auth_data["cookie"],
            user_agent=auth_data.get("user_agent", ""),
            bearer_token=auth_data.get("bearer_token", ""),
            base_url=config.base_url,
            api_endpoint=config.api_endpoint,
            custom_headers=config.custom_headers,
        )

        try:
            messages = [{"role": "user", "content": message}]
            response = await client.chat(messages)

            content = response.get("content", "")
            if content:
                console.print("[green]✓ Response received:[/green]")
                console.print()
                console.print(f"  {content[:200]}...")
                console.print()

                usage = response.get("usage", {})
                if usage:
                    console.print(f"  [dim]Tokens:[/dim] {usage}")
            else:
                console.print("[yellow]⚠ Empty response[/yellow]")

        except Exception as e:
            console.print(f"[red]✗ Error:[/red] {e}")
            sys.exit(1)
        finally:
            await client.close()

    asyncio.run(run_test())


# Add auth command to main CLI
if __name__ == "__main__":
    auth()
