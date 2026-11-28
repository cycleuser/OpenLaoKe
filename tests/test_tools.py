"""Tool tests: Bash, Read, Write, Edit, Glob, Grep."""

from __future__ import annotations

import os
import tempfile

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.bash_tool import BashTool
from openlaoke.tools.edit_tool import EditTool
from openlaoke.tools.glob_tool import GlobTool
from openlaoke.tools.grep_tool import GrepTool
from openlaoke.tools.read_tool import ReadTool
from openlaoke.tools.write_tool import WriteTool
from openlaoke.types.core_types import PermissionMode


def _ctx(d: str) -> ToolContext:
    s = create_app_state(cwd=d)
    return ToolContext(app_state=s, tool_use_id="t1")


@pytest.fixture
def tmp():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── BASH ───────────────────────────────────────────────────────────────────────


class TestBash:
    @pytest.mark.asyncio
    async def test_echo(self, tmp):
        r = await BashTool().call(_ctx(tmp), command="echo hello")
        assert not r.is_error and "hello" in r.content

    @pytest.mark.asyncio
    async def test_empty_command(self, tmp):
        r = await BashTool().call(_ctx(tmp), command="")
        assert r.is_error

    @pytest.mark.asyncio
    async def test_destructive_blocked(self, tmp):
        r = await BashTool().call(_ctx(tmp), command="rm -rf /")
        assert r.is_error

    @pytest.mark.asyncio
    async def test_nonzero_exit(self, tmp):
        s = create_app_state(cwd=tmp)
        s.permission_config.mode = PermissionMode.BYPASS
        ctx = ToolContext(app_state=s, tool_use_id="t1")
        r = await BashTool().call(ctx, command="exit 42")
        assert r.is_error

    def test_metadata(self):
        t = BashTool()
        assert t.name == "Bash"
        assert t.is_destructive
        assert t.requires_approval


# ── READ ───────────────────────────────────────────────────────────────────────


