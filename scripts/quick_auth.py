#!/usr/bin/env python3
"""Quick authentication script for extended web providers.

Usage:
    python3 quick_auth.py deepseek-chat
    python3 quick_auth.py claude-web
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel

console = Console()


def main() -> None:
    """Quick auth entry point."""
    if len(sys.argv) < 2:
        console.print(
            Panel(
                "[bold]Quick Authentication[/bold]\n\n"
                "Usage:\n"
                "  python3 quick_auth.py <provider>\n\n"
                "Available providers:\n"
                "  deepseek-chat   - DeepSeek Chat\n"
                "  deepseek-coder  - DeepSeek Coder\n"
                "  claude-web      - Claude Web\n"
                "  chatgpt-web     - ChatGPT Web\n"
                "  qwen-web        - Qwen Web (通义千问)\n"
                "  kimi-web        - Kimi Web (月之暗面)\n"
                "  gemini-web      - Gemini Web\n"
                "  grok-web        - Grok Web\n"
                "  doubao-web      - Doubao Web (豆包)\n"
                "  glm-web         - GLM Web (智谱清言)",
                border_style="cyan",
            )
        )
        sys.exit(1)

    provider = sys.argv[1]

    console.print(f"[bold]Authenticating {provider}...[/bold]")
    console.print()
    console.print("[dim]Launching browser automatically...[/dim]")
    console.print()

    try:
        from openlaoke.core.extended_web.auto_browser import authenticate_with_auto_browser
        from openlaoke.core.extended_web.types import WEB_PROVIDERS

        config = WEB_PROVIDERS.get(provider)
        if not config:
            console.print(f"[red]Error:[/red] Unknown provider: {provider}")
            console.print(f"\n[dim]Available: {', '.join(WEB_PROVIDERS.keys())}[/dim]")
            sys.exit(1)

        auth_data = authenticate_with_auto_browser(
            provider_type=provider,
            login_url=config.login_url,
            timeout=300,
        )

        # Run async
        import asyncio

        result = asyncio.run(auth_data)

        console.print()
        console.print(
            Panel(
                f"[bold green]✓ Authentication successful![/bold green]\n\n"
                f"Provider: {provider}\n"
                f"Cookie length: {len(result.get('cookie', ''))}\n"
                f"Auth file: ~/.openlaoke/extended_web/{provider}.json",
                border_style="green",
            )
        )

        console.print()
        console.print("[bold]You can now use:[/bold]")
        console.print(f"  openlaoke --provider extended-web --model {provider}")

    except Exception as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        console.print("\n[dim]Make sure you have Chrome/Edge installed.[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
