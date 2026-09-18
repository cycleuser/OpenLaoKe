"""Prompt template system, adapted from pi's ``/name`` markdown templates.

Templates are Markdown files whose filename (without ``.md``) becomes a
``/name`` shortcut.  A template may declare ``description`` and
``argument-hint`` in YAML frontmatter, and references positional arguments
with ``$1``, ``$@``/``$ARGUMENTS``, ``${1:-default}``, ``${@:N}`` and
``${@:N:L}``.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_BRACED_RE = re.compile(r"\$\{([^}]*)\}")
_ARGUMENTS_RE = re.compile(r"\$(?:ARGUMENTS\b|@)")
_POSITIONAL_RE = re.compile(r"\$(\d+)")


def parse_arguments(raw: str) -> list[str]:
    """Split a raw argument string into positional arguments, honoring quotes."""
    if not raw or not raw.strip():
        return []
    try:
        return shlex.split(raw, posix=True)
    except ValueError:
        return raw.split()


def _slice(expr: str, args: list[str]) -> str | None:
    """Resolve ``@:N`` and ``@:N:L`` slice expressions. Returns None if not a slice."""
    m = re.match(r"^@:(\d+)(?::(\d+))?$", expr)
    if not m:
        return None
    start = max(0, int(m.group(1)) - 1)
    if m.group(2) is None:
        return " ".join(args[start:])
    length = int(m.group(2))
    return " ".join(args[start : start + length])


def _expand_braced(expr: str, args: list[str], joined: str) -> str:
    """Expand one ``${...}`` expression."""
    if ":-" in expr:
        name, default = expr.split(":-", 1)
        name = name.strip()
        if name in ("@", "ARGUMENTS"):
            return joined if joined else default
        if name.isdigit():
            idx = int(name)
            if 1 <= idx <= len(args) and args[idx - 1]:
                return args[idx - 1]
            return default
        return default
    sliced = _slice(expr.strip(), args)
    if sliced is not None:
        return sliced
    return "${" + expr + "}"


def expand_template(content: str, arguments: str | list[str]) -> str:
    """Substitute positional arguments into template content."""
    args = parse_arguments(arguments) if isinstance(arguments, str) else list(arguments)
    joined = " ".join(args)

    def braced(match: re.Match[str]) -> str:
        return _expand_braced(match.group(1), args, joined)

    result = _BRACED_RE.sub(braced, content)
    result = _ARGUMENTS_RE.sub(joined, result)

    def positional(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        if 1 <= idx <= len(args):
            return args[idx - 1]
        return match.group(0)

    return _POSITIONAL_RE.sub(positional, result)


@dataclass
class PromptTemplate:
    """A prompt template loaded from a Markdown file."""

    name: str
    content: str
    description: str = ""
    argument_hint: str = ""
    path: Path | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> PromptTemplate | None:
        if not path.exists() or not path.is_file():
            return None
        try:
            return cls.from_content(path.read_text(encoding="utf-8"), path=path)
        except OSError:
            return None

    @classmethod
    def from_content(cls, content: str, path: Path | None = None) -> PromptTemplate:
        metadata: dict[str, object] = {}
        body = content
        match = _FRONTMATTER_RE.match(content)
        if match:
            try:
                parsed = yaml.safe_load(match.group(1))
                if isinstance(parsed, dict):
                    metadata = parsed
            except yaml.YAMLError:
                metadata = {}
            body = content[match.end() :]

        body = body.strip()
        name = path.stem if path else "template"
        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip():
            description = ""
            for line in body.splitlines():
                if line.strip():
                    description = line.strip()
                    break
        argument_hint = metadata.get("argument-hint", metadata.get("argument_hint", ""))
        return cls(
            name=name,
            content=body,
            description=description.strip(),
            argument_hint=str(argument_hint).strip() if argument_hint else "",
            path=path,
            metadata=metadata,
        )

    def expand(self, arguments: str | list[str]) -> str:
        return expand_template(self.content, arguments)


class PromptTemplateRegistry:
    """Registry of prompt templates discovered from one or more directories."""

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._dirs: list[Path] = []

    def add_directory(self, directory: Path | str) -> int:
        directory = Path(directory).expanduser()
        if not directory.exists() or not directory.is_dir():
            return 0
        self._dirs.append(directory)
        count = 0
        for entry in sorted(directory.glob("*.md")):
            template = PromptTemplate.from_file(entry)
            if template and template.name:
                self._templates[template.name] = template
                count += 1
        return count

    def get(self, name: str) -> PromptTemplate | None:
        return self._templates.get(name)

    def names(self) -> list[str]:
        return sorted(self._templates.keys())

    def all(self) -> list[PromptTemplate]:
        return [self._templates[name] for name in self.names()]

    def expand(self, name: str, arguments: str | list[str] = "") -> str | None:
        template = self.get(name)
        if template is None:
            return None
        return template.expand(arguments)


def get_default_prompt_dirs() -> list[Path]:
    """Default prompt template directories (global first, project last)."""
    home = Path.home()
    dirs: list[Path] = []
    global_prompts = home / ".openlaoke" / "prompts"
    if global_prompts.exists():
        dirs.append(global_prompts)
    project_prompts = Path.cwd() / ".openlaoke" / "prompts"
    if project_prompts.exists():
        dirs.append(project_prompts)
    return dirs


_global_registry: PromptTemplateRegistry | None = None


def get_prompt_registry() -> PromptTemplateRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = PromptTemplateRegistry()
        for directory in get_default_prompt_dirs():
            _global_registry.add_directory(directory)
    return _global_registry


def rescan_prompt_templates() -> int:
    global _global_registry
    _global_registry = PromptTemplateRegistry()
    for directory in get_default_prompt_dirs():
        _global_registry.add_directory(directory)
    return len(_global_registry.names())


def list_prompt_templates() -> list[str]:
    return get_prompt_registry().names()


def load_prompt_template(name: str) -> PromptTemplate | None:
    return get_prompt_registry().get(name)


def expand_prompt_template(name: str, arguments: str = "") -> str | None:
    return get_prompt_registry().expand(name, arguments)