class TestRead:
    @pytest.mark.asyncio
    async def test_file(self, tmp):
        p = os.path.join(tmp, "f.txt")
        with open(p, "w") as f:
            f.write("hello\nworld\n")
        r = await ReadTool().call(_ctx(tmp), file_path=p)
        assert not r.is_error and "hello" in r.content

    @pytest.mark.asyncio
    async def test_directory(self, tmp):
        os.makedirs(os.path.join(tmp, "d"))
        with open(os.path.join(tmp, "f.txt"), "w") as f:
            f.write("x")
        r = await ReadTool().call(_ctx(tmp), file_path=tmp)
        assert not r.is_error and "d/" in r.content and "f.txt" in r.content

    @pytest.mark.asyncio
    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="mkfifo is POSIX only")
    async def test_a_pipe_is_refused_instead_of_blocking_the_loop(self, tmp):
        import asyncio
        import threading

        fifo = os.path.join(tmp, "pipe")
        os.mkfifo(fifo)
        collected = []

        def read() -> None:
            collected.append(asyncio.run(ReadTool().call(_ctx(tmp), file_path=fifo)))

        worker = threading.Thread(target=read, daemon=True)
        worker.start()
        worker.join(5)

        assert not worker.is_alive(), "Read blocked forever inside open() on a FIFO"
        assert collected[0].is_error
        assert "not a regular file" in collected[0].content

    @pytest.mark.asyncio
    async def test_offset_limit(self, tmp):
        p = os.path.join(tmp, "m.txt")
        with open(p, "w") as f:
            f.write("\n".join(f"L{i}" for i in range(1, 11)))
        r = await ReadTool().call(_ctx(tmp), file_path=p, offset=5, limit=2)
        body = [line for line in r.content.split("\n") if not line.startswith(("File:", "-"))]
        assert "L5" in "\n".join(body)

    @pytest.mark.asyncio
    async def test_utf8(self, tmp):
        p = os.path.join(tmp, "u.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("hello world\n")
        r = await ReadTool().call(_ctx(tmp), file_path=p)
        assert not r.is_error

    def test_metadata(self):
        t = ReadTool()
        assert t.is_read_only
        assert not t.is_destructive


# ── WRITE ──────────────────────────────────────────────────────────────────────


class TestWrite:
    @pytest.mark.asyncio
    async def test_new_file(self, tmp):
        p = os.path.join(tmp, "w.txt")
        await WriteTool().call(_ctx(tmp), file_path=p, content="data")
        with open(p) as f:
            assert f.read() == "data"

    @pytest.mark.asyncio
    async def test_overwrite(self, tmp):
        p = os.path.join(tmp, "w.txt")
        with open(p, "w") as f:
            f.write("old")
        await WriteTool().call(_ctx(tmp), file_path=p, content="new")
        with open(p) as f:
            assert f.read() == "new"

    @pytest.mark.asyncio
    async def test_mkdir(self, tmp):
        p = os.path.join(tmp, "a", "b", "c.txt")
        await WriteTool().call(_ctx(tmp), file_path=p, content="x")
        assert os.path.exists(p)

    @pytest.mark.asyncio
    async def test_empty_path(self, tmp):
        r = await WriteTool().call(_ctx(tmp), file_path="", content="x")
        assert r.is_error


# ── EDIT ───────────────────────────────────────────────────────────────────────


class TestEdit:
    @pytest.mark.asyncio
    async def test_replace(self, tmp):
        p = os.path.join(tmp, "e.txt")
        with open(p, "w") as f:
            f.write("hello world\n")
        await EditTool().call(_ctx(tmp), file_path=p, old_text="hello", new_text="hi")
        with open(p) as f:
            assert "hi world" in f.read()

    @pytest.mark.asyncio
    async def test_not_found(self, tmp):
        p = os.path.join(tmp, "e.txt")
        with open(p, "w") as f:
            f.write("content")
        r = await EditTool().call(_ctx(tmp), file_path=p, old_text="missing", new_text="x")
        assert r.is_error

    @pytest.mark.asyncio
    async def test_edit_includes_diff(self, tmp):
        fp = os.path.join(tmp, "diff_edit.txt")
        with open(fp, "w") as f:
            f.write("line1\nline2\nline3\n")
        r = await EditTool().call(
            _ctx(tmp), file_path=fp, old_text="line2\n", new_text="modified\n"
        )
        assert "@@" in r.content
        assert "-line2" in r.content
        assert "+modified" in r.content

    @pytest.mark.asyncio
    async def test_edit_uniqueness_check(self, tmp):
        fp = os.path.join(tmp, "unique.txt")
        with open(fp, "w") as f:
            f.write("same\nsame\n")
        r = await EditTool().call(_ctx(tmp), file_path=fp, old_text="same\n", new_text="diff\n")
        assert r.is_error
        assert "multiple locations" in r.content


# ── GLOB ───────────────────────────────────────────────────────────────────────


class TestGlob:
    @pytest.mark.asyncio
    async def test_py_files(self, tmp):
        os.makedirs(os.path.join(tmp, "s"))
        for n in ("a.py", "b.py", "c.txt"):
            with open(os.path.join(tmp, "s", n), "w") as f:
                f.write("")
        r = await GlobTool().call(_ctx(tmp), pattern="**/*.py", path=tmp)
        assert "a.py" in r.content and "b.py" in r.content and "c.txt" not in r.content

    def test_metadata(self):
        t = GlobTool()
        assert t.is_read_only


# ── GREP ───────────────────────────────────────────────────────────────────────


class TestGrep:
    @pytest.mark.asyncio
    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="mkfifo is POSIX only")
    async def test_a_pipe_in_the_tree_is_skipped_not_opened(self, tmp):
        import asyncio
        import threading

        with open(os.path.join(tmp, "real.py"), "w") as f:
            f.write("needle = 1\n")
        os.mkfifo(os.path.join(tmp, "pipe"))
        collected = []

        def grep() -> None:
            collected.append(asyncio.run(GrepTool().call(_ctx(tmp), pattern="needle", path=tmp)))

        worker = threading.Thread(target=grep, daemon=True)
        worker.start()
        worker.join(5)

        assert not worker.is_alive(), "Grep blocked forever inside open() on a FIFO"
        assert "needle" in collected[0].content
        assert not collected[0].is_error

    @pytest.mark.asyncio
    async def test_find_defs(self, tmp):
        with open(os.path.join(tmp, "code.py"), "w") as f:
            f.write("def foo():\n    pass\ndef bar():\n    pass\n")
        r = await GrepTool().call(_ctx(tmp), pattern="def \\w+", path=tmp)
        assert "foo" in r.content and "bar" in r.content

    @pytest.mark.asyncio
    async def test_case_insensitive(self, tmp):
        with open(os.path.join(tmp, "t.txt"), "w") as f:
            f.write("Hello\n")
        r = await GrepTool().call(_ctx(tmp), pattern="hello", case_sensitive=False)
        assert not r.is_error and "Hello" in r.content

    @pytest.mark.asyncio
    async def test_glob_filter(self, tmp):
        with open(os.path.join(tmp, "a.py"), "w") as f:
            f.write("import os\n")
        with open(os.path.join(tmp, "b.md"), "w") as f:
            f.write("import os\n")
        r = await GrepTool().call(_ctx(tmp), pattern="import", glob="*.py")
        assert "a.py" in r.content and "b.md" not in r.content


