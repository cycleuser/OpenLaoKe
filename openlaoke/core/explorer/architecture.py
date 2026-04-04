"""Architecture exploration and analysis module."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.explorer.explorer import ArchitectureAnalysis


@dataclass
class DependencyGraph:
    """Graph representation of code dependencies."""

    nodes: set[str] = field(default_factory=set)
    edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    reverse_edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_node(self, node: str) -> None:
        self.nodes.add(node)

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.nodes.add(from_node)
        self.nodes.add(to_node)
        self.edges[from_node].add(to_node)
        self.reverse_edges[to_node].add(from_node)

    def get_dependencies(self, node: str) -> set[str]:
        return self.edges.get(node, set())

    def get_dependents(self, node: str) -> set[str]:
        return self.reverse_edges.get(node, set())

    def find_cycles(self) -> list[list[str]]:
        visited = set()
        rec_stack = set()
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.edges.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            rec_stack.remove(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node, [])

        return cycles

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "edges": {k: list(v) for k, v in self.edges.items()},
            "reverse_edges": {k: list(v) for k, v in self.reverse_edges.items()},
        }


@dataclass
class ModuleInfo:
    """Information about a Python module."""

    path: Path
    imports: list[str]
    exports: list[str]
    classes: list[str]
    functions: list[str]
    complexity: float = 0.0
    loc: int = 0
    docstring: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "imports": self.imports,
            "exports": self.exports,
            "classes": self.classes,
            "functions": self.functions,
            "complexity": self.complexity,
            "loc": self.loc,
            "docstring": self.docstring,
        }


class ArchitectureExplorer:
    """Analyzes and explores project architecture.

    This class provides comprehensive architecture analysis including:
    - Project structure mapping
    - Design pattern detection
    - Dependency analysis
    - Code smell detection
    - Architecture improvement suggestions
    """

    DESIGN_PATTERNS = {
        "singleton": r"class\s+\w+.*:\s*\n(?:.*\n)*?\s*_instance\s*=",
        "factory": r"(?:class|def)\s+\w*[Ff]actory\w*",
        "observer": r"(?:def|class)\s+\w*[Oo]bserver\w*",
        "strategy": r"class\s+\w*[Ss]trategy\w*",
        "builder": r"class\s+\w*[Bb]uilder\w*",
        "adapter": r"class\s+\w*[Aa]dapter\w*",
        "decorator": r"(?:def\s+\w+.*\n\s*def\s+\w+|@\w+.*\n\s*def\s+\w+)",
        "facade": r"class\s+\w*[Ff]acade\w*",
        "proxy": r"class\s+\w*[Pp]roxy\w*",
        "command": r"class\s+\w*[Cc]ommand\w*",
        "state": r"class\s+\w*[Ss]tate\w*",
        "template": r"class\s+\w*[Tt]emplate\w*",
    }

    CODE_SMELLS = {
        "long_function": {"threshold": 50, "description": "Function exceeds 50 lines"},
        "many_parameters": {"threshold": 6, "description": "Function has more than 6 parameters"},
        "deep_nesting": {"threshold": 4, "description": "Code has more than 4 levels of nesting"},
        "duplicate_code": {"threshold": 0.8, "description": "Similar code blocks detected"},
        "large_class": {"threshold": 500, "description": "Class exceeds 500 lines"},
        "god_class": {"threshold": 20, "description": "Class has more than 20 methods"},
        "long_parameter_list": {"threshold": 4, "description": "Parameter list too long"},
        "circular_dependency": {"threshold": 0, "description": "Circular dependencies detected"},
    }

    def __init__(self) -> None:
        self._dependency_graph = DependencyGraph()
        self._modules: dict[str, ModuleInfo] = {}

    async def analyze(self, project_path: Path) -> ArchitectureAnalysis:
        """Perform comprehensive architecture analysis.

        Args:
            project_path: Root path of the project

        Returns:
            ArchitectureAnalysis with all findings
        """
        from openlaoke.core.explorer.explorer import ArchitectureAnalysis

        structure = await self._analyze_structure(project_path)
        design_patterns = await self._detect_patterns(project_path)
        dependencies = await self._analyze_dependencies(project_path)
        code_smells = await self._detect_code_smells(project_path)
        suggestions = self._generate_suggestions(structure, design_patterns, code_smells)

        return ArchitectureAnalysis(
            project_path=project_path,
            structure=structure,
            design_patterns=design_patterns,
            dependencies=dependencies,
            code_smells=code_smells,
            improvement_suggestions=suggestions,
        )

    async def _analyze_structure(self, path: Path) -> dict[str, Any]:
        """Analyze the directory structure."""
        structure: dict[str, Any] = {}

        for item in path.rglob("*.py"):
            if "__pycache__" in str(item) or ".venv" in str(item):
                continue

            rel_path = item.relative_to(path)
            parts = list(rel_path.parts)

            current = structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            module_info = await self._analyze_module(item)
            current[parts[-1]] = module_info.to_dict()
            self._modules[str(rel_path)] = module_info

        return structure

    async def _analyze_module(self, file_path: Path) -> ModuleInfo:
        """Analyze a single Python module."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return ModuleInfo(
                path=file_path,
                imports=[],
                exports=[],
                classes=[],
                functions=[],
            )

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return ModuleInfo(
                path=file_path,
                imports=[],
                exports=[],
                classes=[],
                functions=[],
            )

        imports: list[str] = []
        exports: list[str] = []
        classes: list[str] = []
        functions: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(
                    f"{module}.{alias.name}" if module else alias.name for alias in node.names
                )
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
                if node.name[0].isupper() and not node.name.startswith("_"):
                    exports.append(node.name)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions.append(node.name)
                if not node.name.startswith("_"):
                    exports.append(node.name)

        complexity = self._calculate_complexity(tree)
        loc = len(content.splitlines())
        docstring = ast.get_docstring(tree) or ""

        return ModuleInfo(
            path=file_path,
            imports=imports,
            exports=exports,
            classes=classes,
            functions=functions,
            complexity=complexity,
            loc=loc,
            docstring=docstring,
        )

    def _calculate_complexity(self, tree: ast.AST) -> float:
        """Calculate cyclomatic complexity of the AST."""
        complexity = 1

        for node in ast.walk(tree):
            if isinstance(node, ast.If | ast.While | ast.For | ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, ast.comprehension):
                complexity += 1
                if node.ifs:
                    complexity += len(node.ifs)

        return float(complexity)

    async def _detect_patterns(self, path: Path) -> list[str]:
        """Detect design patterns in the codebase."""
        detected_patterns: set[str] = set()

        for file_path in path.rglob("*.py"):
            if "__pycache__" in str(file_path) or ".venv" in str(file_path):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            for pattern_name, pattern_regex in self.DESIGN_PATTERNS.items():
                if re.search(pattern_regex, content, re.MULTILINE):
                    detected_patterns.add(pattern_name)

        return list(detected_patterns)

    async def _analyze_dependencies(self, path: Path) -> dict[str, Any]:
        """Analyze module dependencies."""
        self._dependency_graph = DependencyGraph()

        for module_path, module_info in self._modules.items():
            module_name = module_path.replace("/", ".").replace(".py", "")
            self._dependency_graph.add_node(module_name)

            for imp in module_info.imports:
                if imp.startswith("openlaoke."):
                    self._dependency_graph.add_edge(module_name, imp)

        return {
            "graph": self._dependency_graph.to_dict(),
            "cycles": self._dependency_graph.find_cycles(),
        }

    async def _detect_code_smells(self, path: Path) -> list[dict[str, Any]]:
        """Detect code smells in the codebase."""
        smells: list[dict[str, Any]] = []

        for file_path in path.rglob("*.py"):
            if "__pycache__" in str(file_path) or ".venv" in str(file_path):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            smells.extend(self._detect_smells_in_file(file_path, tree))

        return smells

    def _detect_smells_in_file(self, file_path: Path, tree: ast.AST) -> list[dict[str, Any]]:
        """Detect code smells in a single file."""
        smells: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                end_lineno = getattr(node, "end_lineno", None)
                func_lines = (end_lineno - node.lineno) if end_lineno is not None else 0
                threshold_value = self.CODE_SMELLS["long_function"]["threshold"]
                threshold = (
                    int(threshold_value) if isinstance(threshold_value, (int, float)) else 50
                )
                if func_lines > threshold:
                    smells.append(
                        {
                            "type": "long_function",
                            "file": str(file_path),
                            "line": node.lineno,
                            "name": node.name,
                            "value": func_lines,
                            "description": self.CODE_SMELLS["long_function"]["description"],
                        }
                    )

                param_count = len(node.args.args)
                param_threshold_value = self.CODE_SMELLS["many_parameters"]["threshold"]
                param_threshold = (
                    int(param_threshold_value)
                    if isinstance(param_threshold_value, (int, float))
                    else 6
                )
                if param_count > param_threshold:
                    smells.append(
                        {
                            "type": "many_parameters",
                            "file": str(file_path),
                            "line": node.lineno,
                            "name": node.name,
                            "value": param_count,
                            "description": self.CODE_SMELLS["many_parameters"]["description"],
                        }
                    )

            elif isinstance(node, ast.ClassDef):
                method_count = sum(
                    1
                    for n in ast.walk(node)
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                )
                god_threshold_value = self.CODE_SMELLS["god_class"]["threshold"]
                god_threshold = (
                    int(god_threshold_value)
                    if isinstance(god_threshold_value, (int, float))
                    else 20
                )
                if method_count > god_threshold:
                    smells.append(
                        {
                            "type": "god_class",
                            "file": str(file_path),
                            "line": node.lineno,
                            "name": node.name,
                            "value": method_count,
                            "description": self.CODE_SMELLS["god_class"]["description"],
                        }
                    )

        return smells

    def _generate_suggestions(
        self,
        structure: dict[str, Any],
        patterns: list[str],
        smells: list[dict[str, Any]],
    ) -> list[str]:
        """Generate improvement suggestions based on analysis."""
        suggestions: list[str] = []

        if len(smells) > 10:
            suggestions.append(
                "Consider refactoring to reduce code smells. "
                "Focus on the most critical issues first."
            )

        long_functions = [s for s in smells if s["type"] == "long_function"]
        if len(long_functions) > 5:
            suggestions.append(
                "Multiple long functions detected. "
                "Consider breaking them into smaller, focused functions."
            )

        if "factory" not in patterns and len(self._modules) > 20:
            suggestions.append("Consider using the Factory pattern for complex object creation.")

        cycles = self._dependency_graph.find_cycles()
        if cycles:
            suggestions.append(
                f"Circular dependencies detected: {len(cycles)} cycles. "
                "Consider using dependency injection or refactoring."
            )

        if not suggestions:
            suggestions.append(
                "Architecture looks good! Continue maintaining code quality standards."
            )

        return suggestions

    def get_module_info(self, module_path: str) -> ModuleInfo | None:
        """Get information about a specific module."""
        return self._modules.get(module_path)

    def get_dependency_graph(self) -> DependencyGraph:
        """Get the dependency graph."""
        return self._dependency_graph
