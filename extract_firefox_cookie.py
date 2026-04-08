#!/usr/bin/env python3
"""Automatically extract cookies from Firefox."""

import json
import sqlite3
import tempfile
from pathlib import Path
from rich.console import Console

console = Console()


def get_firefox_profile_path() -> Path | None:
    """Find Firefox profile path."""
    if Path.home().name == 'fred':  # macOS
        profiles_path = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        profiles_path = Path.home() / ".mozilla" / "firefox" / "Profiles"
    
    if not profiles_path.exists():
        return None
    
    # Find default profile
    for profile_dir in profiles_path.iterdir():
        if profile_dir.is_dir() and "default" in profile_dir.name:
            return profile_dir
    
    # Return first profile if no default
    profiles = list(profiles_path.iterdir())
    if profiles:
        return profiles[0]
    
    return None


def extract_cookies(profile_path: Path, domains: list[str]) -> dict[str, str]:
    """Extract cookies from Firefox profile.
    
    Args:
        profile_path: Firefox profile directory
        domains: List of domains to extract cookies for
        
    Returns:
        Dictionary of cookie name -> value
    """
    cookies_file = profile_path / "cookies.sqlite"
    
    if not cookies_file.exists():
        console.print(f"[red]Cookies file not found: {cookies_file}[/red]")
        return {}
    
    # Copy to temp file to avoid locking
    temp_cookie = tempfile.mktemp(suffix=".sqlite")
    import shutil
    shutil.copy2(cookies_file, temp_cookie)
    
    try:
        conn = sqlite3.connect(temp_cookie)
        cursor = conn.cursor()
        
        cookies = {}
        for domain in domains:
            cursor.execute(
                "SELECT name, value FROM moz_cookies WHERE host LIKE ?",
                (f"%{domain}%",)
            )
            for name, value in cursor.fetchall():
                cookies[name] = value
        
        conn.close()
        return cookies
        
    finally:
        import os
        os.unlink(temp_cookie)


def main():
    """Main entry point."""
    console.print()
    console.print("[bold cyan]Firefox Cookie Extractor[/bold cyan]")
    console.print()
    
    # Find Firefox profile
    profile_path = get_firefox_profile_path()
    
    if not profile_path:
        console.print("[red]✗ Firefox profile not found[/red]")
        console.print("[dim]Make sure Firefox is installed and has been used.[/dim]")
        return
    
    console.print(f"[green]✓ Found Firefox profile: {profile_path}[/green]")
    
    # Extract Qwen cookies
    console.print()
    console.print("[bold]Extracting Qwen Web cookies...[/bold]")
    
    cookies = extract_cookies(profile_path, ["qianwen.com", "aliyun.com"])
    
    if not cookies:
        console.print("[yellow]⚠ No Qwen cookies found[/yellow]")
        console.print("[dim]Make sure you're logged in to https://www.qianwen.com in Firefox[/dim]")
        return
    
    console.print(f"[green]✓ Found {len(cookies)} cookies[/green]")
    
    # Check for required cookies
    required = ["_tb_token_", "cookie2"]
    found_required = [name for name in required if name in cookies]
    
    if len(found_required) >= 1:
        console.print(f"[green]✓ Found required cookies: {', '.join(found_required)}[/green]")
        
        # Build cookie string
        cookie_parts = [f"{name}={value}" for name, value in cookies.items() if len(value) < 1000]
        cookie_string = "; ".join(cookie_parts[:20])  # Limit to first 20 cookies
        
        # Save to OpenLaoKe auth file
        auth_file = Path.home() / ".openlaoke" / "extended_web" / "qwen-web.json"
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        
        auth_data = {
            "provider_type": "qwen-web",
            "cookie": cookie_string,
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
            "saved_at": "auto-extracted",
            "browser": "firefox",
        }
        
        with open(auth_file, "w") as f:
            json.dump(auth_data, f, indent=2)
        
        console.print()
        console.print(f"[bold green]✓ Cookie saved to: {auth_file}[/bold green]")
        console.print(f"  Cookie length: {len(cookie_string)}")
        console.print()
        console.print("[dim]You can now test with: python3 test_qwen_auth.py[/dim]")
        
    else:
        console.print("[yellow]⚠ Required cookies not found[/yellow]")
        console.print(f"[dim]Found: {list(cookies.keys())[:10]}[/dim]")
        console.print("[dim]Make sure you're logged in to https://www.qianwen.com in Firefox[/dim]")


if __name__ == "__main__":
    main()
