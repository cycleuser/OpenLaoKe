"""Thinking viewer - Rich Panel-based interactive thinking display."""
from __future__ import annotations

from rich.panel import Panel


def format_thinking_panel(text: str, duration_ms: float = 0) -> Panel:
    lines = text.strip().split("\n")
    content_lines = []
    for line in lines:
        content_lines.append(f"  {line}")

    header = f"💭 Thought: {duration_ms:.0f}ms ({len(lines)} lines)"
    body = "\n".join(content_lines)

    return Panel(
        body,
        title=header,
        border_style="dim cyan",
        padding=(0, 1),
    )
