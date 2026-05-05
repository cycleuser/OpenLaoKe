#!/usr/bin/env python3
"""Test all Extended Web providers with auto cookie extraction."""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()


def get_firefox_profile_path():
    """Find Firefox profile path."""
    profiles_path = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"

    if not profiles_path.exists():
        return None

    for profile_dir in profiles_path.iterdir():
        if profile_dir.is_dir() and "default" in profile_dir.name:
            return profile_dir

    return None


def extract_cookies(profile_path: Path, domain: str) -> str:
    """Extract cookies for a domain from Firefox."""
    cookies_file = profile_path / "cookies.sqlite"

    if not cookies_file.exists():
        return ""

    temp_cookie = tempfile.mktemp(suffix=".sqlite")
    import shutil
    shutil.copy2(cookies_file, temp_cookie)

    try:
        conn = sqlite3.connect(temp_cookie)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE ?",
            (f"%{domain}%",)
        )

        cookies = [f"{name}={value}" for name, value in cursor.fetchall()]
        conn.close()

        return "; ".join(cookies)

    finally:
        import os
        os.unlink(temp_cookie)


def save_auth(provider_type: str, cookie: str) -> None:
    """Save authentication."""
    auth_file = Path.home() / ".openlaoke" / "extended_web" / f"{provider_type}.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    auth_data = {
        "provider_type": provider_type,
        "cookie": cookie,
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
        "saved_at": "auto-extracted",
        "browser": "firefox",
    }

    with open(auth_file, "w") as f:
        json.dump(auth_data, f, indent=2)


async def test_deepseek(cookie: str):
    """Test DeepSeek."""
    console.print("\n[bold cyan]Testing DeepSeek...[/bold cyan]")

    try:
        from openlaoke.core.extended_web.clients import DeepSeekWebClient

        client = DeepSeekWebClient(cookie=cookie)
        await client.init()

        messages = [{"role": "user", "content": "hi"}]
        response = await client.chat_completions(messages)

        await client.close()

        content = response.get("content", "")
        if content:
            console.print("[green]✓ DeepSeek works![/green]")
            console.print(f"  Response: {content[:100]}...")
            return True
        else:
            console.print("[yellow]⚠ Empty response[/yellow]")
            return False

    except Exception as e:
        console.print(f"[red]✗ DeepSeek failed: {e}[/red]")
        return False


async def test_qwen(cookie: str):
    """Test Qwen."""
    console.print("\n[bold cyan]Testing Qwen...[/bold cyan]")

    try:
        from openlaoke.core.extended_web.clients import QwenWebClient

        client = QwenWebClient(cookie=cookie)
        await client.init()

        messages = [{"role": "user", "content": "hi"}]
        response = await client.chat_completions(messages)

        await client.close()

        content = response.get("content", "")
        if content:
            console.print("[green]✓ Qwen works![/green]")
            console.print(f"  Response: {content[:100]}...")
            return True
        else:
            console.print("[yellow]⚠ Empty response[/yellow]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Qwen failed: {e}[/red]")
        return False


async def test_glm(cookie: str):
    """Test GLM."""
    console.print("\n[bold cyan]Testing GLM...[/bold cyan]")

    try:
        from openlaoke.core.extended_web.clients import GLMWebClient

        client = GLMWebClient(cookie=cookie)
        await client.init()

        messages = [{"role": "user", "content": "hi"}]
        response = await client.chat_completions(messages)

        await client.close()

        content = response.get("content", "")
        if content:
            console.print("[green]✓ GLM works![/green]")
            console.print(f"  Response: {content[:100]}...")
            return True
        else:
            console.print("[yellow]⚠ Empty response[/yellow]")
            return False

    except Exception as e:
        console.print(f"[red]✗ GLM failed: {e}[/red]")
        return False


async def main():
    """Main test function."""
    console.print()
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]  Extended Web Auto Test[/bold cyan]")
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")

    # Get Firefox profile
    profile_path = get_firefox_profile_path()

    if not profile_path:
        console.print("[red]✗ Firefox profile not found[/red]")
        return

    console.print(f"[green]✓ Found Firefox profile: {profile_path}[/green]")

    # Extract cookies
    console.print()
    console.print("[bold]Extracting cookies...[/bold]")

    deepseek_cookie = extract_cookies(profile_path, "deepseek.com")
    qwen_cookie = extract_cookies(profile_path, "qwen.ai")
    glm_cookie = extract_cookies(profile_path, "chatglm.cn")

    # Save cookies
    if deepseek_cookie:
        save_auth("deepseek-chat", deepseek_cookie)
        console.print(f"[green]✓ DeepSeek cookie extracted ({len(deepseek_cookie)} chars)[/green]")
    else:
        console.print("[yellow]⚠ DeepSeek cookie not found[/yellow]")

    if qwen_cookie:
        save_auth("qwen-web", qwen_cookie)
        console.print(f"[green]✓ Qwen cookie extracted ({len(qwen_cookie)} chars)[/green]")
    else:
        console.print("[yellow]⚠ Qwen cookie not found[/yellow]")

    if glm_cookie:
        save_auth("glm-web", glm_cookie)
        console.print(f"[green]✓ GLM cookie extracted ({len(glm_cookie)} chars)[/green]")
    else:
        console.print("[yellow]⚠ GLM cookie not found[/yellow]")

    # Test providers
    console.print()
    console.print("[bold]Testing providers...[/bold]")

    results = []

    if deepseek_cookie:
        results.append(("DeepSeek", await test_deepseek(deepseek_cookie)))
    else:
        console.print("\n[yellow]⚠ Skipping DeepSeek (no cookie)[/yellow]")

    if qwen_cookie:
        results.append(("Qwen", await test_qwen(qwen_cookie)))
    else:
        console.print("\n[yellow]⚠ Skipping Qwen (no cookie)[/yellow]")

    if glm_cookie:
        results.append(("GLM", await test_glm(glm_cookie)))
    else:
        console.print("\n[yellow]⚠ Skipping GLM (no cookie)[/yellow]")

    # Summary
    console.print()
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")
    console.print("[bold]Test Summary[/bold]")
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")

    for name, result in results:
        status = "[green]✓ PASS[/green]" if result else "[red]✗ FAIL[/red]"
        console.print(f"  {status} - {name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    console.print()
    console.print(f"[bold]Results: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print("\n[bold green]🎉 All tests passed![/bold green]")
        console.print("\n[dim]You can now use:[/dim]")
        console.print("  openlaoke --provider extended-web --model deepseek-chat")
        console.print("  openlaoke --provider extended-web --model qwen-web")
        console.print("  openlaoke --provider extended-web --model glm-web")
    else:
        console.print("\n[yellow]⚠ Some tests failed[/yellow]")


if __name__ == "__main__":
    asyncio.run(main())
