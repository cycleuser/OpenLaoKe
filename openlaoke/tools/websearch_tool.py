"""WebSearch tool - search the web using DuckDuckGo."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class WebSearchInput(BaseModel):
    query: str = Field(description="The search query")
    num_results: int = Field(
        default=5, ge=1, le=20, description="Number of results to return (default 5, max 20)"
    )


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo HTML search."""

    name = "WebSearch"
    description = (
        "Searches the web using DuckDuckGo. "
        "Returns a list of search results with titles, URLs, and snippets. "
        "Use this tool when you need to find information on the web."
    )
    input_schema = WebSearchInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", 5)

        if not query:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: Search query is required",
                is_error=True,
            )

        try:
            results = await self._search_duckduckgo(query, num_results)

            if not results:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"No results found for: {query}",
                    is_error=False,
                )

            output_lines = [f"Search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                output_lines.append(f"{i}. {result['title']}")
                output_lines.append(f"   URL: {result['url']}")
                output_lines.append(f"   {result['snippet']}\n")

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="\n".join(output_lines),
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error performing search: {e}",
                is_error=True,
            )

    async def _search_duckduckgo(self, query: str, num_results: int) -> list[dict[str, str]]:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=params, follow_redirects=True)
            response.raise_for_status()

        return self._parse_ddg_html(response.text, num_results)

    def _parse_ddg_html(self, html: str, max_results: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        i = 0
        while i < len(html) and len(results) < max_results:
            class_pos = html.find('class="result__', i)
            if class_pos == -1:
                break

            a_start = html.find("<a", class_pos)
            if a_start == -1:
                i = class_pos + 1
                continue

            href_start = html.find('href="', a_start)
            if href_start == -1:
                i = a_start + 1
                continue

            href_end = html.find('"', href_start + 6)
            if href_end == -1:
                i = href_start + 1
                continue

            url = html[href_start + 6 : href_end]
            if url.startswith("/l/?uddg="):
                from urllib.parse import unquote

                url = unquote(url[10:].split("&", 1)[0])

            text_start = html.find(">", href_end) + 1
            text_end = html.find("</a>", text_start)
            if text_end == -1:
                i = text_start
                continue

            title = html[text_start:text_end]
            title = self._strip_tags(title).strip()

            snippet = ""
            snippet_start = html.find('class="result__snippet"', text_end)
            if snippet_start != -1 and snippet_start < html.find(
                'class="result__', text_end + 1 if text_end + 1 < len(html) else len(html)
            ):
                snippet_a = html.find(">", snippet_start) + 1
                snippet_end = html.find("</a>", snippet_a)
                if snippet_end != -1:
                    snippet = html[snippet_a:snippet_end]
                    snippet = self._strip_tags(snippet).strip()

            if title and url and not url.startswith("javascript:"):
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet or "(No description)",
                    }
                )

            i = text_end + 4

        return results

    def _strip_tags(self, text: str) -> str:
        result = []
        in_tag = False
        for char in text:
            if char == "<":
                in_tag = True
            elif char == ">":
                in_tag = False
            elif not in_tag:
                result.append(char)
        return "".join(result)


def register(registry: ToolRegistry) -> None:
    registry.register(WebSearchTool())
