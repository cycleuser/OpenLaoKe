"""Auto browser launcher for extended web authentication.

This module automatically launches the system's default browser
with remote debugging enabled, making authentication seamless.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import platform
import socket
import subprocess
import tempfile
import time
from typing import Literal, cast

from rich.console import Console

console = Console()


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_available_port(start_port: int = 9222, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    raise OSError(f"No available port found in range {start_port}-{start_port + max_attempts}")


BrowserType = Literal["chrome", "firefox", "edge", "safari"]


def get_default_browser() -> tuple[str, BrowserType]:
    """Get the system's default browser.

    Returns:
        Tuple of (browser_path, browser_type)
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        # Try common browsers in order of preference
        browsers = [
            ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "chrome"),
            ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "edge"),
            ("/Applications/Firefox.app/Contents/MacOS/firefox", "firefox"),
            ("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "chrome"),
            ("/Applications/Safari.app/Contents/MacOS/Safari", "safari"),
        ]

        for browser_path, browser_type in browsers:
            if os.path.exists(browser_path):
                return browser_path, cast(BrowserType, browser_type)

        # Fallback to Chrome
        return browsers[0][0], cast(BrowserType, browsers[0][1])

    elif system == "Windows":
        browsers = [
            (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "chrome"),
            (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "chrome"),
            (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "edge"),
            (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "edge"),
            (r"C:\Program Files\Mozilla Firefox\firefox.exe", "firefox"),
        ]

        for browser_path, browser_type in browsers:
            if os.path.exists(browser_path):
                return browser_path, cast(BrowserType, browser_type)

        # Try to get from registry
        try:
            import winreg

            with winreg.OpenKey(  # type: ignore[attr-defined]
                winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
            ) as key:
                prog_id = winreg.QueryValueEx(key, "ProgId")[0]  # type: ignore[attr-defined]
                if "Chrome" in prog_id:
                    return browsers[0][0], cast(BrowserType, browsers[0][1])
                elif "Edge" in prog_id:
                    return browsers[2][0], cast(BrowserType, browsers[2][1])
                elif "Firefox" in prog_id:
                    return browsers[4][0], cast(BrowserType, browsers[4][1])
        except Exception:
            pass

        return browsers[0][0], cast(BrowserType, browsers[0][1])

    else:  # Linux
        # Try common environment variables
        browser_env = os.environ.get("BROWSER")
        if browser_env:
            if "firefox" in browser_env.lower():
                return browser_env, cast(BrowserType, "firefox")
            return browser_env, cast(BrowserType, "chrome")

        # Try common browsers
        browsers = [
            ("google-chrome", "chrome"),
            ("chromium", "chrome"),
            ("firefox", "firefox"),
            ("chromium-browser", "chrome"),
            ("microsoft-edge", "edge"),
            ("google-chrome-stable", "chrome"),
        ]

        for browser, browser_type in browsers:
            try:
                result = subprocess.run(
                    ["which", browser],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return result.stdout.strip(), cast(BrowserType, browser_type)
            except Exception:
                pass

        return "google-chrome", "chrome"


def launch_browser_with_debug(
    url: str = "",
    port: int = 0,
    user_data_dir: str = "",
    headless: bool = False,
) -> tuple[int, subprocess.Popen, BrowserType]:
    """Launch browser with remote debugging enabled.

    Args:
        url: URL to open (optional)
        port: Debug port (0 for auto-detect)
        user_data_dir: User data directory (optional)
        headless: Run in headless mode

    Returns:
        Tuple of (port, process, browser_type)
    """
    browser_path, browser_type = get_default_browser()

    # Find available port
    if port == 0:
        port = find_available_port()

    # Create temp user data dir if not specified
    if not user_data_dir:
        user_data_dir = tempfile.mkdtemp(prefix="openlaoke-browser-")

    # Build command based on browser type
    if browser_type == "firefox":
        # Firefox uses different flags
        cmd = [
            browser_path,
            "-remote-debugging-port",
            str(port),
            "-profile",
            user_data_dir,
            "-no-remote",
            "-new-instance",
        ]

        if headless:
            cmd.append("-headless")

        if url:
            cmd.append(url)

    else:
        # Chrome/Edge/Safari (Chrome-based)
        cmd = [
            browser_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
        ]

        if headless:
            cmd.append("--headless=new")

        if url:
            cmd.append(url)

    # Launch browser
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for browser to start (Firefox needs more time)
    wait_time = 3 if browser_type == "firefox" else 2
    time.sleep(wait_time)

    # Verify browser is running
    if process.poll() is not None:
        raise RuntimeError("Failed to launch browser")

    return port, process, browser_type


class AutoBrowserManager:
    """Manages automatic browser launching and authentication."""

    def __init__(self, port: int = 0) -> None:
        """Initialize the auto browser manager.

        Args:
            port: Debug port (0 for auto-detect)
        """
        self.port = port
        self._process: subprocess.Popen | None = None
        self._user_data_dir: str = ""

    def launch(
        self,
        url: str = "",
        headless: bool = False,
        wait_seconds: int = 3,
    ) -> int:
        """Launch browser with remote debugging.

        Args:
            url: URL to open
            headless: Run in headless mode
            wait_seconds: Seconds to wait for browser to start

        Returns:
            Debug port number
        """
        if self._process is not None:
            # Browser already running
            return self.port

        self.port, self._process, _browser_type = launch_browser_with_debug(
            url=url,
            port=self.port,
            headless=headless,
        )

        # Wait for browser to be ready
        time.sleep(wait_seconds)

        return self.port

    def close(self) -> None:
        """Close the browser."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def __enter__(self) -> AutoBrowserManager:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


async def authenticate_with_auto_browser(
    provider_type: str,
    login_url: str,
    timeout: int = 300,
    browser_type: BrowserType | None = None,
) -> dict:
    """Authenticate a provider by automatically launching browser.

    This function:
    1. Launches the system's default browser with remote debugging
    2. Opens the login URL
    3. Waits for user to complete login
    4. Captures authentication cookies
    5. Closes the browser

    Args:
        provider_type: Provider type (e.g., 'deepseek-chat')
        login_url: URL to open for login
        timeout: Login timeout in seconds
        browser_type: Browser type to use (None for auto-detect)

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
        console.print(f"[green]✓ Found existing authentication for {provider_type}[/green]")
        return saved_auth

    # Detect browser type if not specified
    if browser_type is None:
        _, browser_type = get_default_browser()

    console.print(f"\n🌐 Launching browser for {config.name} authentication...")
    console.print(f"   Login URL: {login_url}")
    console.print()

    # Firefox uses different authentication method
    if browser_type == "firefox":
        from openlaoke.core.extended_web.firefox_auth import authenticate_with_firefox

        return await authenticate_with_firefox(provider_type, login_url, timeout)

    # Chrome/Edge/Safari use Playwright
    with AutoBrowserManager() as browser_mgr:
        # Launch browser
        port = browser_mgr.launch(url=login_url, headless=False)

        console.print(f"[green]✓ Browser launched on port {port}[/green]")
        console.print()
        console.print("📱 [bold]Please complete the login in the browser window.[/bold]")
        console.print("   The browser should have opened automatically.")
        console.print(f"   If not, open: [cyan]{login_url}[/cyan]")
        console.print()
        console.print("[dim]Waiting for authentication...[/dim]")
        console.print()

        # Connect to browser and wait for login
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

        try:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            pages = context.pages

            if not pages:
                page = await context.new_page()
                await page.goto(login_url)
            else:
                page = pages[0]

            # Wait for login
            import time as time_module

            start_time = time_module.time()

            while time_module.time() - start_time < timeout:
                # Check for cookies
                cookies = await context.cookies(config.cookie_domains)
                cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

                # Check if required cookies are present
                has_required = all(
                    req_cookie in cookie_string for req_cookie in config.required_cookies
                )

                if has_required:
                    console.print(f"\n[green]✅ Login detected for {config.name}![/green]")

                    # Get user agent
                    user_agent = await page.evaluate("navigator.userAgent")

                    # Try to capture bearer token
                    bearer_token = ""
                    if config.bearer_token:
                        with contextlib.suppress(Exception):
                            bearer_token = await page.evaluate(
                                "() => localStorage.getItem('accessToken') || ''"
                            )

                    auth_data = {
                        "provider_type": provider_type,
                        "cookie": cookie_string,
                        "bearer_token": bearer_token,
                        "user_agent": user_agent,
                        "saved_at": time_module.strftime("%Y-%m-%dT%H:%M:%S"),
                        "browser": browser_type,
                    }

                    # Save authentication
                    auth_manager.save_auth(provider_type, auth_data)

                    console.print("[green]✓ Authentication saved![/green]")
                    console.print(f"  Cookie length: {len(cookie_string)}")
                    console.print(f"  Auth file: {auth_manager._get_auth_file(provider_type)}")

                    return auth_data

                await asyncio.sleep(2)

            raise TimeoutError(f"Login timeout after {timeout} seconds")

        finally:
            await browser.close()
            await playwright.stop()
