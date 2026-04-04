#!/usr/bin/env python3
"""Generate SVG figures for the article."""

from __future__ import annotations

import os
from pathlib import Path

try:
    import svgwrite
except ImportError:
    print("Installing svgwrite...")
    os.system("pip install svgwrite")
    import svgwrite


def create_architecture_comparison() -> None:
    """Create architecture comparison diagram."""
    dwg = svgwrite.Drawing("architecture_comparison.svg", size=("1000px", "600px"))

    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    def draw_box(x: float, y: float, w: float, h: float, text: str, color: str) -> None:
        dwg.add(
            dwg.rect(
                insert=(x, y), size=(w, h), rx=5, ry=5, fill=color, stroke="#333", stroke_width=1.5
            )
        )
        lines = text.split("\n")
        line_height = 16
        total_height = len(lines) * line_height
        start_y = y + (h - total_height) / 2 + line_height - 4
        for i, line in enumerate(lines):
            dwg.add(
                dwg.text(
                    line,
                    insert=(x + w / 2, start_y + i * line_height),
                    text_anchor="middle",
                    font_size="12px",
                    font_family="Arial",
                    fill="black" if color != "#333" else "white",
                )
            )

    def draw_arrow(x1: float, y1: float, x2: float, y2: float, label: str = "") -> None:
        dwg.add(
            dwg.line(
                start=(x1, y1),
                end=(x2, y2),
                stroke="#666",
                stroke_width=1.5,
                stroke_dasharray="4,2",
            )
        )
        if label:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            dwg.add(
                dwg.text(
                    label,
                    insert=(mid_x, mid_y - 5),
                    text_anchor="middle",
                    font_size="9px",
                    font_family="Arial",
                    fill="#666",
                )
            )

    col_width = 280
    col_gap = 40
    start_x = 50

    dwg.add(
        dwg.text(
            "OpenLaoKe",
            insert=(start_x + col_width / 2, 30),
            text_anchor="middle",
            font_size="14px",
            font_weight="bold",
            font_family="Arial",
        )
    )
    draw_box(start_x + 20, 50, col_width - 40, 40, "REPL Loop", "#4A90D9")
    draw_arrow(start_x + col_width / 2, 90, start_x + col_width / 2, 110, "")
    draw_box(start_x + 20, 110, col_width - 40, 40, "MultiProviderClient", "#5BA0E9")
    draw_arrow(start_x + col_width / 2, 150, start_x + col_width / 2, 170, "")
    draw_box(start_x + 20, 170, col_width - 40, 40, "AppState", "#6BB0F9")
    draw_arrow(start_x + col_width / 2, 210, start_x + col_width / 2, 230, "")
    draw_box(start_x + 20, 230, col_width - 40, 40, "ToolRegistry", "#7BC0FF")
    draw_box(
        start_x + 20,
        290,
        col_width - 40,
        100,
        "Tools:\n• Bash\n• Read/Write/Edit\n• Grep/Glob\n• WebFetch",
        "#E8F4FF",
    )
    draw_arrow(start_x + col_width / 2, 280, start_x + col_width / 2, 290, "")

    col2_x = start_x + col_width + col_gap
    dwg.add(
        dwg.text(
            "OpenCode",
            insert=(col2_x + col_width / 2, 30),
            text_anchor="middle",
            font_size="14px",
            font_weight="bold",
            font_family="Arial",
        )
    )
    draw_box(col2_x + 20, 50, col_width - 40, 40, "TUI (Ink/React)", "#D94A4A")
    draw_arrow(col2_x + col_width / 2, 90, col2_x + col_width / 2, 110, "")
    draw_box(col2_x + 20, 110, col_width - 40, 40, "Agent", "#E95A5A")
    draw_arrow(col2_x + col_width / 2, 150, col2_x + col_width / 2, 170, "")
    draw_box(col2_x + 20, 170, col_width - 40, 40, "State (SQLite)", "#F96A6A")
    draw_arrow(col2_x + col_width / 2, 210, col2_x + col_width / 2, 230, "")
    draw_box(col2_x + 20, 230, col_width - 40, 40, "Tools (Effect)", "#FA7A7A")
    draw_box(
        col2_x + 20,
        290,
        col_width - 40,
        100,
        "Tools:\n• Bash\n• Read/Write/Edit\n• Grep/Glob\n• WebFetch",
        "#FFE8E8",
    )
    draw_arrow(col2_x + col_width / 2, 280, col2_x + col_width / 2, 290, "")

    col3_x = col2_x + col_width + col_gap
    dwg.add(
        dwg.text(
            "Claude Code",
            insert=(col3_x + col_width / 2, 30),
            text_anchor="middle",
            font_size="14px",
            font_weight="bold",
            font_family="Arial",
        )
    )
    draw_box(col3_x + 20, 50, col_width - 40, 40, "CLI", "#4AD94A")
    draw_arrow(col3_x + col_width / 2, 90, col3_x + col_width / 2, 110, "")
    draw_box(col3_x + 20, 110, col_width - 40, 40, "QueryEngine", "#5AE95A")
    draw_arrow(col3_x + col_width / 2, 150, col3_x + col_width / 2, 170, "")
    draw_box(col3_x + 20, 170, col_width - 40, 40, "Store", "#6AFA6A")
    draw_arrow(col3_x + col_width / 2, 210, col3_x + col_width / 2, 230, "")
    draw_box(col3_x + 20, 230, col_width - 40, 40, "Tools", "#7AFF7A")
    draw_box(
        col3_x + 20,
        290,
        col_width - 40,
        100,
        "Tools:\n• Bash\n• Read/Write/Edit\n• Grep/Glob\n• MCP Servers",
        "#E8FFE8",
    )
    draw_arrow(col3_x + col_width / 2, 280, col3_x + col_width / 2, 290, "")

    dwg.add(
        dwg.rect(insert=(start_x, 420), size=(910, 40), rx=5, ry=5, fill="#F5F5F5", stroke="#CCC")
    )
    dwg.add(
        dwg.text(
            "LLM Provider APIs (Anthropic, OpenAI, Ollama, etc.)",
            insert=(start_x + 455, 445),
            text_anchor="middle",
            font_size="12px",
            font_family="Arial",
        )
    )

    for col_x in [start_x + col_width / 2, col2_x + col_width / 2, col3_x + col_width / 2]:
        dwg.add(
            dwg.line(
                start=(col_x, 390),
                end=(col_x, 420),
                stroke="#666",
                stroke_width=1.5,
                stroke_dasharray="4,2",
            )
        )

    dwg.save()
    print("✓ architecture_comparison.svg")


