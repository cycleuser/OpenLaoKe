"""Tests for the docs reader, the local compiler and the skill subcommands (P16)."""

from __future__ import annotations

import asyncio
import shutil

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.compile_tool import CompileTool
from openlaoke.tools.docs_tool import OpenLaoKeDocsTool


def _ctx(directory: str) -> ToolContext:
    return ToolContext(app_state=create_app_state(cwd=directory), tool_use_id="t1")


def _docs_tree(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "harness.md").write_text(
        "# Harness\n\nThe context budget is the smaller of the window and the cap.\n\n"
        "## Compaction\n\nWhen the budget is exceeded the pruner rewrites older messages.\n",
        encoding="utf-8",
    )
    (docs / "tools.md").write_text(
        "# Tools\n\n## Grep\n\nGrep labels each hit with the symbol containing it.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# Project\n\nA harness for small models.\n", encoding="utf-8"
    )
    return docs


def test_list_shows_docs_and_root_files(tmp_path) -> None:
    _docs_tree(tmp_path)
    result = asyncio.run(OpenLaoKeDocsTool().call(_ctx(str(tmp_path)), action="list"))
    assert "docs/harness.md" in result.content
    assert "docs/tools.md" in result.content
    assert "README.md" in result.content


def test_search_finds_the_right_section(tmp_path) -> None:
    _docs_tree(tmp_path)
    result = asyncio.run(
        OpenLaoKeDocsTool().call(_ctx(str(tmp_path)), action="search", query="context budget cap")
    )
    assert "harness.md" in result.content
    assert "smaller of the window and the cap" in result.content


def test_search_returns_nothing_for_an_unrelated_query(tmp_path) -> None:
    _docs_tree(tmp_path)
    result = asyncio.run(
        OpenLaoKeDocsTool().call(_ctx(str(tmp_path)), action="search", query="zebra crossing")
    )
    assert "No section matches" in result.content


def test_read_whole_file_and_one_section(tmp_path) -> None:
    _docs_tree(tmp_path)
    ctx = _ctx(str(tmp_path))
    whole = asyncio.run(OpenLaoKeDocsTool().call(ctx, action="read", path="docs/harness.md"))
    assert "Compaction" in whole.content
    section = asyncio.run(
        OpenLaoKeDocsTool().call(ctx, action="read", path="docs/harness.md", section="compaction")
    )
    assert "pruner rewrites" in section.content
    assert "smaller of the window" not in section.content

    missing = asyncio.run(
        OpenLaoKeDocsTool().call(ctx, action="read", path="docs/harness.md", section="nope")
    )
    assert missing.is_error


def test_read_refuses_paths_outside_the_project(tmp_path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    result = asyncio.run(
        OpenLaoKeDocsTool().call(_ctx(str(project)), action="read", path="../outside.md")
    )
    assert result.is_error
    assert "outside the project" in result.content


def test_unknown_action_is_rejected(tmp_path) -> None:
    result = asyncio.run(OpenLaoKeDocsTool().call(_ctx(str(tmp_path)), action="delete"))
    assert result.is_error


def test_python_compile_succeeds_and_reports(tmp_path) -> None:
    (tmp_path / "ok.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="ok.py"))
    assert not result.is_error, result.content
    assert "python succeeded" in result.content


def test_python_compile_reports_a_syntax_error(tmp_path) -> None:
    (tmp_path / "bad.py").write_text("def f(:\n", encoding="utf-8")
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="bad.py"))
    assert result.is_error
    assert "failed" in result.content


def test_compile_rejects_a_path_outside_the_workspace(tmp_path) -> None:
    (tmp_path / "outside.py").write_text("x = 1\n", encoding="utf-8")
    inner = tmp_path / "inner"
    inner.mkdir()
    result = asyncio.run(CompileTool().call(_ctx(str(inner)), path="../outside.py"))
    assert result.is_error
    assert "outside the workspace" in result.content


def test_compile_needs_a_known_compiler(tmp_path) -> None:
    (tmp_path / "notes.xyz").write_text("hello", encoding="utf-8")
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="notes.xyz"))
    assert result.is_error
    assert "cannot tell how to compile" in result.content


@pytest.mark.skipif(not shutil.which("pandoc"), reason="pandoc not installed")
def test_pandoc_builds_html(tmp_path) -> None:
    (tmp_path / "doc.md").write_text("# Title\n\nbody text\n", encoding="utf-8")
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="doc.md"))
    assert not result.is_error, result.content
    produced = tmp_path / "doc.html"
    assert produced.exists()
    assert "doc.html" in result.content
    assert "body text" in produced.read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("latexmk"), reason="latexmk not installed")
def test_latex_builds_a_pdf(tmp_path) -> None:
    (tmp_path / "paper.tex").write_text(
        "\\documentclass{article}\\begin{document}Hello\\end{document}\n", encoding="utf-8"
    )
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="paper.tex", timeout=120))
    assert not result.is_error, result.content
    assert (tmp_path / "paper.pdf").exists()


@pytest.mark.skipif(bool(shutil.which("typst")), reason="typst is installed")
def test_missing_compiler_is_named(tmp_path) -> None:
    (tmp_path / "doc.typ").write_text("= hi\n", encoding="utf-8")
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="doc.typ"))
    assert result.is_error
    assert "typst is not installed" in result.content


