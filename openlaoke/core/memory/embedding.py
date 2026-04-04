"""Vector embedding engine for semantic similarity."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Engine for computing and managing text embeddings."""

    def __init__(self, model: str = "simple", cache_path: Path | None = None):
        self.model = model
        if cache_path is None:
            cache_path = Path.home() / ".openlaoke" / "embeddings"
        self.cache_path = cache_path
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[float]] = {}

    def _get_cache_key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()

    async def embed(self, text: str) -> list[float]:
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        cache_file = self.cache_path / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    embedding: list[float] = json.load(f)
                self._cache[cache_key] = embedding
                return embedding
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")

        embedding = await self._compute_embedding(text)
        self._cache[cache_key] = embedding
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(embedding, f)
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")

        return embedding

    async def _compute_embedding(self, text: str) -> list[float]:
        words = text.lower().split()
        if not words:
            return [0.0] * 128

        vocab: dict[str, int] = {}
        for word in words:
            if word not in vocab:
                vocab[word] = len(vocab)

        embedding = [0.0] * 128
        for word, idx in vocab.items():
            hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
            position = hash_val % 128
            embedding[position] += 1.0 / (idx + 1)

        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=False))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)


class VectorIndex:
    """In-memory vector index for similarity search."""

    def __init__(self, dimension: int = 128):
        self.dimension = dimension
        self.vectors: dict[str, list[float]] = {}

    def add(self, id: str, vector: list[float]) -> None:
        if len(vector) != self.dimension:
            logger.warning(
                f"Vector dimension mismatch: expected {self.dimension}, got {len(vector)}"
            )
            return
        self.vectors[id] = vector

    def remove(self, id: str) -> None:
        if id in self.vectors:
            del self.vectors[id]

    def search(self, query: list[float], k: int = 10) -> list[tuple[str, float]]:
        if len(query) != self.dimension:
            logger.warning(f"Query dimension mismatch: expected {self.dimension}, got {len(query)}")
            return []

        similarities: list[tuple[str, float]] = []
        for id, vector in self.vectors.items():
            similarity = EmbeddingEngine.cosine_similarity(query, vector)
            similarities.append((id, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def get(self, id: str) -> list[float] | None:
        return self.vectors.get(id)

    def clear(self) -> None:
        self.vectors.clear()

    def size(self) -> int:
        return len(self.vectors)
