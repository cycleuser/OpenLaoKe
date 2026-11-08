"""Browser tool - optional, and only when selenium is actually installed.

This is the one capability that genuinely needs a heavy third-party dependency
(a real browser driver), so it is never part of the default tool list. Two things
must both be true for it to register: `enable_browser` in the config, and a
working `selenium` import. If either is missing the tool simply does not appear,
rather than appearing and failing on every call.

Actions are the ones a coding agent actually needs: open a page, read its text,
list links, and run JavaScript to fetch something the static HTML hides.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

MAX_TEXT = 20000
DEFAULT_TIMEOUT = 30.0


def selenium_available() -> bool:
    try:
        import selenium  # noqa: F401
    except Exception:
        return False
    return True


class BrowserInput(BaseModel):
    action: str = Field(default="open", description="open | text | links | script")
    url: str = Field(default="", description="http(s) URL for action=open")
    session: str = Field(
        default="default", description="Session name, so pages persist between calls"
    )
    script: str = Field(default="", description="JavaScript to run for action=script")


class BrowserTool(Tool):
    """Drive a headless browser (optional extension)."""

    name = "Browser"
    description = (
        "Drive a headless browser: open a URL, read the rendered text, list links, or run "
        "JavaScript. Only registered when selenium is installed and enable_browser is set. "
        "For static pages WebFetch is cheaper; use this when the content needs JavaScript."
    )
    input_schema = BrowserInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False

    def __init__(self) -> None:
        self._drivers: dict[str, Any] = {}

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = str(kwargs.get("action") or "open").strip().lower()
        name = str(kwargs.get("session") or "default")
        url = str(kwargs.get("url") or "").strip()

        if not selenium_available():
            return self._error(
                ctx,
                "Error: selenium is not installed. Install it and a browser driver, "
                "or use WebFetch for static pages.",
            )

        if action == "open" and not url.startswith(("http://", "https://")):
            return self._error(ctx, "Error: url must start with http:// or https://")

        try:
            driver = await self._driver(name)
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            return self._error(ctx, f"Error: could not start a browser: {exc}")

        if action == "open":
            try:
                await asyncio.to_thread(driver.get, url)
            except Exception as exc:  # noqa: BLE001
                return self._error(ctx, f"Error: could not open {url}: {exc}")
            return self._result(
                ctx, f"Opened {url}\nTitle: {await asyncio.to_thread(driver.title)}"
            )

        if action == "text":
            body = await asyncio.to_thread(lambda: driver.find_element("tag name", "body").text)
            if len(body) > MAX_TEXT:
                body = body[:MAX_TEXT] + "\n... (truncated)"
            return self._result(ctx, body or "(no text)")

        if action == "links":
            elements = await asyncio.to_thread(lambda: driver.find_elements("tag name", "a"))
            rows = []
            for element in elements[:200]:
                rows.append(f"{element.text.strip()[:60]} -> {element.get_attribute('href')}")
            return self._result(ctx, "\n".join(rows) or "No links on the page.")

        if action == "script":
            script = str(kwargs.get("script") or "")
            if not script.strip():
                return self._error(ctx, "Error: script is required for action=script")
            try:
                value = await asyncio.to_thread(driver.execute_script, script)
            except Exception as exc:  # noqa: BLE001
                return self._error(ctx, f"Error: script failed: {exc}")
            return self._result(ctx, str(value)[:MAX_TEXT])

        return self._error(ctx, "Error: action must be open, text, links or script")

    async def _driver(self, name: str) -> Any:
        existing = self._drivers.get(name)
        if existing is not None:
            return existing
        from selenium import webdriver

        driver = await asyncio.to_thread(webdriver.Chrome)
        await asyncio.to_thread(driver.set_page_load_timeout, DEFAULT_TIMEOUT)
        self._drivers[name] = driver
        return driver

    async def close(self) -> None:
        for driver in list(self._drivers.values()):
            with contextlib.suppress(Exception):
                await asyncio.to_thread(driver.quit)
        self._drivers.clear()

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(BrowserTool())
