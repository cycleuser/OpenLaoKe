"""Tests for the Grep tool: content search, name search, outlines and rendering."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from openlaoke.core.tool import ToolContext, ToolRegistry
from openlaoke.tools.grep_tool import GrepTool, _search_file, register


@pytest.fixture()
def tree(tmp_path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text(
        "def handler():\n"
        "    value = 1\n"
        "    return value\n"
        "\n"
        "\n"
        "class Widget:\n"
        "    def render(self):\n"
        "        return 'render me'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "beta.py").write_text(
        "def other():\n    return 'render here'\n", encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("render is a word here too\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Title\n\nNothing relevant.\n", encoding="utf-8")
    return tmp_path


def ctx(cwd: Path) -> ToolContext:
    return ToolContext(tool_use_id="t1", app_state=SimpleNamespace(get_cwd=lambda: str(cwd)))


def grep(tree: Path, **kwargs):
    return asyncio.run(GrepTool().call(ctx(tree), **kwargs))


# --------------------------------------------------------------------------- #
# Argument validation
# --------------------------------------------------------------------------- #


def test_an_unknown_mode_is_rejected(tree) -> None:
    result = grep(tree, mode="regex", pattern="x")

    assert result.is_error is True
    assert "mode must be one of" in result.content


def test_grep_needs_a_pattern(tree) -> None:
    result = grep(tree, mode="grep", pattern="")

    assert result.is_error is True
    assert "pattern is required" in result.content


def test_an_invalid_regex_is_reported(tree) -> None:
    result = grep(tree, pattern="([unclosed")

    assert result.is_error is True
    assert "Invalid regex" in result.content


def test_a_missing_directory_is_reported(tree) -> None:
    result = grep(tree, pattern="x", path="nowhere")

    assert result.is_error is True
    assert "Directory not found" in result.content


def test_a_path_outside_the_workspace_is_refused(tree) -> None:
    """Reading /etc is allowed; reading a private home directory is not."""
    result = grep(tree, pattern="root", path="~/.ssh")

    assert result.is_error is True
    assert "outside" in result.content.lower() or "path" in result.content.lower()


# --------------------------------------------------------------------------- #
# Content search
# --------------------------------------------------------------------------- #


def test_matches_are_labelled_with_their_definition(tree) -> None:
    result = grep(tree, pattern="render me", glob="*.py")

    assert result.is_error is False
    assert "Found 1 match(es)" in result.content
    assert "src/alpha.py:8:" in result.content
    assert "[in def render (L7-8)]" in result.content


def test_structure_labels_can_be_turned_off(tree) -> None:
    result = grep(tree, pattern="render me", glob="*.py", show_structure=False)

    assert "[in " not in result.content


def test_no_matches_says_where_it_looked(tree) -> None:
    result = grep(tree, pattern="definitely-not-here")

    assert result.content.startswith("No matches in ")


def test_the_search_is_case_insensitive_by_default(tree) -> None:
    result = grep(tree, pattern="RENDER", glob="*.py")

    # "render" appears twice in alpha.py and once in beta.py.
    assert "Found 3 match(es)" in result.content


def test_case_sensitivity_can_be_requested(tree) -> None:
    assert "No matches" in grep(tree, pattern="RENDER", glob="*.py", case_sensitive=True).content


def test_context_lines_use_the_dash_marker(tree) -> None:
    result = grep(tree, pattern="return value", glob="alpha.py", context=1)

    assert "src/alpha.py-2-     value = 1" in result.content
    assert "src/alpha.py:3:     return value" in result.content


def test_multiline_patterns_span_lines(tree) -> None:
    result = grep(tree, pattern="value = 1.*return value", glob="alpha.py", multiline=True)

    assert "1 match(es)" in result.content


def test_paths_only_lists_the_files(tree) -> None:
    result = grep(tree, pattern="render", paths_only=True)

    assert result.content.startswith("Files with matches (3):")
    assert "src/alpha.py" in result.content
    assert "src/beta.py" in result.content
    assert "notes.txt" in result.content


def test_output_mode_count_totals_each_file(tree) -> None:
    result = grep(tree, pattern="return", output_mode="count", glob="*.py")

    assert result.content.startswith("Match counts:")
    assert "src/alpha.py: 2" in result.content


def test_results_are_truncated_at_max_results(tree) -> None:
    result = grep(tree, pattern=".", max_results=2, glob="*.py")

    assert "truncated at 2 results" in result.content


def test_searching_a_single_file_works(tree) -> None:
    result = grep(tree, pattern="render", path="src/beta.py")

    assert "beta.py:2:" in result.content


def test_a_glob_limits_which_files_are_read(tree) -> None:
    result = grep(tree, pattern="render", glob="*.txt")

    assert "notes.txt" in result.content
    assert "alpha.py" not in result.content


def test_gitignored_paths_are_skipped(tree) -> None:
    (tree / ".gitignore").write_text("build/\n", encoding="utf-8")
    (tree / "build").mkdir()
    (tree / "build" / "gen.py").write_text("render generated\n", encoding="utf-8")

    result = grep(tree, pattern="render generated")

    assert "No matches" in result.content


# --------------------------------------------------------------------------- #
# _search_file
# --------------------------------------------------------------------------- #


def test_search_file_reports_no_room_left(tmp_path) -> None:
    path = tmp_path / "a.py"
    path.write_text("x\n", encoding="utf-8")

    import re

    entries, count, capped = _search_file(str(path), "a.py", re.compile("x"), False, 0, 0)

    assert (entries, count, capped) == ([], 0, True)


def test_search_file_survives_an_unreadable_file(tmp_path) -> None:
    import re

    entries, count, capped = _search_file(
        str(tmp_path / "ghost.py"), "ghost.py", re.compile("x"), False, 0, 10
    )

    assert (entries, count, capped) == ([], 0, False)


def test_search_file_caps_the_context_regions(tmp_path) -> None:
    path = tmp_path / "many.py"
    path.write_text("\n".join(f"line {i}" for i in range(1, 41)), encoding="utf-8")
    import re

    entries, _count, capped = _search_file(
        str(path), "many.py", re.compile(r"line (1|10|20|30)$"), False, 1, 100, max_regions=2
    )

    assert capped is True
    assert len({line for _p, line, _t, _m in entries}) <= 6


def test_search_file_deduplicates_multiline_hits_on_one_line(tmp_path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("aaa bbb aaa\n", encoding="utf-8")
    import re

    entries, count, _capped = _search_file(str(path), "a.txt", re.compile("aaa"), True, 0, 10)

    assert count == 1
    assert len(entries) == 1


# --------------------------------------------------------------------------- #
# find
# --------------------------------------------------------------------------- #


def test_find_matches_file_names_by_glob(tree) -> None:
    result = grep(tree, mode="find", glob="*.py")

    assert result.content.startswith("Found 2 file(s):")
    assert "src/alpha.py" in result.content


def test_find_matches_a_substring_pattern(tree) -> None:
    result = grep(tree, mode="find", pattern="beta")

    assert "src/beta.py" in result.content


def test_find_accepts_wildcards_in_the_pattern(tree) -> None:
    result = grep(tree, mode="find", pattern="*.md")

    assert "README.md" in result.content


def test_find_needs_a_pattern_or_glob(tree) -> None:
    result = grep(tree, mode="find")

    assert result.is_error is True
    assert "needs 'pattern' or 'glob'" in result.content


def test_find_reports_a_missing_path(tree) -> None:
    result = grep(tree, mode="find", glob="*.py", path="nowhere")

    assert result.is_error is True
    assert "Path not found" in result.content


def test_find_says_when_nothing_matched(tree) -> None:
    result = grep(tree, mode="find", glob="*.rs")

    assert result.content == "No files matching '*.rs'"


def test_find_caps_the_listing(tree) -> None:
    result = grep(tree, mode="find", glob="*.py", max_results=1)

    assert "capped" in result.content


def test_find_can_start_from_a_single_file(tree) -> None:
    result = grep(tree, mode="find", glob="*.py", path="src/alpha.py")

    assert "alpha.py" in result.content
    assert "beta.py" not in result.content


# --------------------------------------------------------------------------- #
# outline
# --------------------------------------------------------------------------- #


def test_outline_lists_definitions(tree) -> None:
    result = grep(tree, mode="outline", path="src/alpha.py")

    assert "def handler  L1-3" in result.content
    assert "class Widget  L6-8" in result.content


def test_outline_of_a_directory_uses_the_glob(tree) -> None:
    result = grep(tree, mode="outline", glob="*.py", path="src")

    # Paths are relative to the searched directory.
    assert "beta.py:" in result.content
    assert "def other  L1-2" in result.content


def test_outline_of_an_empty_directory_without_a_glob_is_an_error(tree) -> None:
    (tree / "empty").mkdir()

    result = grep(tree, mode="outline", path="empty")

    assert result.is_error is True
    assert "needs 'path' to a file, or a glob" in result.content


def test_outline_reports_files_with_no_definitions(tree) -> None:
    result = grep(tree, mode="outline", glob="*.md", path=".")

    assert "README.md: no recognised definitions" in result.content


def test_outline_reports_a_missing_path(tree) -> None:
    result = grep(tree, mode="outline", glob="*.py", path="nowhere")

    assert result.is_error is True
    assert "Path not found" in result.content


def test_outline_says_when_no_file_matched(tree) -> None:
    result = grep(tree, mode="outline", glob="*.rs", path=".")

    assert result.content == "No files matched for outline"


# --------------------------------------------------------------------------- #
# helpers and registration
# --------------------------------------------------------------------------- #


def test_gitignore_is_only_loaded_when_present(tree) -> None:
    tool = GrepTool()
    assert tool._load_gitignore(str(tree)) is None

    (tree / ".gitignore").write_text("*.log\n", encoding="utf-8")
    spec = tool._load_gitignore(str(tree))

    assert spec is not None
    assert spec.match_file("debug.log")


def test_relative_paths_resolve_against_the_cwd(tree) -> None:
    tool = GrepTool()

    assert tool._resolve_path("src", str(tree)) == str(tree / "src")
    assert tool._resolve_path(str(tree / "src"), str(tree)) == str(tree / "src")


def test_name_matching_rules() -> None:
    matches = GrepTool._name_matches

    assert matches("a.py", None, "") is True
    assert matches("a.py", "*.py", "") is True
    assert matches("a.py", "*.rs", "") is False
    assert matches("a.py", None, "py") is True
    assert matches("a.py", "*.txt", "a") is False


def test_register_adds_the_tool() -> None:
    registry = ToolRegistry()
    register(registry)

    assert "Grep" in {tool.name for tool in registry.get_all()}


def test_a_path_outside_the_workspace_and_system_prefixes_is_refused(tree) -> None:
    """Home and the system read prefixes are allowed; anything else is not."""
    result = grep(tree, pattern="x", path="/nonexistent-root-level-dir")

    assert result.is_error is True
    assert "outside" in result.content.lower()


def test_a_single_file_caps_its_matches(tmp_path) -> None:
    path = tmp_path / "many.txt"
    path.write_text("\n".join("hit" for _ in range(10)), encoding="utf-8")
    import re

    _entries, count, capped = _search_file(str(path), "many.txt", re.compile("hit"), False, 0, 3)

    assert count == 3
    assert capped is True


def test_multiline_matches_are_capped_too(tmp_path) -> None:
    path = tmp_path / "many.txt"
    path.write_text("\n".join("hit" for _ in range(10)), encoding="utf-8")
    import re

    _entries, count, capped = _search_file(str(path), "many.txt", re.compile("hit"), True, 0, 3)

    assert count == 3
    assert capped is True


def test_nearby_context_windows_are_merged(tmp_path) -> None:
    path = tmp_path / "close.txt"
    path.write_text("\n".join(["hit", "a", "hit", "b", "c"]), encoding="utf-8")
    import re

    entries, _count, _capped = _search_file(str(path), "close.txt", re.compile("hit"), False, 1, 10)

    # Lines 1 and 3 are one window (1-4) rather than two overlapping ones.
    assert [line for _p, line, _t, _m in entries] == [1, 2, 3, 4]


def test_many_separate_hits_are_capped_without_context(tmp_path) -> None:
    path = tmp_path / "spread.txt"
    path.write_text("\n".join(["hit", "", "hit", "", "hit", "", "hit"]), encoding="utf-8")
    import re

    _entries, _count, capped = _search_file(
        str(path), "spread.txt", re.compile("hit"), False, 0, 100, max_regions=3
    )

    assert capped is True


def test_find_skips_gitignored_files_and_directories(tree) -> None:
    (tree / ".gitignore").write_text("vendor/\n*.log\n", encoding="utf-8")
    (tree / "vendor").mkdir()
    (tree / "vendor" / "lib.py").write_text("x = 1\n", encoding="utf-8")
    (tree / "debug.log").write_text("noise\n", encoding="utf-8")

    result = grep(tree, mode="find", glob="*")

    assert "vendor" not in result.content
    assert "debug.log" not in result.content
    assert "src/alpha.py" in result.content


def test_grep_honours_a_glob_inside_the_walk(tree) -> None:
    result = grep(tree, pattern=".", glob="*.md")

    assert "README.md" in result.content
    assert "alpha.py" not in result.content


def test_count_mode_ignores_context_lines(tree) -> None:
    result = grep(tree, pattern="return value", glob="alpha.py", context=1, output_mode="count")

    assert "src/alpha.py: 1" in result.content


def test_gitignored_files_are_skipped_inside_kept_directories(tree) -> None:
    (tree / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (tree / "src" / "debug.log").write_text("render inside a log\n", encoding="utf-8")

    result = grep(tree, pattern="render inside a log")

    assert "No matches" in result.content
