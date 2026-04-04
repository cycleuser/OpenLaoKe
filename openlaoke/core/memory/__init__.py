"""Long-term memory and knowledge graph system for OpenLaoKe.

This module provides cross-session memory storage and retrieval:
- Long-term memory with semantic search
- Knowledge graph for code and concepts
- Vector embeddings for similarity search
- Memory consolidation and optimization
"""

from openlaoke.core.memory.consolidation import (
    ConsolidationStrategy,
    MemoryConsolidator,
)
from openlaoke.core.memory.embedding import (
    EmbeddingEngine,
    VectorIndex,
)
from openlaoke.core.memory.knowledge_graph import (
    Fact,
    GraphVisualization,
    Inference,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
)
from openlaoke.core.memory.memory import (
    LongTermMemory,
    Memory,
    MemorySummary,
    get_memory,
)
from openlaoke.core.memory.retrieval import (
    MemoryRetriever,
    SearchResult,
)

__all__ = [
    "LongTermMemory",
    "Memory",
    "MemorySummary",
    "get_memory",
    "KnowledgeGraph",
    "KnowledgeNode",
    "KnowledgeEdge",
    "Fact",
    "Inference",
    "GraphVisualization",
    "EmbeddingEngine",
    "VectorIndex",
    "MemoryRetriever",
    "SearchResult",
    "MemoryConsolidator",
    "ConsolidationStrategy",
]
