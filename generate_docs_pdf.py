#!/usr/bin/env python3
"""Generate PDF documentation using weasyprint with Chinese support."""

from __future__ import annotations

import os
import markdown
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration


def collect_md_files(root_dir: str) -> list[str]:
    """Collect markdown files."""
    md_files = []
    priority = ["README.md", "README_CN.md", "汇报.md", "AGENTS.md"]

    # Priority files first
    for p in priority:
        path = os.path.join(root_dir, p)
        if os.path.exists(path):
            md_files.append(path)

    # Other files
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ["__pycache__", ".git", "pdf_output", "venv", "node_modules"]
        ]
        for f in files:
            if f.endswith(".md"):
                path = os.path.join(root, f)
                if path not in md_files:
                    md_files.append(path)

    return md_files


def generate_docs_pdf(root_dir: str, output_path: str) -> None:
    """Generate PDF from markdown files."""
    md_files = collect_md_files(root_dir)
    print(f"Found {len(md_files)} markdown files")

    # Create HTML content
    html_parts = []
    html_parts.append("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OpenLaoKe Documentation</title>
    <style>
        @page {
            size: A4;
            margin: 2cm;
            @bottom-center {
                content: counter(page);
                font-size: 10pt;
                color: #666;
            }
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei";
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            font-size: 24pt;
            color: #1a1a1a;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        h2 {
            font-size: 18pt;
            color: #2a2a2a;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-top: 25px;
        }
        h3 {
            font-size: 14pt;
            color: #3a3a3a;
            margin-top: 20px;
        }
        code {
            font-family: "SF Mono", Monaco, Consolas, "Courier New", monospace;
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10pt;
        }
        pre {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
            font-size: 9pt;
        }
        pre code {
            background: transparent;
            padding: 0;
        }
        blockquote {
            border-left: 4px solid #3b82f6;
            margin-left: 0;
            padding-left: 15px;
            color: #555;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #e2e8f0;
            padding: 8px;
            text-align: left;
        }
        th {
            background: #f8fafc;
            font-weight: 600;
        }
        ul, ol {
            margin: 10px 0;
            padding-left: 25px;
        }
        li {
            margin: 5px 0;
        }
        .file-header {
            background: #3b82f6;
            color: white;
            padding: 15px;
            margin: 30px -2cm 20px -2cm;
            padding-left: 2cm;
            font-family: monospace;
            font-size: 12pt;
        }
        .title-page {
            text-align: center;
            padding-top: 150px;
        }
        .title-page h1 {
            font-size: 36pt;
            border: none;
            color: #1e40af;
        }
        .title-page .subtitle {
            font-size: 18pt;
            color: #64748b;
            margin-top: 20px;
        }
        .title-page .meta {
            font-size: 12pt;
            color: #94a3b8;
            margin-top: 100px;
        }
        strong {
            color: #1e40af;
        }
        hr {
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 30px 0;
        }
    </style>
</head>
<body>
""")

    # Add title page
    html_parts.append("""
    <div class="title-page">
        <h1>OpenLaoKe Project</h1>
        <div class="subtitle">Documentation Collection</div>
        <div class="meta">
            Complete project documentation<br>
            Generated: 2025
        </div>
    </div>
""")

    # Add table of contents
    html_parts.append("<h1>Table of Contents</h1><ul>")
    for i, filepath in enumerate(md_files, 1):
        rel_path = os.path.relpath(filepath, root_dir)
        html_parts.append(f"<li>{i}. {rel_path}</li>")
    html_parts.append("</ul>")

    # Process each file
    processed = 0
    for i, filepath in enumerate(md_files, 1):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if not content.strip():
                continue

            rel_path = os.path.relpath(filepath, root_dir)
            print(f"Processing [{i}/{len(md_files)}]: {rel_path}")

            # Add file header
            html_parts.append(f'<div class="file-header">[{i}/{len(md_files)}] {rel_path}</div>')

            # Convert markdown to HTML
            md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
            html_content = md.convert(content)
            html_parts.append(html_content)
            html_parts.append("<hr>")

            processed += 1

        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            continue

    html_parts.append("</body></html>")

    # Generate PDF
    html_string = "".join(html_parts)
    font_config = FontConfiguration()

    HTML(string=html_string).write_pdf(output_path, font_config=font_config)

    print(f"\nDocumentation PDF generated: {output_path}")
    print(f"Files processed: {processed}/{len(md_files)}")


if __name__ == "__main__":
    root_dir = "/Users/fred/Documents/GitHub/cycleuser/OpenLaoKe"
    output_dir = os.path.join(root_dir, "pdf_output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("Generating Documentation PDF with WeasyPrint")
    print("=" * 60)

    generate_docs_pdf(root_dir, os.path.join(output_dir, "OpenLaoKe_Documentation.pdf"))

    print("=" * 60)
    print("Done!")
    print("=" * 60)
