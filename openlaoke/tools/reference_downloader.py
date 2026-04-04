"""Reference downloader tool - download academic papers as PDFs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class DownloadReferenceInput(BaseModel):
    source: str = Field(
        description="Source identifier (arXiv ID, DOI, or URL). Examples: 'arXiv:2301.12345', '10.1234/journal.2023.001', or full URL"
    )
    filename: str | None = Field(
        default=None,
        description="Optional custom filename (without .pdf extension). If not provided, will auto-generate from source.",
    )


class ReferenceDownloader(Tool):
    """Download academic papers from various sources."""

    name = "DownloadReference"
    description = (
        "Download academic papers as PDFs from arXiv, DOI, or direct URLs. "
        "Automatically saves to 'pdf/' directory in working directory. "
        "Returns the path to the downloaded PDF."
    )
    input_schema = DownloadReferenceInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        source = kwargs.get("source", "")
        custom_filename = kwargs.get("filename")

        if not source:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: source is required (arXiv ID, DOI, or URL)",
                is_error=True,
            )

        pdf_dir = Path(ctx.app_state.get_cwd()) / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)

        try:
            pdf_url, suggested_name = await self._resolve_source(source)

            if not pdf_url:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Could not resolve source: {source}",
                    is_error=True,
                )

            filename = custom_filename or suggested_name
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            filepath = pdf_dir / filename

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()

                filepath.write_bytes(response.content)

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Downloaded: {filepath}\nSource: {source}\nSize: {len(response.content):,} bytes",
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error downloading reference: {e}",
                is_error=True,
            )

    async def _resolve_source(self, source: str) -> tuple[str | None, str]:
        """Resolve source to PDF URL and suggested filename."""

        if source.startswith("arXiv:") or re.match(r"\d{4}\.\d{4,5}", source):
            return self._resolve_arxiv(source)

        if source.startswith("10.") or "/" in source:
            return await self._resolve_doi(source)

        if source.startswith("http"):
            return self._resolve_url(source)

        return None, ""

    def _resolve_arxiv(self, source: str) -> tuple[str, str]:
        """Resolve arXiv ID to PDF URL."""
        arxiv_id = source.replace("arXiv:", "").replace("arxiv:", "").strip()
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        filename = f"arxiv_{arxiv_id.replace('/', '_')}"

        return pdf_url, filename

    async def _resolve_doi(self, source: str) -> tuple[str | None, str]:
        """Resolve DOI to PDF URL."""
        doi = source if source.startswith("10.") else None

        if not doi:
            if "/" in source and not source.startswith("http"):
                doi = source

        if not doi:
            return None, ""

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                headers = {"Accept": "application/vnd.citationstyles.csl+json"}
                url = f"https://doi.org/{doi}"
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    title = data.get("title", "")
                    if title:
                        safe_title = re.sub(r"[^\w\s-]", "", title)
                        safe_title = re.sub(r"\s+", "_", safe_title)[:50]
                        filename = f"doi_{safe_title}"
                    else:
                        filename = f"doi_{doi.replace('/', '_')[:30]}"

                    link = data.get("link", [])
                    if link and isinstance(link, list):
                        for link_item in link:
                            if link_item.get("content-type") == "application/pdf":
                                return link_item.get("URL"), filename

                    return f"https://doi.org/{doi}", filename

        except Exception:
            pass

        filename = f"doi_{doi.replace('/', '_')[:30]}"
        return f"https://doi.org/{doi}", filename

    def _resolve_url(self, source: str) -> tuple[str, str]:
        """Resolve direct URL."""
        filename = source.split("/")[-1]
        if "." in filename:
            filename = filename.rsplit(".", 1)[0]
        filename = re.sub(r"[^\w-]", "", filename)[:50] or "downloaded_paper"

        if "arxiv.org" in source:
            match = re.search(r"(\d{4}\.\d{4,5})", source)
            if match:
                filename = f"arxiv_{match.group(1)}"

        return source, filename


class BatchDownloadInput(BaseModel):
    sources: list[str] = Field(description="List of sources to download (arXiv IDs, DOIs, or URLs)")


class BatchDownloadReferences(Tool):
    """Download multiple academic papers in batch."""

    name = "BatchDownloadReferences"
    description = (
        "Download multiple academic papers at once. "
        "Accepts list of arXiv IDs, DOIs, or URLs. "
        "Creates 'pdf/' directory and saves all papers there."
    )
    input_schema = BatchDownloadInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        sources = kwargs.get("sources", [])

        if not sources:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: sources list is required",
                is_error=True,
            )

        downloader = ReferenceDownloader()
        results = []

        for i, source in enumerate(sources, 1):
            result = await downloader.call(
                ToolContext(app_state=ctx.app_state, tool_use_id=f"{ctx.tool_use_id}_{i}"),
                source=source,
            )
            results.append(f"{i}. {source}:\n   {result.content}")

        successful = sum(1 for r in results if "Error" not in r)
        total = len(sources)

        summary = f"Downloaded {successful}/{total} papers\n\n" + "\n\n".join(results)

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=summary,
            is_error=successful == 0,
        )


class SearchAndDownloadInput(BaseModel):
    query: str = Field(description="Search query for academic papers")
    max_results: int = Field(
        default=5, ge=1, le=20, description="Maximum number of papers to download"
    )


class SearchAndDownloadPapers(Tool):
    """Search for papers and download them."""

    name = "SearchAndDownloadPapers"
    description = (
        "Search for academic papers and automatically download them. "
        "Uses Semantic Scholar API to find relevant papers. "
        "Downloads PDFs to 'pdf/' directory."
    )
    input_schema = SearchAndDownloadInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)

        if not query:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: query is required",
                is_error=True,
            )

        try:
            papers = await self._search_papers(query, max_results)

            if not papers:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"No papers found for: {query}",
                    is_error=False,
                )

            pdf_dir = Path(ctx.app_state.get_cwd()) / "pdf"
            pdf_dir.mkdir(parents=True, exist_ok=True)

            results = []
            for paper in papers:
                result = await self._download_paper(paper, pdf_dir)
                results.append(result)

            successful = sum(1 for r in results if r["success"])
            summary_lines = [
                f"Search: {query}",
                f"Found: {len(papers)} papers",
                f"Downloaded: {successful}/{len(papers)}",
                "",
                "Results:",
            ]

            for r in results:
                status = "✓" if r["success"] else "✗"
                summary_lines.append(f"  {status} {r['title'][:60]}")
                if r.get("path"):
                    summary_lines.append(f"    → {r['path']}")
                if r.get("error"):
                    summary_lines.append(f"    Error: {r['error']}")

            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="\n".join(summary_lines),
                is_error=successful == 0,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error searching papers: {e}",
                is_error=True,
            )

    async def _search_papers(self, query: str, limit: int) -> list[dict]:
        """Search papers using Semantic Scholar API."""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,year,authors,openAccessPdf,externalIds",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        papers = []
        for item in data.get("data", []):
            paper = {
                "title": item.get("title", "Unknown"),
                "year": item.get("year"),
                "authors": [a.get("name", "") for a in item.get("authors", [])],
                "external_ids": item.get("externalIds", {}),
            }

            oa_pdf = item.get("openAccessPdf")
            if oa_pdf:
                paper["pdf_url"] = oa_pdf.get("url")

            arxiv_id = item.get("externalIds", {}).get("ArXiv")
            if arxiv_id:
                paper["arxiv_id"] = arxiv_id
                paper["pdf_url"] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            doi = item.get("externalIds", {}).get("DOI")
            if doi:
                paper["doi"] = doi

            papers.append(paper)

        return papers

    async def _download_paper(self, paper: dict, pdf_dir: Path) -> dict:
        """Download a single paper."""
        result = {
            "title": paper.get("title", "Unknown"),
            "success": False,
            "path": None,
            "error": None,
        }

        pdf_url = paper.get("pdf_url")
        if not pdf_url:
            result["error"] = "No PDF URL available"
            return result

        try:
            safe_title = re.sub(r"[^\w\s-]", "", paper["title"])
            safe_title = re.sub(r"\s+", "_", safe_title)[:50]
            year = paper.get("year", "")
            filename = f"{safe_title}_{year}.pdf" if year else f"{safe_title}.pdf"
            filepath = pdf_dir / filename

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(pdf_url)
                response.raise_for_status()
                filepath.write_bytes(response.content)

            result["success"] = True
            result["path"] = str(filepath)

        except Exception as e:
            result["error"] = str(e)

        return result


def register(registry: ToolRegistry) -> None:
    registry.register(ReferenceDownloader())
    registry.register(BatchDownloadReferences())
    registry.register(SearchAndDownloadPapers())