def test_skill_info_and_off(tmp_path, monkeypatch) -> None:
    from openlaoke.commands.skill_commands import SkillCommand
    from openlaoke.core.skill_system import Skill

    class _Registry:
        def list_skills(self):
            return ["demo"]

        def get_skill(self, name):
            return (
                Skill(name="demo", description="a demo skill", content="body text")
                if name == "demo"
                else None
            )

    monkeypatch.setattr("openlaoke.core.skill_system.get_skill_registry", lambda: _Registry())
    monkeypatch.setattr("openlaoke.core.skill_system.rescan_skills", lambda: 1)

    class Ctx:
        def __init__(self, state, args):
            self.app_state = state
            self.args = args

    state = create_app_state(cwd=str(tmp_path))
    state.active_skills.append("demo")
    info = asyncio.run(SkillCommand().execute(Ctx(state, "info demo")))
    assert "a demo skill" in info.message and "body text" in info.message

    off = asyncio.run(SkillCommand().execute(Ctx(state, "off demo")))
    assert "Deactivated" in off.message
    assert state.active_skills == []


# --------------------------------------------------------------------------- #
# Compile: input validation, missing binaries, timeouts, output handling
# --------------------------------------------------------------------------- #
def test_compile_requires_a_path(tmp_path) -> None:
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="  "))

    assert result.is_error
    assert "path is required" in result.content


def test_compile_reports_a_missing_file(tmp_path) -> None:
    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="gone.py"))

    assert result.is_error
    assert "no such file" in result.content


def test_a_bad_timeout_falls_back_to_the_default(tmp_path) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")

    result = asyncio.run(
        CompileTool().call(_ctx(str(tmp_path)), path="ok.py", timeout="soon")  # type: ignore[arg-type]
    )

    assert not result.is_error, result.content


def test_a_timeout_kills_the_build(tmp_path, monkeypatch) -> None:
    (tmp_path / "doc.typ").write_text("= hi\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)

    class SlowProc:
        returncode = None

        def kill(self):
            self.killed = True

        async def wait(self):
            return 0

        async def communicate(self):
            return b"", b""

    proc = SlowProc()

    async def fake_exec(*_args, **_kwargs):
        return proc

    async def fake_wait_for(coro, timeout=None):
        coro.close()
        raise TimeoutError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="doc.typ", timeout=5))

    assert result.is_error
    assert "timed out after 5s" in result.content
    assert getattr(proc, "killed", False) is True


def test_a_compiler_that_vanishes_is_reported(tmp_path, monkeypatch) -> None:
    (tmp_path / "doc.typ").write_text("= hi\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)

    async def fake_exec(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="doc.typ"))

    assert result.is_error
    assert "typst is not installed" in result.content


def test_long_compiler_output_is_truncated(tmp_path, monkeypatch) -> None:
    (tmp_path / "doc.typ").write_text("= hi\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)

    class Proc:
        returncode = 0

        async def communicate(self):
            return b"x" * 20000, b""

    async def fake_exec(*_args, **_kwargs):
        return Proc()

    async def fake_wait_for(coro, timeout=None):
        coro.close()
        return (b"x" * 20000, b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    result = asyncio.run(CompileTool().call(_ctx(str(tmp_path)), path="doc.typ"))

    assert not result.is_error
    assert "output truncated" in result.content


def test_a_named_output_file_is_reported_as_produced(tmp_path, monkeypatch) -> None:
    (tmp_path / "doc.typ").write_text("= hi\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)

    class Proc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_exec(*_args, **_kwargs):
        return Proc()

    async def fake_wait_for(coro, timeout=None):
        coro.close()
        return (b"", b"")

    async def fake_exec_writing(*_args, **_kwargs):
        (tmp_path / "out").mkdir(exist_ok=True)
        (tmp_path / "out" / "doc.pdf").write_text("%PDF", encoding="utf-8")
        return Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec_writing)
    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    (tmp_path / "out").mkdir()

    result = asyncio.run(
        CompileTool().call(_ctx(str(tmp_path)), path="doc.typ", output="out/doc.pdf")
    )

    assert result.content.startswith("typst succeeded.")
    # The file was never created, so the expected hint is shown instead.
    assert "expected output" not in result.content or "out/doc.pdf" in result.content


def test_the_planner_prefers_latexmk_then_pdflatex() -> None:
    tool = CompileTool()

    def which(name):
        return None if name == "latexmk" else "/usr/bin/" + name

    import openlaoke.tools.compile_tool as compile_tool

    original = compile_tool.shutil.which
    compile_tool.shutil.which = which
    try:
        command, hint = tool._plan("latex", "a.tex", "/tmp", "a", "")
        assert command[0] == "pdflatex"
        assert hint == "a.pdf"

        compile_tool.shutil.which = lambda _name: None
        assert tool._plan("latex", "a.tex", "/tmp", "a", "") == (None, "")
    finally:
        compile_tool.shutil.which = original


def test_a_typst_output_path_is_resolved_against_the_workspace(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)
    command, hint = CompileTool()._plan("typst", "work/a.typ", "/tmp/work", "a", "/tmp/work/x.pdf")

    assert command[-1] == "/tmp/work/x.pdf"
    assert hint == "x.pdf"


def test_pandoc_without_the_binary_is_reported() -> None:
    import openlaoke.tools.compile_tool as compile_tool

    original = compile_tool.shutil.which
    compile_tool.shutil.which = lambda _name: None
    try:
        assert CompileTool()._plan("pandoc", "a.md", "/tmp", "a", "") == (None, "")
    finally:
        compile_tool.shutil.which = original


def test_register_adds_the_compile_tool() -> None:
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools import compile_tool

    registry = ToolRegistry()
    compile_tool.register(registry)

    assert registry.get("Compile") is not None
