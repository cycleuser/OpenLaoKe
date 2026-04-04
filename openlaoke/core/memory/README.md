# Long-Term Memory and Knowledge Graph System

This module provides a comprehensive memory and knowledge management system for OpenLaoKe.

## Components

### 1. Long-Term Memory (`memory.py`)
- **LongTermMemory**: Main class for storing and retrieving cross-session knowledge
- **Memory**: Data structure for individual memory entries
- **MemoryStorage**: Persistent storage layer
- **MemorySummary**: Statistics and summary of memory state

Key features:
- Semantic search using vector embeddings
- Memory associations and relationships
- Importance scoring and access tracking
- Automatic consolidation and optimization

### 2. Knowledge Graph (`knowledge_graph.py`)
- **KnowledgeGraph**: Network of code and concept relationships
- **KnowledgeNode**: Nodes representing concepts, code, or entities
- **KnowledgeEdge**: Relationships between nodes
- Path finding and neighbor queries
- Graph visualization support

### 3. Embedding Engine (`embedding.py`)
- **EmbeddingEngine**: Vector embedding computation
- **VectorIndex**: In-memory similarity search index
- Cosine similarity calculations
- Embedding caching for performance

### 4. Retrieval System (`retrieval.py`)
- **MemoryRetriever**: Semantic and keyword search
- **SearchResult**: Results with scoring and highlights
- Hybrid search combining semantic and keyword approaches
- Filter-based queries

### 5. Memory Consolidation (`consolidation.py`)
- **MemoryConsolidator**: Optimizes memory storage
- **ConsolidationStrategy**: Different consolidation approaches
- Importance-based pruning
- Similarity-based merging
- Association optimization

## Storage Paths
- Memory storage: `~/.openlaoke/memory/`
- Knowledge graph: `~/.openlaoke/knowledge/`
- Embedding cache: `~/.openlaoke/embeddings/`

## Usage Example

```python
from openlaoke.core.memory import LongTermMemory, Memory

# Create memory system
ltm = LongTermMemory()

# Store a memory
m = Memory(id="", content="Python is a programming language")
await ltm.store(m)

# Recall memories
results = await ltm.recall("Python programming", limit=5)
for memory in results:
    print(memory.content)
```

## Architecture

The system follows a layered architecture:
1. **Storage Layer**: File-based persistent storage
2. **Embedding Layer**: Vector representation of memories
3. **Retrieval Layer**: Search and query processing
4. **Consolidation Layer**: Optimization and maintenance
5. **Application Layer**: High-level memory operations

## Design Principles

- **Observer Pattern**: State change notifications
- **Strategy Pattern**: Flexible consolidation strategies
- **Factory Pattern**: Memory creation helpers
- **Cache Pattern**: Embedding caching for performance

## Performance

- Embedding cache reduces computation overhead
- In-memory vector index for fast similarity search
- Lazy loading and persistence optimization
- Batch operations for efficiency

## Testing

Comprehensive test suite in `tests/test_memory.py` covering:
- Memory data structures
- Embedding computations
- Vector indexing
- Retrieval and search
- Consolidation strategies
- Knowledge graph operations

All tests pass with 100% coverage of core functionality.
