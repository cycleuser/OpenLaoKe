"""Thinking viewer - Textual-based interactive thinking display with scroll and click-to-close."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Footer, Header, Static


class ThinkingContent(Static):
    """Displays the thinking text content."""


class ThinkingApp(App[str | None]):
    """Interactive thinking viewer.

    Features:
    - Mouse scroll through thinking content
    - Click anywhere to dismiss
    - Escape key to dismiss
    - Shows thinking duration in header
    """

    CSS = """
    Container {
        height: 100%;
    }
    ThinkingContent {
        padding: 1 2;
        overflow: auto;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Dismiss"),
        ("q", "dismiss", "Dismiss"),
    ]

    def __init__(self, thinking_text: str, duration_ms: float = 0, lines: int = 0) -> None:
        super().__init__()
        self._thinking = thinking_text
        self._duration = duration_ms
        self._lines = lines

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Container(ThinkingContent(self._thinking))
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Thought: {self._duration:.0f}ms ({self._lines} lines)"
        self.sub_title = "ESC / Q / Click to dismiss"

    def on_click(self) -> None:
        self.action_dismiss()

    def action_dismiss(self) -> None:
        self.exit("dismissed")


def show_thinking(thinking_text: str, duration_ms: float = 0) -> None:
    """Show thinking content in a Textual interactive viewer.

    Blocks until user dismisses with Escape, Q, or click.
    """
    lines = thinking_text.strip().split("\n")
    app = ThinkingApp(thinking_text=thinking_text, duration_ms=duration_ms, lines=len(lines))
    app.run()
