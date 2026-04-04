"""Knowledge graph for building code and concept networks."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.core.memory.embedding import VectorIndex

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph."""

    id: str
    type: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeNode:
        return cls(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", 0.0),
        )


@dataclass
class KnowledgeEdge:
    """An edge connecting two knowledge nodes."""

    id: str
    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeEdge:
        return cls(
            id=data["id"],
            source=data["source"],
            target=data["target"],
            relation=data["relation"],
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Fact:
    """A fact for knowledge inference."""

    subject: str
    predicate: str
    obj: str
    confidence: float = 1.0


@dataclass
class Inference:
    """An inferred fact."""

    fact: Fact
    source: str
    confidence: float


@dataclass
class GraphVisualization:
    """Graph visualization data."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
        }


class KnowledgeGraph:
    """Knowledge graph for building code and concept networks."""

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".openlaoke" / "knowledge"
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.storage_path / "graph.json"
        self.nodes: dict[str, KnowledgeNode] = {}
        self.edges: list[KnowledgeEdge] = []
        self.index = VectorIndex()
        self._load()

    def _load(self) -> None:
        if self.graph_file.exists():
            try:
                with open(self.graph_file, encoding="utf-8") as f:
                    data = json.load(f)
                self.nodes = {
                    k: KnowledgeNode.from_dict(v) for k, v in data.get("nodes", {}).items()
                }
                self.edges = [KnowledgeEdge.from_dict(e) for e in data.get("edges", [])]
            except Exception as e:
                logger.warning(f"Failed to load knowledge graph: {e}")

    def _save(self) -> None:
        try:
            data = {
                "version": "1.0",
                "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
                "edges": [e.to_dict() for e in self.edges],
            }
            temp_path = self.graph_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.graph_file)
        except Exception as e:
            logger.error(f"Failed to save knowledge graph: {e}")

    async def add_node(self, node: KnowledgeNode) -> str:
        if not node.id:
            node.id = f"node_{uuid.uuid4().hex[:8]}"
        self.nodes[node.id] = node
        if node.embedding:
            self.index.add(node.id, node.embedding)
        self._save()
        return node.id

    async def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> str:
        edge_id = f"edge_{uuid.uuid4().hex[:8]}"
        edge = KnowledgeEdge(
            id=edge_id,
            source=source,
            target=target,
            relation=relation,
            weight=weight,
        )
        self.edges.append(edge)
        self._save()
        return edge_id

    async def query(self, sparql: str) -> list[dict]:
        logger.warning("SPARQL query not fully implemented, using simplified query")
        results: list[dict] = []
        return results

    async def infer(self, facts: list[Fact]) -> list[Inference]:
        inferences: list[Inference] = []
        for fact in facts:
            matching_edges = [
                e for e in self.edges if e.source == fact.subject and e.relation == fact.predicate
            ]
            for edge in matching_edges:
                inferred_fact = Fact(
                    subject=edge.target,
                    predicate=fact.predicate,
                    obj=fact.obj,
                    confidence=fact.confidence * edge.weight,
                )
                inferences.append(
                    Inference(
                        fact=inferred_fact,
                        source="transitive_inference",
                        confidence=inferred_fact.confidence,
                    )
                )
        return inferences

    async def visualize(self) -> GraphVisualization:
        nodes = [
            {
                "id": node.id,
                "type": node.type,
                "label": node.content[:50],
                "metadata": node.metadata,
            }
            for node in self.nodes.values()
        ]
        edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "weight": edge.weight,
            }
            for edge in self.edges
        ]
        return GraphVisualization(nodes=nodes, edges=edges)

    async def merge(self, other: KnowledgeGraph) -> None:
        for node_id, node in other.nodes.items():
            if node_id not in self.nodes:
                self.nodes[node_id] = node
                if node.embedding:
                    self.index.add(node_id, node.embedding)

        for edge in other.edges:
            exists = any(
                e.source == edge.source and e.target == edge.target and e.relation == edge.relation
                for e in self.edges
            )
            if not exists:
                self.edges.append(edge)

        self._save()

    def get_neighbors(self, node_id: str, relation: str | None = None) -> list[KnowledgeNode]:
        neighbors: list[KnowledgeNode] = []
        for edge in self.edges:
            if (edge.source == node_id or edge.target == node_id) and (
                relation is None or edge.relation == relation
            ):
                neighbor_id = edge.target if edge.source == node_id else edge.source
                if neighbor_id in self.nodes:
                    neighbors.append(self.nodes[neighbor_id])
        return neighbors

    def find_path(self, source: str, target: str, max_depth: int = 5) -> list[str] | None:
        if source not in self.nodes or target not in self.nodes:
            return None

        visited: set[str] = set()
        queue: list[tuple[str, list[str]]] = [(source, [source])]

        while queue:
            current, path = queue.pop(0)
            if current == target:
                return path
            if len(path) > max_depth:
                continue
            if current in visited:
                continue
            visited.add(current)

            for neighbor in self.get_neighbors(current):
                if neighbor.id not in visited:
                    queue.append((neighbor.id, path + [neighbor.id]))

        return None