def create_tool_invocation_flow() -> None:
    """Create tool invocation flow diagram."""
    dwg = svgwrite.Drawing("tool_invocation_flow.svg", size=("900px", "500px"))

    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    def draw_box(x: float, y: float, w: float, h: float, text: str, color: str) -> None:
        dwg.add(
            dwg.rect(
                insert=(x, y), size=(w, h), rx=8, ry=8, fill=color, stroke="#333", stroke_width=1.5
            )
        )
        lines = text.split("\n")
        line_height = 15
        total_height = len(lines) * line_height
        start_y = y + (h - total_height) / 2 + line_height - 3
        for i, line in enumerate(lines):
            dwg.add(
                dwg.text(
                    line,
                    insert=(x + w / 2, start_y + i * line_height),
                    text_anchor="middle",
                    font_size="11px",
                    font_family="Arial",
                    fill="black",
                )
            )

    def draw_arrow(x1: float, y1: float, x2: float, y2: float) -> None:
        dwg.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke="#333", stroke_width=2))
        angle = 0.5
        arrow_len = 8
        import math

        theta = math.atan2(y2 - y1, x2 - x1)
        dwg.add(
            dwg.line(
                start=(x2, y2),
                end=(
                    x2 - arrow_len * math.cos(theta - angle),
                    y2 - arrow_len * math.sin(theta - angle),
                ),
                stroke="#333",
                stroke_width=2,
            )
        )
        dwg.add(
            dwg.line(
                start=(x2, y2),
                end=(
                    x2 - arrow_len * math.cos(theta + angle),
                    y2 - arrow_len * math.sin(theta + angle),
                ),
                stroke="#333",
                stroke_width=2,
            )
        )

    box_w = 130
    box_h = 45

    positions = [
        (80, 60, "User Input", "#E3F2FD"),
        (260, 60, "LLM\nInference", "#FFF3E0"),
        (440, 60, "Tool Selection", "#E8F5E9"),
        (620, 60, "Permission\nCheck", "#FFF9C4"),
        (800, 60, "Decision", "#F3E5F5"),
    ]

    for x, y, text, color in positions[:4]:
        draw_box(x, y, box_w, box_h, text, color)
        if x < 700:
            draw_arrow(x + box_w, y + box_h / 2, x + box_w + 30, y + box_h / 2)

    draw_box(620, 60, box_w, box_h, "Permission\nCheck", "#FFF9C4")
    draw_arrow(620 + box_w, 60 + box_h / 2, 800, 60 + box_h / 2)

    dwg.add(
        dwg.polygon(
            points=[
                (800, 60 + box_h / 2),
                (830, 60 + 10),
                (870, 60 + box_h / 2),
                (830, 60 + box_h - 10),
            ],
            fill="#F3E5F5",
            stroke="#333",
        )
    )
    dwg.add(
        dwg.text(
            "?",
            insert=(835, 60 + box_h / 2 + 4),
            text_anchor="middle",
            font_size="14px",
            font_weight="bold",
        )
    )

    draw_box(600, 180, box_w, box_h, "Ask User\nPermission", "#FFCDD2")
    draw_arrow(835, 60 + box_h, 835, 110)
    dwg.add(dwg.text("Deny", insert=(855, 100), font_size="10px", fill="#D32F2F"))
    draw_arrow(835, 110, 835, 155)
    draw_arrow(835, 155, 665 + box_w / 2, 180)
    dwg.add(dwg.text("Retry", insert=(750, 165), font_size="10px", fill="#666"))

    draw_box(260, 300, box_w, box_h, "Tool\nExecution", "#C8E6C9")
    draw_arrow(835, 155, 260 + box_w / 2, 300)
    dwg.add(dwg.text("Allow", insert=(550, 250), font_size="10px", fill="#388E3C"))

    draw_box(440, 300, box_w, box_h, "Result\nProcessing", "#B3E5FC")
    draw_arrow(260 + box_w, 300 + box_h / 2, 440, 300 + box_h / 2)

    draw_box(620, 300, box_w, box_h, "Continue\nConversation", "#D1C4E9")
    draw_arrow(440 + box_w, 300 + box_h / 2, 620, 300 + box_h / 2)

    draw_arrow(620 + box_w / 2, 300, 260 + box_w / 2, 60 + box_h)
    dwg.add(dwg.text("Loop", insert=(450, 200), font_size="10px", fill="#666"))

    dwg.add(dwg.rect(insert=(50, 400), size=(800, 70), rx=5, ry=5, fill="#FAFAFA", stroke="#DDD"))
    dwg.add(
        dwg.text(
            "Key Components:",
            insert=(70, 425),
            font_size="12px",
            font_weight="bold",
            font_family="Arial",
        )
    )
    dwg.add(
        dwg.text(
            "• Permission System: Validates tool access before execution",
            insert=(70, 445),
            font_size="11px",
            font_family="Arial",
        )
    )
    dwg.add(
        dwg.text(
            "• Tool Registry: Manages available tools and their schemas",
            insert=(70, 460),
            font_size="11px",
            font_family="Arial",
        )
    )

    dwg.save()
    print("✓ tool_invocation_flow.svg")


