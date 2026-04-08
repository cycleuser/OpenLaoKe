#!/usr/bin/env python3
"""Extract GLM cookie from Firefox."""

import json
import sqlite3
import tempfile
from pathlib import Path
from rich.console import Console

console = Console()


def get_firefox_profile_path() -> Path | None:
    """Find Firefox profile path."""
    profiles_path = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    
    if not profiles_path.exists():
        return None
    
    for profile_dir in profiles_path.iterdir():
        if profile_dir.is_dir() and "default" in profile_dir.name:
            return profile_dir
    
    profiles = list(profiles_path.iterdir())
    if profiles:
        return profiles[0]
    
    return None


def extract_glm_cookies(profile_path: Path) -> str | None:
    """Extract GLM cookies from Firefox."""
    cookies_file = profile_path / "cookies.sqlite"
    
    if not cookies_file.exists():
        return None
    
    # Copy to temp file
    temp_cookie = tempfile.mktemp(suffix=".sqlite")
    import shutil
    shutil.copy2(cookies_file, temp_cookie)
    
    try:
        conn = sqlite3.connect(temp_cookie)
        cursor = conn.cursor()
        
        # Search for GLM cookies
        cursor.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE '%chatglm%' OR host LIKE '%zhipu%'"
        )
        
        cookies = {}
        for name, value in cursor.fetchall():
            cookies[name] = value
        
        conn.close()
        
        if cookies:
            cookie_parts = [f"{name}={value}" for name, value in cookies.items()]
            return "; ".join(cookie_parts)
        
        return None
        
    finally:
        import os
        os.unlink(temp_cookie)


def main():
    """Main entry point."""
    console.print()
    console.print("[bold cyan]GLM Cookie Extractor[/bold cyan]")
    console.print()
    
    # Make sure user is logged in
    console.print("[bold]IMPORTANT:[/bold]")
    console.print("  1. Make sure you're logged in to https://chatglm.cn in Firefox")
    console.print("  2. If not, please login first, then run this script again")
    console.print()
    
    if not console.input("  Are you logged in to GLM in Firefox? [y/n]: ").lower().startswith('y'):
        console.print("[yellow]Please login first, then run this script again.[/yellow]")
        return
    
    # Find Firefox profile
    profile_path = get_firefox_profile_path()
    
    if not profile_path:
        console.print("[red]✗ Firefox profile not found[/red]")
        return
    
    console.print(f"[green]✓ Found Firefox profile: {profile_path}[/green]")
    
    # Extract GLM cookies
    console.print()
    console.print("[bold]Extracting GLM cookies...[/bold]")
    
    cookie_string = extract_glm_cookies(profile_path)
    
    if not cookie_string:
        console.print("[red]✗ No GLM cookies found[/red]")
        console.print("[dim]Make sure you're logged in to https://chatglm.cn in Firefox[/dim]")
        return
    
    console.print(f"[green]✓ Found GLM cookies![/green]")
    console.print(f"  Cookie length: {len(cookie_string)}")
    
    # Save to auth file
    auth_file = Path.home() / ".openlaoke" / "extended_web" / "glm-web.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    
    auth_data = {
        "provider_type": "glm-web",
        "cookie": cookie_string,
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
        "saved_at": "auto-extracted",
        "browser": "firefox",
    }
    
    with open(auth_file, "w") as f:
        json.dump(auth_data, f, indent=2)
    
    console.print()
    console.print(f"[bold green]✓ Cookie saved to: {auth_file}[/bold green]")
    console.print()
    console.print("[dim]You can now use GLM Web in OpenLaoKe:[/dim]")
    console.print("  openlaoke --provider extended-web --model glm-web")


if __name__ == "__main__":
    main()
