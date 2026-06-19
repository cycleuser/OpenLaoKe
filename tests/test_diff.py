"""Tests for openlaoke.utils.diff — LCS diff generator ported from sekrun."""
from __future__ import annotations

from openlaoke.utils.diff import diff_lines


class TestDiffLines:
    def test_new_file(self):
        result = diff_lines("a.py", "", "hello\nworld", False)
        assert "(new file)" in result
        assert "+hello" in result
        assert "+world" in result

    def test_identical_no_changes(self):
        result = diff_lines("a.py", "abc\ndef", "abc\ndef", True)
        assert "(no changes)" in result

    def test_single_line_change(self):
        result = diff_lines("a.py", "old\n", "new\n", True)
        assert "-old" in result
        assert "+new" in result
        assert "@@" in result

    def test_add_line_middle(self):
        result = diff_lines("a.py", "line1\nline3\n", "line1\nline2\nline3\n", True)
        assert "+line2" in result

    def test_delete_line(self):
        result = diff_lines("a.py", "a\nb\nc\n", "a\nc\n", True)
        assert "-b" in result

    def test_multiple_hunks(self):
        old = "\n".join(f"line{i}" for i in range(1, 21))
        new = "\n".join(f"line{i}" for i in range(1, 11)) + "\n" + "\n".join(
            f"line{i}" for i in range(16, 21)
        )
        result = diff_lines("a.py", old, new, True)
        assert result.count("@@") >= 1
        assert "-line11" in result

    def test_empty_new_file(self):
        result = diff_lines("a.py", "", "", False)
        assert "(empty new file)" in result

    def test_completely_different_content(self):
        result = diff_lines("a.py", "old content\n", "brand new content\n", True)
        assert "-old content" in result
        assert "+brand new content" in result

    def test_new_file_with_single_line(self):
        result = diff_lines("a.py", "", "only line", False)
        assert "(new file)" in result
        assert "+only line" in result

    def test_deleting_all_lines(self):
        result = diff_lines("a.py", "a\nb\nc\n", "", True)
        assert "-a" in result
        assert "-b" in result
        assert "-c" in result