def create_state_management_comparison() -> None:
    """Create state management comparison diagram."""
    dwg = svgwrite.Drawing("state_management_comparison.svg", size=("950px", "400px"))

    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    def draw_box(x: float, y: float, w: float, h: float, text: str, color: str) -> None:
        dwg.add(
            dwg.rect(
                insert=(x, y), size=(w, h), rx=5, ry=5, fill=color, stroke="#333", stroke_width=1.5
            )
        )
        lines = text.split("\n")
        line_height = 14
        total_height = len(lines) * line_height
        start_y = y + (h - total_height) / 2 + line_height - 3
        for i, line in enumerate(lines):
            dwg.add(
                dwg.text(
                    line,
                    insert=(x + w / 2, start_y + i * line_height),
                    text_anchor="middle",
                    font_size="11px",
                    font_family="Arial",
                    fill="black",
                )
            )

    def draw_arrow(x1: float, y1: float, x2: float, y2: float) -> None:
        dwg.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke="#666", stroke_width=1.5))

    col_width = 280
    start_x = 50

    dwg.add(
        dwg.text(
            "OpenLaoKe: Centralized Dataclass",
            insert=(start_x + col_width / 2, 25),
            text_anchor="middle",
            font_size="12px",
            font_weight="bold",
            font_family="Arial",
        )
    )

    draw_box(start_x + 30, 50, col_width - 60, 50, "AppState\ndataclass", "#4A90D9")

    boxes = [
        (start_x + 20, 120, "messages: list[Message]"),
        (start_x + 20, 155, "tasks: dict[str, Task]"),
        (start_x + 20, 190, "permissions: PermissionConfig"),
        (start_x + 20, 225, "token_usage: TokenUsage"),
    ]
    for x, y, text in boxes:
        draw_box(x, y, col_width - 40, 30, text, "#E3F2FD")
        draw_arrow(start_x + col_width / 2, 100, start_x + col_width / 2, 120)

    draw_box(start_x + 30, 280, col_width - 60, 40, "JSON File\nPersistence", "#FFE0B2")
    draw_arrow(start_x + col_width / 2, 255, start_x + col_width / 2, 280)

    col2_x = start_x + col_width + 50
    dwg.add(
        dwg.text(
            "OpenCode: SQLite + Effect",
            insert=(col2_x + col_width / 2, 25),
            text_anchor="middle",
            font_size="12px",
            font_weight="bold",
            font_family="Arial",
        )
    )

    draw_box(col2_x + 30, 50, col_width - 60, 50, "State\nService", "#D94A4A")

    boxes2 = [
        (col2_x + 20, 120, "Session Table"),
        (col2_x + 20, 155, "Message Table"),
        (col2_x + 20, 190, "Tool Result Table"),
        (col2_x + 20, 225, "Project Table"),
    ]
    for x, y, text in boxes2:
        draw_box(x, y, col_width - 40, 30, text, "#FFEBEE")
        draw_arrow(col2_x + col_width / 2, 100, col2_x + col_width / 2, 120)

    draw_box(col2_x + 30, 280, col_width - 60, 40, "SQLite\nDatabase", "#FFCDD2")
    draw_arrow(col2_x + col_width / 2, 255, col2_x + col_width / 2, 280)

    col3_x = col2_x + col_width + 50
    dwg.add(
        dwg.text(
            "Claude Code: Store Pattern",
            insert=(col3_x + col_width / 2, 25),
            text_anchor="middle",
            font_size="12px",
            font_weight="bold",
            font_family="Arial",
        )
    )

    draw_box(col3_x + 30, 50, col_width - 60, 50, "Store\n(React-like)", "#4AD94A")

    boxes3 = [
        (col3_x + 20, 120, "messages: Message[]"),
        (col3_x + 20, 155, "tools: ToolRegistry"),
        (col3_x + 20, 190, "permissionContext"),
        (col3_x + 20, 225, "queryEngine"),
    ]
    for x, y, text in boxes3:
        draw_box(x, y, col_width - 40, 30, text, "#E8F5E9")
        draw_arrow(col3_x + col_width / 2, 100, col3_x + col_width / 2, 120)

    draw_box(col3_x + 30, 280, col_width - 60, 40, "Transcript\nFiles", "#C8E6C9")
    draw_arrow(col3_x + col_width / 2, 255, col3_x + col_width / 2, 280)

    dwg.add(dwg.rect(insert=(50, 350), size=("90%", 40), rx=5, ry=5, fill="#F5F5F5", stroke="#CCC"))
    dwg.add(
        dwg.text(
            "Trade-offs: Simplicity (JSON) vs Queryability (SQLite) vs Readability (Transcript)",
            insert=(475, 375),
            text_anchor="middle",
            font_size="11px",
            font_family="Arial",
        )
    )

    dwg.save()
    print("✓ state_management_comparison.svg")


