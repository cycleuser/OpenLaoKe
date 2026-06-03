"""WebSearch tool - search the web using DuckDuckGo.

Primary: duckduckgo_search Python package (clean API, no parsing).
Fallback: html.duckduckgo.com HTML scraping (no external deps).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class WebSearchInput(BaseModel):
    query: str = Field(description="The search query")
    num_results: int = Field(
        default=5, ge=1, le=20, description="Number of results (default 5, max 20)"
    )


class WebSearchTool(Tool):
    name = "WebSearch"
    description = (
        "Searches the web using DuckDuckGo. Returns titles, URLs, and snippets. "
        "Use for: weather, news, docs, facts, current information, research. "
        "ALWAYS search before saying you don't know something."
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
            results = await self._search(query, num_results)
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Search error: {e}",
                is_error=True,
            )

        if not results:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No results found for: {query}",
                is_error=False,
            )

        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            lines.append(f"   {r['snippet']}\n")

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(lines),
            is_error=False,
        )

    async def _search(self, query: str, num: int) -> list[dict[str, str]]:
        results = await self._search_ddg_lib(query, num)
        if results:
            return results
        return await self._search_ddg_html(query, num)

    async def _search_ddg_lib(self, query: str, num: int) -> list[dict[str, str]]:
        def _run() -> list[dict[str, str]]:
            for mod_name in ("ddgs", "duckduckgo_search"):
                try:
                    import importlib

                    mod = importlib.import_module(mod_name)
                    raw = list(mod.DDGS().text(query, max_results=num))
                    results = [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", r.get("link", "")),
                            "snippet": r.get("body", r.get("snippet", "")),
                        }
                        for r in raw
                    ]
                    if results:
                        return results
                except Exception:
                    continue
            return []

        try:
            return await asyncio.to_thread(_run)
        except Exception:
            return []

    async def _search_ddg_html(self, query: str, num: int) -> list[dict[str, str]]:
        url = "https://html.duckduckgo.com/html/"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.post(url, data={"q": query})
            resp.raise_for_status()
        return self._parse_html(resp.text, num)

    def _parse_html(self, html: str, max_results: int) -> list[dict[str, str]]:
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
            href_start2 = html.find("href='", a_start)
            if href_start == -1 and href_start2 == -1:
                i = a_start + 1
                continue
            if href_start2 != -1 and (href_start == -1 or href_start2 < href_start):
                href_start = href_start2
                q = "'"
            else:
                q = '"'

            href_end = html.find(q, href_start + 6)
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

            title = self._strip_tags(html[text_start:text_end]).strip()

            snippet = ""
            snippet_class = html.find('class="result__snippet"', text_end)
            next_result = html.find('class="result__', text_end + 1)
            if snippet_class != -1 and (next_result == -1 or snippet_class < next_result):
                snip_a = html.find(">", snippet_class) + 1
                snip_end = html.find("</a>", snip_a)
                if snip_end != -1:
                    snippet = self._strip_tags(html[snip_a:snip_end]).strip()

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

    @staticmethod
    def _strip_tags(text: str) -> str:
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
