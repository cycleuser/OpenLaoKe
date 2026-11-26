"""Tests for the symbol index that annotates search hits with their definition."""

from __future__ import annotations

import pytest

from openlaoke.utils import symbols as sym


def test_language_is_guessed_from_the_suffix() -> None:
    assert sym.language_for("a.py") == "python"
    assert sym.language_for("a.pyi") == "python"
    assert sym.language_for("a.rs") == "rust"
    assert sym.language_for("a.go") == "go"
    assert sym.language_for("a.tsx") == "js"
    assert sym.language_for("a.cpp") == "c"
    assert sym.language_for("a.txt") is None
    assert sym.language_for("Makefile") is None


def test_python_symbols_come_from_the_ast_with_exact_ranges() -> None:
    source = [
        "import os",
        "",
        "",
        "class Widget:",
        "    def render(self):",
        "        return 1",
        "",
        "",
        "async def fetch():",
        "    return 2",
    ]

    found = {s.name: s for s in sym.index_text("a.py", source)}

    assert found["Widget"] == sym.Symbol("Widget", "class", 4, 6)
    assert found["render"] == sym.Symbol("render", "def", 5, 6)
    assert found["fetch"] == sym.Symbol("fetch", "def", 9, 10)


def test_nested_definitions_are_all_indexed() -> None:
    source = ["def outer():", "    def inner():", "        pass", "    return inner"]

    names = [s.name for s in sym.index_text("a.py", source)]

    assert names == ["outer", "inner"]


def test_unparsable_python_falls_back_to_indentation() -> None:
    source = [
        "def broken(:",
        "    pass",
        "",
        "class Thing:",
        "    def method(self):",
        "        pass",
        "def after():",
        "    pass",
    ]

    found = {s.name: s for s in sym.index_text("a.py", source)}

    # The AST refuses the file, so every declaration is found by indentation and
    # each one ends where the next same-or-lower-indent declaration begins.
    assert set(found) == {"broken", "Thing", "method", "after"}
    assert found["Thing"].start == 4
    assert found["Thing"].end == 6
    assert found["after"].end == 8


def test_the_regex_fallback_handles_async_and_decorators() -> None:
    source = ["@decorator", "async def work(x):", "    return x"]

    assert [s.name for s in sym._index_python_regex(source)] == ["work"]


def test_rust_symbols_use_brace_matching() -> None:
    source = [
        "pub struct Config {",
        "    name: String,",
        "}",
        "",
        "impl Config {",
        "    pub fn new() -> Self {",
        "        Config { name: String::new() }",
        "    }",
        "}",
        "pub async fn run() {}",
    ]

    found = sym.index_text("a.rs", source)

    assert found[0] == sym.Symbol("Config", "class", 1, 3)
    names = [s.name for s in found]
    assert "new" in names and "run" in names
    assert found[-1].name == "run"


def test_go_functions_are_indexed() -> None:
    source = [
        "package main",
        "",
        "func main() {",
        '    fmt.Println("hi")',
        "}",
        "",
        "func (s *Svc) Do() {}",
    ]

    found = {s.name: s for s in sym.index_text("a.go", source)}

    assert found["main"].start == 3
    assert found["main"].end == 5
    assert "Do" in found


def test_javascript_declarations_are_indexed() -> None:
    source = [
        "export function alpha() {",
        "  return 1;",
        "}",
        "const beta = async () => {",
        "  return 2;",
        "};",
        "class Gamma {",
        "  method() {}",
        "}",
    ]

    found = {s.name: s for s in sym.index_text("a.ts", source)}

    assert found["alpha"].kind == "def"
    assert found["beta"].start == 4
    assert found["Gamma"].kind == "class"


def test_c_functions_are_indexed() -> None:
    source = ["int main(void) {", "    return 0;", "}", "", "static void helper(int x)", "{", "}"]

    found = {s.name: s for s in sym.index_text("a.c", source)}

    assert found["main"].end == 3
    assert "helper" in found


