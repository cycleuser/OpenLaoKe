"""Long-term memory system for storing and retrieving cross-session knowledge."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlaoke.core.memory.consolidation import (
    ConsolidationResult,
    ConsolidationStrategy,
    MemoryConsolidator,
)
from openlaoke.core.memory.embedding import EmbeddingEngine
from openlaoke.core.memory.retrieval import MemoryRetriever

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """A single memory entry with metadata and associations."""

    id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5
    associations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "importance": self.importance,
            "associations": self.associations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            accessed_at=data.get("accessed_at", time.time()),
            access_count=data.get("access_count", 0),
            importance=data.get("importance", 0.5),
            associations=data.get("associations", []),
        )

    def touch(self) -> None:
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class MemorySummary:
    """Summary of memory state."""

    total_memories: int
    total_associations: int
    avg_importance: float
    avg_access_count: float
    oldest_memory: float
    newest_memory: float
    categories: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_memories": self.total_memories,
            "total_associations": self.total_associations,
            "avg_importance": self.avg_importance,
            "avg_access_count": self.avg_access_count,
            "oldest_memory": self.oldest_memory,
            "newest_memory": self.newest_memory,
            "categories": self.categories,
        }


class MemoryStorage:
    """Persistent storage for memories."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.memories_file = self.storage_path / "memories.json"
        self.index_file = self.storage_path / "index.json"
        self._load()

    def _load(self) -> None:
        if self.memories_file.exists():
            try:
                with open(self.memories_file, encoding="utf-8") as f:
                    data = json.load(f)
                self.memories: dict[str, Memory] = {
                    k: Memory.from_dict(v) for k, v in data.get("memories", {}).items()
                }
            except Exception as e:
                logger.warning(f"Failed to load memories: {e}")
                self.memories = {}
        else:
            self.memories = {}

    def _save(self) -> None:
        try:
            data = {
                "version": "1.0",
                "memories": {k: v.to_dict() for k, v in self.memories.items()},
            }
            temp_path = self.memories_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.memories_file)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    def add(self, memory: Memory) -> None:
        self.memories[memory.id] = memory
        self._save()

    def get(self, memory_id: str) -> Memory | None:
        return self.memories.get(memory_id)

    def update(self, memory: Memory) -> None:
        self.memories[memory.id] = memory
        self._save()

    def delete(self, memory_id: str) -> bool:
        if memory_id in self.memories:
            del self.memories[memory_id]
            self._save()
            return True
        return False

    def get_all(self) -> list[Memory]:
        return list(self.memories.values())


class LongTermMemory:
    """Long-term memory system - stores and retrieves cross-session knowledge."""

    def __init__(self, storage_path: Path | None = None):
        if storage_path is None:
            storage_path = Path.home() / ".openlaoke" / "memory"
        self.storage = MemoryStorage(storage_path)
        self.embedder = EmbeddingEngine()
        self.retriever = MemoryRetriever(self.embedder)
        self.consolidator = MemoryConsolidator(self.storage, self.embedder)

    async def store(self, memory: Memory) -> str:
        if not memory.id:
            memory.id = f"mem_{uuid.uuid4().hex[:8]}"
        if not memory.embedding:
            memory.embedding = await self.embedder.embed(memory.content)
        self.storage.add(memory)
        return memory.id

    async def recall(self, query: str, limit: int = 10) -> list[Memory]:
        query_embedding = await self.embedder.embed(query)
        results = self.retriever.search(
            memories=self.storage.get_all(),
            query_embedding=query_embedding,
            limit=limit,
        )
        for memory in results:
            memory.touch()
            self.storage.update(memory)
        return results

    async def consolidate(
        self, strategy: ConsolidationStrategy = ConsolidationStrategy.HYBRID
    ) -> ConsolidationResult:
        return await self.consolidator.consolidate(strategy)

    async def forget(self, memory_id: str) -> bool:
        return self.storage.delete(memory_id)

    async def associate(self, memory_ids: list[str]) -> None:
        memories = [self.storage.get(mid) for mid in memory_ids]
        valid_memories = [m for m in memories if m is not None]
        for i, memory in enumerate(valid_memories):
            for j, other in enumerate(valid_memories):
                if i != j and other.id not in memory.associations:
                    memory.associations.append(other.id)
            self.storage.update(memory)

    async def summarize(self) -> MemorySummary:
        memories = self.storage.get_all()
        if not memories:
            return MemorySummary(
                total_memories=0,
                total_associations=0,
                avg_importance=0.0,
                avg_access_count=0.0,
                oldest_memory=0.0,
                newest_memory=0.0,
                categories={},
            )

        total_associations = sum(len(m.associations) for m in memories)
        avg_importance = sum(m.importance for m in memories) / len(memories)
        avg_access_count = sum(m.access_count for m in memories) / len(memories)
        oldest = min(m.created_at for m in memories)
        newest = max(m.created_at for m in memories)
        categories: dict[str, int] = {}
        for m in memories:
            category = m.metadata.get("category", "uncategorized")
            categories[category] = categories.get(category, 0) + 1

        return MemorySummary(
            total_memories=len(memories),
            total_associations=total_associations,
            avg_importance=avg_importance,
            avg_access_count=avg_access_count,
            oldest_memory=oldest,
            newest_memory=newest,
            categories=categories,
        )


_memory_instance: LongTermMemory | None = None


def get_memory(storage_path: Path | None = None) -> LongTermMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = LongTermMemory(storage_path)
    return _memory_instance
