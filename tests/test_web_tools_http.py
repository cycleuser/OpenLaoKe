"""WebFetch and WebSearch against a scripted HTTP transport (no real network).

The tools build their own ``httpx.AsyncClient``, so the module-level ``httpx`` name
is replaced with a small shim that hands back a ``MockTransport`` client. That
keeps the real request-building code in the test path.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx

from openlaoke.core.tool import ToolContext
from openlaoke.tools import webfetch_tool, websearch_tool
from openlaoke.tools.webfetch_tool import WebFetchTool, html_to_text
from openlaoke.tools.websearch_tool import WebSearchTool, _clean_url, parse_results

PAGE = (
    "<html><head><title>The Title</title></head><body>"
    "<h1>Heading</h1><p>Body text.</p></body></html>"
)


class Shim:
    """Stand-in for the ``httpx`` module that routes through a MockTransport."""

    HTTPError = httpx.HTTPError

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.handler = handler

    def AsyncClient(self, **kwargs: Any) -> httpx.AsyncClient:  # noqa: N802 - mirrors httpx
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def use(monkeypatch, module: Any, handler) -> None:
    monkeypatch.setattr(module, "httpx", Shim(handler), raising=True)


def ctx() -> ToolContext:
    return ToolContext(tool_use_id="t1", app_state=SimpleNamespace(get_cwd=lambda: "."))


def fetch(monkeypatch, handler, **kwargs: Any):
    use(monkeypatch, webfetch_tool, handler)
    return asyncio.run(WebFetchTool().call(ctx(), **kwargs))


def search(monkeypatch, handler, **kwargs: Any):
    use(monkeypatch, websearch_tool, handler)
    return asyncio.run(WebSearchTool().call(ctx(), **kwargs))


# --------------------------------------------------------------------------- #
# WebFetch
# --------------------------------------------------------------------------- #


def test_html_pages_are_reduced_to_text_with_a_title(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=PAGE)

    result = fetch(monkeypatch, handler, url="https://example.com/doc")

    assert result.is_error is False
    assert result.content.startswith("200 https://example.com/doc")
    assert "The Title" in result.content
    assert "Body text." in result.content
    assert "<h1>" not in result.content


def test_non_html_content_is_returned_as_is(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, text='{"a": 1}')

    result = fetch(monkeypatch, handler, url="https://api.example.com/v1")

    assert '{"a": 1}' in result.content


def test_raw_mode_skips_the_html_conversion(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=PAGE)

    result = fetch(monkeypatch, handler, url="https://example.com/", raw=True)

    assert "<h1>Heading</h1>" in result.content


def test_long_pages_are_truncated_with_a_marker(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="x" * 5000)

    result = fetch(monkeypatch, handler, url="https://example.com/big", max_chars=600)

    assert "truncated at 600 characters" in result.content
    assert len(result.content) < 1000


def test_max_chars_has_a_floor(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="y" * 2000)

    result = fetch(monkeypatch, handler, url="https://example.com/", max_chars=1)

    assert len(result.content) > 400  # floored at 500 characters, not 1


def test_an_error_status_with_no_body_is_reported(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="")

    result = fetch(monkeypatch, handler, url="https://example.com/boom")

    assert result.is_error is True
    assert "HTTP 500 from https://example.com/boom" in result.content


def test_an_error_status_with_a_body_still_returns_the_body(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, headers={"content-type": "text/plain"}, text="no such page")

    result = fetch(monkeypatch, handler, url="https://example.com/missing")

    assert "no such page" in result.content
    assert result.content.startswith("404")


def test_a_page_without_text_says_so(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, headers={"content-type": "text/html"}, text="<html></html>")

    result = fetch(monkeypatch, handler, url="https://example.com/empty")

    assert "page contained no text" in result.content


def test_a_transport_failure_is_reported_not_raised(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure")

    result = fetch(monkeypatch, handler, url="https://example.com/")

    assert result.is_error is True
    assert "Fetch failed" in result.content
    assert "dns failure" in result.content


def test_the_request_carries_a_user_agent(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent", "")
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="ok")

    fetch(monkeypatch, handler, url="https://example.com/")

    assert "openlaoke" in seen["ua"].lower() or seen["ua"]


def test_html_to_text_unescapes_entities() -> None:
    body, _title = html_to_text("<p>a &amp; b &lt;tag&gt;</p>")

    assert "a & b <tag>" in body


# --------------------------------------------------------------------------- #
# WebSearch
# --------------------------------------------------------------------------- #

RESULTS_PAGE = """
<div class="result">
  <a class="result__a" href="https://example.com/one">First &amp; result</a>
  <a class="result__snippet" href="https://example.com/one">Snippet one</a>
