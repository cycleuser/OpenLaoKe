"""Code understanding and semantic analysis engine."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.explorer.explorer import CodeUnderstanding


@dataclass
class SemanticContext:
    """Semantic context extracted from code."""

    domain_concepts: list[str]
    business_logic: list[str]
    data_flows: list[str]
    control_flows: list[str]
    abstractions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_concepts": self.domain_concepts,
            "business_logic": self.business_logic,
            "data_flows": self.data_flows,
            "control_flows": self.control_flows,
            "abstractions": self.abstractions,
        }


@dataclass
class IntentAnalysis:
    """Analysis of code intent and purpose."""

    primary_intent: str
    secondary_intents: list[str]
    assumptions: list[str]
    constraints: list[str]
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_intent": self.primary_intent,
            "secondary_intents": self.secondary_intents,
            "assumptions": self.assumptions,
            "constraints": self.constraints,
            "confidence": self.confidence,
        }


@dataclass
class BehaviorModel:
    """Model of code behavior."""

    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    side_effects: list[str]
    preconditions: list[str]
    postconditions: list[str]
    invariants: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "side_effects": self.side_effects,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "invariants": self.invariants,
        }


class CodeUnderstandingEngine:
    """Deep code understanding and semantic analysis engine.

    This class provides comprehensive code understanding through:
    - Semantic analysis
    - Intent inference
    - Behavior modeling
    - Quality metrics
    """

    DOMAIN_KEYWORDS = {
        "data": ["data", "record", "entry", "item", "entity", "model"],
        "api": ["api", "endpoint", "route", "request", "response", "handler"],
        "database": ["db", "database", "query", "table", "schema", "migration"],
        "auth": ["auth", "login", "token", "session", "user", "permission"],
        "config": ["config", "setting", "option", "preference", "env"],
        "test": ["test", "spec", "mock", "fixture", "assert"],
        "util": ["util", "helper", "common", "shared", "tool"],
        "core": ["core", "main", "primary", "base", "foundation"],
    }

    INTENT_INDICATORS = {
        "validation": ["validate", "check", "verify", "ensure", "assert"],
        "transformation": ["transform", "convert", "parse", "format", "serialize"],
        "query": ["get", "fetch", "retrieve", "query", "find", "search"],
        "mutation": ["create", "update", "delete", "modify", "save", "write"],
        "coordination": ["coordinate", "orchestrate", "manage", "control", "schedule"],
        "communication": ["send", "receive", "notify", "emit", "broadcast"],
    }

    def __init__(self) -> None:
        self._analysis_cache: dict[str, CodeUnderstanding] = {}

    async def analyze(self, file_path: Path) -> CodeUnderstanding:
        """Perform deep code understanding analysis.

        Args:
            file_path: Path to the file to analyze

        Returns:
            CodeUnderstanding with complete analysis
        """
        from openlaoke.core.explorer.explorer import CodeUnderstanding

        cache_key = str(file_path)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return CodeUnderstanding(
                file_path=file_path,
                semantic_summary="Unable to read file",
                intent="Unknown",
                behavior_model={},
                complexity_score=0.0,
                quality_metrics={},
            )

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return CodeUnderstanding(
                file_path=file_path,
                semantic_summary="Unable to parse file",
                intent="Unknown",
                behavior_model={},
                complexity_score=0.0,
                quality_metrics={},
            )

        semantic_ctx = self._extract_semantics(tree, content)
        intent_analysis = self._infer_intent(tree, content, semantic_ctx)
        behavior_model = self._model_behavior(tree)
        complexity = self._calculate_complexity(tree)
        quality = self._calculate_quality(tree, content)

        understanding = CodeUnderstanding(
            file_path=file_path,
            semantic_summary=self._generate_summary(semantic_ctx, intent_analysis),
            intent=intent_analysis.primary_intent,
            behavior_model=behavior_model.to_dict(),
            complexity_score=complexity,
            quality_metrics=quality,
        )

        self._analysis_cache[cache_key] = understanding
        return understanding

    def _extract_semantics(self, tree: ast.AST, content: str) -> SemanticContext:
        """Extract semantic context from code."""
        domain_concepts: set[str] = set()
        business_logic: list[str] = []
        data_flows: list[str] = []
        control_flows: list[str] = []
        abstractions: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                domain = self._identify_domain(node.name)
                if domain:
                    domain_concepts.add(domain)
                abstractions.add(node.name)

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                intent_type = self._identify_intent_type(node.name)
                if intent_type:
                    business_logic.append(f"{node.name}: {intent_type}")

                for arg in node.args.args:
                    if arg.arg != "self":
                        data_flows.append(arg.arg)

                if isinstance(node.body[0], ast.Return):
                    data_flows.append("direct_return")

            elif isinstance(node, ast.If):
                control_flows.append("conditional")
            elif isinstance(node, ast.For | ast.While):
                control_flows.append("iteration")
            elif isinstance(node, ast.Try):
                control_flows.append("exception_handling")

        docstring = ast.get_docstring(tree) if isinstance(tree, ast.Module) else None
        if docstring:
            words = docstring.lower().split()
            for domain, keywords in self.DOMAIN_KEYWORDS.items():
                if any(kw in words for kw in keywords):
                    domain_concepts.add(domain)

        return SemanticContext(
            domain_concepts=list(domain_concepts),
            business_logic=business_logic,
            data_flows=data_flows[:10],
            control_flows=list(set(control_flows)),
            abstractions=list(abstractions),
        )

    def _identify_domain(self, name: str) -> str | None:
        """Identify the domain based on naming conventions."""
        name_lower = name.lower()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                return domain
        return None

    def _identify_intent_type(self, name: str) -> str | None:
        """Identify the intent type based on function/method name."""
        name_lower = name.lower()
        for intent_type, indicators in self.INTENT_INDICATORS.items():
            if any(ind in name_lower for ind in indicators):
                return intent_type
        return None

    def _infer_intent(
        self, tree: ast.AST, content: str, semantic_ctx: SemanticContext
    ) -> IntentAnalysis:
        """Infer the primary intent of the code."""
        primary_intent = "Unknown"
        secondary_intents: list[str] = []
        assumptions: list[str] = []
        constraints: list[str] = []
        confidence = 0.5

        docstring = ast.get_docstring(tree) if isinstance(tree, ast.Module) else None
        if docstring:
            primary_intent = self._extract_intent_from_docstring(docstring)
            confidence = 0.8

        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        functions = [
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        ]

        if classes:
            class_names = [c.name for c in classes]
            primary_intent = f"Define classes: {', '.join(class_names[:3])}"
            confidence = 0.7

        if functions:
            func_intents: list[str] = []
            for func in functions:
                intent_type = self._identify_intent_type(func.name)
                if intent_type:
                    func_intents.append(f"{func.name} ({intent_type})")

            if func_intents and confidence < 0.7:
                primary_intent = f"Provide functionality: {func_intents[0]}"
                secondary_intents = func_intents[1:4]
                confidence = 0.65

        domain_hints = semantic_ctx.domain_concepts
        if domain_hints:
            assumptions.append(f"Related to domains: {', '.join(domain_hints)}")

        if "auth" in domain_hints:
            constraints.append("Requires security considerations")
        if "database" in domain_hints:
            constraints.append("Handles data persistence")
        if "api" in domain_hints:
            constraints.append("Exposes external interface")

        return IntentAnalysis(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            assumptions=assumptions,
            constraints=constraints,
            confidence=confidence,
        )

    def _extract_intent_from_docstring(self, docstring: str) -> str:
        """Extract intent information from docstring."""
        first_line = docstring.split("\n")[0].strip()
        if len(first_line) < 100:
            return first_line

        sentences = re.split(r"[.!?]", docstring)
        if sentences:
            return sentences[0].strip()[:100]

        return "Purpose unclear from documentation"

    def _model_behavior(self, tree: ast.AST) -> BehaviorModel:
        """Model the behavior of the code."""
        inputs: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []
        side_effects: list[str] = []
        preconditions: list[str] = []
        postconditions: list[str] = []
        invariants: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                func_inputs = [
                    {"name": arg.arg, "type": "unknown"}
                    for arg in node.args.args
                    if arg.arg != "self"
                ]
                inputs.extend(func_inputs)

                returns = [n for n in ast.walk(node) if isinstance(n, ast.Return) and n.value]
                if returns:
                    outputs.append({"type": "return", "count": len(returns), "function": node.name})

                calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
                for call in calls:
                    if isinstance(call.func, ast.Name):
                        func_name = call.func.id
                        if any(
                            kw in func_name.lower()
                            for kw in ["write", "save", "delete", "update", "create"]
                        ):
                            side_effects.append(f"{node.name}: calls {func_name}")

        if inputs:
            preconditions.append("Requires valid input parameters")
        if outputs:
            postconditions.append("Returns computed result")
        if side_effects:
            invariants.append("May modify external state")

        return BehaviorModel(
            inputs=inputs[:20],
            outputs=outputs[:10],
            side_effects=list(set(side_effects))[:10],
            preconditions=preconditions,
            postconditions=postconditions,
            invariants=invariants,
        )

    def _calculate_complexity(self, tree: ast.AST) -> float:
        """Calculate code complexity score."""
        complexity = 0
        total_lines = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                func_complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, ast.If | ast.For | ast.While):
                        func_complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        func_complexity += len(child.values) - 1
                    elif isinstance(child, ast.ExceptHandler):
                        func_complexity += 1
                complexity += func_complexity
                total_lines += 1

        return complexity / max(total_lines, 1)

    def _calculate_quality(self, tree: ast.AST, content: str) -> dict[str, float]:
        """Calculate various quality metrics."""
        lines = content.splitlines()
        code_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
        comment_lines = [line for line in lines if line.strip().startswith("#")]

        docstrings = sum(
            1
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                and ast.get_docstring(node)
            )
        )

        functions = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        )

        classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

        return {
            "documentation_coverage": docstrings / max(functions + classes, 1) * 100,
            "comment_ratio": len(comment_lines) / max(len(code_lines), 1) * 100,
            "lines_of_code": len(code_lines),
            "function_count": functions,
            "class_count": classes,
            "avg_function_length": len(code_lines) / max(functions, 1),
        }

    def _generate_summary(
        self, semantic_ctx: SemanticContext, intent_analysis: IntentAnalysis
    ) -> str:
        """Generate a semantic summary."""
        parts: list[str] = []

        if semantic_ctx.domain_concepts:
            domains = ", ".join(semantic_ctx.domain_concepts[:3])
            parts.append(f"Domain: {domains}")

        if intent_analysis.primary_intent:
            parts.append(f"Intent: {intent_analysis.primary_intent}")

        if semantic_ctx.abstractions:
            abstractions = ", ".join(semantic_ctx.abstractions[:3])
            parts.append(f"Key abstractions: {abstractions}")

        if semantic_ctx.business_logic:
            logic = semantic_ctx.business_logic[0]
            parts.append(f"Main logic: {logic}")

        return ". ".join(parts) if parts else "Purpose unclear"

    async def understand_function(self, file_path: Path, function_name: str) -> dict[str, Any]:
        """Understand a specific function in detail."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == function_name
            ):
                return {
                    "name": function_name,
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node),
                    "complexity": self._calculate_complexity(node),
                    "line_start": node.lineno,
                    "line_end": getattr(node, "end_lineno", node.lineno),
                }

        return {"error": f"Function {function_name} not found"}

    async def understand_class(self, file_path: Path, class_name: str) -> dict[str, Any]:
        """Understand a specific class in detail."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                methods = [
                    n.name
                    for n in ast.walk(node)
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                ]
                attributes: list[str] = []
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                attributes.append(target.id)

                return {
                    "name": class_name,
                    "methods": methods,
                    "attributes": attributes,
                    "docstring": ast.get_docstring(node),
                    "bases": [
                        base.id if isinstance(base, ast.Name) else str(base) for base in node.bases
                    ],
                    "line_start": node.lineno,
                    "line_end": getattr(node, "end_lineno", node.lineno),
                }

        return {"error": f"Class {class_name} not found"}
