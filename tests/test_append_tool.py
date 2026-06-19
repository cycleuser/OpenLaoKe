"""Tests for AppendFile tool."""
from __future__ import annotations

import os

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.append_tool import AppendFileTool


@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


def _ctx(tmp_dir):
    state = create_app_state(cwd=tmp_dir)
    return ToolContext(app_state=state, tool_use_id="t1")


class TestAppendFile:
    @pytest.mark.asyncio
    async def test_creates_new_file(self, tmp_dir):
        fp = os.path.join(tmp_dir, "new.txt")
        r = await AppendFileTool().call(_ctx(tmp_dir), file_path=fp, content="hello\n")
        assert not r.is_error
        assert "Appended" in r.content
        with open(fp) as f:
            data = f.read()
        assert data == "hello\n"

    @pytest.mark.asyncio
    async def test_append_to_existing(self, tmp_dir):
        fp = os.path.join(tmp_dir, "existing.txt")
        with open(fp, "w") as f:
            f.write("line1\n")
        r = await AppendFileTool().call(_ctx(tmp_dir), file_path=fp, content="line2\n")
        assert not r.is_error
        with open(fp) as f:
            data = f.read()
        assert data == "line1\nline2\n"

    @pytest.mark.asyncio
    async def test_missing_path_returns_error(self, tmp_dir):
        r = await AppendFileTool().call(_ctx(tmp_dir), file_path="", content="x")
        assert r.is_error

    @pytest.mark.asyncio
    async def test_diff_in_output(self, tmp_dir):
        fp = os.path.join(tmp_dir, "diff_test.txt")
        with open(fp, "w") as f:
            f.write("original\n")
        r = await AppendFileTool().call(_ctx(tmp_dir), file_path=fp, content="appended\n")
        assert not r.is_error
        assert "@@" in r.content or "(new file)" in r.content

    @pytest.mark.asyncio
    async def test_append_empty_content(self, tmp_dir):
        fp = os.path.join(tmp_dir, "empty_append.txt")
        with open(fp, "w") as f:
            f.write("data\n")
        r = await AppendFileTool().call(_ctx(tmp_dir), file_path=fp, content="")
        assert not r.is_error
        with open(fp) as f:
            data = f.read()
        assert data == "data\n"
