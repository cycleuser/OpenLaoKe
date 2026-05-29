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
