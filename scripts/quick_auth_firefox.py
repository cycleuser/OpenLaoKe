#!/usr/bin/env python3
"""Quick authentication script using Firefox.

Usage:
    python3 quick_auth_firefox.py deepseek-chat
"""

from __future__ import annotations

import asyncio
import sys

from rich.console import Console
from rich.panel import Panel

console = Console()


def main() -> None:
    """Quick auth entry point using Firefox."""
    if len(sys.argv) < 2:
        console.print(Panel(
            "[bold]Firefox Quick Authentication[/bold]\n\n"
            "Usage:\n"
            "  python3 quick_auth_firefox.py <provider>\n\n"
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
            "  glm-web         - GLM Web (智谱清言)\n\n"
            "This script uses Firefox for authentication.",
            border_style="cyan",
        ))
        sys.exit(1)

    provider = sys.argv[1]

    console.print(f"[bold]Authenticating {provider} using Firefox...[/bold]")
    console.print()
    console.print("[dim]Launching Firefox automatically...[/dim]")
    console.print()

    try:
        from openlaoke.core.extended_web.auto_browser import authenticate_with_auto_browser
        from openlaoke.core.extended_web.types import WEB_PROVIDERS

        config = WEB_PROVIDERS.get(provider)
        if not config:
            console.print(f"[red]Error:[/red] Unknown provider: {provider}")
            console.print(f"\n[dim]Available: {', '.join(WEB_PROVIDERS.keys())}[/dim]")
            sys.exit(1)

        # Authenticate using Firefox
        result = asyncio.run(authenticate_with_auto_browser(
            provider_type=provider,
            login_url=config.login_url,
            timeout=300,
            browser_type="firefox",
        ))

        console.print()
        console.print(Panel(
            f"[bold green]✓ Authentication successful![/bold green]\n\n"
            f"Provider: {provider}\n"
            f"Browser: Firefox\n"
            f"Cookie length: {len(result.get('cookie', ''))}\n"
            f"Auth file: ~/.openlaoke/extended_web/{provider}.json",
            border_style="green",
        ))

        console.print()
        console.print("[bold]You can now use:[/bold]")
        console.print(f"  openlaoke --provider extended-web --model {provider}")

    except Exception as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        console.print("\n[dim]Make sure Firefox is installed.[/dim]")
        console.print("[dim]Install with: brew install --cask firefox (macOS)[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
