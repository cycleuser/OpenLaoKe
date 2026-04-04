"""Discovery system for pattern detection and knowledge building."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from openlaoke.core.explorer.explorer import KnowledgeGraph, Pattern


@dataclass
class PatternCandidate:
    """Candidate pattern before full validation."""

    pattern_type: str
    occurrences: list[dict[str, Any]]
    confidence: float = 0.0
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "features": self.features,
        }


@dataclass
class KnowledgeNode:
    """Node in the knowledge graph."""

    id: str
    node_type: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    connections: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "content": self.content,
            "metadata": self.metadata,
            "connections": self.connections,
            "timestamp": self.timestamp,
        }


@dataclass
class KnowledgeEdge:
    """Edge in the knowledge graph."""

    id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "weight": self.weight,
            "metadata": self.metadata,
        }


class DiscoverySystem:
    """System for discovering patterns and building knowledge graphs.

    This class provides:
    - Pattern discovery from code analysis
    - Knowledge graph construction
    - Insight extraction
    - Knowledge synthesis
    """

    PATTERN_TYPES = {
        "structural": "Patterns in code structure and organization",
        "behavioral": "Patterns in code behavior and execution",
        "naming": "Patterns in naming conventions",
        "dependency": "Patterns in module dependencies",
        "architectural": "Patterns in overall architecture",
        "idiomatic": "Language-specific idioms and conventions",
    }

    PATTERN_FEATURES = {
        "structural": ["class_count", "function_count", "module_count", "nesting_depth"],
        "behavioral": ["side_effects", "return_types", "parameter_count", "exception_handling"],
        "naming": ["camel_case", "snake_case", "prefix_patterns", "suffix_patterns"],
        "dependency": ["import_count", "dependency_depth", "circular_dependencies"],
        "architectural": ["layer_count", "module_coupling", "separation_of_concerns"],
        "idiomatic": ["language_features", "framework_patterns", "common_practices"],
    }

    def __init__(self) -> None:
        self._discovered_patterns: dict[str, Pattern] = {}
        self._knowledge_nodes: dict[str, KnowledgeNode] = {}
        self._knowledge_edges: dict[str, KnowledgeEdge] = {}

    async def discover_patterns(self, codebase: Path) -> list[Pattern]:
        """Discover patterns in the codebase.

        Args:
            codebase: Path to the codebase to analyze

        Returns:
            List of discovered patterns
        """
        from openlaoke.core.explorer.explorer import Pattern

        candidates = await self._collect_pattern_candidates(codebase)
        validated_patterns: list[Pattern] = []

        for candidate in candidates:
            if self._validate_pattern_candidate(candidate):
                pattern_id = f"pattern_{uuid4().hex[:8]}"
                pattern = Pattern(
                    id=pattern_id,
                    name=self._generate_pattern_name(candidate),
                    pattern_type=candidate.pattern_type,
                    occurrences=candidate.occurrences,
                    confidence=candidate.confidence,
                    description=self._generate_pattern_description(candidate),
                )
                validated_patterns.append(pattern)
                self._discovered_patterns[pattern_id] = pattern

        return validated_patterns

    async def _collect_pattern_candidates(self, codebase: Path) -> list[PatternCandidate]:
        """Collect candidates for pattern discovery."""
        candidates: list[PatternCandidate] = []

        candidates.extend(await self._discover_structural_patterns(codebase))
        candidates.extend(await self._discover_naming_patterns(codebase))
        candidates.extend(await self._discover_dependency_patterns(codebase))
        candidates.extend(await self._discover_behavioral_patterns(codebase))

        return candidates

    async def _discover_structural_patterns(self, codebase: Path) -> list[PatternCandidate]:
        """Discover structural patterns."""
        import ast

        candidates: list[PatternCandidate] = []
        occurrences: list[dict[str, Any]] = []

        for py_file in codebase.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            function_count = sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            )

            occurrences.append(
                {
                    "file": str(py_file.relative_to(codebase)),
                    "class_count": class_count,
                    "function_count": function_count,
                    "ratio": function_count / max(class_count, 1),
                }
            )

        if occurrences:
            avg_ratio = sum(o["ratio"] for o in occurrences) / len(occurrences)
            if avg_ratio > 5:
                candidates.append(
                    PatternCandidate(
                        pattern_type="structural",
                        occurrences=occurrences[:10],
                        confidence=min(0.8, avg_ratio / 10),
                        features={"average_function_to_class_ratio": avg_ratio},
                    )
                )

        return candidates

    async def _discover_naming_patterns(self, codebase: Path) -> list[PatternCandidate]:
        """Discover naming convention patterns."""
        import ast

        candidates: list[PatternCandidate] = []
        naming_data: dict[str, list[str]] = defaultdict(list)

        for py_file in codebase.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    naming_data["classes"].append(node.name)
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    naming_data["functions"].append(node.name)

        snake_case_functions = sum(
            1 for name in naming_data["functions"] if "_" in name and name.islower()
        )
        camel_case_classes = sum(
            1
            for name in naming_data["classes"]
            if "_" not in name and any(c.isupper() for c in name)
        )

        total_functions = len(naming_data["functions"])
        total_classes = len(naming_data["classes"])

        if total_functions > 0 and snake_case_functions / total_functions > 0.7:
            candidates.append(
                PatternCandidate(
                    pattern_type="naming",
                    occurrences=[
                        {
                            "type": "function",
                            "convention": "snake_case",
                            "percentage": snake_case_functions / total_functions * 100,
                        }
                    ],
                    confidence=0.85,
                    features={"snake_case_percentage": snake_case_functions / total_functions},
                )
            )

        if total_classes > 0 and camel_case_classes / total_classes > 0.7:
            candidates.append(
                PatternCandidate(
                    pattern_type="naming",
                    occurrences=[
                        {
                            "type": "class",
                            "convention": "CamelCase",
                            "percentage": camel_case_classes / total_classes * 100,
                        }
                    ],
                    confidence=0.85,
                    features={"camel_case_percentage": camel_case_classes / total_classes},
                )
            )

        return candidates

    async def _discover_dependency_patterns(self, codebase: Path) -> list[PatternCandidate]:
        """Discover dependency patterns."""
        import ast

        candidates: list[PatternCandidate] = []
        import_counts: dict[str, int] = defaultdict(int)

        for py_file in codebase.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_counts[alias.name] += 1
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module:
                        import_counts[module] += 1

        common_imports = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        if common_imports and common_imports[0][1] > 5:
            candidates.append(
                PatternCandidate(
                    pattern_type="dependency",
                    occurrences=[
                        {
                            "module": module,
                            "count": count,
                            "usage_percentage": count / max(sum(import_counts.values()), 1) * 100,
                        }
                        for module, count in common_imports[:3]
                    ],
                    confidence=min(0.8, common_imports[0][1] / 10),
                    features={
                        "most_common_import": common_imports[0][0],
                        "import_diversity": len(import_counts),
                    },
                )
            )

        return candidates

    async def _discover_behavioral_patterns(self, codebase: Path) -> list[PatternCandidate]:
        """Discover behavioral patterns."""
        import ast

        candidates: list[PatternCandidate] = []
        behavior_stats: dict[str, int] = defaultdict(int)

        for py_file in codebase.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if any(isinstance(n, ast.Return) for n in ast.walk(node)):
                        behavior_stats["returns_value"] += 1
                    if any(isinstance(n, ast.Raise) for n in ast.walk(node)):
                        behavior_stats["raises_exception"] += 1
                    if any(isinstance(n, ast.Yield) for n in ast.walk(node)):
                        behavior_stats["yields_value"] += 1

        total_functions = sum(behavior_stats.values())
        if total_functions > 0:
            return_percentage = behavior_stats["returns_value"] / total_functions * 100
            exception_percentage = behavior_stats["raises_exception"] / total_functions * 100

            if return_percentage > 70:
                candidates.append(
                    PatternCandidate(
                        pattern_type="behavioral",
                        occurrences=[
                            {
                                "behavior": "returns_value",
                                "percentage": return_percentage,
                            }
                        ],
                        confidence=min(0.8, return_percentage / 100),
                        features={"return_behavior_dominant": True},
                    )
                )

            if exception_percentage > 10:
                candidates.append(
                    PatternCandidate(
                        pattern_type="behavioral",
                        occurrences=[
                            {
                                "behavior": "raises_exception",
                                "percentage": exception_percentage,
                            }
                        ],
                        confidence=0.6,
                        features={"exception_handling_present": True},
                    )
                )

        return candidates

    def _validate_pattern_candidate(self, candidate: PatternCandidate) -> bool:
        """Validate a pattern candidate."""
        min_occurrences = 2
        min_confidence = 0.5

        return (
            len(candidate.occurrences) >= min_occurrences and candidate.confidence >= min_confidence
        )

    def _generate_pattern_name(self, candidate: PatternCandidate) -> str:
        """Generate a descriptive name for the pattern."""
        pattern_type = candidate.pattern_type

        if pattern_type == "structural":
            features = candidate.features
            if "average_function_to_class_ratio" in features:
                ratio = features["average_function_to_class_ratio"]
                if ratio > 5:
                    return "Function-Heavy Structure"
                elif ratio < 2:
                    return "Class-Heavy Structure"
            return "Mixed Structure"

        elif pattern_type == "naming":
            occurrences = candidate.occurrences
            if occurrences:
                convention = occurrences[0].get("convention", "unknown")
                return f"{convention} Naming Convention"
            return "Consistent Naming"

        elif pattern_type == "dependency":
            features = candidate.features
            if "most_common_import" in features:
                module = features["most_common_import"]
                return f"Common {module} Dependency"
            return "Centralized Dependencies"

        elif pattern_type == "behavioral":
            occurrences = candidate.occurrences
            if occurrences:
                behavior = occurrences[0].get("behavior", "unknown")
                return f"{behavior.replace('_', ' ').title()} Pattern"
            return "Behavioral Pattern"

        return f"{pattern_type.title()} Pattern"

    def _generate_pattern_description(self, candidate: PatternCandidate) -> str:
        """Generate a description for the pattern."""
        pattern_type = candidate.pattern_type
        occurrences = candidate.occurrences
        confidence = candidate.confidence

        desc = f"{self.PATTERN_TYPES.get(pattern_type, 'General pattern')}."

        if occurrences:
            first_occ = occurrences[0]
            if "percentage" in first_occ:
                desc += f" Observed in {first_occ['percentage']:.1f}% of cases."
            elif "count" in first_occ:
                desc += f" Found {first_occ['count']} times."

        desc += f" Confidence: {confidence:.2f}."
        return desc

    async def build_knowledge_graph(self, explorations: list[dict[str, Any]]) -> KnowledgeGraph:
        """Build a knowledge graph from exploration results.

        Args:
            explorations: List of exploration results

        Returns:
            KnowledgeGraph representing discovered knowledge
        """
        from openlaoke.core.explorer.explorer import KnowledgeGraph

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for exploration in explorations:
            exp_type = exploration.get("type", "unknown")
            exp_data = exploration.get("data", {})

            node_id = f"node_{uuid4().hex[:8]}"
            node = KnowledgeNode(
                id=node_id,
                node_type=exp_type,
                content=self._summarize_exploration(exp_type, exp_data),
                metadata={"source": "exploration"},
            )
            nodes.append(node.to_dict())
            self._knowledge_nodes[node_id] = node

        node_ids = list(self._knowledge_nodes.keys())
        for i, source_id in enumerate(node_ids):
            for target_id in node_ids[i + 1 :]:
                source_node = self._knowledge_nodes[source_id]
                target_node = self._knowledge_nodes[target_id]

                edge_type = self._determine_edge_type(source_node, target_node)
                if edge_type:
                    edge_id = f"edge_{uuid4().hex[:8]}"
                    edge = KnowledgeEdge(
                        id=edge_id,
                        source_id=source_id,
                        target_id=target_id,
                        edge_type=edge_type,
                        weight=self._calculate_edge_weight(source_node, target_node),
                    )
                    edges.append(edge.to_dict())
                    self._knowledge_edges[edge_id] = edge

        metadata = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "exploration_types": list(set(e.get("type", "unknown") for e in explorations)),
            "build_timestamp": time.time(),
        }

        return KnowledgeGraph(
            nodes=nodes,
            edges=edges,
            metadata=metadata,
        )

    def _summarize_exploration(self, exp_type: str, exp_data: dict[str, Any] | list[Any]) -> str:
        """Summarize exploration data for a node."""
        if exp_type == "architecture":
            patterns = exp_data.get("design_patterns", []) if isinstance(exp_data, dict) else []
            return f"Architecture with {len(patterns)} design patterns"

        elif exp_type == "patterns":
            if isinstance(exp_data, list):
                return f"{len(exp_data)} patterns discovered"
            return "Pattern analysis"

        elif exp_type == "hypotheses":
            if isinstance(exp_data, list):
                validated = sum(1 for h in exp_data if h.get("validation_status") == "validated")
                return f"{len(exp_data)} hypotheses, {validated} validated"
            return "Hypothesis analysis"

        elif exp_type == "code_understanding":
            return "Code semantic understanding"

        else:
            return f"{exp_type} exploration"

    def _determine_edge_type(self, source: KnowledgeNode, target: KnowledgeNode) -> str | None:
        """Determine the relationship between two nodes."""
        type_relations = {
            ("architecture", "patterns"): "contains",
            ("architecture", "hypotheses"): "generates",
            ("patterns", "hypotheses"): "supports",
            ("hypotheses", "validation"): "validated_by",
            ("code_understanding", "architecture"): "contributes_to",
            ("code_understanding", "hypotheses"): "evidence_for",
        }

        key = (source.node_type, target.node_type)
        return type_relations.get(key)

    def _calculate_edge_weight(self, source: KnowledgeNode, target: KnowledgeNode) -> float:
        """Calculate the weight of an edge."""
        weight = 1.0

        if "patterns" in source.content.lower() and "hypotheses" in target.content.lower():
            weight = 0.8

        elif "architecture" in source.content.lower() and "patterns" in target.content.lower():
            weight = 0.9

        elif "hypotheses" in source.content.lower() and "validated" in target.content.lower():
            weight = 0.7

        return weight

    async def extract_insights(self, knowledge_graph: KnowledgeGraph) -> list[str]:
        """Extract insights from the knowledge graph.

        Args:
            knowledge_graph: The knowledge graph to analyze

        Returns:
            List of extracted insights
        """
        insights: list[str] = []

        nodes = knowledge_graph.nodes
        edges = knowledge_graph.edges

        node_types = [n.get("node_type", "unknown") for n in nodes]
        type_counts: dict[str, int] = defaultdict(int)
        for nt in node_types:
            type_counts[nt] += 1

        if type_counts.get("architecture", 0) > 0:
            insights.append("Architecture analysis provided structural understanding")

        if type_counts.get("patterns", 0) > 0:
            insights.append("Pattern discovery revealed coding conventions")

        if type_counts.get("hypotheses", 0) > 1:
            insights.append("Multiple hypotheses were generated and tested")

        highly_connected_nodes = [
            n for n in nodes if len([e for e in edges if e.get("source_id") == n.get("id")]) > 2
        ]
        if highly_connected_nodes:
            insights.append(f"{len(highly_connected_nodes)} key findings connect multiple analyses")

        if insights:
            insights.append(
                f"Knowledge graph built with {len(nodes)} nodes and {len(edges)} relationships"
            )

        return insights

    def get_pattern(self, pattern_id: str) -> Pattern | None:
        """Get a specific pattern by ID."""
        return self._discovered_patterns.get(pattern_id)

    def get_all_patterns(self) -> list[Pattern]:
        """Get all discovered patterns."""
        return list(self._discovered_patterns.values())

    async def synthesize_knowledge(self, knowledge_graph: KnowledgeGraph) -> dict[str, Any]:
        """Synthesize knowledge from the graph."""
        nodes = knowledge_graph.nodes
        edges = knowledge_graph.edges

        synthesis: dict[str, Any] = {
            "summary": f"Discovered {len(nodes)} pieces of knowledge",
            "key_findings": [],
            "recommendations": [],
        }

        node_contents = [n.get("content", "") for n in nodes]
        synthesis["key_findings"] = node_contents[:5]

        edge_types = [e.get("edge_type", "") for e in edges]
        common_relation = max(set(edge_types), key=edge_types.count, default="")
        if common_relation:
            synthesis["recommendations"].append(
                f"Strong {common_relation} relationships detected in knowledge structure"
            )

        return synthesis