</div>
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Ftwo">Second</a>
  <div class="result__snippet">Snippet <b>two</b></div>
</div>
<div class="result">
  <a class="result__a" href="not-a-url">Broken</a>
</div>
"""


def test_results_are_parsed_with_redirects_unwrapped() -> None:
    results = parse_results(RESULTS_PAGE)

    assert [item["url"] for item in results] == [
        "https://example.com/one",
        "https://example.org/two",
    ]
    assert results[0]["title"] == "First & result"
    assert results[1]["snippet"] == "Snippet two"


def test_clean_url_leaves_ordinary_links_alone() -> None:
    assert _clean_url("https://example.com/x") == "https://example.com/x"
    assert _clean_url("//example.com/x") == "https://example.com/x"


def test_a_search_formats_its_results(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RESULTS_PAGE)

    result = search(monkeypatch, handler, query="openlaoke")

    assert result.is_error is False
    assert result.content.startswith("2 result(s) for 'openlaoke'")
    assert "1. First & result" in result.content
    assert "https://example.org/two" in result.content


def test_a_long_result_list_suggests_webfetch(monkeypatch) -> None:
    rows = "".join(
        f'<a class="result__a" href="https://example.com/{i}">Result number {i}</a>'
        f'<a class="result__snippet">A reasonably long snippet for entry {i}</a>'
        for i in range(8)
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rows)

    result = search(monkeypatch, handler, query="many")

    assert "Use WebFetch on one of these URLs" in result.content


def test_count_and_site_are_applied(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["q"] = str(request.url)
        return httpx.Response(200, text=RESULTS_PAGE)

    result = search(monkeypatch, handler, query="asyncio", count=1, site="docs.python.org")

    assert len(parse_results(RESULTS_PAGE)) == 2
    assert "1 result(s)" in result.content
    assert (
        "site%3Adocs.python.org" in seen["q"].replace("+", "%20") or "docs.python.org" in seen["q"]
    )


def test_count_is_clamped(monkeypatch) -> None:
    rows = "".join(
        f'<a class="result__a" href="https://example.com/{i}">Result {i}</a>' for i in range(20)
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=rows)

    result = search(monkeypatch, handler, query="clamp", count=99)

    assert result.content.startswith("15 result(s)")


def test_an_empty_query_is_rejected(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made")

    result = search(monkeypatch, handler, query="   ")

    assert result.is_error is True
    assert "query is required" in result.content


def test_an_endpoint_error_explains_what_to_do_instead(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="challenge")

    result = search(monkeypatch, handler, query="blocked")

    assert result.is_error is True
    assert "HTTP 403" in result.content
    assert "WebFetch" in result.content


def test_a_transport_failure_is_reported(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    result = search(monkeypatch, handler, query="slow")

    assert result.is_error is True
    assert "Search failed" in result.content


def test_markup_that_yields_nothing_mentions_the_challenge_page(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>nothing here</body></html>")

    result = search(monkeypatch, handler, query="weird")

    assert result.is_error is False
    assert "No results parsed" in result.content


def test_script_and_style_bodies_are_dropped(monkeypatch) -> None:
    page = (
        "<html><head><style>body{color:red}</style><script>alert('x')</script>"
        "</head><body><p>kept</p></body></html>"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=page)

    result = fetch(monkeypatch, handler, url="https://example.com/")

    assert "kept" in result.content
    assert "color:red" not in result.content
    assert "alert" not in result.content


def test_a_non_http_url_is_refused_before_any_request(monkeypatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made")

    result = fetch(monkeypatch, handler, url="file:///etc/passwd")

    assert result.is_error is True
    assert "must start with http" in result.content


def test_both_tools_register_themselves() -> None:
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools.register import register_all_tools

    registry = ToolRegistry()
    webfetch_tool.register(registry)
    websearch_tool.register(registry)

    assert {tool.name for tool in registry.get_all()} == {"WebFetch", "WebSearch"}

    full = ToolRegistry()
    register_all_tools(full)
    assert "WebSearch" in {tool.name for tool in full.get_all()}


def test_markup_inside_a_result_title_is_kept_as_text(monkeypatch) -> None:
    page = (
        '<a class="result__a" href="https://example.com/x"><b>bold</b> title</a>'
        '<div class="result__snippet">snippet</div>'
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=page)

    result = search(monkeypatch, handler, query="nested")

    assert "bold title" in result.content
