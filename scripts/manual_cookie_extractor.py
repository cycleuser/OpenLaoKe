#!/usr/bin/env python3
"""Manual cookie extractor with step-by-step guide."""

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()


def save_cookie(provider_type: str, cookie: str):
    """Save cookie to auth file."""
    auth_file = Path.home() / ".openlaoke" / "extended_web" / f"{provider_type}.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    auth_data = {
        "provider_type": provider_type,
        "cookie": cookie,
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
        "saved_at": "manual-extracted",
        "browser": "manual",
    }

    with open(auth_file, "w") as f:
        json.dump(auth_data, f, indent=2)


def extract_cookie_for(provider_type: str, service_name: str, login_url: str, cookie_names: list):
    """Extract cookie for a specific service."""
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]{service_name}[/bold cyan]\n"
        f"[dim]{login_url}[/dim]",
        border_style="cyan"
    ))
    console.print()
    console.print("[bold]Steps to extract cookie:[/bold]")
    console.print()
    console.print(f"  [dim]1. Open: [cyan underline]{login_url}[/cyan underline][/dim]")
    console.print("  [dim]2. Login with your account[/dim]")
    console.print("  [dim]3. Press F12 (or right-click → Inspect)[/dim]")
    console.print("  [dim]4. Go to 'Application' tab (Chrome) or 'Storage' tab (Firefox)[/dim]")
    console.print("  [dim]5. Expand 'Cookies' on the left[/dim]")
    console.print(f"  [dim]6. Select the website ({login_url})[/dim]")
    console.print("  [dim]7. Find these cookies:[/dim]")
    for name in cookie_names:
        console.print(f"      [cyan]{name}[/cyan]")
    console.print("  [dim]8. Copy the 'Value' column for each cookie[/dim]")
    console.print()

    if not console.input("  Have you logged in and ready to extract? [y/n]: ").lower().startswith('y'):
        console.print("[yellow]⚠ Skipped[/yellow]")
        return False

    console.print()
    cookie_parts = []
    for name in cookie_names:
        value = console.input(f"  Enter [cyan]{name}[/cyan] value: ")
        if value and len(value) > 5:
            cookie_parts.append(f"{name}={value}")

    if cookie_parts:
        cookie_string = "; ".join(cookie_parts)
        save_cookie(provider_type, cookie_string)
        console.print()
        console.print("[green]✓ Cookie saved![/green]")
        console.print(f"  Length: {len(cookie_string)} chars")
        return True
    else:
        console.print("[yellow]⚠ No cookie entered[/yellow]")
        return False


def main():
    """Main function."""
    console.print()
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]  Cookie Extractor[/bold cyan]")
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")

    services = [
        ("deepseek-chat", "DeepSeek Chat", "https://chat.deepseek.com", ["d_id", "ds_session_id"]),
        ("qwen-web", "Qwen Web (通义千问)", "https://chat.qwen.ai", ["qwen_session"]),
        ("glm-web", "GLM Web (智谱清言)", "https://chatglm.cn", ["glmsession"]),
    ]

    console.print()
    console.print("[bold]Which service do you want to extract cookie for?[/bold]")
    console.print()
    for i, (provider, name, url, cookies) in enumerate(services, 1):
        console.print(f"  [{i}] {name}")

    console.print()
    choice = console.input("Select service [1/2/3]: ")

    if choice == "1":
        extract_cookie_for(*services[0])
    elif choice == "2":
        extract_cookie_for(*services[1])
    elif choice == "3":
        extract_cookie_for(*services[2])
    else:
        console.print("[yellow]⚠ Invalid choice[/yellow]")

    console.print()
    console.print("[dim]After extracting cookies, you can use:[/dim]")
    console.print("  openlaoke --provider extended-web --model <service>")


if __name__ == "__main__":
    main()
