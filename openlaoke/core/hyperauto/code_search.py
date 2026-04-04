"""Intelligent code search system for finding and adapting code."""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class SearchSource(StrEnum):
    """Source of code snippets."""

    LOCAL = "local"
    REFERENCE_PROJECT = "reference_project"
    GITHUB = "github"
    STACKOVERFLOW = "stackoverflow"
    DOCS = "docs"


@dataclass
class CodeSnippet:
    """Represents a code snippet found during search."""

    source: str
    file_path: str
    language: str
    content: str
    description: str
    relevance_score: float = 0.0
    adaptability_score: float = 0.0
    line_start: int = 0
    line_end: int = 0
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "file_path": self.file_path,
            "language": self.language,
            "content": self.content,
            "description": self.description,
            "relevance_score": self.relevance_score,
            "adaptability_score": self.adaptability_score,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeSnippet:
        return cls(
            source=data.get("source", ""),
            file_path=data.get("file_path", ""),
            language=data.get("language", ""),
            content=data.get("content", ""),
            description=data.get("description", ""),
            relevance_score=data.get("relevance_score", 0.0),
            adaptability_score=data.get("adaptability_score", 0.0),
            line_start=data.get("line_start", 0),
            line_end=data.get("line_end", 0),
            context=data.get("context", {}),
        )


@dataclass
class SearchResult:
    """Container for search results."""

    query: str
    snippets: list[CodeSnippet]
    total_results: int
    search_time_ms: float = 0.0
    sources_searched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "snippets": [s.to_dict() for s in self.snippets],
            "total_results": self.total_results,
            "search_time_ms": self.search_time_ms,
            "sources_searched": self.sources_searched,
        }


