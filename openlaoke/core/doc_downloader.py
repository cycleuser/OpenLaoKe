"""Document downloader and indexer for knowledge base.

Downloads official documentation and creates searchable knowledge base
for small models to learn from.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from openlaoke.core.doc_sources import DOC_SOURCES, LANGUAGE_ALIASES


@dataclass
class DocumentChunk:
    doc_id: str
    source: str
    title: str
    content: str
    url: str
    category: str
    language: str
    chunk_index: int
    metadata: dict[str, Any]


class DocumentationDownloader:
    """Download and process documentation from official sources."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".openlaoke" / "docs"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; OpenLaoKe/0.1.0; +https://github.com/cycleuser/OpenLaoKe)"
            }
        )

    def download_source(self, source_id: str, force: bool = False) -> list[DocumentChunk]:
        """Download all URLs for a source."""
        if source_id not in DOC_SOURCES:
            print(f"Unknown source: {source_id}")
            return []

        source_info = DOC_SOURCES[source_id]
        source_name: str = source_info["name"]
        urls: list[str] = source_info["urls"]
        category: str = source_info.get("category", "general")
        language = self._detect_language(source_id, category)

        all_chunks = []

        for url_idx, url in enumerate(urls):
            cache_file = self._get_cache_path(source_id, url_idx)

            if cache_file.exists() and not force:
                print(f"[{source_name}] Loading from cache: {url}")
                with open(cache_file, encoding="utf-8") as f:
                    cached_data = json.load(f)
                content = cached_data["content"]
                title = cached_data.get("title", f"{source_name} - Part {url_idx + 1}")
            else:
                print(f"[{source_name}] Downloading: {url}")
                content, title = self._fetch_url(url)
                if not content:
                    print(f"[{source_name}] Failed to download: {url}")
                    continue

                cached_data = {
                    "content": content,
                    "title": title,
                    "url": url,
                    "downloaded_at": time.time(),
                }
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cached_data, f, ensure_ascii=False, indent=2)

            chunks = self._chunk_document(
                content=content,
                source=source_name,
                title=title,
                url=url,
                category=category,
                language=language,
                source_id=source_id,
            )

            all_chunks.extend(chunks)

        print(f"[{source_name}] Total chunks: {len(all_chunks)}")
        return all_chunks

    def download_multiple_sources(
        self, source_ids: list[str], force: bool = False
    ) -> list[DocumentChunk]:
        """Download multiple sources."""
        all_chunks = []

        for source_id in source_ids:
            chunks = self.download_source(source_id, force=force)
            all_chunks.extend(chunks)

        return all_chunks

    def download_task_relevant_docs(
        self, task_description: str, force: bool = False
    ) -> list[DocumentChunk]:
        """Download docs relevant to a task description."""
        task_lower = task_description.lower()

        source_ids = set()

        for keyword, sources in [
            ("benchmark", ["multiprocessing", "asyncio", "threading"]),
            ("web", ["flask", "fastapi", "requests"]),
            ("api", ["fastapi", "flask", "requests"]),
            ("data", ["numpy", "pandas"]),
            ("test", ["pytest", "unittest"]),
            ("cli", ["click", "argparse"]),
            ("database", ["sqlalchemy"]),
            ("file", ["pathlib", "json"]),
            ("async", ["asyncio"]),
            ("gui", ["tkinter"]),
        ]:
            if keyword in task_lower:
                source_ids.update(sources)

        for lang in ["python", "javascript", "typescript", "rust", "go", "java", "cpp"]:
            if lang in task_lower:
                source_ids.add(lang)

        if not source_ids:
            source_ids.update(["python", "numpy", "pathlib", "json"])

        print(f"Task-relevant sources: {', '.join(sorted(source_ids))}")
        return self.download_multiple_sources(list(source_ids), force=force)

    def _fetch_url(self, url: str) -> tuple[str, str]:
        """Fetch content from URL."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            content = response.text
            title = self._extract_title(content, url)

            content = self._clean_content(content)

            return content, title

        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return "", ""

    def _extract_title(self, content: str, url: str) -> str:
        """Extract title from content or URL."""
        title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()

        h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_match:
            return h1_match.group(1).strip()

        path_parts = url.split("/")
        if path_parts:
            return path_parts[-1].replace(".html", "").replace(".md", "").replace("_", " ").title()

        return "Untitled"

    def _clean_content(self, content: str) -> str:
        """Clean HTML/Markdown content to plain text."""
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

        content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<nav[^>]*>.*?</nav>", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"<footer[^>]*>.*?</footer>", "", content, flags=re.DOTALL | re.IGNORECASE)

        content = re.sub(r"<[^>]+>", " ", content)

        content = re.sub(r"\n\s*\n", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)

        return content.strip()

    def _chunk_document(
        self,
        content: str,
        source: str,
        title: str,
        url: str,
        category: str,
        language: str,
        source_id: str,
        chunk_size: int = 2000,
    ) -> list[DocumentChunk]:
        """Split document into chunks for better retrieval."""
        chunks = []

        paragraphs = re.split(r"\n\s*\n", content)

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
                doc_id = self._generate_doc_id(source_id, chunk_index)
                chunks.append(
                    DocumentChunk(
                        doc_id=doc_id,
                        source=source,
                        title=title,
                        content=current_chunk.strip(),
                        url=url,
                        category=category,
                        language=language,
                        chunk_index=chunk_index,
                        metadata={
                            "source_id": source_id,
                            "char_count": len(current_chunk),
                        },
                    )
                )
                chunk_index += 1
                current_chunk = para + "\n\n"
            else:
                current_chunk += para + "\n\n"

        if current_chunk.strip():
            doc_id = self._generate_doc_id(source_id, chunk_index)
            chunks.append(
                DocumentChunk(
                    doc_id=doc_id,
                    source=source,
                    title=title,
                    content=current_chunk.strip(),
                    url=url,
                    category=category,
                    language=language,
                    chunk_index=chunk_index,
                    metadata={
                        "source_id": source_id,
                        "char_count": len(current_chunk),
                    },
                )
            )

        return chunks

    def _detect_language(self, source_id: str, category: str) -> str:
        """Detect programming language from source ID."""
        if category == "programming_language":
            return source_id
        if source_id in LANGUAGE_ALIASES:
            return LANGUAGE_ALIASES[source_id]
        if source_id in [
            "python",
            "numpy",
            "pandas",
            "flask",
            "fastapi",
            "pytest",
            "django",
            "click",
            "rich",
            "pydantic",
        ]:
            return "python"
        if source_id in ["javascript", "react", "vue"]:
            return "javascript"
        if source_id in ["typescript"]:
            return "typescript"
        if source_id in ["rust"]:
            return "rust"
        if source_id in ["go"]:
            return "go"
        if source_id in ["java"]:
            return "java"
        if source_id in ["cpp"]:
            return "cpp"
        return "general"

    def _get_cache_path(self, source_id: str, url_index: int) -> Path:
        """Get cache file path for a downloaded document."""
        safe_source = re.sub(r"[^\w\-]", "_", source_id)
        return self.cache_dir / f"{safe_source}_{url_index}.json"

    def _generate_doc_id(self, source_id: str, chunk_index: int) -> str:
        """Generate unique document ID."""
        hash_input = f"{source_id}_{chunk_index}_{time.time()}"
        hash_digest = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{source_id}_{chunk_index}_{hash_digest}"


def create_downloader(cache_dir: Path | None = None) -> DocumentationDownloader:
    """Create a document downloader instance."""
    return DocumentationDownloader(cache_dir)


def download_knowledge_for_task(
    task_description: str, cache_dir: Path | None = None, force: bool = False
) -> list[DocumentChunk]:
    """Download relevant documentation for a task."""
    downloader = DocumentationDownloader(cache_dir)
    return downloader.download_task_relevant_docs(task_description, force=force)
