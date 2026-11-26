"""Tests for Panel rendering and Open validation (P17)."""

from __future__ import annotations

import asyncio

from openlaoke.core.panel_render import markdown_to_html, render_panel, write_panel
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.viewer_tools import OpenTool, PanelTool


def _ctx(directory: str) -> ToolContext:
    return ToolContext(app_state=create_app_state(cwd=directory), tool_use_id="t1")


def test_headings_lists_and_code_blocks() -> None:
    text = "# Title\n\nintro\n\n- one\n- two\n\n```python\nprint(1)\n```\n"
    html = markdown_to_html(text)
    assert "<h1>Title</h1>" in html
    assert "<p>intro</p>" in html
    assert "<ul>" in html and "<li>one</li>" in html
    assert '<code class="language-python">print(1)</code>' in html


def test_inline_markup_and_links() -> None:
    html = markdown_to_html("**bold** and *italic* and `code` and [site](https://example.com)")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<code>code</code>" in html
    assert '<a href="https://example.com"' in html


def test_raw_html_is_escaped() -> None:
    html = markdown_to_html('<script>alert("x")</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_links_are_not_emitted() -> None:
    html = markdown_to_html("[click](javascript:alert(1))")
    assert "javascript:" not in html
    assert "click" in html


def test_document_is_self_contained() -> None:
    page = render_panel("报告", "# 标题\n\n正文")
    assert page.startswith("<!doctype html>")
    assert "<style>" in page
    assert "<script" not in page and "http://" not in page.split("<body>")[0].split("<style>")[0]
    assert "标题" in page


def test_write_panel_creates_the_file(tmp_path) -> None:
    target = tmp_path / "panel.html"
    path = write_panel("demo", "# hi", str(target))
    assert path == str(target)
    assert target.exists()
    assert "<h1>hi</h1>" in target.read_text(encoding="utf-8")


def test_write_panel_default_location_is_under_home() -> None:
    path = write_panel("default location test", "# hi")
    assert ".openlaoke/panels" in path
    import os

    os.remove(path)


def test_panel_tool_reports_the_path(tmp_path) -> None:
    out = tmp_path / "p.html"
    result = asyncio.run(
        PanelTool().call(
            _ctx(str(tmp_path)), title="Summary", markdown="| a | b |\n|---|---|", path="p.html"
        )
    )
    assert not result.is_error
    assert str(out) in result.content
    assert out.exists()


def test_panel_tool_refuses_an_outside_path(tmp_path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    result = asyncio.run(PanelTool().call(_ctx(str(inner)), markdown="# x", path="../escape.html"))
    assert result.is_error
    assert not (tmp_path / "escape.html").exists()


def test_open_rejects_other_schemes(tmp_path) -> None:
    ctx = _ctx(str(tmp_path))
    for target in ("file:///etc/passwd", "javascript:alert(1)", "ssh://host"):
        result = asyncio.run(OpenTool().call(ctx, target=target))
        assert result.is_error or "outside" in result.content


def test_open_rejects_paths_outside_the_workspace(tmp_path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    result = asyncio.run(OpenTool().call(_ctx(str(inner)), target="../secret.txt"))
    assert result.is_error
    assert "outside the workspace" in result.content


def test_open_rejects_missing_files(tmp_path) -> None:
    result = asyncio.run(OpenTool().call(_ctx(str(tmp_path)), target="nope.txt"))
    assert result.is_error
    assert "no such file" in result.content


def test_open_requires_a_target(tmp_path) -> None:
    assert asyncio.run(OpenTool().call(_ctx(str(tmp_path)), target="  ")).is_error


# --------------------------------------------------------------------------- #
# the tools' own edges: missing input, browser opening, opener failures
# --------------------------------------------------------------------------- #
def test_panel_requires_markdown(tmp_path) -> None:
    result = asyncio.run(PanelTool().call(_ctx(str(tmp_path)), markdown="   "))

    assert result.is_error
    assert "markdown is required" in result.content


def test_panel_can_open_the_page_in_a_browser(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    launched: list[tuple] = []

    class FakeProc:
        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        launched.append((args, kwargs))
        return FakeProc()

    monkeypatch.setattr(viewer_tools, "_opener", lambda: ["open"])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = asyncio.run(
        PanelTool().call(_ctx(str(tmp_path)), markdown="# hi", path="p.html", open_in_browser=True)
    )

    assert not result.is_error
    assert launched and launched[0][0][0] == "open"
    assert "opened in the browser" in result.content


def test_panel_keeps_the_file_when_the_browser_fails(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    async def boom(*_args, **_kwargs):
        raise OSError("no display")

    monkeypatch.setattr(viewer_tools, "_opener", lambda: ["open"])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", boom)

    result = asyncio.run(
        PanelTool().call(_ctx(str(tmp_path)), markdown="# hi", path="p.html", open_in_browser=True)
    )

    assert not result.is_error
    assert "opened in the browser" not in result.content
    assert (tmp_path / "p.html").exists()


def test_panel_without_a_known_opener_still_writes(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    monkeypatch.setattr(viewer_tools, "_opener", lambda: None)

    result = asyncio.run(
        PanelTool().call(_ctx(str(tmp_path)), markdown="# hi", path="p.html", open_in_browser=True)
    )

    assert not result.is_error
    assert "opened in the browser" not in result.content


def test_open_runs_the_platform_opener(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    (tmp_path / "doc.md").write_text("x", encoding="utf-8")
    launched: list[tuple] = []

    class FakeProc:
        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        launched.append(args)
        return FakeProc()

    monkeypatch.setattr(viewer_tools, "_opener", lambda: ["open"])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = asyncio.run(OpenTool().call(_ctx(str(tmp_path)), target="doc.md"))

    assert not result.is_error
    assert result.content.startswith("Opened ")
    assert launched[0][0] == "open"


def test_open_accepts_an_http_url(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    opened: list[str] = []

    class FakeProc:
        async def wait(self):
            return 0

    async def fake_exec(*args, **_kwargs):
        opened.append(args[1])
        return FakeProc()

    monkeypatch.setattr(viewer_tools, "_opener", lambda: ["open"])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = asyncio.run(OpenTool().call(_ctx(str(tmp_path)), target="https://example.com"))

    assert not result.is_error
    assert opened == ["https://example.com"]


def test_open_says_so_when_no_opener_is_known(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    (tmp_path / "doc.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(viewer_tools, "_opener", lambda: None)

    result = asyncio.run(OpenTool().call(_ctx(str(tmp_path)), target="doc.md"))

    assert result.is_error
    assert "No system opener known" in result.content


def test_open_reports_an_opener_failure(tmp_path, monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    (tmp_path / "doc.md").write_text("x", encoding="utf-8")

    async def boom(*_args, **_kwargs):
        raise OSError("spawn failed")

    monkeypatch.setattr(viewer_tools, "_opener", lambda: ["open"])
    monkeypatch.setattr(asyncio, "create_subprocess_exec", boom)

    result = asyncio.run(OpenTool().call(_ctx(str(tmp_path)), target="doc.md"))

    assert result.is_error
    assert "spawn failed" in result.content


def test_register_adds_both_tools() -> None:
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools import viewer_tools

    registry = ToolRegistry()
    viewer_tools.register(registry)

    assert registry.get("Panel") is not None
    assert registry.get("Open") is not None


def test_the_opener_table_is_platform_specific(monkeypatch) -> None:
    from openlaoke.tools import viewer_tools

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    assert viewer_tools._opener() == ["open"]
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert viewer_tools._opener() == ["xdg-open"]
    monkeypatch.setattr("platform.system", lambda: "Plan9")
    assert viewer_tools._opener() is None