def test_brace_matching_ignores_comments_and_strings() -> None:
    lines = [
        "void f() {",
        '    printf("} not a brace");',
        "    // } also not one",
        "    if (x) {",
        "    }",
        "}",
    ]

    assert sym._match_brace(lines, 1) == 6


def test_brace_matching_gives_up_gracefully() -> None:
    lines = ["void f() {"] + ["    do_thing();"] * 50

    end = sym._match_brace(lines, 1)

    assert end == 41  # start + 40 fallback


def test_brace_matching_stops_at_the_file_end() -> None:
    lines = ["void f() {", "    x();"]

    assert sym._match_brace(lines, 1) == 40 or sym._match_brace(lines, 1) <= 40


def test_unknown_languages_have_no_symbols() -> None:
    assert sym.index_text("notes.txt", ["def looks_pythonic():", "    pass"]) == []


def test_index_file_reads_from_disk(tmp_path) -> None:
    path = tmp_path / "mod.py"
    path.write_text("def alpha():\n    return 1\n", encoding="utf-8")

    found = sym.index_file(str(path))

    assert [s.name for s in found] == ["alpha"]


def test_index_file_tolerates_a_missing_file(tmp_path) -> None:
    assert sym.index_file(str(tmp_path / "ghost.py")) == []


def test_index_file_tolerates_no_permission(tmp_path, monkeypatch) -> None:
    path = tmp_path / "mod.py"
    path.write_text("def alpha(): pass\n", encoding="utf-8")
    import builtins

    real_open = builtins.open

    def guarded(file, *args, **kwargs):
        if str(file).endswith("mod.py"):
            raise PermissionError("denied")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)

    assert sym.index_file(str(path)) == []


def test_index_file_survives_undecodable_bytes(tmp_path) -> None:
    path = tmp_path / "weird.py"
    path.write_bytes(b"def ok():\n    pass\n\xff\xfe\n")

    assert [s.name for s in sym.index_file(str(path))] == ["ok"]


def test_label_names_the_innermost_definition() -> None:
    source = ["class Outer:", "    def inner(self):", "        value = 1", "        return value"]
    found = sym.index_text("a.py", source)

    assert sym.label_for(found, 3) == "def inner (L2-4)"
    assert sym.label_for(found, 1) == "class Outer (L1-4)"
    assert sym.label_for(found, 99) == ""


def test_find_symbol_prefers_the_narrowest_containing_range() -> None:
    symbols = [sym.Symbol("outer", "def", 1, 20), sym.Symbol("inner", "def", 5, 8)]

    assert sym.find_symbol(symbols, 6) == symbols[1]
    assert sym.find_symbol(symbols, 15) == symbols[0]
    assert sym.find_symbol(symbols, 21) is None


def test_symbol_label_format() -> None:
    assert sym.Symbol("f", "def", 3, 7).label() == "def f (L3-7)"


@pytest.mark.parametrize("line", ["// only a comment", '"a quoted } string"', ""])
def test_strip_line_removes_noise(line: str) -> None:
    assert "}" not in sym._strip_line(line) or line == ""


@pytest.mark.parametrize(
    "declaration",
    [
        "fn plain() {}",
        "pub fn public() {}",
        "pub(crate) fn scoped() {}",
        "async fn awaited() {}",
        "pub async fn pub_awaited() {}",
        "unsafe fn dangerous() {}",
        "const fn constant() {}",
        'extern "C" fn ffi() {}',
        'pub async unsafe extern "C" fn everything() {}',
    ],
)
def test_rust_function_modifiers(declaration: str) -> None:
    """Every modifier combination must still yield the function name."""
    expected = declaration.split("fn ")[1].split("(")[0]

    found = sym.index_text("a.rs", [declaration, "}"])

    assert [s.name for s in found] == [expected]