def create_multi_provider_flow() -> None:
    """Create multi-provider integration flow diagram."""
    dwg = svgwrite.Drawing("multi_provider_flow.svg", size=("1000px", "600px"))

    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    def draw_box(x: float, y: float, w: float, h: float, text: str, color: str) -> None:
        dwg.add(
            dwg.rect(
                insert=(x, y), size=(w, h), rx=5, ry=5, fill=color, stroke="#333", stroke_width=1.5
            )
        )
        lines = text.split("\n")
        line_height = 13
        total_height = len(lines) * line_height
        start_y = y + (h - total_height) / 2 + line_height - 3
        for i, line in enumerate(lines):
            dwg.add(
                dwg.text(
                    line,
                    insert=(x + w / 2, start_y + i * line_height),
                    text_anchor="middle",
                    font_size="10px",
                    font_family="Arial",
                    fill="black",
                )
            )

    def draw_arrow(x1: float, y1: float, x2: float, y2: float, label: str = "") -> None:
        dwg.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke="#333", stroke_width=1.5))
        if label:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            dwg.add(dwg.text(label, insert=(mid_x + 10, mid_y), font_size="9px", fill="#666"))

    dwg.add(
        dwg.text(
            "Multi-Provider API Integration Architecture",
            insert=(500, 25),
            text_anchor="middle",
            font_size="14px",
            font_weight="bold",
            font_family="Arial",
        )
    )

    draw_box(400, 50, 200, 40, "Application Layer\n(REPL / Agent)", "#E3F2FD")

    draw_arrow(500, 90, 500, 120)
    draw_box(400, 120, 200, 40, "MultiProviderClient", "#BBDEFB")

    draw_box(100, 200, 160, 50, "Anthropic\nAdapter", "#C8E6C9")
    draw_box(300, 200, 160, 50, "OpenAI\nAdapter", "#FFF9C4")
    draw_box(500, 200, 160, 50, "MiniMax\nAdapter", "#FFCCBC")
    draw_box(700, 200, 160, 50, "Ollama\nAdapter", "#E1BEE7")

    draw_arrow(450, 160, 180, 200)
    draw_arrow(480, 160, 380, 200)
    draw_arrow(520, 160, 580, 200)
    draw_arrow(550, 160, 780, 200)

    draw_box(400, 160, 200, 30, "Message Format Conversion", "#F5F5F5")

    draw_box(100, 290, 160, 50, "Claude API\n(streaming)", "#A5D6A7")
    draw_box(300, 290, 160, 50, "OpenAI API\n(streaming)", "#FFF59D")
    draw_box(500, 290, 160, 50, "MiniMax API\n(streaming)", "#FFAB91")
    draw_box(700, 290, 160, 50, "Local LLM\n(streaming)", "#CE93D8")

    draw_arrow(180, 250, 180, 290)
    draw_arrow(380, 250, 380, 290)
    draw_arrow(580, 250, 580, 290)
    draw_arrow(780, 250, 780, 290)

    draw_box(
        50,
        400,
        300,
        150,
        "Message Conversion:\n\n• System prompt formatting\n• Tool schema translation\n• Streaming normalization\n• Token counting\n• Cost calculation",
        "#E8F5E9",
    )

    draw_box(
        350,
        400,
        300,
        150,
        "Error Handling:\n\n• Retry logic with backoff\n• Rate limit handling\n• Timeout management\n• Connection pooling\n• Fallback providers",
        "#FFF3E0",
    )

    draw_box(
        650,
        400,
        300,
        150,
        "Configuration:\n\n• API key management\n• Base URL customization\n• Model selection\n• Proxy support\n• Provider-specific options",
        "#F3E5F5",
    )

    draw_arrow(500, 340, 200, 400)
    draw_arrow(500, 340, 500, 400)
    draw_arrow(500, 340, 800, 400)

    dwg.save()
    print("✓ multi_provider_flow.svg")


def main() -> None:
    """Generate all SVG figures."""
    output_dir = Path(__file__).parent.parent
    os.chdir(output_dir)

    print("Generating SVG figures...")
    create_architecture_comparison()
    create_tool_invocation_flow()
    create_state_management_comparison()
    create_multi_provider_flow()
    print("\nAll figures generated successfully!")


if __name__ == "__main__":
    main()
