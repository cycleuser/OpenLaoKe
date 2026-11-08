"""Panel and Open tools: show things the terminal cannot.

``Panel`` renders markdown to a standalone HTML file with inline CSS, so a wide
table or a long code listing can be read in a browser without the terminal
wrapping it into soup. ``Open`` hands a path or a URL to the platform opener,
refusing anything that is not http(s) or a file inside the workspace.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import platform
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.panel_render import write_panel
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

PLATFORM_OPENERS = {
    "Darwin": ["open"],
    "Linux": ["xdg-open"],
    "Windows": ["cmd", "/c", "start", ""],
}


class PanelInput(BaseModel):
    title: str = Field(
        default="Panel", description="Title shown at the top and used for the file name"
    )
    markdown: str = Field(description="Markdown to render")
    path: str = Field(
        default="",
        description="Where to write the HTML; defaults to ~/.openlaoke/panels/<title>.html",
    )
    open_in_browser: bool = Field(
        default=False, description="Open the rendered page with the system opener"
    )


class PanelTool(Tool):
    """Render markdown to a standalone HTML page."""

    name = "Panel"
    description = (
        "Render a markdown summary into a single self-contained HTML file and return its path. "
        "Use it for long tables, wide code, or anything that reads badly in a terminal; pass "
        "open_in_browser=true to show it immediately. Supports headings, lists, fenced code, "
        "inline code, bold/italic, links, quotes and rules."
    )
    input_schema = PanelInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        title = str(kwargs.get("title") or "Panel").strip()
        markdown = str(kwargs.get("markdown") or "")
        if not markdown.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content="Error: markdown is required", is_error=True
            )

        target = str(kwargs.get("path") or "").strip()
        path = None
        if target:
            resolved = os.path.realpath(os.path.join(ctx.app_state.get_cwd(), target))
            root = os.path.realpath(ctx.app_state.get_cwd())
            if resolved != root and not resolved.startswith(root + os.sep):
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: {target} is outside the workspace",
                    is_error=True,
                )
            path = resolved

        written = write_panel(title, markdown, path)
        opened = ""
        if kwargs.get("open_in_browser"):
            opener = _opener()
            if opener:
                with contextlib.suppress(Exception):
                    proc = await asyncio.create_subprocess_exec(
                        *opener,
                        written,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(proc.wait(), timeout=10)
                    opened = " and opened in the browser"
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Rendered {len(markdown):,} characters to {written}{opened}.",
        )


class OpenInput(BaseModel):
    target: str = Field(description="An http(s) URL, or a path inside the workspace")


class OpenTool(Tool):
    """Open a URL or file with the system default application."""

    name = "Open"
    description = (
        "Open an http(s) URL or a workspace file in the system default application. Refuses "
        "anything else: no file:// URLs, no other schemes, no paths outside the workspace."
    )
    input_schema = OpenInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        target = str(kwargs.get("target") or "").strip()
        if not target:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id, content="Error: target is required", is_error=True
            )

        if target.startswith(("http://", "https://")):
            resolved = target
        elif "://" in target or target.lower().startswith(("javascript:", "data:", "file:")):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: only http(s) URLs and workspace paths are allowed, not {target[:40]}",
                is_error=True,
            )
        else:
            root = os.path.realpath(ctx.app_state.get_cwd())
            candidate = os.path.realpath(os.path.join(root, target))
            if candidate != root and not candidate.startswith(root + os.sep):
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: {target} is outside the workspace",
                    is_error=True,
                )
            if not os.path.exists(candidate):
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: no such file: {target}",
                    is_error=True,
                )
            resolved = candidate

        opener = _opener()
        if not opener:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"No system opener known for {platform.system()}; open {resolved} yourself.",
                is_error=True,
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                *opener,
                resolved,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=15)
        except (OSError, TimeoutError) as exc:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Could not open {resolved}: {exc}",
                is_error=True,
            )
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=f"Opened {resolved}.")


def _opener() -> list[str] | None:
    return PLATFORM_OPENERS.get(platform.system())


def register(registry: ToolRegistry) -> None:
    registry.register(PanelTool())
    registry.register(OpenTool())
