"""WebFetch tool - fetch content from URLs."""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class WebFetchInput(BaseModel):
    url: str = Field(description="The URL to fetch content from")
    format: Literal["markdown", "text", "html"] = Field(
        default="markdown",
        description="Output format: markdown (default), text, or html",
    )
    timeout: float | None = Field(default=None, description="Optional timeout in seconds (max 120)")


class WebFetchTool(Tool):
    """Fetch content from a URL and convert to specified format."""

    name = "WebFetch"
    description = (
        "Fetches content from a specified URL and converts it to the requested format. "
        "Supports markdown (default), text, and html output formats. "
        "HTTP URLs are automatically upgraded to HTTPS. "
        "Results may be summarized for very large content."
    )
    input_schema = WebFetchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        url = kwargs.get("url", "")
        output_format = kwargs.get("format", "markdown")
        timeout = min(kwargs.get("timeout") or 30.0, 120.0)

        if not url:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: URL is required",
                is_error=True,
            )

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

            content = response.text

            if output_format == "text":
                from html.parser import HTMLParser

                class TextExtractor(HTMLParser):
                    def __init__(self) -> None:
                        super().__init__()
                        self.text_parts: list[str] = []
                        self.skip = False

                    def handle_starttag(
                        self, tag: str, attrs: list[tuple[str, str | None]]
                    ) -> None:
                        if tag in ("script", "style", "nav", "footer", "header"):
                            self.skip = True

                    def handle_endtag(self, tag: str) -> None:
                        if tag in ("script", "style", "nav", "footer", "header"):
                            self.skip = False

                    def handle_data(self, data: str) -> None:
                        if not self.skip:
                            self.text_parts.append(data)

                extractor = TextExtractor()
                extractor.feed(content)
                result = " ".join(" ".join(extractor.text_parts).split())

            elif output_format == "html":
                result = content
            else:
                result = self._html_to_markdown(content)

            max_len = 50000
            if len(result) > max_len:
                result = (
                    result[:max_len] + f"\n\n... (truncated, {len(result) - max_len} chars omitted)"
                )

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=result,
                is_error=False,
            )

        except httpx.TimeoutException:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Request timed out after {timeout}s",
                is_error=True,
            )
        except httpx.HTTPStatusError as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}",
                is_error=True,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error fetching URL: {e}",
                is_error=True,
            )

    def _html_to_markdown(self, html: str) -> str:
        lines: list[str] = []
        in_pre = False
        in_code = False
        i = 0
        while i < len(html):
            if html[i : i + 4].lower() == "<pre":
                in_pre = True
                lines.append("\n```\n")
                i = html.find(">", i) + 1
                continue
            if html[i : i + 6].lower() == "</pre>" and in_pre:
                in_pre = False
                lines.append("\n```\n")
                i += 6
                continue
            if html[i : i + 5].lower() == "<code" and not in_code:
                in_code = True
                lines.append("`")
                i = html.find(">", i) + 1
                continue
            if html[i : i + 7].lower() == "</code>" and in_code:
                in_code = False
                lines.append("`")
                i += 7
                continue
            if not in_pre:
                if html[i : i + 2].lower() == "<h":
                    end_tag = html.find(">", i)
                    if end_tag != -1:
                        level = html[i + 2]
                        if level.isdigit():
                            lines.append("\n" + "#" * int(level) + " ")
                            i = end_tag + 1
                            continue
                if html[i : i + 4].lower() == "</h":
                    lines.append("\n")
                    i = html.find(">", i) + 1
                    continue
                if html[i : i + 2].lower() == "<p":
                    lines.append("\n")
                    i = html.find(">", i) + 1
                    continue
                if html[i : i + 4].lower() == "</p>":
                    lines.append("\n")
                    i += 4
                    continue
                if html[i : i + 2].lower() == "<b" or html[i : i + 3].lower() == "<st":
                    lines.append("**")
                    i = html.find(">", i) + 1
                    continue
                if html[i : i + 4].lower() == "</b>" or html[i : i + 5].lower() == "</st":
                    lines.append("**")
                    i += 4 if html[i : i + 4].lower() == "</b>" else 5
                    continue
                if html[i : i + 2].lower() == "<i" or html[i : i + 3].lower() == "<em":
                    lines.append("*")
                    i = html.find(">", i) + 1
                    continue
                if html[i : i + 4].lower() == "</i>" or html[i : i + 5].lower() == "</em":
                    lines.append("*")
                    i += 4 if html[i : i + 4].lower() == "</i>" else 5
                    continue
                if html[i : i + 2].lower() == "<l":
                    i = html.find(">", i) + 1
                    lines.append("\n- ")
                    continue
                if html[i : i + 2].lower() == "<a":
                    href_start = html.find('href="', i)
                    if href_start != -1:
                        href_end = html.find('"', href_start + 6)
                        href = html[href_start + 6 : href_end]
                        text_start = html.find(">", href_end) + 1
                        text_end = html.find("</a>", text_start)
                        text = html[text_start:text_end].strip()
                        lines.append(f"[{text}]({href})")
                        i = text_end + 4
                        continue
                if html[i : i + 2].lower() == "<b" and html[i : i + 3].lower() != "<br":
                    lines.append("\n")
                    i = html.find(">", i) + 1
                    continue
            if html[i] == "<":
                end = html.find(">", i)
                if end != -1:
                    i = end + 1
                    continue
            if html[i] == "&":
                if html[i : i + 4] == "&lt;":
                    lines.append("<")
                    i += 4
                    continue
                if html[i : i + 4] == "&gt;":
                    lines.append(">")
                    i += 4
                    continue
                if html[i : i + 6] == "&nbsp;":
                    lines.append(" ")
                    i += 6
                    continue
                if html[i : i + 5] == "&amp;":
                    lines.append("&")
                    i += 5
                    continue
            lines.append(html[i])
            i += 1

        return "".join(lines).strip()


def register(registry: ToolRegistry) -> None:
    registry.register(WebFetchTool())
