"""Web browser tool - browser automation using Playwright."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class WebBrowserInput(BaseModel):
    action: Literal["navigate", "click", "type", "screenshot", "wait", "evaluate", "close"] = Field(
        description="Browser action to perform"
    )
    url: str | None = Field(default=None, description="URL to navigate to")
    selector: str | None = Field(default=None, description="CSS selector for element")
    text: str | None = Field(default=None, description="Text to type or value to set")
    wait_time: float | None = Field(default=None, description="Time to wait in seconds")
    script: str | None = Field(default=None, description="JavaScript to evaluate")
    screenshot_path: str | None = Field(default=None, description="Path to save screenshot")
    headless: bool = Field(default=True, description="Run browser in headless mode")


class WebBrowserTool(Tool):
    """Browser automation using Playwright."""

    name = "WebBrowser"
    description = (
        "Automate web browser interactions using Playwright. "
        "Supports navigation, clicking, typing, screenshots, JavaScript execution, and more. "
        "Useful for testing, web scraping, and browser automation tasks."
    )
    input_schema = WebBrowserInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False
    requires_approval = True

    def __init__(self) -> None:
        super().__init__()
        self._browser: Any = None
        self._page: Any = None
        self._playwright: Any = None

    async def _ensure_browser(self, headless: bool = True) -> tuple[Any, Any]:
        """Ensure browser instance is running."""
        if self._page is None:
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=headless)
                self._page = await self._browser.new_page()
            except ImportError:
                raise RuntimeError(
                    "Playwright not installed. Install with: pip install playwright && playwright install chromium"
                ) from None
        return self._browser, self._page

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        try:
            if action == "navigate":
                url = kwargs.get("url")
                if not url:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: url is required for navigate action",
                        is_error=True,
                    )

                headless = kwargs.get("headless", True)
                _, page = await self._ensure_browser(headless)
                await page.goto(url)
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Navigated to {url}",
                    is_error=False,
                )

            elif action == "click":
                selector = kwargs.get("selector")
                if not selector:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: selector is required for click action",
                        is_error=True,
                    )

                if self._page is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: No active page. Navigate to a URL first.",
                        is_error=True,
                    )

                await self._page.click(selector)
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Clicked element: {selector}",
                    is_error=False,
                )

            elif action == "type":
                selector = kwargs.get("selector")
                text = kwargs.get("text")
                if not selector or text is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: selector and text are required for type action",
                        is_error=True,
                    )

                if self._page is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: No active page. Navigate to a URL first.",
                        is_error=True,
                    )

                await self._page.fill(selector, text)
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Typed text into: {selector}",
                    is_error=False,
                )

            elif action == "screenshot":
                if self._page is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: No active page. Navigate to a URL first.",
                        is_error=True,
                    )

                screenshot_path = kwargs.get("screenshot_path", "screenshot.png")
                await self._page.screenshot(path=screenshot_path)
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Screenshot saved to {screenshot_path}",
                    is_error=False,
                )

            elif action == "wait":
                wait_time = kwargs.get("wait_time", 1.0)
                import asyncio

                await asyncio.sleep(wait_time)
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Waited {wait_time} seconds",
                    is_error=False,
                )

            elif action == "evaluate":
                script = kwargs.get("script")
                if not script:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: script is required for evaluate action",
                        is_error=True,
                    )

                if self._page is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: No active page. Navigate to a URL first.",
                        is_error=True,
                    )

                result = await self._page.evaluate(script)
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=str(result),
                    is_error=False,
                )

            elif action == "close":
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                    self._page = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content="Browser closed",
                    is_error=False,
                )

            else:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Unknown action: {action}",
                    is_error=True,
                )

        except ImportError as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: {e}. Install with: pip install playwright && playwright install chromium",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error during browser operation: {e}",
                is_error=True,
            )

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


def register(registry: ToolRegistry) -> None:
    registry.register(WebBrowserTool())
