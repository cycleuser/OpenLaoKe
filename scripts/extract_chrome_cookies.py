#!/usr/bin/env python3
"""Extract cookies from Chrome."""

import json
import sqlite3
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()


def get_chrome_profile_path():
    """Find Chrome profile path."""
    profile_path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default"

    if profile_path.exists():
        return profile_path

    # Try other profiles
    chrome_path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    if chrome_path.exists():
        for profile in chrome_path.iterdir():
            if profile.is_dir() and profile.name.startswith("Profile"):
                return profile

    return None


def extract_cookies(profile_path: Path, domain: str) -> str:
    """Extract cookies for a domain from Chrome."""
    cookies_file = profile_path / "Cookies"

    if not cookies_file.exists():
        return ""

    temp_cookie = tempfile.mktemp(suffix=".sqlite")
    import shutil
    shutil.copy2(cookies_file, temp_cookie)

    try:
        conn = sqlite3.connect(temp_cookie)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, value FROM cookies WHERE host_key LIKE ?",
            (f"%{domain}%",)
        )

        cookies = [f"{name}={value}" for name, value in cursor.fetchall()]
        conn.close()

        return "; ".join(cookies)

    finally:
        import os
        os.unlink(temp_cookie)


def main():
    """Main function."""
    console.print()
    console.print("[bold cyan]Chrome Cookie Extractor[/bold cyan]")
    console.print()

    profile_path = get_chrome_profile_path()

    if not profile_path:
        console.print("[red]✗ Chrome profile not found[/red]")
        console.print("[dim]Make sure you're using Chrome and logged in to the services[/dim]")
        return

    console.print(f"[green]✓ Found Chrome profile: {profile_path}[/green]")

    # Extract cookies
    console.print()
    console.print("[bold]Extracting cookies...[/bold]")

    domains = {
        "deepseek-chat": "deepseek.com",
        "qwen-web": "qwen.ai",
        "glm-web": "chatglm.cn",
    }

    for provider, domain in domains.items():
        cookie = extract_cookies(profile_path, domain)

        if cookie:
            console.print(f"[green]✓ {provider}: {len(cookie)} chars[/green]")

            # Save
            auth_file = Path.home() / ".openlaoke" / "extended_web" / f"{provider}.json"
            auth_file.parent.mkdir(parents=True, exist_ok=True)

            auth_data = {
                "provider_type": provider,
                "cookie": cookie,
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
                "saved_at": "auto-extracted-chrome",
                "browser": "chrome",
            }

            with open(auth_file, "w") as f:
                json.dump(auth_data, f, indent=2)
        else:
            console.print(f"[yellow]⚠ {provider}: not found[/yellow]")


if __name__ == "__main__":
    main()
