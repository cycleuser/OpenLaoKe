"""Memory retrieval system with semantic search."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openlaoke.core.memory.embedding import EmbeddingEngine

if TYPE_CHECKING:
    from openlaoke.core.memory.memory import Memory

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A search result with score and metadata."""

    memory: Memory
    score: float
    match_type: str = "semantic"
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "match_type": self.match_type,
            "highlights": self.highlights,
        }


class MemoryRetriever:
    """Retrieval system for semantic and keyword search."""

    def __init__(self, embedder: EmbeddingEngine | None = None):
        self.embedder = embedder or EmbeddingEngine()

    def search(
        self,
        memories: list[Memory],
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.0,
        filters: dict[str, Any] | None = None,
    ) -> list[Memory]:
        if not memories:
            return []

        scored_memories: list[tuple[Memory, float]] = []
        for memory in memories:
            if filters and not self._matches_filters(memory, filters):
                continue

            if memory.embedding is None:
                continue

            similarity = EmbeddingEngine.cosine_similarity(query_embedding, memory.embedding)
            if similarity >= threshold:
                recency_boost = self._compute_recency_boost(memory)
                importance_boost = memory.importance
                final_score = similarity * 0.6 + recency_boost * 0.2 + importance_boost * 0.2
                scored_memories.append((memory, final_score))

        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, _ in scored_memories[:limit]]

    def keyword_search(
        self,
        memories: list[Memory],
        keywords: list[str],
        limit: int = 10,
    ) -> list[SearchResult]:
        if not keywords:
            return []

        keywords_lower = [k.lower() for k in keywords]
        results: list[SearchResult] = []

        for memory in memories:
            content_lower = memory.content.lower()
            matches = sum(1 for k in keywords_lower if k in content_lower)
            if matches > 0:
                score = matches / len(keywords_lower)
                highlights = self._extract_highlights(memory.content, keywords_lower)
                results.append(
                    SearchResult(
                        memory=memory,
                        score=score,
                        match_type="keyword",
                        highlights=highlights,
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def hybrid_search(
        self,
        memories: list[Memory],
        query_embedding: list[float],
        keywords: list[str],
        limit: int = 10,
        semantic_weight: float = 0.7,
    ) -> list[SearchResult]:
        semantic_results = self.search(memories, query_embedding, limit=limit * 2)
        keyword_results = self.keyword_search(memories, keywords, limit=limit * 2)

        combined: dict[str, SearchResult] = {}
        for memory in semantic_results:
            if memory.id not in combined:
                combined[memory.id] = SearchResult(
                    memory=memory,
                    score=0.0,
                    match_type="hybrid",
                )

        for result in keyword_results:
            if result.memory.id in combined:
                existing = combined[result.memory.id]
                combined[result.memory.id] = SearchResult(
                    memory=existing.memory,
                    score=existing.score + (1 - semantic_weight),
                    match_type="hybrid",
                    highlights=result.highlights,
                )
            else:
                combined[result.memory.id] = SearchResult(
                    memory=result.memory,
                    score=(1 - semantic_weight) * result.score,
                    match_type="hybrid",
                    highlights=result.highlights,
                )

        results = list(combined.values())
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _matches_filters(self, memory: Memory, filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if key in memory.metadata:
                if memory.metadata[key] != value:
                    return False
            elif hasattr(memory, key) and getattr(memory, key) != value:
                return False
        return True

    def _compute_recency_boost(self, memory: Memory) -> float:
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

    def _extract_highlights(
        self, content: str, keywords: list[str], context_chars: int = 50
    ) -> list[str]:
        highlights: list[str] = []
        content_lower = content.lower()

        for keyword in keywords:
            idx = content_lower.find(keyword)
            if idx != -1:
                start = max(0, idx - context_chars)
                end = min(len(content), idx + len(keyword) + context_chars)
                highlight = content[start:end]
                if start > 0:
                    highlight = "..." + highlight
                if end < len(content):
                    highlight = highlight + "..."
                highlights.append(highlight)

        return highlights

    async def find_similar(
        self,
        memory: Memory,
        memories: list[Memory],
        limit: int = 5,
    ) -> list[SearchResult]:
        if not memory.embedding:
            return []

        similar = self.search(memories, memory.embedding, limit=limit + 1)
        results: list[SearchResult] = []
        for m in similar:
            if m.id != memory.id:
                similarity = (
                    EmbeddingEngine.cosine_similarity(memory.embedding, m.embedding)
                    if m.embedding
                    else 0.0
                )
                results.append(
                    SearchResult(
                        memory=m,
                        score=similarity,
                        match_type="similar",
                    )
                )

        return results[:limit]
