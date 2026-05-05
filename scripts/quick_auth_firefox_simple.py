#!/usr/bin/env python3
"""Simple Firefox authentication - direct launch without complex setup."""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from rich.console import Console

console = Console()

def get_firefox_path():
    """Get Firefox path."""
    import platform
    system = platform.system()

    if system == "Darwin":
        paths = [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox",
        ]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
        ]
    else:
        paths = ["/usr/bin/firefox", "/usr/bin/firefox-esr"]

    for path in paths:
        if Path(path).exists():
            return path
    return "firefox"


def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python3 quick_auth_firefox_simple.py <provider>[/red]")
        console.print("Example: python3 quick_auth_firefox_simple.py deepseek-chat")
        sys.exit(1)

    provider = sys.argv[1]

    # Login URLs
    login_urls = {
        "deepseek-chat": "https://chat.deepseek.com",
        "deepseek-coder": "https://chat.deepseek.com",
        "claude-web": "https://claude.ai",
        "chatgpt-web": "https://chat.openai.com",
        "qwen-web": "https://tongyi.aliyun.com",
        "kimi-web": "https://kimi.moonshot.cn",
        "gemini-web": "https://gemini.google.com",
        "grok-web": "https://grok.x.ai",
        "doubao-web": "https://doubao.com",
        "glm-web": "https://chatglm.cn",
    }

    login_url = login_urls.get(provider, "https://chat.deepseek.com")

    console.print(f"[bold]Firefox Authentication for {provider}[/bold]")
    console.print(f"Login URL: [cyan underline]{login_url}[/cyan underline]")
    console.print()

    # Get Firefox path
    firefox_path = get_firefox_path()
    console.print(f"Firefox: {firefox_path}")

    # Create temp profile
    profile_dir = tempfile.mkdtemp(prefix="openlaoke-firefox-")
    console.print(f"Profile: {profile_dir}")
    console.print()

    console.print("[bold]Launching Firefox...[/bold]")
    console.print("[dim]A Firefox window should open on your screen.[/dim]")
    console.print()

    # Launch Firefox directly
    cmd = [
        firefox_path,
        "-profile", profile_dir,
        "-no-remote",
        "-new-instance",
        login_url,
    ]

    console.print(f"Command: {' '.join(cmd)}")
    console.print()

    # Launch Firefox
    process = subprocess.Popen(cmd)

    console.print("[green]✓ Firefox launched![/green]")
    console.print()
    console.print("[bold red]IMPORTANT:[/bold red]")
    console.print("  1. Look for the Firefox window on your screen")
    console.print("  2. Login to your account")
    console.print("  3. After login, press Ctrl+C here to save cookies")
    console.print()
    console.print("[dim]Waiting for you to login...[/dim]")
    console.print()

    try:
        # Wait for user to login
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Process interrupted[/yellow]")
        console.print("[dim]Note: Manual cookie extraction not implemented yet.[/dim]")
        console.print("[dim]For now, just keep using Firefox normally.[/dim]")

    process.terminate()


if __name__ == "__main__":
    main()
