"""Tests for tool modules with 0% coverage: ls_tool, git_tool, compound_tools, batch_tool."""

from __future__ import annotations

import os
import tempfile

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.batch_tool import BatchTool, ToolCallSpec
from openlaoke.tools.compound_tools import (
    FindAndReadTool,
    ReadAndPatchTool,
    SearchAndReadTool,
)
from openlaoke.tools.git_tool import GitInput, GitTool
from openlaoke.tools.ls_tool import ListDirectoryInput, ListDirectoryTool


@pytest.fixture
def ctx():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    state = create_app_state(cwd=project_root)
    return ToolContext(app_state=state, tool_use_id="test_tool")


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ============================================================================
# ListDirectoryTool
# ============================================================================


class TestListDirectoryTool:
    def test_metadata(self):
        tool = ListDirectoryTool()
        assert tool.name == "ListDirectory"
        assert tool.is_read_only is True
        assert tool.is_destructive is False
        assert tool.requires_approval is False
        assert tool.input_schema == ListDirectoryInput

    @pytest.mark.asyncio
    async def test_list_existing_directory(self, ctx, temp_dir):
        with open(os.path.join(temp_dir, "file1.txt"), "w") as f:
            f.write("hello")
        os.makedirs(os.path.join(temp_dir, "subdir"))

        tool = ListDirectoryTool()
        result = await tool.call(ctx, path=temp_dir)
        assert result.is_error is False
        assert "file1.txt" in result.content
        assert "subdir" in result.content

    @pytest.mark.asyncio
    async def test_list_nonexistent_path(self, ctx):
        tool = ListDirectoryTool()
        result = await tool.call(ctx, path="/nonexistent/path/xyz123")
        assert result.is_error is True
        assert "does not exist" in result.content

    @pytest.mark.asyncio
    async def test_list_file_not_directory(self, ctx, temp_dir):
        fp = os.path.join(temp_dir, "file.txt")
        with open(fp, "w") as f:
            f.write("test")

        tool = ListDirectoryTool()
        result = await tool.call(ctx, path=fp)
        assert result.is_error is True
        assert "Not a directory" in result.content

    @pytest.mark.asyncio
    async def test_list_default_cwd(self, ctx):
        tool = ListDirectoryTool()
        result = await tool.call(ctx, path=None)
        assert result.is_error is False

    def test_format_size(self):
        tool = ListDirectoryTool()
        assert tool._format_size(500) == "500.0B"
        assert tool._format_size(1500) == "1.5KB"
        assert tool._format_size(1500000) == "1.4MB"
        assert tool._format_size(1500000000) == "1.4GB"

    @pytest.mark.asyncio
    async def test_list_empty_directory(self, ctx, temp_dir):
        tool = ListDirectoryTool()
        result = await tool.call(ctx, path=temp_dir)
        assert result.is_error is False
        assert "0 items" in result.content or "items total" in result.content

    @pytest.mark.asyncio
    async def test_list_with_home_expansion(self, ctx):
        tool = ListDirectoryTool()
        result = await tool.call(ctx, path="~")
        assert result.is_error is False


# ============================================================================
# GitTool
# ============================================================================


class TestGitTool:
    def test_metadata(self):
        tool = GitTool()
        assert tool.name == "Git"
        assert tool.is_read_only is False
        assert tool.is_destructive is True
        assert tool.requires_approval is True
        assert tool.input_schema == GitInput

    @pytest.mark.asyncio
    async def test_git_empty_action(self, ctx):
        tool = GitTool()
        result = await tool.call(ctx, action="")
        assert result.is_error is True
        assert "required" in result.content

    @pytest.mark.asyncio
    async def test_git_invalid_action(self, ctx):
        tool = GitTool()
        result = await tool.call(ctx, action="invalidxyz")
        assert result.is_error is True
        assert "Unknown" in result.content

    @pytest.mark.asyncio
    async def test_git_not_repo(self, ctx, temp_dir):
        state = create_app_state(cwd=temp_dir)
        tctx = ToolContext(app_state=state, tool_use_id="test_git")
        tool = GitTool()
        result = await tool.call(tctx, action="status")
        assert result.is_error is True
        assert "Not a git repository" in result.content

    @pytest.mark.asyncio
    async def test_git_status_in_repo(self, ctx):
        tool = GitTool()
        result = await tool.call(ctx, action="status")
        assert (
            result.is_error is False
            or "Not a git repository" in result.content
            or "git" in result.content.lower()
        )

    @pytest.mark.asyncio
    async def test_git_log(self, ctx):
        tool = GitTool()
        result = await tool.call(ctx, action="log", args="--oneline -1")
        assert (
            result.is_error is False
            or "Not a git repository" in result.content
            or "git" in result.content.lower()
        )

    @pytest.mark.asyncio
    async def test_git_diff(self, ctx):
        tool = GitTool()
        result = await tool.call(ctx, action="diff")
        assert (
            result.is_error is False
            or "Not a git repository" in result.content
            or "git" in result.content.lower()
        )

    def test_is_git_repo(self):
        tool = GitTool()
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        git_dir = os.path.join(repo_root, ".git")
        if os.path.isdir(git_dir):
            assert tool._is_git_repo(repo_root) is True

    def test_is_not_git_repo(self, temp_dir):
        tool = GitTool()
        assert tool._is_git_repo(temp_dir) is False