class CodeSearchEngine:
    """Engine for searching code across multiple sources."""

    LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
        "python": [".py", ".pyw", ".pyi"],
        "javascript": [".js", ".jsx", ".mjs"],
        "typescript": [".ts", ".tsx"],
        "java": [".java"],
        "go": [".go"],
        "rust": [".rs"],
        "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
        "c": [".c", ".h"],
        "ruby": [".rb", ".rake"],
        "php": [".php"],
        "swift": [".swift"],
        "kotlin": [".kt", ".kts"],
        "scala": [".scala"],
        "shell": [".sh", ".bash", ".zsh"],
        "yaml": [".yaml", ".yml"],
        "json": [".json"],
        "markdown": [".md", ".markdown"],
    }

    EXTENSION_TO_LANGUAGE: dict[str, str] = {}
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        for ext in exts:
            EXTENSION_TO_LANGUAGE[ext] = lang

    def __init__(
        self,
        project_path: Path | None = None,
        reference_projects: list[Path] | None = None,
        github_token: str | None = None,
    ):
        try:
            self.project_path = project_path or Path.cwd()
        except (OSError, FileNotFoundError):
            self.project_path = Path(".")
        self.reference_projects = reference_projects or []
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self._index_cache: dict[str, list[dict[str, Any]]] = {}

    def search_local(
        self,
        query: str,
        project_path: Path | None = None,
        max_results: int = 50,
        file_pattern: str = "*.py",
    ) -> list[CodeSnippet]:
        """Search local codebase for relevant code."""
        search_path = project_path or self.project_path
        results: list[CodeSnippet] = []

        if not search_path.exists():
            logger.warning(f"Search path does not exist: {search_path}")
            return results

        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for file_path in search_path.rglob(file_pattern):
            if self._should_ignore(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                snippets = self._extract_relevant_snippets(
                    content=content,
                    file_path=str(file_path.relative_to(search_path)),
                    query_terms=query_terms,
                    query=query,
                )
                results.extend(snippets)
            except (PermissionError, OSError) as e:
                logger.debug(f"Cannot read {file_path}: {e}")
                continue

        results.sort(key=lambda s: s.relevance_score, reverse=True)
        return results[:max_results]

    def search_reference_projects(
        self,
        query: str,
        max_results: int = 30,
    ) -> list[CodeSnippet]:
        """Search reference projects for code examples."""
        results: list[CodeSnippet] = []

        for ref_path in self.reference_projects:
            if not ref_path.exists():
                continue

            snippets = self.search_local(
                query=query,
                project_path=ref_path,
                max_results=max_results,
            )
            for snippet in snippets:
                snippet.source = SearchSource.REFERENCE_PROJECT.value
            results.extend(snippets)

        results.sort(key=lambda s: s.relevance_score, reverse=True)
        return results[:max_results]

    async def search_github(
        self,
        query: str,
        language: str = "python",
        max_results: int = 20,
    ) -> list[CodeSnippet]:
        """Search GitHub for code snippets."""
        results: list[CodeSnippet] = []

        try:
            import urllib.request

            encoded_query = quote_plus(f"{query} language:{language}")
            url = f"https://api.github.com/search/code?q={encoded_query}&per_page={max_results}"

            headers = {"Accept": "application/vnd.github.v3+json"}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            for item in data.get("items", []):
                snippet = CodeSnippet(
                    source=SearchSource.GITHUB.value,
                    file_path=item.get("path", ""),
                    language=language,
                    content="",
                    description=f"{item.get('repository', {}).get('full_name', '')}: {item.get('path', '')}",
                    relevance_score=1.0 - (item.get("score", 0) / 100),
                    context={
                        "html_url": item.get("html_url", ""),
                        "repository": item.get("repository", {}).get("full_name", ""),
                    },
                )
                results.append(snippet)

        except Exception as e:
            logger.warning(f"GitHub search failed: {e}")

        return results

    def search_semantic(
        self,
        query: str,
        code_context: str | None = None,
        max_results: int = 20,
    ) -> list[CodeSnippet]:
        """Perform semantic search using code understanding."""
        results: list[CodeSnippet] = []

        local_results = self.search_local(query, max_results=max_results)
        results.extend(local_results)

        ref_results = self.search_reference_projects(query, max_results=max_results)
        results.extend(ref_results)

        if code_context:
            results = self._rerank_by_context(results, code_context)

        results = self._deduplicate(results)
        results.sort(key=lambda s: (s.relevance_score + s.adaptability_score) / 2, reverse=True)

        return results[:max_results]

    def analyze_reusability(self, snippet: CodeSnippet) -> float:
        """Analyze how reusable a code snippet is."""
        if not snippet.content:
            return 0.0

        score = 0.5

        try:
            if snippet.language == "python":
                score = self._analyze_python_reusability(snippet.content)
            else:
                score = self._analyze_generic_reusability(snippet.content)
        except Exception as e:
            logger.debug(f"Reusability analysis failed: {e}")

        snippet.adaptability_score = score
        return score

    def _analyze_python_reusability(self, content: str) -> float:
        """Analyze reusability of Python code."""
        score = 0.5

        try:
            tree = ast.parse(content)

            function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

            if function_count > 0:
                score += 0.1
            if class_count > 0:
                score += 0.1
            if function_count > 2:
                score += 0.05

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.args.args:
                        score += 0.02
                    if ast.unparse(node).startswith("def "):
                        has_docstring = ast.get_docstring(node) is not None
                        if has_docstring:
                            score += 0.03

            imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
            if len(imports) < 5:
                score += 0.05

        except SyntaxError:
            pass

        return min(1.0, score)

    def _analyze_generic_reusability(self, content: str) -> float:
        """Analyze reusability for non-Python code."""
        score = 0.5

        lines = content.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]
        if len(non_empty_lines) > 5:
            score += 0.1

        if "function" in content or "def " in content:
            score += 0.1
        if "class " in content:
            score += 0.1

        comment_ratio = self._calculate_comment_ratio(content)
        if comment_ratio > 0.1:
            score += 0.05

        return min(1.0, score)

    def _calculate_comment_ratio(self, content: str) -> float:
        """Calculate the ratio of comments in code."""
        lines = content.split("\n")
        if not lines:
            return 0.0

        comment_lines = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*"):
                comment_lines += 1

        return comment_lines / len(lines)

    def adapt_code(
        self,
        snippet: CodeSnippet,
        context: dict[str, Any],
    ) -> str:
        """Adapt a code snippet to fit the given context."""
        if not snippet.content:
            return ""

        adapted = snippet.content

        if "imports" in context:
            adapted = self._inject_imports(adapted, context["imports"])

        if "rename_map" in context:
            adapted = self._apply_renames(adapted, context["rename_map"])

        if "target_class" in context:
            adapted = self._adapt_to_class(adapted, context["target_class"])

        if "style" in context:
            adapted = self._apply_style(adapted, context["style"])

        return adapted

    def _inject_imports(self, code: str, imports: list[str]) -> str:
        """Inject necessary imports into code."""
        existing_imports = set()
        lines = code.split("\n")
        import_lines = []

        for line in lines:
            if line.startswith("import ") or line.startswith("from "):
                existing_imports.add(line.strip())
                import_lines.append(line)

        new_imports = []
        for imp in imports:
            if imp not in existing_imports:
                new_imports.append(imp)

        if new_imports:
            insert_pos = 0
            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    insert_pos = i + 1
                elif line.strip() and not line.startswith("#"):
                    break

            for imp in reversed(new_imports):
                lines.insert(insert_pos, imp)

        return "\n".join(lines)

    def _apply_renames(self, code: str, rename_map: dict[str, str]) -> str:
        """Apply variable/function renames to code."""
        for old_name, new_name in rename_map.items():
            pattern = r"\b" + re.escape(old_name) + r"\b"
            code = re.sub(pattern, new_name, code)
        return code

    def _adapt_to_class(self, code: str, target_class: str) -> str:
        """Adapt standalone functions to class methods."""
        lines = code.split("\n")
        adapted_lines = []

        for line in lines:
            if line.strip().startswith("def "):
                if not line.strip().startswith("def __"):
                    indent = len(line) - len(line.lstrip())
                    adapted_lines.append(" " * indent + line.lstrip())
                    adapted_lines.append(" " * (indent + 4) + "self")
                else:
                    adapted_lines.append(line)
            else:
                adapted_lines.append(line)

        return "\n".join(adapted_lines)

    def _apply_style(self, code: str, style: str) -> str:
        """Apply code style transformations."""
        if style == "google":
            code = self._apply_google_style(code)
        elif style == "numpy":
            code = self._apply_numpy_style(code)
        return code

    def _apply_google_style(self, code: str) -> str:
        """Apply Google docstring style."""
        return code

    def _apply_numpy_style(self, code: str) -> str:
        """Apply NumPy docstring style."""
        return code

    async def auto_search_and_adapt(
        self,
        query: str,
        context: dict[str, Any],
        max_results: int = 10,
    ) -> list[str]:
        """Automatically search and adapt code snippets."""
        snippets = self.search_semantic(
            query=query,
            code_context=context.get("code_context"),
            max_results=max_results * 2,
        )

        github_snippets = await self.search_github(
            query=query,
            language=context.get("language", "python"),
            max_results=max_results,
        )
        snippets.extend(github_snippets)

        for snippet in snippets:
            self.analyze_reusability(snippet)

        snippets.sort(
            key=lambda s: (s.relevance_score + s.adaptability_score) / 2,
            reverse=True,
        )

        adapted = []
        seen_content = set()

        for snippet in snippets[:max_results]:
            adapted_code = self.adapt_code(snippet, context)
            content_hash = hash(adapted_code)
            if content_hash not in seen_content:
                adapted.append(adapted_code)
                seen_content.add(content_hash)

        return adapted

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        ignore_dirs = {
            "__pycache__",
            ".git",
            ".hg",
            ".svn",
            "node_modules",
            "venv",
            ".venv",
            "env",
            ".env",
            "dist",
            "build",
            ".tox",
            ".eggs",
            "*.egg-info",
        }

        return any(part in ignore_dirs for part in path.parts)

    def _extract_relevant_snippets(
        self,
        content: str,
        file_path: str,
        query_terms: set[str],
        query: str,
    ) -> list[CodeSnippet]:
        """Extract relevant code snippets from file content."""
        results: list[CodeSnippet] = []
        ext = Path(file_path).suffix.lower()
        language = self.EXTENSION_TO_LANGUAGE.get(ext, "text")

        if language == "python":
            snippets = self._extract_python_snippets(content, file_path, query_terms)
        else:
            snippets = self._extract_generic_snippets(content, file_path, query_terms)

        for snippet in snippets:
            snippet.language = language
            snippet.relevance_score = self._calculate_relevance(
                snippet.content,
                query_terms,
                query,
            )
            results.append(snippet)

        return results

    def _extract_python_snippets(
        self,
        content: str,
        file_path: str,
        query_terms: set[str],
    ) -> list[CodeSnippet]:
        """Extract Python functions and classes."""
        results: list[CodeSnippet] = []

        try:
            tree = ast.parse(content)
            lines = content.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_line = node.lineno - 1
                    end_line = node.end_lineno or start_line + 1

                    snippet_content = "\n".join(lines[start_line:end_line])

                    name = node.name
                    docstring = ast.get_docstring(node) or ""
                    node_type = (
                        "function"
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        else "class"
                    )

                    description = f"{node_type} {name}"
                    if docstring:
                        description += f": {docstring.split(chr(10))[0]}"

                    snippet = CodeSnippet(
                        source=SearchSource.LOCAL.value,
                        file_path=file_path,
                        language="python",
                        content=snippet_content,
                        description=description,
                        line_start=start_line + 1,
                        line_end=end_line,
                    )
                    results.append(snippet)

        except SyntaxError:
            pass

        return results

    def _extract_generic_snippets(
        self,
        content: str,
        file_path: str,
        query_terms: set[str],
    ) -> list[CodeSnippet]:
        """Extract snippets from non-Python files."""
        results: list[CodeSnippet] = []
        lines = content.split("\n")

        snippet_lines: list[str] = []
        snippet_start = 0

        for i, line in enumerate(lines):
            should_include = False
            for term in query_terms:
                if term in line.lower():
                    should_include = True
                    break

            if should_include:
                if not snippet_lines:
                    snippet_start = max(0, i - 2)
                snippet_lines.append(line)
            elif snippet_lines:
                if len(snippet_lines) > 2:
                    snippet_content = "\n".join(snippet_lines)
                    results.append(
                        CodeSnippet(
                            source=SearchSource.LOCAL.value,
                            file_path=file_path,
                            language="text",
                            content=snippet_content,
                            description=f"Lines {snippet_start + 1}-{i}",
                            line_start=snippet_start + 1,
                            line_end=i,
                        )
                    )
                snippet_lines = []

        if snippet_lines and len(snippet_lines) > 2:
            snippet_content = "\n".join(snippet_lines)
            results.append(
                CodeSnippet(
                    source=SearchSource.LOCAL.value,
                    file_path=file_path,
                    language="text",
                    content=snippet_content,
                    description=f"Lines {snippet_start + 1}-{len(lines)}",
                    line_start=snippet_start + 1,
                    line_end=len(lines),
                )
            )

        return results

    def _calculate_relevance(
        self,
        content: str,
        query_terms: set[str],
        query: str,
    ) -> float:
        """Calculate relevance score for a snippet."""
        if not content:
            return 0.0

        content_lower = content.lower()
        score = 0.0

        for term in query_terms:
            if term in content_lower:
                score += 0.2
                count = content_lower.count(term)
                score += min(0.1, count * 0.02)

        if query.lower() in content_lower:
            score += 0.3

        length_penalty = max(0, (len(content) - 500) / 5000)
        score -= length_penalty * 0.1

        return max(0.0, min(1.0, score))

    def _rerank_by_context(
        self,
        snippets: list[CodeSnippet],
        context: str,
    ) -> list[CodeSnippet]:
        """Rerank snippets based on code context."""
        context_terms = set(context.lower().split())

        for snippet in snippets:
            content_terms = set(snippet.content.lower().split())
            overlap = len(context_terms & content_terms)
            snippet.relevance_score += overlap * 0.01

        return sorted(snippets, key=lambda s: s.relevance_score, reverse=True)

    def _deduplicate(self, snippets: list[CodeSnippet]) -> list[CodeSnippet]:
        """Remove duplicate snippets."""
        seen: set[int] = set()
        results: list[CodeSnippet] = []

        for snippet in snippets:
            content_hash = hash(snippet.content)
            if content_hash not in seen:
                seen.add(content_hash)
                results.append(snippet)

        return results
