"""Symbol index used to annotate search results.

Search hits are far more useful when the model can see which definition a line
belongs to: it no longer has to read the whole file to learn that a match sits
inside a 40-line function.  Python uses :mod:`ast` for exact ranges; other
languages fall back to declaration regexes with brace matching, which is
approximate but never wrong about the name.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

MAX_FILE_BYTES = 2_000_000

KIND_DEF = "def"
KIND_CLASS = "class"

RE_PY_DECLS = re.compile(r"^(?P<indent>\s*)(?:async\s+)?(?P<kind>def|class)\s+(?P<name>\w+)")
RE_RUST_FN = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:default\s+)?(?:async\s+)?(?:unsafe\s+)?"
    r"(?:const\s+)?(?:extern\s+\"C\"\s+)?fn\s+(?P<name>\w+)"
)
RE_RUST_TY = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?P<kind>struct|enum|trait|impl|mod)\s+(?P<name>\w+)"
)
RE_GO_FUNC = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)")
RE_JS_DECL = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+(?P<fname>\w+)"
    r"|(?:const|let|var)\s+(?P<cname>\w+)\s*=\s*(?:async\s*)?(?:function|\()"
    r"|class\s+(?P<cls>\w+))"
)
RE_C_FUNC = re.compile(r"^\s{0,4}[\w*][\w\s*&<>,\[\]]*?\s(?P<name>\w+)\s*\([^;]*$")

_LANG_BY_SUFFIX = {
    ".py": "python",
    ".pyi": "python",
    ".rs": "rust",
    ".go": "go",
    ".js": "js",
    ".jsx": "js",
    ".mjs": "js",
    ".ts": "js",
    ".tsx": "js",
    ".java": "c",
    ".c": "c",
    ".h": "c",
    ".cc": "c",
    ".cpp": "c",
    ".hpp": "c",
}


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    start: int
    end: int

    def label(self) -> str:
        return f"{self.kind} {self.name} (L{self.start}-{self.end})"


def language_for(path: str) -> str | None:
    for suffix, lang in _LANG_BY_SUFFIX.items():
        if path.endswith(suffix):
            return lang
    return None


def index_text(path: str, lines: list[str]) -> list[Symbol]:
    """Build the symbol list for one file's contents."""
    lang = language_for(path)
    if lang == "python":
        return _index_python(lines) or _index_python_regex(lines)
    if lang == "rust":
        return _index_braced(lines, (RE_RUST_FN, RE_RUST_TY))
    if lang == "go":
        return _index_braced(lines, (RE_GO_FUNC,))
    if lang == "js":
        return _index_js(lines)
    if lang == "c":
        return _index_braced(lines, (RE_C_FUNC,))
    return []


def index_file(path: str) -> list[Symbol]:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read(MAX_FILE_BYTES).splitlines()
    except (PermissionError, OSError):
        return []
    return index_text(path, lines)


def find_symbol(symbols: list[Symbol], line: int) -> Symbol | None:
    """Innermost definition containing ``line``."""
    best: Symbol | None = None
    for symbol in symbols:
        if symbol.start <= line <= symbol.end and (
            best is None or (symbol.end - symbol.start) < (best.end - best.start)
        ):
            best = symbol
    return best


def label_for(symbols: list[Symbol], line: int) -> str:
    symbol = find_symbol(symbols, line)
    return symbol.label() if symbol else ""


def _index_python(lines: list[str]) -> list[Symbol]:
    try:
        tree = ast.parse("\n".join(lines))
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return []
    found: list[Symbol] = []

    class Visitor(ast.NodeVisitor):
        def _record(self, node: ast.AST, name: str, kind: str) -> None:
            start = getattr(node, "lineno", 0)
            end = getattr(node, "end_lineno", start) or start
            if start:
                found.append(Symbol(name, kind, start, end))

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._record(node, node.name, KIND_DEF)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._record(node, node.name, KIND_DEF)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            self._record(node, node.name, KIND_CLASS)
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _index_python_regex(lines: list[str]) -> list[Symbol]:
    """Indentation-based fallback for files that do not parse."""
    decls: list[tuple[int, str, str, int]] = []
    for idx, line in enumerate(lines):
        match = RE_PY_DECLS.match(line)
        if not match:
            continue
        indent = len(match.group("indent") or "")
        decls.append((idx + 1, match.group("name"), match.group("kind"), indent))
    symbols: list[Symbol] = []
    for position, (start, name, kind, indent) in enumerate(decls):
        end = len(lines)
        for later_start, _later, _later_kind, later_indent in decls[position + 1 :]:
            if later_indent <= indent:
                end = later_start - 1
                break
        symbols.append(Symbol(name, kind, start, max(end, start)))
    return symbols


def _strip_line(line: str) -> str:
    """Remove line comments and string bodies so brace counting is reliable."""
    comment = line.find("//")
    if comment >= 0:
        line = line[:comment]
    out: list[str] = []
    quote: str | None = None
    for char in line:
        if quote:
            if char == quote:
                quote = None
            continue
        if char in "\"'`":
            quote = char
            continue
        out.append(char)
    return "".join(out)


def _match_brace(lines: list[str], start: int) -> int:
    """Closing brace for the block opened at or after ``start``."""
    depth = 0
    opened = False
    limit = min(len(lines), start - 1 + 4000)
    for idx in range(start - 1, limit):
        for char in _strip_line(lines[idx]):
            if char == "{":
                depth += 1
                opened = True
            elif char == "}":
                depth -= 1
                if opened and depth <= 0:
                    return idx + 1
    return min(len(lines), start + 40)


def _index_braced(lines: list[str], patterns: tuple[re.Pattern[str], ...]) -> list[Symbol]:
    symbols: list[Symbol] = []
    for idx, line in enumerate(lines):
        for pattern in patterns:
            match = pattern.match(line)
            if not match:
                continue
            groups = match.groupdict()
            name = groups.get("name") or next((v for v in groups.values() if v), "")
            if not name:
                break
            kind = KIND_CLASS if groups.get("kind") else KIND_DEF
            start = idx + 1
            symbols.append(Symbol(name, kind, start, _match_brace(lines, start)))
            break
    return symbols


def _index_js(lines: list[str]) -> list[Symbol]:
    symbols: list[Symbol] = []
    for idx, line in enumerate(lines):
        match = RE_JS_DECL.match(line)
        if not match:
            continue
        groups = match.groupdict()
        name = groups.get("fname") or groups.get("cname") or groups.get("cls")
        if not name:
            continue
        kind = KIND_CLASS if groups.get("cls") else KIND_DEF
        start = idx + 1
        symbols.append(Symbol(name, kind, start, _match_brace(lines, start)))
    return symbols
