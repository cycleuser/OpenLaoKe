"""Memory consolidation system for optimizing storage."""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openlaoke.core.memory.embedding import EmbeddingEngine

if TYPE_CHECKING:
    from openlaoke.core.memory.memory import Memory, MemoryStorage

logger = logging.getLogger(__name__)


class ConsolidationStrategy(enum.Enum):
    """Strategy for memory consolidation."""

    IMPORTANCE = "importance"
    RECENCY = "recency"
    HYBRID = "hybrid"
    ASSOCIATION = "association"


@dataclass
class ConsolidationResult:
    """Result of memory consolidation."""

    memories_removed: int
    memories_merged: int
    associations_created: int
    space_saved: int


class MemoryConsolidator:
    """Consolidates and optimizes memory storage."""

    def __init__(
        self,
        storage: MemoryStorage,
        embedder: EmbeddingEngine,
        max_memories: int = 1000,
        similarity_threshold: float = 0.95,
    ):
        self.storage = storage
        self.embedder = embedder
        self.max_memories = max_memories
        self.similarity_threshold = similarity_threshold

    async def consolidate(
        self,
        strategy: ConsolidationStrategy = ConsolidationStrategy.HYBRID,
    ) -> ConsolidationResult:
        memories = self.storage.get_all()

        if len(memories) <= self.max_memories:
            return ConsolidationResult(
                memories_removed=0,
                memories_merged=0,
                associations_created=0,
                space_saved=0,
            )

        to_remove = await self._select_memories_for_removal(memories, strategy)
        to_merge = await self._find_merge_candidates(memories)

        memories_removed = 0
        for memory in to_remove:
            if self.storage.delete(memory.id):
                memories_removed += 1

        memories_merged = 0
        associations_created = 0
        for group in to_merge:
            if len(group) > 1:
                merged = await self._merge_memories(group)
                if merged:
                    memories_merged += len(group) - 1
                    associations_created += len(group) - 1

        space_saved = memories_removed + memories_merged

        return ConsolidationResult(
            memories_removed=memories_removed,
            memories_merged=memories_merged,
            associations_created=associations_created,
            space_saved=space_saved,
        )

    async def _select_memories_for_removal(
        self,
        memories: list[Memory],
        strategy: ConsolidationStrategy,
    ) -> list[Memory]:
        if len(memories) <= self.max_memories:
            return []

        num_to_remove = len(memories) - self.max_memories

        if strategy == ConsolidationStrategy.IMPORTANCE:
            sorted_memories = sorted(memories, key=lambda m: m.importance)
        elif strategy == ConsolidationStrategy.RECENCY:
            sorted_memories = sorted(memories, key=lambda m: m.accessed_at)
        elif strategy == ConsolidationStrategy.HYBRID:
            sorted_memories = sorted(
                memories,
                key=lambda m: m.importance * 0.5 + self._recency_score(m) * 0.5,
            )
        elif strategy == ConsolidationStrategy.ASSOCIATION:
            sorted_memories = sorted(memories, key=lambda m: len(m.associations))
        else:
            sorted_memories = sorted(memories, key=lambda m: m.importance)

        return sorted_memories[:num_to_remove]

    async def _find_merge_candidates(self, memories: list[Memory]) -> list[list[Memory]]:
        candidates: list[list[Memory]] = []
        processed: set[str] = set()

        for i, memory1 in enumerate(memories):
            if memory1.id in processed:
                continue

            if not memory1.embedding:
                continue

            similar_group = [memory1]
            for j, memory2 in enumerate(memories):
                if i != j and memory2.id not in processed and memory2.embedding:
                    similarity = EmbeddingEngine.cosine_similarity(
                        memory1.embedding,
                        memory2.embedding,
                    )
                    if similarity >= self.similarity_threshold:
                        similar_group.append(memory2)
                        processed.add(memory2.id)

            if len(similar_group) > 1:
                candidates.append(similar_group)
                processed.add(memory1.id)

        return candidates

    async def _merge_memories(self, memories: list[Memory]) -> Memory | None:
        if not memories:
            return None

        best_memory = max(memories, key=lambda m: m.importance)

        for memory in memories:
            if memory.id != best_memory.id:
                for assoc in memory.associations:
                    if assoc not in best_memory.associations:
                        best_memory.associations.append(assoc)
                best_memory.importance = max(best_memory.importance, memory.importance)
                best_memory.access_count += memory.access_count

        self.storage.update(best_memory)
        return best_memory

    def _recency_score(self, memory: Memory) -> float:
        age = time.time() - memory.accessed_at
        days = age / 86400.0

        if days < 1:
            return 1.0
        elif days < 7:
            return 0.8
        elif days < 30:
            return 0.6
        elif days < 90:
            return 0.4
        else:
            return 0.2

    async def optimize_associations(self, max_associations: int = 10) -> int:
        memories = self.storage.get_all()
        optimized = 0

        for memory in memories:
            if len(memory.associations) > max_associations:
                memory.associations = memory.associations[:max_associations]
                self.storage.update(memory)
                optimized += 1

        return optimized

    async def update_importance_scores(self) -> int:
        memories = self.storage.get_all()
        updated = 0

        for memory in memories:
            recency = self._recency_score(memory)
            frequency = min(memory.access_count / 10.0, 1.0)
            connections = min(len(memory.associations) / 5.0, 1.0)

            new_importance = recency * 0.4 + frequency * 0.4 + connections * 0.2
            if abs(new_importance - memory.importance) > 0.01:
                memory.importance = new_importance
                self.storage.update(memory)
                updated += 1

        return updated
