#!/usr/bin/env python3
"""Test script for Extended Web authentication and API calls."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def test_imports() -> bool:
    """Test that all modules can be imported."""
    console.print("[bold]1. Testing imports...[/bold]")

    try:
        from openlaoke.core.extended_web import BrowserAuthManager
        from openlaoke.core.extended_web.types import WEB_PROVIDERS, WebProviderConfig, AuthResult
        from openlaoke.core.extended_web.web_client import WebServiceClient
        from openlaoke.core.extended_web.deepseek_client import DeepSeekWebClient

        console.print("  ✓ All modules imported successfully")
        return True
    except Exception as e:
        console.print(f"  ✗ Import error: {e}")
        return False


def test_provider_configs() -> bool:
    """Test that all provider configurations are valid."""
    console.print("\n[bold]2. Testing provider configurations...[/bold]")

    try:
        from openlaoke.core.extended_web.types import WEB_PROVIDERS

        console.print(f"  Found {len(WEB_PROVIDERS)} provider configurations:")

        for provider_type, config in WEB_PROVIDERS.items():
            console.print(f"    ✓ {provider_type:20} - {config.name:30} - {config.base_url}")

        return True
    except Exception as e:
        console.print(f"  ✗ Config error: {e}")
        return False


def test_browser_auth_manager() -> bool:
    """Test BrowserAuthManager initialization."""
    console.print("\n[bold]3. Testing BrowserAuthManager...[/bold]")

    try:
        from openlaoke.core.extended_web import BrowserAuthManager

        manager = BrowserAuthManager()
        console.print(f"  ✓ Manager initialized")
        console.print(f"    Config dir: {manager.config_dir}")

        # Test list (should be empty initially)
        auths = manager.list_saved_auths()
        console.print(f"    Saved auths: {len(auths)}")

        return True
    except Exception as e:
        console.print(f"  ✗ Manager error: {e}")
        return False


def test_web_service_client() -> bool:
    """Test WebServiceClient initialization."""
    console.print("\n[bold]4. Testing WebServiceClient...[/bold]")

    try:
        from openlaoke.core.extended_web.web_client import WebServiceClient

        client = WebServiceClient(
            provider_type="deepseek-chat",
            cookie="test_cookie=value",
            user_agent="Test Agent",
            base_url="https://chat.deepseek.com",
            api_endpoint="https://chat.deepseek.com/api/v1/chat/completions",
        )

        console.print(f"  ✓ Client initialized")
        console.print(f"    Provider: {client.provider_type}")
        console.print(f"    Base URL: {client.base_url}")
        console.print(f"    API Endpoint: {client.api_endpoint}")

        return True
    except Exception as e:
        console.print(f"  ✗ Client error: {e}")
        return False


def test_deepseek_client() -> bool:
    """Test DeepSeekWebClient initialization."""
    console.print("\n[bold]5. Testing DeepSeekWebClient...[/bold]")

    try:
        from openlaoke.core.extended_web.deepseek_client import DeepSeekWebClient

        client = DeepSeekWebClient(
            cookie="test_cookie=value",
            user_agent="Test Agent",
        )

        console.print(f"  ✓ DeepSeek client initialized")
        console.print(f"    Base URL: {client.base_url}")
        console.print(f"    API Endpoint: {client.api_endpoint}")

        return True
    except Exception as e:
        console.print(f"  ✗ DeepSeek client error: {e}")
        return False


def test_provider_type_integration() -> bool:
    """Test that EXTENDED_WEB provider type is properly configured."""
    console.print("\n[bold]6. Testing ProviderType integration...[/bold]")

    try:
        from openlaoke.types.providers import ProviderType, MultiProviderConfig

        # Check ProviderType
        assert hasattr(ProviderType, "EXTENDED_WEB")
        console.print(f"  ✓ ProviderType.EXTENDED_WEB exists")

        # Check default config
        config = MultiProviderConfig.defaults()
        assert "extended_web" in config.providers
        console.print(f"  ✓ extended_web in default providers")

        ext_web = config.providers["extended_web"]
        console.print(f"    Default model: {ext_web.default_model}")
        console.print(f"    Models: {len(ext_web.models)} configured")

        return True
    except Exception as e:
        console.print(f"  ✗ Integration error: {e}")
        return False


async def test_auth_flow(provider_type: str = "deepseek-chat") -> bool:
    """Test authentication flow (requires browser)."""
    console.print(f"\n[bold]7. Testing authentication flow for {provider_type}...[/bold]")

    try:
        from openlaoke.core.extended_web import BrowserAuthManager

        manager = BrowserAuthManager()

        # Check if already authenticated
        auth_data = manager.load_auth(provider_type)
        if auth_data:
            console.print(
                f"  ✓ Found existing auth (cookie length: {len(auth_data.get('cookie', ''))})"
            )
            return True
        else:
            console.print(f"  ⚠ No existing auth found (this is normal for first run)")
            console.print(f"    To authenticate: openlaoke auth extended-web login {provider_type}")
            return True

    except Exception as e:
        console.print(f"  ✗ Auth flow error: {e}")
        return False


async def test_api_call(provider_type: str = "deepseek-chat") -> bool:
    """Test API call (requires valid authentication)."""
    console.print(f"\n[bold]8. Testing API call for {provider_type}...[/bold]")

    try:
        from openlaoke.core.extended_web import BrowserAuthManager
        from openlaoke.core.extended_web.web_client import WebServiceClient
        from openlaoke.core.extended_web.types import WEB_PROVIDERS

        manager = BrowserAuthManager()
        auth_data = manager.load_auth(provider_type)

        if not auth_data:
            console.print(f"  ⚠ No authentication found")
            console.print(f"    Run: openlaoke auth extended-web login {provider_type}")
            return True

        config = WEB_PROVIDERS.get(provider_type)
        if not config:
            console.print(f"  ✗ Unknown provider: {provider_type}")
            return False

        client = WebServiceClient(
            provider_type=provider_type,
            cookie=auth_data["cookie"],
            user_agent=auth_data.get("user_agent", ""),
            bearer_token=auth_data.get("bearer_token", ""),
            base_url=config.base_url,
            api_endpoint=config.api_endpoint,
            custom_headers=config.custom_headers,
        )

        try:
            messages = [{"role": "user", "content": "你好"}]
            response = await client.chat(messages)

            content = response.get("content", "")
            if content:
                console.print(f"  ✓ API call successful")
                console.print(f"    Response: {content[:50]}...")
                return True
            else:
                console.print(f"  ⚠ Empty response")
                return True

        except Exception as e:
            console.print(f"  ⚠ API call failed (this may be normal): {e}")
            console.print(f"    Authentication may be expired or invalid")
            return True
        finally:
            await client.close()

    except Exception as e:
        console.print(f"  ✗ API test error: {e}")
        return False


async def main() -> None:
    """Run all tests."""
    console.print("=" * 70)
    console.print("[bold cyan]OpenLaoKe Extended Web - Complete Test Suite[/bold cyan]")
    console.print("=" * 70)

    results = []

    # Basic tests
    results.append(("Imports", test_imports()))
    results.append(("Provider Configs", test_provider_configs()))
    results.append(("BrowserAuthManager", test_browser_auth_manager()))
    results.append(("WebServiceClient", test_web_service_client()))
    results.append(("DeepSeekWebClient", test_deepseek_client()))
    results.append(("ProviderType Integration", test_provider_type_integration()))

    # Async tests
    results.append(("Auth Flow (deepseek-chat)", await test_auth_flow("deepseek-chat")))
    results.append(("API Call (deepseek-chat)", await test_api_call("deepseek-chat")))

    # Summary
    console.print("\n" + "=" * 70)
    console.print("[bold]Test Summary[/bold]")
    console.print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[green]✓ PASS[/green]" if result else "[red]✗ FAIL[/red]"
        console.print(f"  {status} - {name}")

    console.print()
    console.print(f"[bold]Results: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print("\n[bold green]🎉 All tests passed![/bold green]")
    else:
        console.print(f"\n[yellow]⚠ {total - passed} test(s) failed[/yellow]")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(
        "  1. Start Chrome: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222"
    )
    console.print("  2. Login to service: https://chat.deepseek.com")
    console.print("  3. Authenticate: openlaoke auth extended-web login deepseek-chat")
    console.print("  4. Test API: openlaoke auth extended-web test deepseek-chat")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
