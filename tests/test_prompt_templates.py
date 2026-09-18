"""Tests for the pi-inspired prompt template system."""

from __future__ import annotations

from pathlib import Path

from openlaoke.core.prompt_templates import (
    PromptTemplate,
    PromptTemplateRegistry,
    expand_template,
    parse_arguments,
)


def _write(directory: Path, name: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class TestParseArguments:
    def test_empty(self) -> None:
        assert parse_arguments("") == []
        assert parse_arguments("   ") == []

    def test_plain(self) -> None:
        assert parse_arguments("a b c") == ["a", "b", "c"]

    def test_quoted(self) -> None:
        assert parse_arguments('Button "onClick handler"') == ["Button", "onClick handler"]

    def test_unbalanced_quotes_fallback(self) -> None:
        assert parse_arguments('a "b') == ["a", '"b']


class TestExpandTemplate:
    def test_positional(self) -> None:
        assert expand_template("Create $1 with $2", "Button disabled") == "Create Button with disabled"

    def test_all_arguments(self) -> None:
        assert expand_template("Features: $@", "a b c") == "Features: a b c"
        assert expand_template("Features: $ARGUMENTS", "a b c") == "Features: a b c"

    def test_default_when_missing(self) -> None:
        assert expand_template("Use ${1:-7} points", "") == "Use 7 points"
        assert expand_template("Use ${1:-7} points", "3") == "Use 3 points"

    def test_arguments_default(self) -> None:
        assert expand_template("Do ${@:-nothing}", "") == "Do nothing"
        assert expand_template("Do ${@:-nothing}", "x y") == "Do x y"

    def test_slice_from(self) -> None:
        assert expand_template("rest: ${@:2}", "a b c") == "rest: b c"
        assert expand_template("rest: ${@:2}", "a") == "rest: "

    def test_slice_length(self) -> None:
        assert expand_template("mid: ${@:2:2}", "a b c d") == "mid: b c"

    def test_missing_positional_kept(self) -> None:
        assert expand_template("x $3", "a b") == "x $3"

    def test_empty_when_no_args(self) -> None:
        assert expand_template("hello", "") == "hello"


class TestPromptTemplate:
    def test_frontmatter_description(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "review.md",
            "---\ndescription: Review staged changes\n---\nReview $1 now.\n",
        )
        t = PromptTemplate.from_file(p)
        assert t is not None
        assert t.name == "review"
        assert t.description == "Review staged changes"
        assert t.content == "Review $1 now."
        assert t.expand("foo") == "Review foo now."

    def test_description_fallback(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "plain.md", "\nFirst meaningful line\nsecond\n")
        t = PromptTemplate.from_file(p)
        assert t is not None
        assert t.description == "First meaningful line"

    def test_argument_hint(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "pr.md",
            '---\ndescription: Review PR\nargument-hint: "<PR-URL>"\n---\nbody\n',
        )
        t = PromptTemplate.from_file(p)
        assert t is not None
        assert t.argument_hint == "<PR-URL>"

    def test_invalid_frontmatter_is_ignored(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "broken.md", "---\n: : invalid : :\n---\nBody here\n")
        t = PromptTemplate.from_file(p)
        assert t is not None
        assert t.content == "Body here"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert PromptTemplate.from_file(tmp_path / "nope.md") is None


class TestPromptTemplateRegistry:
    def test_discovery_and_lookup(self, tmp_path: Path) -> None:
        _write(tmp_path, "one.md", "---\ndescription: One\n---\nbody one\n")
        _write(tmp_path, "two.md", "body two\n")
        registry = PromptTemplateRegistry()
        assert registry.add_directory(tmp_path) == 2
        assert registry.names() == ["one", "two"]
        assert registry.get("one").description == "One"
        assert registry.expand("two", "arg") == "body two"
        assert registry.expand("missing") is None

    def test_non_recursive(self, tmp_path: Path) -> None:
        _write(tmp_path, "top.md", "top\n")
        _write(tmp_path / "nested", "deep.md", "deep\n")
        registry = PromptTemplateRegistry()
        assert registry.add_directory(tmp_path) == 1
        assert registry.names() == ["top"]

    def test_missing_directory(self, tmp_path: Path) -> None:
        registry = PromptTemplateRegistry()
        assert registry.add_directory(tmp_path / "absent") == 0

    def test_later_directory_overrides(self, tmp_path: Path) -> None:
        first = tmp_path / "a"
        second = tmp_path / "b"
        _write(first, "same.md", "from-a\n")
        _write(second, "same.md", "from-b\n")
        registry = PromptTemplateRegistry()
        registry.add_directory(first)
        registry.add_directory(second)
        assert registry.get("same").content == "from-b"
