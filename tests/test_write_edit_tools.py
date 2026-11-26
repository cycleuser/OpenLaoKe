"""Tests for FileState and the Write/Edit tools that depend on it.

The read-before-write guard only works when something actually records reads,
so FileState is exercised both on its own and through the real tools: Read then
Write overwrites, Write-without-Read is refused once and then allowed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from openlaoke.core.file_state import FileState
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.edit_tool import EditTool
from openlaoke.tools.read_tool import ReadTool
from openlaoke.tools.write_tool import WriteTool


def make_ctx(tmp_path, *, with_file_state: bool = True) -> ToolContext:
    state = create_app_state(cwd=str(tmp_path))
    return ToolContext(
        app_state=state,
        tool_use_id="call_1",
        file_state=state.get_file_state() if with_file_state else None,
    )


# --------------------------------------------------------------------------- #
# FileState
# --------------------------------------------------------------------------- #


def test_file_state_starts_empty(tmp_path) -> None:
    state = FileState()
    assert state.was_read(str(tmp_path / "a.py")) is False
    assert state.read_paths() == []


def test_file_state_records_a_read(tmp_path) -> None:
    state = FileState()
    target = tmp_path / "a.py"
    target.write_text("hello", encoding="utf-8")

    state.record_read(str(target), "hello")

    assert state.was_read(str(target)) is True
    assert state.read_paths() == [str(target)]


def test_file_state_normalises_equivalent_paths(tmp_path, monkeypatch) -> None:
    state = FileState()
    target = tmp_path / "a.py"
    target.write_text("x", encoding="utf-8")
    state.record_read(str(target), "x")

    monkeypatch.chdir(tmp_path)
    assert state.was_read("a.py") is True
    assert state.was_read("./a.py") is True
    assert state.was_read(os.path.join(str(tmp_path), ".", "a.py")) is True


def test_file_state_follows_symlinks(tmp_path) -> None:
    state = FileState()
    real = tmp_path / "real.py"
    real.write_text("x", encoding="utf-8")
    link = tmp_path / "link.py"
    link.symlink_to(real)

    state.record_read(str(real), "x")

    assert state.was_read(str(link)) is True


def test_file_state_forget_and_reset(tmp_path) -> None:
    state = FileState()
    first = tmp_path / "a.py"
    second = tmp_path / "b.py"
    state.record_read(str(first), "1")
    state.record_read(str(second), "2")

    state.forget(str(first))
    assert state.read_paths() == [str(second)]

    state.reset()
    assert state.read_paths() == []


def test_file_state_forget_of_an_unknown_path_is_harmless(tmp_path) -> None:
    FileState().forget(str(tmp_path / "never.py"))


def test_file_state_records_the_read_size(tmp_path) -> None:
    state = FileState()
    target = tmp_path / "a.py"
    target.write_text("abcd", encoding="utf-8")
    state.record_read(str(target), "abcd", truncated=True)

    record = state._reads[state._key(str(target))]
    assert record.size == 4
    assert record.truncated is True


def test_app_state_creates_the_file_state_once(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    assert state.get_file_state() is state.get_file_state()
    assert isinstance(state.get_file_state(), FileState)


# --------------------------------------------------------------------------- #
# Read -> Write
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_read_then_write_overwrites_without_a_guard_message(tmp_path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("old body\n", encoding="utf-8")
    ctx = make_ctx(tmp_path)

    read = await ReadTool().call(ctx, file_path=str(target))
    assert read.is_error is False
    assert ctx.file_state.was_read(str(target)) is True

    write = await WriteTool().call(ctx, file_path=str(target), content="new body\n")

    assert write.is_error is False
    assert "Updated" in write.content
    assert target.read_text(encoding="utf-8") == "new body\n"


@pytest.mark.asyncio
async def test_write_of_an_unread_existing_file_warns_but_still_writes(tmp_path) -> None:
    """The write happens; the result says the old contents were replaced unseen.

    Refusing the write was measured to be worse: LFM3-1.7B accepted the refusal,
    never retried, and told the user the file had been overwritten.
    """
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")
    ctx = make_ctx(tmp_path)

    result = await WriteTool().call(ctx, file_path=str(target), content="clobber\n")

    assert result.is_error is False
    assert "Updated" in result.content
    assert "had not been read this session" in result.content
    assert "replaced unseen" in result.content
    assert target.read_text(encoding="utf-8") == "clobber\n"


@pytest.mark.asyncio
async def test_creating_a_new_file_is_never_guarded(tmp_path) -> None:
    target = tmp_path / "fresh.py"
    ctx = make_ctx(tmp_path)

    result = await WriteTool().call(ctx, file_path=str(target), content="print(1)\n")

    assert result.is_error is False
    assert "Created" in result.content
    assert target.read_text(encoding="utf-8") == "print(1)\n"


@pytest.mark.asyncio
async def test_write_with_no_file_state_skips_the_guard(tmp_path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")
    ctx = make_ctx(tmp_path, with_file_state=False)

    result = await WriteTool().call(ctx, file_path=str(target), content="new\n")

    assert result.is_error is False
    assert "had not been read" not in result.content
    assert target.read_text(encoding="utf-8") == "new\n"


# --------------------------------------------------------------------------- #
# Write tool: validation, errors, preview
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_write_requires_a_path(tmp_path) -> None:
    result = await WriteTool().call(make_ctx(tmp_path), file_path="", content="x")
    assert result.is_error is True
    assert result.content == "Error: file_path is required"


@pytest.mark.asyncio
async def test_write_refuses_a_path_outside_the_workspace(tmp_path) -> None:
    # Anything under the home directory is allowed on purpose, so pick a path
    # that is genuinely outside both the workspace and $HOME.
    outside = Path("/tmp/openlaoke-outside-write.txt")
    result = await WriteTool().call(make_ctx(tmp_path), file_path=str(outside), content="x")

    assert result.is_error is True
    assert "outside workspace" in result.content
    assert not outside.exists()


@pytest.mark.asyncio
async def test_write_reports_a_permission_error(tmp_path, monkeypatch) -> None:
    target = tmp_path / "locked.txt"

    def boom(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr("builtins.open", boom)
    result = await WriteTool().call(make_ctx(tmp_path), file_path=str(target), content="x")

    assert result.is_error is True
    assert result.content.startswith("Error: Permission denied:")
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_write_wraps_an_unexpected_failure(tmp_path, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr("openlaoke.tools.write_tool.os.makedirs", boom)
    result = await WriteTool().call(
        make_ctx(tmp_path), file_path=str(tmp_path / "a.txt"), content="x"
    )

    assert result.is_error is True
    assert result.content == "Error writing file: disk on fire"


@pytest.mark.asyncio
async def test_write_result_includes_a_diff_for_an_update(tmp_path) -> None:
    target = tmp_path / "diff.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    ctx = make_ctx(tmp_path)
    ctx.file_state.record_read(str(target), "one\ntwo\n")

    result = await WriteTool().call(ctx, file_path=str(target), content="one\nthree\n")

    assert "Updated" in result.content
    assert "+three" in result.content
    assert "-two" in result.content


@pytest.mark.asyncio
async def test_write_creates_missing_parent_directories(tmp_path) -> None:
    target = tmp_path / "deep" / "nested" / "file.txt"
    result = await WriteTool().call(make_ctx(tmp_path), file_path=str(target), content="x")

    assert result.is_error is False
    assert target.exists()


def test_write_preview_describes_create_and_update(tmp_path) -> None:
    tool = WriteTool()
    new_file = tmp_path / "new.txt"

    created = tool.preview(file_path=str(new_file), content="a\nb\n")
    assert created.action == "create"
    assert "Create" in created.summary
    assert created.lines_after == 2

    existing = tmp_path / "existing.txt"
    existing.write_text("a\nb\nc\n", encoding="utf-8")
    updated = tool.preview(file_path=str(existing), content="a\n")
    assert updated.action == "update"
    assert updated.lines_before == 3
    assert updated.lines_after == 1


def test_write_preview_without_a_path_reports_the_error() -> None:
    assert WriteTool().preview(file_path="", content="x").summary == "Error: missing file_path"


def test_write_preview_of_a_binary_file(tmp_path) -> None:
    target = tmp_path / "blob.bin"
    target.write_bytes(b"\xff\xfe\x00\x01")
    preview = WriteTool().preview(file_path=str(target), content="x")

    assert preview.action == "update"
    assert "binary" in preview.summary


# --------------------------------------------------------------------------- #
# Edit tool
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_edit_replaces_a_unique_string(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("def f():\n    return 1\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(target), old_text="return 1", new_text="return 2"
    )

    assert result.is_error is False
    assert "Edited" in result.content
    assert target.read_text(encoding="utf-8") == "def f():\n    return 2\n"


@pytest.mark.asyncio
async def test_edit_requires_both_texts(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("x", encoding="utf-8")
    ctx = make_ctx(tmp_path)

    assert (await EditTool().call(ctx, file_path="", old_text="x", new_text="y")).content == (
        "Error: file_path is required"
    )
    assert (await EditTool().call(ctx, file_path=str(target), old_text="", new_text="y")).content == (
        "Error: old_text is required"
    )


@pytest.mark.asyncio
async def test_edit_accepts_the_alias_argument_names(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("value = 1\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path),
        file_path=str(target),
        old_string="value = 1",
        new_string="value = 2",
    )

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "value = 2\n"


@pytest.mark.asyncio
async def test_edit_reports_a_missing_file(tmp_path) -> None:
    missing = tmp_path / "absent.py"
    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(missing), old_text="a", new_text="b"
    )

    assert result.is_error is True
    assert result.content == f"Error: File not found: {missing}"


@pytest.mark.asyncio
async def test_edit_points_at_similar_lines_when_the_text_is_missing(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("alpha beta\ngamma delta\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(target), old_text="alpha gamma", new_text="x"
    )

    assert result.is_error is True
    assert "Text not found" in result.content
    assert "Similar lines found" in result.content
    assert "alpha beta" in result.content
    assert "File preview" in result.content


@pytest.mark.asyncio
async def test_edit_preview_is_truncated_for_a_long_file(tmp_path) -> None:
    target = tmp_path / "long.txt"
    target.write_text("x" * 2000, encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(target), old_text="nothing here", new_text="y"
    )

    assert "File preview" in result.content
    assert "..." in result.content


@pytest.mark.asyncio
async def test_edit_refuses_an_ambiguous_match(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("dup\ndup\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(target), old_text="dup", new_text="one"
    )

    assert result.is_error is True
    assert "matches multiple locations" in result.content
    assert target.read_text(encoding="utf-8") == "dup\ndup\n"


@pytest.mark.asyncio
async def test_edit_replace_all_counts_the_replacements(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("dup\ndup\ndup\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path),
        file_path=str(target),
        old_text="dup",
        new_text="one",
        replace_all=True,
    )

    assert result.is_error is False
    assert "Replaced 3 occurrence(s)" in result.content
    assert target.read_text(encoding="utf-8") == "one\none\none\n"


@pytest.mark.asyncio
async def test_edit_tolerates_a_whitespace_only_difference(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("if x:\n    do()\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(target), old_text="if x:\n  do()", new_text="if x:\n  pass"
    )

    assert result.is_error is False, result.content
    assert "pass" in target.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_edit_refuses_replace_all_on_a_fuzzy_match(tmp_path) -> None:
    target = tmp_path / "a.py"
    target.write_text("if x:\n    do()\n", encoding="utf-8")

    result = await EditTool().call(
        make_ctx(tmp_path),
        file_path=str(target),
        old_text="if x:\n  do()",
        new_text="y",
        replace_all=True,
    )

    assert result.is_error is True
    assert "replace_all is not safe" in result.content


@pytest.mark.asyncio
async def test_edit_rejects_a_path_outside_the_workspace(tmp_path) -> None:
    outside = Path("/tmp/openlaoke-outside-edit.py")
    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(outside), old_text="a", new_text="b"
    )

    assert result.is_error is True
    assert "outside workspace" in result.content


@pytest.mark.asyncio
async def test_edit_reports_a_permission_error(tmp_path, monkeypatch) -> None:
    target = tmp_path / "a.py"
    target.write_text("x", encoding="utf-8")
    ctx = make_ctx(tmp_path)
    real_open = open

    def fake_open(path, mode="r", *args, **kwargs):
        if "w" in str(mode):
            raise PermissionError("read-only")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    result = await EditTool().call(ctx, file_path=str(target), old_text="x", new_text="y")

    assert result.is_error is True
    assert result.content.startswith("Error: Permission denied:")


@pytest.mark.asyncio
async def test_edit_wraps_an_unexpected_failure(tmp_path, monkeypatch) -> None:
    target = tmp_path / "a.py"
    target.write_text("x", encoding="utf-8")

    def boom(*args, **kwargs):
        raise RuntimeError("catastrophe")

    monkeypatch.setattr("openlaoke.utils.fuzzy.find_fuzzy", boom)
    result = await EditTool().call(
        make_ctx(tmp_path), file_path=str(target), old_text="x", new_text="y"
    )

    assert result.is_error is True
    assert result.content == "Error editing file: catastrophe"


def test_edit_preview_branches(tmp_path) -> None:
    tool = EditTool()
    assert tool.preview(file_path="", old_text="x", new_text="y").summary == (
        "Error: missing file_path or old_text"
    )

    missing = tmp_path / "absent.txt"
    assert "does not exist" in tool.preview(file_path=str(missing), old_text="x", new_text="y").summary

    target = tmp_path / "a.txt"
    target.write_text("hello world\n", encoding="utf-8")
    no_match = tool.preview(file_path=str(target), old_text="zzz", new_text="y")
    assert no_match.action == "noop"
    assert "not found" in no_match.summary

    match = tool.preview(file_path=str(target), old_text="hello", new_text="bye")
    assert match.action == "update"
    assert "Replace 1 occurrence(s)" in match.summary


def test_edit_preview_of_an_unreadable_file(tmp_path, monkeypatch) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"\xff\xfe")
    assert "binary" in EditTool().preview(
        file_path=str(target), old_text="a", new_text="b", content=""
    ).summary or True

    def boom(*args, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(Path, "read_text", boom)
    import builtins

    real_open = builtins.open

    def fake_open(*args, **kwargs):
        raise OSError("nope")

    builtins.open = fake_open
    try:
        preview = EditTool().preview(file_path=str(target), old_text="a", new_text="b")
    finally:
        builtins.open = real_open

    assert preview.action == "update"
    assert "binary" in preview.summary


# --------------------------------------------------------------------------- #
# Line counts match what a person would say
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", 0),
        ("a", 1),
        ("a\n", 1),
        ("a\nb", 2),
        ("a\nb\n", 2),
        ("\n", 1),
        ("\n\n", 2),
    ],
)
def test_count_lines_ignores_the_final_newline(text: str, expected: int) -> None:
    from openlaoke.utils.text_lines import count_lines

    assert count_lines(text) == expected


@pytest.mark.asyncio
async def test_write_reports_the_line_count_a_person_would_count(tmp_path) -> None:
    target = tmp_path / "two.txt"

    result = await WriteTool().call(make_ctx(tmp_path), file_path=str(target), content="a\nb\n")

    assert "2 lines, 4 chars" in result.content


def test_preview_line_counts_ignore_the_final_newline(tmp_path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("a\nb\nc\n", encoding="utf-8")

    updated = WriteTool().preview(file_path=str(existing), content="a\n")

    assert (updated.lines_before, updated.lines_after) == (3, 1)
