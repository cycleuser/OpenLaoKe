"""Render markdown into a self-contained HTML page for the browser.

The terminal is a poor place to read a long table or a wide code block. This
writes one HTML file with inline CSS - no CDN, no fonts to download, no
JavaScript - and leaves opening it to the caller. The markdown support is
deliberately small: headings, fenced code, inline code, bold/italic, links,
lists, blockquotes and rules, which is what an agent's summaries actually use.
"""

from __future__ import annotations

import html
import os
import re

PANEL_DIR = os.path.join(os.path.expanduser("~"), ".openlaoke", "panels")

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^```(\w*)\s*$")
_LIST = re.compile(r"^\s*([-*+]|\d+[.)])\s+(.*)$")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    """Escape first, then apply inline markup, so raw HTML cannot slip through."""
    escaped = html.escape(text, quote=False)
    escaped = _INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC.sub(r"<em>\1</em>", escaped)

    def link(match: re.Match[str]) -> str:
        label, href = match.group(1), match.group(2)
        if not href.startswith(("http://", "https://", "mailto:", "#")):
            return label
        return f'<a href="{html.escape(href)}" rel="noreferrer noopener">{label}</a>'

    return _LINK.sub(link, escaped)


def markdown_to_html(text: str) -> str:
    """Convert a small markdown subset to HTML."""
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    code_language = ""
    code_lines: list[str] = []
    list_kind = ""
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + " ".join(_inline(line.strip()) for line in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = ""

    for raw in lines:
        if in_code:
            if raw.strip().startswith("```"):
                language = (
                    f' class="language-{html.escape(code_language)}"' if code_language else ""
                )
                out.append(
                    f"<pre><code{language}>" + html.escape("\n".join(code_lines)) + "</code></pre>"
                )
                in_code = False
                code_lines = []
                code_language = ""
            else:
                code_lines.append(raw)
            continue

        fence = _FENCE.match(raw.strip())
        if fence:
            flush_paragraph()
            flush_list()
            in_code = True
            code_language = fence.group(1)
            continue

        if not raw.strip():
            flush_paragraph()
            flush_list()
            continue

        heading = _HEADING.match(raw)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            continue

        if raw.strip() in ("---", "***", "___"):
            flush_paragraph()
            flush_list()
            out.append("<hr>")
            continue

        if raw.startswith(">"):
            flush_paragraph()
            flush_list()
            out.append("<blockquote>" + _inline(raw.lstrip("> ").strip()) + "</blockquote>")
            continue

        item = _LIST.match(raw)
        if item:
            flush_paragraph()
            ordered = item.group(1)[0].isdigit()
            wanted = "ol" if ordered else "ul"
            if list_kind != wanted:
                flush_list()
                out.append(f"<{wanted}>")
                list_kind = wanted
            out.append("<li>" + _inline(item.group(2).strip()) + "</li>")
            continue

        paragraph.append(raw)

    if in_code and code_lines:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    flush_paragraph()
    flush_list()
    return "\n".join(out)


TEMPLATE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{
    margin: 0 auto; max-width: 52rem; padding: 2.5rem 1.5rem 4rem;
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: 16px; line-height: 1.75; color: #1f2328; background: #ffffff;
  }}
  h1, h2, h3, h4 {{ line-height: 1.3; margin: 2rem 0 0.75rem; font-weight: 600; }}
  h1 {{ font-size: 1.9rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.4rem; }}
  h2 {{ font-size: 1.45rem; }}
  h3 {{ font-size: 1.2rem; }}
  p, li {{ margin: 0.6rem 0; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88em;
          background: #f3f4f6; padding: 0.12em 0.35em; border-radius: 4px; }}
  pre {{ background: #f6f8fa; border: 1px solid #e5e7eb; border-radius: 8px;
         padding: 0.9rem 1rem; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; font-size: 0.86em; }}
  blockquote {{ margin: 1rem 0; padding: 0.1rem 1rem; border-left: 3px solid #d1d5db; color: #4b5563; }}
  a {{ color: #0b5fff; }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }}
  .meta {{ color: #6b7280; font-size: 0.85rem; margin-bottom: 1.5rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">Rendered by OpenLaoKe</div>
{body}
</body>
</html>
"""


def render_panel(title: str, markdown: str) -> str:
    """Return a complete HTML document."""
    return TEMPLATE.format(title=html.escape(title), body=markdown_to_html(markdown))


def write_panel(title: str, markdown: str, path: str | None = None) -> str:
    """Write the panel to disk and return the path."""
    target = path or os.path.join(PANEL_DIR, f"{_slug(title)}.html")
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    html_text = render_panel(title, markdown)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(html_text)
    os.replace(tmp, target)
    return target


def _slug(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff_-]+", "-", title.strip()) or "panel"
    return cleaned[:60]
