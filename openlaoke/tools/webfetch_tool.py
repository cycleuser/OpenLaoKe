"""WebFetch tool - read a URL as text.

Uses httpx, which is already a dependency, and the stdlib HTML parser, so this
adds no requirements.  Output is capped by the shared token estimator so a page
cannot arrive larger than the session budget allows, and the result ledger in
front of the tool turns a re-fetch of the same page into a pointer.
"""

from __future__ import annotations

import contextlib
import html
import re
from html.parser import HTMLParser
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

MAX_BYTES = 2_000_000
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "OpenLaoKe/1.0 (+https://github.com/cycleuser/OpenLaoKe)"

_DROP_TAGS = {"script", "style", "noscript", "template", "svg"}
_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "li",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "article",
    "section",
    "table",
    "ul",
    "ol",
    "blockquote",
    "pre",
    "header",
    "footer",
    "nav",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _DROP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_TAGS and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title and not self.title:
            self.title = data.strip()
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")


def html_to_text(markup: str) -> tuple[str, str]:
    """Return ``(body, title)`` for an HTML document."""
    parser = _TextExtractor()
    with contextlib.suppress(Exception):
        parser.feed(markup)
    body = html.unescape("".join(parser.parts))
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n\s*\n\s*\n+", "\n\n", body)
    return body.strip(), parser.title


class WebFetchInput(BaseModel):
    url: str = Field(description="Absolute http(s) URL to fetch")
    max_chars: int = Field(
        default=20000, description="Truncate the extracted text at this many characters"
    )
    raw: bool = Field(
        default=False, description="Return the response body without HTML-to-text conversion"
    )


class WebFetchTool(Tool):
    """Fetch a URL and return readable text."""

    name = "WebFetch"
    description = (
        "Fetch a URL and return its text with scripts and markup removed. Use it to read "
        "documentation or an issue you already have a link to; use WebSearch first when you "
        "only know the topic. Re-fetching the same page costs almost nothing: the harness "
        "replaces a repeat with a pointer."
    )
    input_schema = WebFetchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        url = str(kwargs.get("url") or "").strip()
        max_chars = max(500, int(kwargs.get("max_chars") or 20000))
        raw = bool(kwargs.get("raw", False))

        if not re.match(r"^https?://", url):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: url must start with http:// or https://",
                is_error=True,
            )

        headers = {"user-agent": USER_AGENT, "accept-language": "en,zh-CN;q=0.8"}
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT, follow_redirects=True, headers=headers
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content=f"Fetch failed: {exc}", is_error=True
            )

        body = response.text[:MAX_BYTES]
        if response.is_error and not body.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"HTTP {response.status_code} from {url}",
                is_error=True,
            )

        if raw or "html" not in response.headers.get("content-type", ""):
            text, title = body, ""
        else:
            text, title = html_to_text(body)

        truncated = len(text) > max_chars
        text = text[:max_chars]
        header = f"{response.status_code} {url}"
        if title:
            header += f"\n{title}"
        if truncated:
            text += f"\n\n... (truncated at {max_chars} characters)"
        if not text.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"{header}\n(page contained no text)",
                is_error=response.is_error,
            )
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=f"{header}\n\n{text}")


def register(registry: ToolRegistry) -> None:
    registry.register(WebFetchTool())