# ── GLOB edges ─────────────────────────────────────────────────────────────────


class TestGlobEdges:
    @pytest.mark.asyncio
    async def test_a_missing_pattern_is_refused(self, tmp):
        result = await GlobTool().call(_ctx(tmp))

        assert result.is_error
        assert "pattern is required" in result.content

    @pytest.mark.asyncio
    async def test_a_missing_directory_is_reported(self, tmp):
        result = await GlobTool().call(_ctx(tmp), pattern="*.py", path="nope")

        assert result.is_error
        assert "Directory not found" in result.content

    @pytest.mark.asyncio
    async def test_no_matches_says_so(self, tmp):
        result = await GlobTool().call(_ctx(tmp), pattern="*.nothing", path=tmp)

        assert not result.is_error
        assert result.content.startswith("No files matching")

    @pytest.mark.asyncio
    async def test_gitignore_directories_and_files_are_skipped(self, tmp):
        os.makedirs(os.path.join(tmp, "build"))
        with open(os.path.join(tmp, ".gitignore"), "w") as handle:
            handle.write("build/\nsecret.py\n")
        for name in ("keep.py", "secret.py", os.path.join("build", "gen.py")):
            full = os.path.join(tmp, name)
            with open(full, "w") as handle:
                handle.write("")

        result = await GlobTool().call(_ctx(tmp), pattern="**/*.py", path=tmp)

        assert "keep.py" in result.content
        assert "secret.py" not in result.content
        assert "gen.py" not in result.content

    @pytest.mark.asyncio
    async def test_a_flat_pattern_matches_the_basename(self, tmp):
        with open(os.path.join(tmp, "notes.md"), "w") as handle:
            handle.write("")

        result = await GlobTool().call(_ctx(tmp), pattern="*.md", path=tmp)

        assert "notes.md" in result.content

    @pytest.mark.asyncio
    async def test_the_result_list_is_capped(self, tmp):
        for index in range(1005):
            with open(os.path.join(tmp, f"f{index:04d}.txt"), "w") as handle:
                handle.write("")

        result = await GlobTool().call(_ctx(tmp), pattern="*.txt", path=tmp)

        assert result.content.startswith("Found 1000 file(s):")
        # Five files never made it into the list; the result has to say so
        # instead of looking complete.
        assert "capped at 1000 results" in result.content
        assert len(result.content.splitlines()[1:-2]) == 1000

    def test_register_adds_the_glob_tool(self, tmp):
        from openlaoke.core.tool import ToolRegistry
        from openlaoke.tools import glob_tool

        registry = ToolRegistry()
        glob_tool.register(registry)

        assert registry.get("Glob") is not None

    def test_the_pattern_matcher_handles_recursive_and_flat_globs(self):
        tool = GlobTool()

        assert tool._match_pattern("src/app.py", "**/*.py") is True
        # A leading **/ also matches zero directories, like globstar/gitignore.
        assert tool._match_pattern("app.py", "**/*.py") is True
        assert tool._match_pattern("src/app.py", "*.py") is True
        assert tool._match_pattern("src/app.js", "*.py") is False


class TestGlobSafetyAndMatching:
    @pytest.mark.asyncio
    async def test_a_rejected_read_path_is_returned_as_an_error(self, tmp, monkeypatch):
        import openlaoke.utils.path_safety as safety

        monkeypatch.setattr(safety, "validate_read_path", lambda _abs, _cwd: "Error: outside")

        result = await GlobTool().call(_ctx(tmp), pattern="*.py", path=tmp)

        assert result.is_error
        assert result.content == "Error: outside"

    def test_a_recursive_glob_that_does_not_match_falls_through(self):
        tool = GlobTool()

        # `**` in the middle keeps pathlib's single-component meaning, so this
        # is a miss rather than an exception.
        assert tool._match_pattern("a.py", "lib**/*.py") is False
