#!/usr/bin/env python3
"""Test Qwen Web authentication and API call."""

import asyncio
import json
from pathlib import Path

from rich.console import Console

console = Console()


def extract_cookie_from_firefox() -> str:
    """Help user extract cookie from Firefox.
    
    Returns:
        Cookie string
    """
    console.print()
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]  Extract Cookie from Firefox[/bold cyan]")
    console.print("[bold cyan]════════════════════════════════════════[/bold cyan]")
    console.print()
    console.print("[bold]Please follow these steps:[/bold]")
    console.print()
    console.print("  [dim]1. Open Firefox and go to: https://www.qianwen.com[/dim]")
    console.print("  [dim]2. Make sure you're logged in[/dim]")
    console.print("  [dim]3. Press F12 to open Developer Tools[/dim]")
    console.print("  [dim]4. Go to 'Storage' tab → 'Cookies' → 'https://www.qianwen.com'[/dim]")
    console.print("  [dim]5. Find these cookies:[/dim]")
    console.print("      [cyan]_tb_token_[/cyan]")
    console.print("      [cyan]cookie2[/cyan]")
    console.print("  [dim]6. Copy the cookie values[/dim]")
    console.print()

    tb_token = console.input("  Enter [cyan]_tb_token_[/cyan] value: ")
    cookie2 = console.input("  Enter [cyan]cookie2[/cyan] value: ")

    cookie_string = f"_tb_token_={tb_token}; cookie2={cookie2}"

    return cookie_string


def save_cookie(provider_type: str, cookie: str) -> None:
    """Save cookie to auth file.
    
    Args:
        provider_type: Provider type
        cookie: Cookie string
    """
    auth_file = Path.home() / ".openlaoke" / "extended_web" / f"{provider_type}.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    auth_data = {
        "provider_type": provider_type,
        "cookie": cookie,
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
        "saved_at": asyncio.get_event_loop().time(),
        "browser": "firefox",
    }

    with open(auth_file, "w") as f:
        json.dump(auth_data, f, indent=2)

    console.print()
    console.print(f"[green]✓ Cookie saved to: {auth_file}[/green]")


async def test_qwen_api(cookie: str) -> bool:
    """Test Qwen Web API call.
    
    Args:
        cookie: Cookie string
        
    Returns:
        True if successful
    """
    console.print()
    console.print("[bold]Testing Qwen Web API...[/bold]")
    console.print()

    try:
        from openlaoke.core.extended_web.clients import QwenWebClient

        client = QwenWebClient(
            cookie=cookie,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
        )
        await client.init()

        messages = [{"role": "user", "content": "今天几号？用一句话回答"}]
        response = await client.chat_completions(
            messages=messages,
            model="qwen-turbo",
            max_tokens=200,
        )

        await client.close()

        console.print("[green]✓ API call successful![/green]")
        console.print()

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content:
            console.print("[bold]Response:[/bold]")
            console.print(f"  {content[:200]}")
        else:
            console.print("[yellow]⚠ Empty response[/yellow]")
            console.print(f"Full response: {response}")

        return True

    except Exception as e:
        console.print(f"[red]✗ API call failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    console.print()
    console.print("[bold cyan]Qwen Web Authentication Test[/bold cyan]")
    console.print()

    # Check existing auth
    auth_file = Path.home() / ".openlaoke" / "extended_web" / "qwen-web.json"

    if auth_file.exists():
        with open(auth_file) as f:
            auth_data = json.load(f)

        cookie = auth_data.get("cookie", "")

        if cookie and cookie != "placeholder_need_manual_extraction":
            console.print(f"[green]✓ Found existing cookie in {auth_file}[/green]")
            console.print(f"  Cookie length: {len(cookie)}")
            console.print()

            if await test_qwen_api(cookie):
                console.print()
                console.print("[bold green]✅ Authentication verified successfully![/bold green]")
                return
        else:
            console.print("[yellow]⚠ Existing cookie is placeholder, need to extract real cookie[/yellow]")

    # Extract cookie from Firefox
    cookie = extract_cookie_from_firefox()

    # Save cookie
    save_cookie("qwen-web", cookie)

    # Test API
    console.print()
    if await test_qwen_api(cookie):
        console.print()
        console.print("[bold green]✅ Authentication and API test successful![/bold green]")
        console.print()
        console.print("[dim]You can now use OpenLaoKe with qwen-web:[/dim]")
        console.print("  openlaoke")
        console.print()
    else:
        console.print()
        console.print("[yellow]⚠ API test failed, but cookie is saved.[/yellow]")
        console.print("[dim]You can try again later.[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
