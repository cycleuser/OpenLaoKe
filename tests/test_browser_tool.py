"""Tests for the optional Browser tool, driven by a fake selenium driver.

The tool is only registered when selenium is installed, so the tests fake the
import: a stub driver records what the tool asked it to do. The point is the tool
contract (actions, error messages, session reuse, truncation), not Selenium.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from openlaoke.core.tool import ToolContext, ToolRegistry
from openlaoke.tools import browser_tool
from openlaoke.tools.browser_tool import BrowserTool, selenium_available


class FakeElement:
    def __init__(self, text: str, href: str | None = None) -> None:
        self.text = text
        self._href = href

    def get_attribute(self, name: str) -> str | None:
        return self._href if name == "href" else None


class FakeDriver:
    def __init__(self, *, fail_get: bool = False, fail_script: bool = False) -> None:
        self.title = "Example Domain"
        self.text = "Rendered body text"
        self.links = [FakeElement("Docs", "https://example.com/docs"), FakeElement("", None)]
        self.opened: list[str] = []
        self.scripts: list[str] = []
        self.timeouts: list[float] = []
        self.quit_called = False
        self._fail_get = fail_get
        self._fail_script = fail_script
        self.script_result: Any = "scripted"

    def get(self, url: str) -> None:
        if self._fail_get:
            raise RuntimeError("ERR_NAME_NOT_RESOLVED")
        self.opened.append(url)

    def set_page_load_timeout(self, seconds: float) -> None:
        self.timeouts.append(seconds)

    def find_element(self, by: str, value: str) -> FakeElement:
        assert (by, value) == ("tag name", "body")
        return FakeElement(self.text)

    def find_elements(self, by: str, value: str) -> list[FakeElement]:
        assert (by, value) == ("tag name", "a")
        return self.links

    def execute_script(self, script: str) -> Any:
        if self._fail_script:
            raise RuntimeError("SyntaxError: bad script")
        self.scripts.append(script)
        return self.script_result

    def quit(self) -> None:
        self.quit_called = True


def ctx() -> ToolContext:
    return ToolContext(tool_use_id="t1", app_state=SimpleNamespace(get_cwd=lambda: "."))


@pytest.fixture()
def driver(monkeypatch):
    """Install a fake selenium whose webdriver.Chrome returns the given driver."""
    holder: dict[str, Any] = {"driver": FakeDriver(), "created": 0}

    class FakeWebdriver:
        def __init__(self) -> None:
            self.Chrome = self._chrome

        def _chrome(self) -> FakeDriver:
            holder["created"] += 1
            return holder["driver"]

    fake_module = SimpleNamespace(webdriver=FakeWebdriver())
    monkeypatch.setitem(__import__("sys").modules, "selenium", fake_module)
    return holder


def call(tool: BrowserTool, **kwargs: Any):
    return asyncio.run(tool.call(ctx(), **kwargs))


def test_selenium_availability_follows_the_import(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "selenium", SimpleNamespace())
    assert selenium_available() is True

    monkeypatch.setitem(__import__("sys").modules, "selenium", None)
    assert selenium_available() is False


def test_open_reports_the_title(driver) -> None:
    result = call(BrowserTool(), action="open", url="https://example.com")

    assert result.is_error is False
    assert result.content == "Opened https://example.com\nTitle: Example Domain"
    assert driver["driver"].opened == ["https://example.com"]
    assert driver["driver"].timeouts == [browser_tool.DEFAULT_TIMEOUT]


def test_open_requires_an_absolute_http_url(driver) -> None:
    result = call(BrowserTool(), action="open", url="example.com")

    assert result.is_error is True
    assert "must start with http" in result.content
    assert driver["driver"].opened == []


def test_text_action_returns_the_body(driver) -> None:
    result = call(BrowserTool(), action="text")

    assert result.content == "Rendered body text"


def test_long_text_is_truncated(driver) -> None:
    driver["driver"].text = "x" * (browser_tool.MAX_TEXT + 50)

    result = call(BrowserTool(), action="text")

    assert result.content.endswith("(truncated)")
    assert len(result.content) < browser_tool.MAX_TEXT + 50


def test_empty_text_is_reported(driver) -> None:
    driver["driver"].text = ""

    assert call(BrowserTool(), action="text").content == "(no text)"


def test_links_are_listed(driver) -> None:
    result = call(BrowserTool(), action="links")

    assert "Docs -> https://example.com/docs" in result.content
    assert "None" in result.content  # an anchor without href still shows up


def test_a_page_without_links_says_so(driver) -> None:
    driver["driver"].links = []

    assert call(BrowserTool(), action="links").content == "No links on the page."


def test_script_action_returns_the_value(driver) -> None:
    result = call(BrowserTool(), action="script", script="return 1 + 1")

    assert result.content == "scripted"
    assert driver["driver"].scripts == ["return 1 + 1"]


def test_script_action_requires_a_script(driver) -> None:
    result = call(BrowserTool(), action="script", script="   ")

    assert result.is_error is True
    assert "script is required" in result.content


def test_a_failing_script_is_reported(driver) -> None:
    driver["driver"] = FakeDriver(fail_script=True)

    result = call(BrowserTool(), action="script", script="boom()")

    assert result.is_error is True
    assert "script failed" in result.content


def test_an_unknown_action_lists_the_valid_ones(driver) -> None:
    result = call(BrowserTool(), action="screenshot")

    assert result.is_error is True
    assert "open, text, links or script" in result.content


def test_a_navigation_error_is_reported(driver) -> None:
    driver["driver"] = FakeDriver(fail_get=True)

    result = call(BrowserTool(), action="open", url="https://example.com")

    assert result.is_error is True
    assert "could not open" in result.content
    assert "ERR_NAME_NOT_RESOLVED" in result.content


def test_a_missing_selenium_is_explained(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "selenium", None)

    result = call(BrowserTool(), action="open", url="https://example.com")

    assert result.is_error is True
    assert "selenium is not installed" in result.content


def test_a_failing_browser_start_is_reported(driver, monkeypatch) -> None:
    class Broken:
        def Chrome(self) -> Any:  # noqa: N802 - selenium's attribute name
            raise RuntimeError("no chromedriver on PATH")

    monkeypatch.setitem(__import__("sys").modules, "selenium", SimpleNamespace(webdriver=Broken()))

    result = call(BrowserTool(), action="open", url="https://example.com")

    assert result.is_error is True
    assert "no chromedriver" in result.content


def test_sessions_reuse_one_driver_and_close_releases_it(driver) -> None:
    tool = BrowserTool()

    call(tool, action="open", url="https://example.com")
    call(tool, action="text")
    call(tool, action="open", url="https://example.org", session="other")

    assert driver["created"] == 2
    assert list(tool._drivers) == ["default", "other"]

    asyncio.run(tool.close())

    assert tool._drivers == {}
    assert driver["driver"].quit_called is True


def test_close_survives_a_driver_that_cannot_quit(driver) -> None:
    tool = BrowserTool()

    class Stubborn:
        def quit(self) -> None:
            raise RuntimeError("already gone")

    tool._drivers["default"] = Stubborn()

    asyncio.run(tool.close())

    assert tool._drivers == {}


def test_register_adds_the_tool() -> None:
    registry = ToolRegistry()
    browser_tool.register(registry)

    assert "Browser" in {tool.name for tool in registry.get_all()}