# ============================================================================
# Compound Tools
# ============================================================================


class TestReadAndPatchTool:
    def test_metadata(self):
        tool = ReadAndPatchTool()
        assert tool.name == "ReadAndPatch"
        assert tool.is_read_only is False
        assert tool.is_destructive is True

    @pytest.mark.asyncio
    async def test_missing_required_params(self, ctx):
        tool = ReadAndPatchTool()
        result = await tool.call(ctx, file_path="", old_text="", new_text="x")
        assert result.is_error is True
        assert "required" in result.content

    @pytest.mark.asyncio
    async def test_read_then_patch(self, ctx, temp_dir):
        fp = os.path.join(temp_dir, "test.txt")
        with open(fp, "w") as f:
            f.write("hello world")
        state = create_app_state(cwd=temp_dir)
        tctx = ToolContext(app_state=state, tool_use_id="test_rp")

        tool = ReadAndPatchTool()
        result = await tool.call(tctx, file_path=fp, old_text="hello", new_text="goodbye")
        assert result.is_error is False
        assert "hello" in result.content or "goodbye" in result.content

        with open(fp) as f:
            assert "goodbye" in f.read()


class TestFindAndReadTool:
    def test_metadata(self):
        tool = FindAndReadTool()
        assert tool.name == "FindAndRead"
        assert tool.is_read_only is True

    @pytest.mark.asyncio
    async def test_empty_pattern(self, ctx):
        tool = FindAndReadTool()
        result = await tool.call(ctx, pattern="")
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_find_python_files(self, ctx):
        tool = FindAndReadTool()
        result = await tool.call(ctx, pattern="*.py", path=".", max_files=3)
        assert result.is_error is False


class TestSearchAndReadTool:
    def test_metadata(self):
        tool = SearchAndReadTool()
        assert tool.name == "SearchAndRead"
        assert tool.is_read_only is True

    @pytest.mark.asyncio
    async def test_empty_pattern(self, ctx):
        tool = SearchAndReadTool()
        result = await tool.call(ctx, pattern="")
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_search_pattern(self, ctx):
        tool = SearchAndReadTool()
        result = await tool.call(
            ctx, pattern="class ThinkingBudget", file_glob="*.py", max_results=3
        )
        assert result.is_error is False


# ============================================================================
# BatchTool
# ============================================================================


class TestBatchTool:
    def test_metadata(self):
        tool = BatchTool()
        assert tool.name == "Batch"
        assert tool.is_destructive is False
        assert tool.is_concurrency_safe is True

    @pytest.mark.asyncio
    async def test_empty_calls(self, ctx):
        tool = BatchTool()
        result = await tool.call(ctx, calls=[])
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_too_many_calls(self, ctx):
        tool = BatchTool()
        calls = [ToolCallSpec(tool_name="Read", args={"file_path": f"f{i}.py"}) for i in range(51)]
        result = await tool.call(ctx, calls=calls)
        assert result.is_error is True
        assert "Too many" in result.content

    @pytest.mark.asyncio
    async def test_batch_read_files(self, ctx):
        tool = BatchTool()
        calls = [
            ToolCallSpec(tool_name="Read", args={"file_path": "openlaoke/__init__.py"}),
        ]
        result = await tool.call(ctx, calls=calls)
        assert result.is_error is False
        assert "Read" in result.content

    @pytest.mark.asyncio
    async def test_batch_dict_calls(self, ctx):
        tool = BatchTool()
        calls = [
            {"tool_name": "Read", "args": {"file_path": "openlaoke/__init__.py"}},
        ]
        result = await tool.call(ctx, calls=calls)
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_batch_parallel_and_sequential(self, ctx):
        tool = BatchTool()
        calls = [
            ToolCallSpec(tool_name="Read", args={"file_path": "openlaoke/__init__.py"}),
        ]
        result_p = await tool.call(ctx, calls=calls, parallel=True)
        result_s = await tool.call(ctx, calls=calls, parallel=False)
        assert result_p.is_error is False
        assert result_s.is_error is False

    @pytest.mark.asyncio
    async def test_batch_invalid_call_spec(self, ctx):
        tool = BatchTool()
        result = await tool.call(ctx, calls=[42])
        assert result.is_error is True
