"""Firefox browser authentication support.

Firefox uses WebDriver protocol instead of Chrome DevTools Protocol.
This module provides Firefox-specific authentication support.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from typing import Any

from rich.console import Console

_console = Console()


def get_firefox_path() -> str:
    """Get Firefox browser path."""
    import platform

    system = platform.system()

    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            "/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox",
            "/Applications/Firefox Nightly.app/Contents/MacOS/firefox",
        ]
    elif system == "Windows":
        paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ]
    else:  # Linux
        paths = [
            "/usr/bin/firefox",
            "/usr/bin/firefox-esr",
            "/snap/bin/firefox",
        ]

    for path in paths:
        if os.path.exists(path):
            return path

    return "firefox"


def launch_firefox_with_marionette(
    url: str = "",
    port: int = 2828,
    headless: bool = False,
) -> tuple[int, Any]:
    """Launch Firefox with Marionette debugging enabled.

    Args:
        url: URL to open
        port: Marionette port (default: 2828)
        headless: Run in headless mode

    Returns:
        Tuple of (port, firefox_process)
    """
    import subprocess

    firefox_path = get_firefox_path()
    user_data_dir = tempfile.mkdtemp(prefix="openlaoke-firefox-")

    cmd = [
        firefox_path,
        "-marionette",
        "-marionette-port",
        str(port),
        "-profile",
        user_data_dir,
        "-no-remote",
        "-new-instance",
    ]

    if headless:
        cmd.append("-headless")

    if url:
        cmd.extend(["-url", url])

    # Launch Firefox
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for Firefox to start
    time.sleep(3)

    if process.poll() is not None:
        raise RuntimeError("Failed to launch Firefox")

    return port, process


async def authenticate_with_firefox(
    provider_type: str,
    login_url: str,
    timeout: int = 300,
) -> dict:
    """Authenticate a provider using Firefox.

    This function:
    1. Launches Firefox with Marionette debugging
    2. Opens the login URL
    3. Waits for user to complete login
    4. Captures authentication cookies via Selenium
    5. Returns auth data

    Args:
        provider_type: Provider type (e.g., 'deepseek-chat')
        login_url: URL to open for login
        timeout: Login timeout in seconds

    Returns:
        Auth data dict with cookies and tokens
    """
    from openlaoke.core.extended_web import BrowserAuthManager
    from openlaoke.core.extended_web.types import WEB_PROVIDERS

    config = WEB_PROVIDERS.get(provider_type)
    if not config:
        raise ValueError(f"Unknown provider type: {provider_type}")

    auth_manager = BrowserAuthManager()

    # Check if already authenticated
    saved_auth = auth_manager.load_auth(provider_type)
    if saved_auth:
        _console.print(f"[green]✓ Found existing authentication for {provider_type}[/green]")
        return saved_auth

    _console.print(f"\n🦊 Launching Firefox for {config.name} authentication...")
    _console.print(f"   Login URL: {login_url}")
    _console.print()

    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
    except ImportError:
        _console.print("[red]Error:[/red] Selenium not installed")
        _console.print("\n[dim]Install with: pip install selenium[/dim]")
        raise

    # Setup Firefox options
    options = Options()
    options.add_argument("-profile")
    options.add_argument(tempfile.mkdtemp(prefix="openlaoke-firefox-"))

    # Don't use headless mode for authentication
    # options.add_argument("-headless")

    _console.print("[dim]Starting Firefox...[/dim]")

    try:
        # Launch Firefox
        service = Service()
        driver = webdriver.Firefox(service=service, options=options)

        _console.print("[green]✓ Firefox launched[/green]")
        _console.print()
        _console.print("📱 [bold]Please complete the login in the Firefox window.[/bold]")
        _console.print(f"   If not already open, navigate to: [cyan]{login_url}[/cyan]")
        _console.print()
        _console.print("[dim]Waiting for authentication...[/dim]")
        _console.print()

        # Open login URL
        driver.get(login_url)

        # Wait for login
        import time as time_module

        start_time = time_module.time()

        cookie_found = False
        while time_module.time() - start_time < timeout:
            try:
                # Check for cookies
                cookies = driver.get_cookies()

                # Convert to cookie string
                cookie_parts = []
                for cookie in cookies:
                    cookie_parts.append(f"{cookie['name']}={cookie['value']}")
                cookie_string = "; ".join(cookie_parts)

                # Check if required cookies are present
                has_required = all(
                    req_cookie in cookie_string for req_cookie in config.required_cookies
                )

                if has_required and len(cookie_string) > 50:
                    _console.print(f"\n[green]✅ Login detected for {config.name}![/green]")

                    # Get user agent
                    user_agent = driver.execute_script("return navigator.userAgent;")

                    # Try to capture bearer token
                    bearer_token = ""
                    if config.bearer_token:
                        with contextlib.suppress(Exception):
                            bearer_token = driver.execute_script(
                                "return localStorage.getItem('accessToken') || '';"
                            )

                    auth_data = {
                        "provider_type": provider_type,
                        "cookie": cookie_string,
                        "bearer_token": bearer_token,
                        "user_agent": user_agent,
                        "saved_at": time_module.strftime("%Y-%m-%dT%H:%M:%S"),
                        "browser": "firefox",
                    }

                    # Save authentication
                    auth_manager.save_auth(provider_type, auth_data)

                    _console.print("[green]✓ Authentication saved![/green]")
                    _console.print(f"  Cookie length: {len(cookie_string)}")
                    _console.print(f"  Auth file: {auth_manager._get_auth_file(provider_type)}")

                    cookie_found = True
                    break

            except Exception:
                # Ignore transient errors
                pass

            time_module.sleep(2)

        if not cookie_found:
            driver.quit()
            raise TimeoutError(f"Login timeout after {timeout} seconds")

        # Close Firefox
        driver.quit()

        return auth_data

    except Exception as e:
        _console.print(f"\n[red]✗ Error:[/red] {e}")
        _console.print("\n[dim]Make sure Firefox is installed.[/dim]")
        _console.print("[dim]Install with: brew install --cask firefox (macOS)[/dim]")
        raise
