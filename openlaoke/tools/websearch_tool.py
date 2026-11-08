"""WebSearch tool - a search results list, without an API key.

Uses the DuckDuckGo HTML endpoint, which needs no key and no JavaScript.  The
parser is deliberately tolerant: it reads anchors marked as results and their
snippets by class name, and if the page shape changes the call reports that it
found nothing rather than inventing results.

Pair this with WebFetch: search gives links, fetch reads the page that matters.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

ENDPOINT = "https://html.duckduckgo.com/html/"
USER_AGENT = "Mozilla/5.0 (compatible; OpenLaoKe/1.0; +https://github.com/OpenLaoKe/OpenLaoKe)"
DEFAULT_TIMEOUT = 25.0


def _clean_url(href: str) -> str:
    """Unwrap DuckDuckGo's redirect form into the destination URL."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return href


class _ResultParser(HTMLParser):
    """Collect result anchors and snippets by class name."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._anchor_depth = 0
        self._current: dict[str, str] | None = None
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        attributes = dict(attrs)
        classes = attributes.get("class", "") or ""
        if tag == "a" and "result__a" in classes:
            self._current = {
                "title": "",
                "url": _clean_url(attributes.get("href", "")),
                "snippet": "",
            }
            self.results.append(self._current)
            self._anchor_depth = 1
            return
        if self._anchor_depth:
            self._anchor_depth += 1
        if self._current is not None and "result__snippet" in classes:
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if self._anchor_depth:
            self._anchor_depth -= 1
        if self._in_snippet and tag in ("a", "div", "span"):
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        if self._anchor_depth:
            self._current["title"] += data
        elif self._in_snippet:
            self._current["snippet"] += data


def parse_results(markup: str) -> list[dict[str, str]]:
    parser = _ResultParser()
    parser.feed(markup)
    results: list[dict[str, str]] = []
    for item in parser.results:
        title = " ".join(html.unescape(item["title"]).split())
        url = item["url"]
        if not title or not url.startswith("http"):
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": " ".join(html.unescape(item["snippet"]).split()),
            }
        )
    return results


class WebSearchInput(BaseModel):
    query: str = Field(description="Search terms")
    count: int = Field(default=8, description="How many results to return (1-15)")
    site: str = Field(default="", description="Restrict to one site, e.g. 'docs.python.org'")


class WebSearchTool(Tool):
    """Search the web and return titles, links and snippets."""

    name = "WebSearch"
    description = (
        "Search the web and get back titles, URLs and snippets. Use it when you know the "
        "topic but not the link, then call WebFetch on the result that matters. The search "
        "backend needs no API key but does need network access."
    )
    input_schema = WebSearchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return self._error(ctx, "Error: query is required")
        count = max(1, min(15, int(kwargs.get("count") or 8)))
        site = str(kwargs.get("site") or "").strip()
        if site:
            query = f"{query} site:{site}"

        headers = {"user-agent": USER_AGENT, "accept-language": "en,zh-CN;q=0.8"}
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT, follow_redirects=True, headers=headers
            ) as client:
                response = await client.get(ENDPOINT, params={"q": query})
        except httpx.HTTPError as exc:
            return self._error(ctx, f"Search failed: {exc}")

        if response.status_code >= 400:
            return self._error(
                ctx,
                f"Search endpoint returned HTTP {response.status_code}. "
                "If this machine has no access to it, use WebFetch on a known URL instead.",
            )

        results = parse_results(response.text)[:count]
        if not results:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=(
                    f"No results parsed for '{query}'. The endpoint may have changed its markup "
                    "or returned a challenge page; try a different wording, or WebFetch a URL "
                    "you already know."
                ),
            )

        lines: list[str] = []
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {item['title']}\n   {item['url']}")
            if item["snippet"]:
                lines.append(f"   {item['snippet'][:300]}")
        body = "\n".join(lines)
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"{len(results)} result(s) for '{query}':\n\n{body}"
            + ("\n\nUse WebFetch on one of these URLs to read it." if len(body) > 200 else ""),
        )

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(WebSearchTool())
