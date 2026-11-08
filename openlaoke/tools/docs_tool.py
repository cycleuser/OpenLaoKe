"""OpenLaoKeDocs - read this project's own documentation.

A coding agent gets asked "how does the context budget work" about the
repository it is sitting in. The answer is in `docs/`, and searching it costs one
call instead of a walk over the tree.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.session_index import score_documents
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

DOC_SUFFIXES = (".md", ".markdown", ".txt", ".rst")
ROOT_FILES = ("README.md", "CHANGELOG.md", "AGENTS.md", "CONTRIBUTING.md")
MAX_READ_CHARS = 20000
MAX_SEARCH_HITS = 12


def _roots(cwd: str) -> list[str]:
    """Files and directories that count as project documentation."""
    roots: list[str] = []
    docs_dir = os.path.join(cwd, "docs")
    if os.path.isdir(docs_dir):
        roots.append(docs_dir)
    for name in ROOT_FILES:
        path = os.path.join(cwd, name)
        if os.path.isfile(path):
            roots.append(path)
    return roots


def _iter_docs(cwd: str) -> list[str]:
    found: list[str] = []
    for root in _roots(cwd):
        if os.path.isfile(root):
            found.append(root)
            continue
        for directory, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]
            for name in sorted(filenames):
                if name.lower().endswith(DOC_SUFFIXES):
                    found.append(os.path.join(directory, name))
    return found


def _sections(path: str) -> list[tuple[str, str]]:
    """Split a document into (heading, body) pairs on markdown headings."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return []
    sections: list[tuple[str, str]] = []
    heading = os.path.basename(path)
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if buffer and "".join(buffer).strip():
                sections.append((heading, "\n".join(buffer).strip()))
            heading = line.lstrip("#").strip() or heading
            buffer = []
        else:
            buffer.append(line)
    if "".join(buffer).strip():
        sections.append((heading, "\n".join(buffer).strip()))
    if not sections:
        sections.append((os.path.basename(path), text[:4000]))
    return sections


class DocsInput(BaseModel):
    action: str = Field(default="list", description="list | search | read")
    query: str = Field(default="", description="search: what to look for")
    path: str = Field(
        default="", description="read: path relative to the project, e.g. docs/HARNESS.md"
    )
    section: str = Field(
        default="", description="read: only the section whose heading contains this"
    )
    limit: int = Field(default=8, description="search: maximum sections to return")


class OpenLaoKeDocsTool(Tool):
    """Search and read the repository's own docs."""

    name = "OpenLaoKeDocs"
    description = (
        "Read this project's documentation: 'list' shows the files under docs/ and the "
        "root README/CHANGELOG/AGENTS, 'search' finds the section that discusses a topic, "
        "'read' returns a file (optionally one section). Use it before guessing how this "
        "codebase is meant to be used."
    )
    input_schema = DocsInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        cwd = ctx.app_state.get_cwd()
        action = str(kwargs.get("action") or "list").strip().lower()

        if action == "list":
            paths = _iter_docs(cwd)
            if not paths:
                return self._result(ctx, f"No docs found under {cwd}/docs or the root files.")
            rows = []
            for path in paths[:100]:
                rel = os.path.relpath(path, cwd)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                rows.append(f"{rel} ({size:,} bytes)")
            return self._result(ctx, f"{len(paths)} document(s):\n" + "\n".join(rows))

        if action == "search":
            query = str(kwargs.get("query") or "").strip()
            if not query:
                return self._error(ctx, "Error: query is required for search")
            limit = max(1, min(MAX_SEARCH_HITS, int(kwargs.get("limit") or 8)))
            chunks: list[tuple[str, str, str]] = []
            for path in _iter_docs(cwd):
                rel = os.path.relpath(path, cwd)
                for heading, body in _sections(path):
                    chunks.append((rel, heading, body))
            if not chunks:
                return self._result(ctx, "No documentation to search.")
            scores = score_documents(
                query, [f"{heading}\n{body}" for _rel, heading, body in chunks]
            )
            ranked = sorted(
                zip(chunks, scores, strict=True), key=lambda item: item[1], reverse=True
            )
            hits = [(chunk, score) for chunk, score in ranked if score > 0][:limit]
            if not hits:
                return self._result(ctx, f"No section matches '{query}'.")
            rows = []
            for (rel, heading, body), _score in hits:
                snippet = " ".join(body.split())[:240]
                rows.append(f"{rel} — {heading}\n    {snippet}")
            return self._result(ctx, "\n\n".join(rows))

        if action == "read":
            raw_path = str(kwargs.get("path") or "").strip()
            if not raw_path:
                return self._error(ctx, "Error: path is required for read")
            candidate = os.path.realpath(os.path.join(cwd, raw_path))
            root = os.path.realpath(cwd)
            if candidate != root and not candidate.startswith(root + os.sep):
                return self._error(ctx, f"Error: {raw_path} is outside the project")
            if not os.path.isfile(candidate):
                return self._error(ctx, f"Error: no such document: {raw_path}")

            section = str(kwargs.get("section") or "").strip().lower()
            if not section:
                with open(candidate, encoding="utf-8", errors="replace") as handle:
                    text = handle.read(MAX_READ_CHARS + 1)
                if len(text) > MAX_READ_CHARS:
                    text = text[:MAX_READ_CHARS] + "\n... (truncated)"
                return self._result(ctx, f"{raw_path}\n\n{text}")

            matches = [
                (heading, body)
                for heading, body in _sections(candidate)
                if section in heading.lower()
            ]
            if not matches:
                headings = ", ".join(heading for heading, _body in _sections(candidate)[:12])
                return self._error(
                    ctx, f"Error: no section matching '{section}'. Sections: {headings}"
                )
            body = "\n\n".join(f"{heading}\n{text}" for heading, text in matches)
            return self._result(ctx, body[:MAX_READ_CHARS])

        return self._error(ctx, "Error: action must be list, search or read")

    @staticmethod
    def _result(ctx: ToolContext, content: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=content)

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(OpenLaoKeDocsTool())
