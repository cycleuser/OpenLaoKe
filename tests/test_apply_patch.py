"""Tests for ApplyPatch: the Codex envelope, unified diffs, and atomicity (P11)."""

from __future__ import annotations

import asyncio

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.apply_patch_tool import ApplyPatchTool, parse_codex, parse_unified


def _ctx(directory: str) -> ToolContext:
    return ToolContext(app_state=create_app_state(cwd=directory), tool_use_id="p1")


def _run(ctx: ToolContext, patch: str):
    return asyncio.run(ApplyPatchTool().call(ctx, patch=patch))


ENVELOPE = """*** Begin Patch
*** Add File: notes/new.txt
+alpha
+beta
*** Update File: notes/old.txt
@@
 one
-two
+TWO
+two-and-a-half
 three
*** Delete File: notes/gone.txt
*** End Patch
"""


def test_codex_envelope_adds_updates_and_deletes(tmp_path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "old.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (notes / "gone.txt").write_text("bye\n", encoding="utf-8")

    result = _run(_ctx(str(tmp_path)), ENVELOPE)
    assert not result.is_error, result.content
    assert (notes / "new.txt").read_text() == "alpha\nbeta\n"
    assert (notes / "old.txt").read_text() == "one\nTWO\ntwo-and-a-half\nthree\n"
    assert not (notes / "gone.txt").exists()
    assert "3 file(s)" in result.content


def test_codex_parse_rejects_text_outside_a_section() -> None:
    parsed = parse_codex("*** Begin Patch\n*** Add File: a.txt\n+x\n*** End Patch\n")
    assert parsed[0].path == "a.txt" and parsed[0].content == ["x"]


def test_unified_diff_updates_a_file(tmp_path) -> None:
    (tmp_path / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    patch = """--- a/m.py
+++ b/m.py
@@ -1,2 +1,2 @@
 def f():
-    return 1
+    return 2
"""
    result = _run(_ctx(str(tmp_path)), patch)
    assert not result.is_error, result.content
    assert (tmp_path / "m.py").read_text() == "def f():\n    return 2\n"


def test_unified_diff_can_create_and_delete(tmp_path) -> None:
    (tmp_path / "gone.txt").write_text("x\n", encoding="utf-8")
    patch = """--- /dev/null
+++ b/fresh.txt
@@ -0,0 +1,1 @@
+hello
--- a/gone.txt
+++ /dev/null
@@ -1,1 +0,0 @@
-x
"""
    result = _run(_ctx(str(tmp_path)), patch)
    assert not result.is_error, result.content
    assert (tmp_path / "fresh.txt").read_text() == "hello\n"
    assert not (tmp_path / "gone.txt").exists()


def test_a_failing_hunk_writes_nothing(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: a.txt
@@
-alpha
+ALPHA
*** Add File: b.txt
+bee
*** Update File: a.txt
@@
-no-such-line
+x
*** End Patch
"""
    result = _run(_ctx(str(tmp_path)), patch)
    assert result.is_error
    assert "does not match" in result.content
    assert (tmp_path / "a.txt").read_text() == "alpha\n", "the first hunk must not land"
    assert not (tmp_path / "b.txt").exists()


def test_unknown_target_is_rejected(tmp_path) -> None:
    result = _run(
        _ctx(str(tmp_path)),
        "*** Begin Patch\n*** Update File: nope.txt\n@@\n-a\n+b\n*** End Patch\n",
    )
    assert result.is_error
    assert "does not exist" in result.content


def test_adding_an_existing_file_is_rejected(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    result = _run(_ctx(str(tmp_path)), "*** Begin Patch\n*** Add File: a.txt\n+x\n*** End Patch\n")
    assert result.is_error
    assert "already exists" in result.content


def test_paths_outside_the_workspace_are_rejected(tmp_path) -> None:
    result = _run(
        _ctx(str(tmp_path)), "*** Begin Patch\n*** Add File: ../escape.txt\n+x\n*** End Patch\n"
    )
    assert result.is_error


def test_patch_updates_edit_stats(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    ctx = _ctx(str(tmp_path))
    _run(ctx, "*** Begin Patch\n*** Update File: a.txt\n@@\n one\n-two\n+2\n*** End Patch\n")
    stats = ctx.app_state.edit_stats
    assert stats["files_modified"] == 1
    assert stats["lines_added"] == 1 and stats["lines_removed"] == 1


def test_parse_unified_requires_hunks() -> None:
    try:
        parse_unified("--- a/x\n+++ b/x\n")
    except Exception as exc:  # noqa: BLE001 - the message is the assertion
        assert "no hunks" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a rejection")


def test_blank_line_handling_round_trips(tmp_path) -> None:
    (tmp_path / "doc.md").write_text("title\n\nbody\n", encoding="utf-8")
    patch = """*** Begin Patch
*** Update File: doc.md
@@
 title
 
-body
+new body
*** End Patch
"""
    result = _run(_ctx(str(tmp_path)), patch)
    assert not result.is_error, result.content
    assert (tmp_path / "doc.md").read_text() == "title\n\nnew body\n"


# --------------------------------------------------------------------------- #
# parser and executor edges
# --------------------------------------------------------------------------- #
def test_text_outside_a_section_is_rejected() -> None:
    import pytest

    from openlaoke.tools.apply_patch_tool import PatchError

    with pytest.raises(PatchError, match="outside a file section"):
        parse_codex("*** Begin Patch\nstray instruction\n*** End Patch\n")


def test_a_hunk_header_with_an_offset_is_accepted() -> None:
    parsed = parse_codex(
        "*** Begin Patch\n"
        "*** Update File: a.txt\n"
        "@@ -3,2 +3,2 @@\n"
        " keep\n"
        "-old\n"
        "+new\n"
        "*** End Patch\n"
    )

    assert parsed[0].hunks[0].old_start == 3
    assert parsed[0].hunks[0].old_lines == ["keep", "old"]
    assert parsed[0].hunks[0].new_lines == ["keep", "new"]


def test_blank_lines_in_an_added_file_are_kept() -> None:
    parsed = parse_codex("*** Begin Patch\n*** Add File: a.txt\n+one\n\n+two\n*** End Patch\n")

    assert parsed[0].content == ["one", "", "two"]


def test_a_blank_line_inside_an_update_hunk_is_a_context_line() -> None:
    parsed = parse_codex(
        "*** Begin Patch\n"
        "*** Update File: a.txt\n"
        "@@\n"
        " keep\n"
        "\n"
        "-old\n"
        "+new\n"
        "*** End Patch\n"
    )

    hunk = parsed[0].hunks[0]
    assert hunk.old_lines == ["keep", "", "old"]
    assert hunk.new_lines == ["keep", "", "new"]


def test_an_envelope_without_a_start_marker_is_rejected() -> None:
    import pytest

    from openlaoke.tools.apply_patch_tool import PatchError

    with pytest.raises(PatchError, match="missing '\\*\\*\\* Begin Patch'"):
        parse_codex("*** Add File: a.txt\n+x\n")


def test_an_envelope_with_no_files_is_rejected() -> None:
    import pytest

    from openlaoke.tools.apply_patch_tool import PatchError

    with pytest.raises(PatchError, match="no file sections"):
        parse_codex("*** Begin Patch\n*** End Patch\n")


def test_move_to_is_ignored() -> None:
    parsed = parse_codex(
        "*** Begin Patch\n"
        "*** Update File: a.txt\n"
        "*** Move to: b.txt\n"
        "@@\n"
        "-one\n"
        "+uno\n"
        "*** End Patch\n"
    )

    assert parsed[0].path == "a.txt"
    assert parsed[0].hunks[0].new_lines == ["uno"]


def test_a_malformed_unified_hunk_header_is_rejected() -> None:
    import pytest

    from openlaoke.tools.apply_patch_tool import PatchError

    with pytest.raises(PatchError, match="malformed hunk header"):
        parse_unified("--- a/x\n+++ b/x\n@@ nonsense\n-a\n+b\n")


def test_a_unified_diff_with_no_files_is_rejected() -> None:
    import pytest

    from openlaoke.tools.apply_patch_tool import PatchError

    with pytest.raises(PatchError, match="no file sections"):
        parse_unified("this is not a diff\n")


def test_text_before_the_first_header_is_ignored() -> None:
    parsed = parse_unified(
        "a note from the model\n--- a/x.txt\n+++ b/x.txt\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    )

    assert len(parsed) == 1
    assert parsed[0].path == "x.txt"
    assert parsed[0].hunks[0].new_lines == ["b"]


def test_an_empty_patch_is_refused(tmp_path) -> None:
    result = _run(_ctx(str(tmp_path)), "   ")

    assert result.is_error
    assert "patch is required" in result.content


def test_an_oversized_patch_is_refused(tmp_path) -> None:
    from openlaoke.tools.apply_patch_tool import MAX_PATCH_BYTES

    result = _run(_ctx(str(tmp_path)), "x" * (MAX_PATCH_BYTES + 1))

    assert result.is_error
    assert "larger than" in result.content


def test_a_section_without_a_path_is_refused(tmp_path) -> None:
    result = _run(_ctx(str(tmp_path)), "*** Begin Patch\n*** Add File:\n+x\n*** End Patch\n")

    assert result.is_error
    assert "no path" in result.content


def test_an_unreadable_target_is_reported(tmp_path, monkeypatch) -> None:
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    real_open = open

    def guarded(path, *args, **kwargs):
        if str(path).endswith("a.txt") and "r" in (args[0] if args else "r"):
            raise OSError("permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", guarded)

    result = _run(
        _ctx(str(tmp_path)), "*** Begin Patch\n*** Update File: a.txt\n@@\n-one\n+uno\n*** End Patch\n"
    )

    assert result.is_error
    assert "cannot read a.txt" in result.content


def test_a_write_failure_is_reported(tmp_path, monkeypatch) -> None:
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    real_open = open

    def guarded(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if str(path).endswith("a.txt") and mode == "w":
            raise OSError("disk full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", guarded)

    result = _run(
        _ctx(str(tmp_path)), "*** Begin Patch\n*** Update File: a.txt\n@@\n-one\n+uno\n*** End Patch\n"
    )

    assert result.is_error
    assert "disk full" in result.content


def test_an_update_keeps_a_missing_final_newline(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("one\ntwo", encoding="utf-8")

    result = _run(
        _ctx(str(tmp_path)), "*** Begin Patch\n*** Update File: a.txt\n@@\n-one\n+uno\n*** End Patch\n"
    )

    assert not result.is_error
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "uno\ntwo"


def test_register_adds_the_tool() -> None:
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools import apply_patch_tool

    registry = ToolRegistry()
    apply_patch_tool.register(registry)

    assert registry.get("ApplyPatch") is not None


def test_blank_lines_before_the_first_section_are_skipped() -> None:
    parsed = parse_codex("*** Begin Patch\n\n*** Add File: a.txt\n+x\n*** End Patch\n")

    assert parsed[0].content == ["x"]


def test_diff_content_before_a_hunk_header_is_skipped() -> None:
    parsed = parse_unified(
        "--- a/x.txt\n+++ b/x.txt\n+orphan\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    )

    assert parsed[0].hunks[0].new_lines == ["b"]


def test_a_parse_error_becomes_a_tool_error(tmp_path) -> None:
    result = _run(_ctx(str(tmp_path)), "*** Begin Patch\nstray\n*** End Patch\n")

    assert result.is_error
    assert result.content.startswith("Patch rejected:")
