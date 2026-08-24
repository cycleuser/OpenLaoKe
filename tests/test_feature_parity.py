"""Tests for feature parity upgrades: Edit.replace_all and Grep context/multiline."""

from __future__ import annotations

import os
import tempfile

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext


def _ctx(d: str) -> ToolContext:
    s = create_app_state(cwd=d)
    return ToolContext(app_state=s, tool_use_id="t_feat")


@pytest.fixture
def tmp():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestEditReplaceAll:
    @pytest.mark.asyncio
    async def test_replace_all_multiple(self, tmp):
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "multi.txt")
        with open(p, "w") as f:
            f.write("foo bar foo baz foo")
        r = await EditTool().call(
            _ctx(tmp), file_path=p, old_text="foo", new_text="qux", replace_all=True
        )
        assert not r.is_error
        assert "3 occurrence(s)" in r.content
        with open(p) as f:
            assert f.read() == "qux bar qux baz qux"

    @pytest.mark.asyncio
    async def test_replace_all_single(self, tmp):
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "single.txt")
        with open(p, "w") as f:
            f.write("only one here")
        r = await EditTool().call(
            _ctx(tmp), file_path=p, old_text="one", new_text="1", replace_all=True
        )
        assert not r.is_error
        with open(p) as f:
            assert f.read() == "only 1 here"

    @pytest.mark.asyncio
    async def test_without_replace_all_still_rejects_multiple(self, tmp):
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "m.txt")
        with open(p, "w") as f:
            f.write("a b a")
        r = await EditTool().call(_ctx(tmp), file_path=p, old_text="a", new_text="c")
        assert r.is_error
        assert "replace_all" in r.content

    @pytest.mark.asyncio
    async def test_replace_all_includes_diff(self, tmp):
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "d.txt")
        with open(p, "w") as f:
            f.write("x\ny\nx\n")
        r = await EditTool().call(
            _ctx(tmp), file_path=p, old_text="x", new_text="z", replace_all=True
        )
        assert not r.is_error
        assert "@@" in r.content


class TestGrepContextAndMultiline:
    @pytest.mark.asyncio
    async def test_context_lines(self, tmp):
        from openlaoke.tools.grep_tool import GrepTool

        p = os.path.join(tmp, "ctx.txt")
        with open(p, "w") as f:
            f.write("line1\nline2\nTARGET\nline4\nline5\n")
        r = await GrepTool().call(_ctx(tmp), pattern="TARGET", path=tmp, context=1)
        assert not r.is_error
        assert "ctx.txt:3: TARGET" in r.content
        assert "ctx.txt-2- line2" in r.content
        assert "ctx.txt-4- line4" in r.content

    @pytest.mark.asyncio
    async def test_context_groups_separated(self, tmp):
        from openlaoke.tools.grep_tool import GrepTool

        p = os.path.join(tmp, "groups.txt")
        with open(p, "w") as f:
            f.write("A\nx\nx\nx\nB\nx\nx\nx\nA\n")
        r = await GrepTool().call(_ctx(tmp), pattern="A", path=tmp, context=1, case_sensitive=True)
        assert "--" in r.content
        assert r.content.count("A") >= 2

    @pytest.mark.asyncio
    async def test_multiline_match(self, tmp):
        from openlaoke.tools.grep_tool import GrepTool

        p = os.path.join(tmp, "ml.py")
        with open(p, "w") as f:
            f.write("def foo(\n    a,\n    b,\n):\n    pass\n")
        r = await GrepTool().call(_ctx(tmp), pattern=r"def foo\(\n\s+a,", path=tmp, multiline=True)
        assert not r.is_error
        assert "ml.py:1" in r.content

    @pytest.mark.asyncio
    async def test_multiline_disabled_no_match(self, tmp):
        from openlaoke.tools.grep_tool import GrepTool

        p = os.path.join(tmp, "ml2.py")
        with open(p, "w") as f:
            f.write("def foo(\n    a,\n):\n    pass\n")
        r = await GrepTool().call(_ctx(tmp), pattern=r"foo\(\n\s+a,", path=tmp)
        assert "No matches" in r.content

    @pytest.mark.asyncio
    async def test_count_mode_ignores_context_lines(self, tmp):
        from openlaoke.tools.grep_tool import GrepTool

        p = os.path.join(tmp, "c.txt")
        with open(p, "w") as f:
            f.write("hit\npad\nhit\n")
        r = await GrepTool().call(
            _ctx(tmp), pattern="hit", path=tmp, context=1, output_mode="count"
        )
        assert "c.txt: 2" in r.content

    @pytest.mark.asyncio
    async def test_default_format_unchanged(self, tmp):
        from openlaoke.tools.grep_tool import GrepTool

        p = os.path.join(tmp, "f.txt")
        with open(p, "w") as f:
            f.write("alpha\nbeta\n")
        r = await GrepTool().call(_ctx(tmp), pattern="beta", path=tmp)
        assert "f.txt:2: beta" in r.content
        assert "Found 1 match(es)" in r.content
