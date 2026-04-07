"""Browser-based authentication manager for extended web providers.

This module manages browser authentication for various Web AI services.
It uses Playwright to connect to existing Chrome/Edge browsers and capture
authentication cookies and tokens.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page


class BrowserAuthManager:
    """Manages browser-based authentication for web AI providers."""

    def __init__(self, config_dir: str | None = None) -> None:
        """Initialize the browser auth manager.

        Args:
            config_dir: Directory to store auth credentials. Defaults to ~/.openlaoke/extended_web/
        """
        if config_dir is None:
            config_dir = os.path.expanduser("~/.openlaoke/extended_web")

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def _get_auth_file(self, provider_type: str) -> Path:
        """Get the path to the auth file for a provider."""
        return self.config_dir / f"{provider_type}.json"

    def load_auth(self, provider_type: str) -> dict | None:
        """Load saved authentication for a provider.

        Args:
            provider_type: The provider type (e.g., 'deepseek-chat')

        Returns:
            Auth data dict or None if not found
        """
        auth_file = self._get_auth_file(provider_type)
        if not auth_file.exists():
            return None

        try:
            with open(auth_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def save_auth(self, provider_type: str, auth_data: dict) -> None:
        """Save authentication for a provider.

        Args:
            provider_type: The provider type
            auth_data: Authentication data to save
        """
        auth_file = self._get_auth_file(provider_type)
        with open(auth_file, "w", encoding="utf-8") as f:
            json.dump(auth_data, f, indent=2, ensure_ascii=False)

        # Set restrictive permissions (only owner can read/write)
        os.chmod(auth_file, 0o600)

    def delete_auth(self, provider_type: str) -> bool:
        """Delete saved authentication for a provider.

        Args:
            provider_type: The provider type

        Returns:
            True if deleted, False if file didn't exist
        """
        auth_file = self._get_auth_file(provider_type)
        if auth_file.exists():
            auth_file.unlink()
            return True
        return False

    def list_saved_auths(self) -> list[str]:
        """List all providers with saved authentication.

        Returns:
            List of provider types with saved auth
        """
        auths = []
        for auth_file in self.config_dir.glob("*.json"):
            provider_type = auth_file.stem
            auths.append(provider_type)
        return auths

    async def connect_to_browser(self, cdp_port: int = 9222) -> BrowserContext:
        """Connect to an existing Chrome/Edge browser via CDP.

        Args:
            cdp_port: Chrome DevTools Protocol port (default: 9222)

        Returns:
            BrowserContext for the connected browser
        """
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()

        # Try to connect to existing browser
        cdp_url = f"http://127.0.0.1:{cdp_port}"

        try:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            self._browser = browser
            contexts = browser.contexts
            if contexts:
                self._context = contexts[0]
            else:
                self._context = await browser.new_context()
            return self._context
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to browser at {cdp_url}. "
                f"Make sure Chrome is running with remote debugging enabled:\n"
                f"  Chrome: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
                f"--remote-debugging-port={cdp_port}\n"
                f"  Edge: /Applications/Microsoft\\ Edge.app/Contents/MacOS/Microsoft\\ Edge "
                f"--remote-debugging-port={cdp_port}"
            ) from e

    async def capture_cookies(
        self,
        context: BrowserContext,
        domains: list[str],
    ) -> str:
        """Capture cookies for specified domains.

        Args:
            context: Browser context
            domains: List of domains to capture cookies from

        Returns:
            Cookie string in format "name1=value1; name2=value2; ..."
        """
        cookies = await context.cookies(domains)
        cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        return cookie_string

    async def wait_for_login(
        self,
        page: Page,
        provider_type: str,
        timeout: int = 300,
    ) -> dict:
        """Wait for user to complete login and capture credentials.

        Args:
            page: Browser page
            provider_type: Provider type
            timeout: Timeout in seconds

        Returns:
            Auth data dict with cookies and tokens
        """
        from .types import WEB_PROVIDERS

        config = WEB_PROVIDERS.get(provider_type)
        if not config:
            raise ValueError(f"Unknown provider type: {provider_type}")

        print(f"\n📱 Please log in to {config.name} in the browser window.")
        print(f"   If already logged in, the page should be detected automatically.")
        print(f"   Waiting for login... (timeout: {timeout}s)")

        # Navigate to login URL
        await page.goto(config.login_url, wait_until="domcontentloaded")

        # Poll for authentication
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check for cookies
            cookies = await self.capture_cookies(page.context, config.cookie_domains)

            # Check if required cookies are present
            has_required = all(req_cookie in cookies for req_cookie in config.required_cookies)

            if has_required:
                print(f"\n✅ Login detected for {config.name}!")

                # Get user agent
                user_agent = await page.evaluate("navigator.userAgent")

                # Try to capture bearer token if needed
                bearer_token = ""
                if config.bearer_token:
                    bearer_token = await self._capture_bearer_token(page, config.api_endpoint)

                return {
                    "cookie": cookies,
                    "bearer_token": bearer_token,
                    "user_agent": user_agent,
                    "provider_type": provider_type,
                }

            await asyncio.sleep(2)

        raise TimeoutError(f"Login timeout for {config.name}. Please try again.")

    async def _capture_bearer_token(self, page: Page, api_endpoint: str) -> str:
        """Try to capture bearer token from page or requests.

        Args:
            page: Browser page
            api_endpoint: API endpoint URL

        Returns:
            Bearer token if found, empty string otherwise
        """
        # Try to get from localStorage or sessionStorage
        try:
            token = await page.evaluate(
                "() => localStorage.getItem('accessToken') || sessionStorage.getItem('accessToken')"
            )
            if token:
                return token
        except Exception:
            pass

        # Try to get from page context
        try:
            token = await page.evaluate("() => window.__TOKEN__ || window.token || ''")
            if token:
                return token
        except Exception:
            pass

        return ""

    async def authenticate_provider(
        self,
        provider_type: str,
        cdp_port: int = 9222,
        timeout: int = 300,
    ) -> dict:
        """Authenticate a provider via browser.

        Args:
            provider_type: Provider type to authenticate
            cdp_port: Chrome DevTools Protocol port
            timeout: Login timeout in seconds

        Returns:
            Auth data dict
        """
        import asyncio
        from .types import WEB_PROVIDERS

        # Check if already authenticated
        saved_auth = self.load_auth(provider_type)
        if saved_auth:
            print(f"✅ Found saved authentication for {provider_type}")
            return saved_auth

        # Connect to browser
        context = await self.connect_to_browser(cdp_port)

        # Check if user is already logged in (existing cookies)
        config = WEB_PROVIDERS.get(provider_type)
        if config:
            cookies = await self.capture_cookies(context, config.cookie_domains)
            has_required = all(req_cookie in cookies for req_cookie in config.required_cookies)

            if has_required:
                print(f"✅ Found existing session for {config.name}!")
                user_agent = (
                    await context.pages[0].evaluate("navigator.userAgent") if context.pages else ""
                )
                auth_data = {
                    "cookie": cookies,
                    "bearer_token": "",
                    "user_agent": user_agent,
                    "provider_type": provider_type,
                }
                self.save_auth(provider_type, auth_data)
                return auth_data

        # Create new page for login
        page = await context.new_page()

        try:
            # Wait for login
            auth_data = await self.wait_for_login(page, provider_type, timeout)

            # Save authentication
            self.save_auth(provider_type, auth_data)

            print(f"\n✅ Authentication saved for {provider_type}")
            print(f"   Auth file: {self._get_auth_file(provider_type)}")

            return auth_data

        finally:
            await page.close()

    def get_auth_header(self, provider_type: str) -> dict[str, str]:
        """Get authentication headers for a provider.

        Args:
            provider_type: Provider type

        Returns:
            Headers dict with cookies and tokens
        """
        from .types import WEB_PROVIDERS

        auth_data = self.load_auth(provider_type)
        if not auth_data:
            raise ValueError(
                f"No authentication found for {provider_type}. "
                f"Run: openlaoke auth extended-web {provider_type}"
            )

        config = WEB_PROVIDERS.get(provider_type)
        if not config:
            raise ValueError(f"Unknown provider type: {provider_type}")

        headers = {
            "Cookie": auth_data["cookie"],
            "User-Agent": auth_data.get("user_agent", ""),
            **config.custom_headers,
        }

        if auth_data.get("bearer_token"):
            headers["Authorization"] = f"Bearer {auth_data['bearer_token']}"

        return headers
