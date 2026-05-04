"""SQLite-based persistent memory store with FTS5 full-text search.

Inspired by Rein's architecture: single SQLite file, FTS5 + jieba for Chinese,
vector storage, knowledge graph, and timeline events.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jieba

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".openlaoke" / "memory" / "memories.db"


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", text))


def _jieba_tokenize(text: str) -> list[str]:
    if _contains_cjk(text):
        segments = []
        for seg in jieba.cut(text, HMM=True):
            if _contains_cjk(seg):
                segments.extend(jieba.lcut(seg))
            else:
                segments.extend(seg.split())
        return [s.lower() for s in segments if s.strip()]
    return text.lower().split()


def _bm25_score(
    tf: int,
    doc_len: int,
    avg_dl: float,
    n_docs: int,
    n_with_term: int,
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
    if n_with_term == 0:
        return 0.0
    idf = math.log((n_docs - n_with_term + 0.5) / (n_with_term + 0.5) + 1.0)
    numer = tf * (k1 + 1)
    denom = tf + k1 * (1 - b + b * doc_len / max(avg_dl, 1))
    return idf * numer / denom


@dataclass
class MemoryRecord:
    id: str
    content: str
    memory_type: str = "fact"
    key: str = ""
    tags: list[str] = field(default_factory=list)
    source_session: str = ""
    source_tool: str = ""
    confidence: float = 1.0
    importance: float = 0.5
    hit_count: int = 0
    embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "key": self.key,
            "tags": self.tags,
            "source_session": self.source_session,
            "source_tool": self.source_tool,
            "confidence": self.confidence,
            "importance": self.importance,
            "hit_count": self.hit_count,
            "embedding": self.embedding,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> MemoryRecord:
        return cls(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            key=row["key"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            source_session=row["source_session"],
            source_tool=row["source_tool"],
            confidence=row["confidence"],
            importance=row["importance"],
            hit_count=row["hit_count"],
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


@dataclass
class TimelineEvent:
    id: str
    event_type: str
    session_id: str
    tool_name: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "summary": self.summary,
            "details": self.details,
            "created_at": self.created_at,
        }


@dataclass
class ConceptNode:
    id: str
    name: str
    category: str = "general"
    memory_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "memory_ids": self.memory_ids,
            "created_at": self.created_at,
        }


class SQLiteMemoryStore:
    _instances: dict[str, SQLiteMemoryStore] = {}

    def __new__(cls, db_path: Path | None = None) -> SQLiteMemoryStore:
        db_path = db_path or DB_PATH
        key = str(db_path)
        if key not in cls._instances:
            instance = super().__new__(cls)
            instance._db_path = db_path
            instance._db_path.parent.mkdir(parents=True, exist_ok=True)
            instance._conn = sqlite3.connect(
                str(instance._db_path),
                check_same_thread=False,
            )
            instance._conn.row_factory = sqlite3.Row
            instance._conn.execute("PRAGMA journal_mode=WAL")
            instance._conn.execute("PRAGMA synchronous=NORMAL")
            instance._init_schema()
            cls._instances[key] = instance
        return cls._instances[key]

    def _init_schema(self) -> None:
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT DEFAULT 'fact',
                key TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                source_session TEXT DEFAULT '',
                source_tool TEXT DEFAULT '',
                confidence REAL DEFAULT 1.0,
                importance REAL DEFAULT 0.5,
                hit_count INTEGER DEFAULT 0,
                embedding TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                updated_at REAL DEFAULT (strftime('%s', 'now')),
                metadata TEXT DEFAULT '{}'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                memory_id, content, content_tokens, key, tags,
                tokenize='unicode61'
            );

            CREATE TABLE IF NOT EXISTS timeline (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                session_id TEXT DEFAULT '',
                tool_name TEXT DEFAULT '',
                summary TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                created_at REAL DEFAULT (strftime('%s', 'now'))
            );

            CREATE TABLE IF NOT EXISTS concepts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'general',
                memory_ids TEXT DEFAULT '[]',
                created_at REAL DEFAULT (strftime('%s', 'now'))
            );

            CREATE TABLE IF NOT EXISTS concept_links (
                source_concept TEXT NOT NULL,
                target_concept TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                PRIMARY KEY (source_concept, target_concept)
            );

            CREATE TABLE IF NOT EXISTS feedback_log (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                selected_memory_id TEXT,
                skipped_memory_ids TEXT DEFAULT '[]',
                query_type TEXT DEFAULT 'general',
                created_at REAL DEFAULT (strftime('%s', 'now'))
            );

            CREATE TABLE IF NOT EXISTS fusion_params (
                query_type TEXT PRIMARY KEY,
                alpha_bm25 REAL DEFAULT 0.4,
                alpha_vector REAL DEFAULT 0.35,
                alpha_graph REAL DEFAULT 0.25,
                updated_at REAL DEFAULT (strftime('%s', 'now'))
            );

            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(source_session);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_timeline_session ON timeline(session_id);
            CREATE INDEX IF NOT EXISTS idx_timeline_created ON timeline(created_at);
            CREATE INDEX IF NOT EXISTS idx_timeline_type ON timeline(event_type);
        """)

        conn.execute("""
            INSERT OR IGNORE INTO fusion_params (query_type, alpha_bm25, alpha_vector, alpha_graph)
            VALUES ('general', 0.4, 0.35, 0.25)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO fusion_params (query_type, alpha_bm25, alpha_vector, alpha_graph)
            VALUES ('code', 0.3, 0.45, 0.25)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO fusion_params (query_type, alpha_bm25, alpha_vector, alpha_graph)
            VALUES ('debug', 0.35, 0.35, 0.3)
        """)
        conn.commit()

    def _ensure_fts_sync(self) -> None:
        self._conn.execute("""
            INSERT OR REPLACE INTO memories_fts (rowid, content, key, tags)
            SELECT rowid, content, key, tags FROM memories
            WHERE rowid NOT IN (SELECT rowid FROM memories_fts)
        """)
        self._conn.commit()

    def store(self, record: MemoryRecord) -> str:
        conn = self._conn
        now = time.time()
        conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, content, memory_type, key, tags, source_session, source_tool,
                confidence, importance, hit_count, embedding, created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.content,
                record.memory_type,
                record.key,
                json.dumps(record.tags, ensure_ascii=False),
                record.source_session,
                record.source_tool,
                record.confidence,
                record.importance,
                record.hit_count,
                json.dumps(record.embedding) if record.embedding else None,
                record.created_at,
                now,
                json.dumps(record.metadata, ensure_ascii=False),
            ),
        )
        content_tokens = " ".join(_jieba_tokenize(record.content))
        self._conn.execute(
            "INSERT OR REPLACE INTO memories_fts (memory_id, content, content_tokens, key, tags) VALUES (?, ?, ?, ?, ?)",
            (
                record.id,
                record.content,
                content_tokens,
                record.key,
                json.dumps(record.tags, ensure_ascii=False),
            ),
        )
        self._extract_and_link_concepts(record.id, record.content, record.memory_type)
        conn.commit()
        return record.id

    def recall(self, memory_id: str) -> MemoryRecord | None:
        self._conn.execute(
            "UPDATE memories SET hit_count = hit_count + 1, updated_at = ? WHERE id = ?",
            (time.time(), memory_id),
        )
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row:
            return MemoryRecord.from_row(row)
        return None

    def delete(self, memory_id: str) -> bool:
        self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.execute(
            "DELETE FROM memories_fts WHERE rowid = (SELECT rowid FROM memories WHERE id = ?)",
            (memory_id,),
        )
        self._conn.commit()
        return True

    def search_bm25(
        self, query: str, limit: int = 20, memory_type: str | None = None
    ) -> list[tuple[str, float]]:
        tokens = _jieba_tokenize(query)
        if not tokens:
            return []
        fts_query = " OR ".join(tokens)
        type_filter = ""
        params: list[Any] = [fts_query]
        if memory_type:
            type_filter = "AND memories.memory_type = ?"
            params.append(memory_type)
        rows = self._conn.execute(
            f"""SELECT memories_fts.memory_id, memories_fts.rank
                FROM memories_fts
                JOIN memories ON memories_fts.memory_id = memories.id
                WHERE memories_fts MATCH ?
                {type_filter}
                ORDER BY memories_fts.rank
                LIMIT ?""",
            (*params, limit),
        ).fetchall()
        results = []
        for row in rows:
            score = -row["rank"] if row["rank"] < 0 else 1.0 / (1.0 + row["rank"])
            results.append((row["memory_id"], score))
        return results

    def search_vector(
        self, query_embedding: list[float], limit: int = 20
    ) -> list[tuple[str, float]]:
        if not query_embedding:
            return []
        rows = self._conn.execute(
            "SELECT id, embedding FROM memories WHERE embedding IS NOT NULL"
        ).fetchall()
        if not rows:
            return []
        scored = []
        for row in rows:
            emb = json.loads(row["embedding"])
            sim = _cosine_similarity(query_embedding, emb)
            if sim > 0.0:
                scored.append((row["id"], sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def search_graph(self, query: str, limit: int = 20, depth: int = 2) -> list[tuple[str, float]]:
        tokens = _jieba_tokenize(query)
        if not tokens:
            return []
        concept_rows = self._conn.execute(
            "SELECT id, name, memory_ids FROM concepts WHERE name IN ({})".format(
                ",".join("?" * len(tokens))
            ),
            tokens,
        ).fetchall()
        seed_concepts = []
        for row in concept_rows:
            seed_concepts.append((row["id"], row["name"], json.loads(row["memory_ids"])))
        if not seed_concepts:
            partial_rows = self._conn.execute(
                "SELECT id, name, memory_ids FROM concepts WHERE name LIKE ?",
                (f"%{tokens[0]}%",),
            ).fetchall()
            for row in partial_rows:
                seed_concepts.append((row["id"], row["name"], json.loads(row["memory_ids"])))
        visited_concepts: set[str] = set()
        memory_scores: dict[str, float] = {}
        queue = [(cid, cname, 1.0, 0) for cid, cname, _ in seed_concepts]
        while queue:
            cid, cname, weight, d = queue.pop(0)
            if d > depth or cid in visited_concepts:
                continue
            visited_concepts.add(cid)
            row = self._conn.execute(
                "SELECT memory_ids FROM concepts WHERE id = ?", (cid,)
            ).fetchone()
            if row:
                for mid in json.loads(row["memory_ids"]):
                    memory_scores[mid] = memory_scores.get(mid, 0.0) + weight
            link_rows = self._conn.execute(
                "SELECT target_concept, weight FROM concept_links WHERE source_concept = ?",
                (cid,),
            ).fetchall()
            for lr in link_rows:
                if lr["target_concept"] not in visited_concepts:
                    queue.append(
                        (lr["target_concept"], lr["target_concept"], weight * lr["weight"], d + 1)
                    )
        if not memory_scores:
            return []
        max_score = max(memory_scores.values())
        results = [(mid, score / max_score) for mid, score in memory_scores.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        limit: int = 10,
        memory_type: str | None = None,
        query_type: str = "general",
    ) -> list[MemoryRecord]:
        bm25_results = self.search_bm25(query, limit=limit * 3, memory_type=memory_type)
        vector_results = (
            self.search_vector(query_embedding or [], limit=limit * 3) if query_embedding else []
        )
        graph_results = self.search_graph(query, limit=limit * 3)

        params = self._conn.execute(
            "SELECT alpha_bm25, alpha_vector, alpha_graph FROM fusion_params WHERE query_type = ?",
            (query_type,),
        ).fetchone()
        if params:
            a_bm25, a_vec, a_graph = (
                params["alpha_bm25"],
                params["alpha_vector"],
                params["alpha_graph"],
            )
        else:
            a_bm25, a_vec, a_graph = 0.4, 0.35, 0.25

        all_ids = set()
        for mid, _ in bm25_results + vector_results + graph_results:
            all_ids.add(mid)
        if not all_ids:
            return []
        bm25_map = {mid: score for mid, score in bm25_results}
        vec_map = {mid: score for mid, score in vector_results}
        graph_map = {mid: score for mid, score in graph_results}
        max_bm25 = max(bm25_map.values()) if bm25_map else 1.0
        max_vec = max(vec_map.values()) if vec_map else 1.0
        max_graph = max(graph_map.values()) if graph_map else 1.0

        fused = []
        for mid in all_ids:
            s_bm25 = bm25_map.get(mid, 0.0) / max_bm25
            s_vec = vec_map.get(mid, 0.0) / max_vec
            s_graph = graph_map.get(mid, 0.0) / max_graph
            final = a_bm25 * s_bm25 + a_vec * s_vec + a_graph * s_graph
            fused.append((mid, final))
        fused.sort(key=lambda x: x[1], reverse=True)
        records = []
        for mid, score in fused[:limit]:
            record = self.recall(mid)
            if record:
                record.importance = score
                records.append(record)
        return records

    def add_timeline_event(self, event: TimelineEvent) -> str:
        self._conn.execute(
            """INSERT OR REPLACE INTO timeline
               (id, event_type, session_id, tool_name, summary, details, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.id,
                event.event_type,
                event.session_id,
                event.tool_name,
                event.summary,
                json.dumps(event.details, ensure_ascii=False),
                event.created_at,
            ),
        )
        self._conn.commit()
        return event.id

    def query_timeline(
        self,
        session_id: str = "",
        event_type: str = "",
        since: float = 0,
        until: float = 0,
        limit: int = 50,
    ) -> list[TimelineEvent]:
        conditions = []
        params: list[Any] = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since > 0:
            conditions.append("created_at >= ?")
            params.append(since)
        if until > 0:
            conditions.append("created_at <= ?")
            params.append(until)
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._conn.execute(
            f"SELECT * FROM timeline WHERE {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [
            TimelineEvent(
                id=r["id"],
                event_type=r["event_type"],
                session_id=r["session_id"],
                tool_name=r["tool_name"],
                summary=r["summary"],
                details=json.loads(r["details"]) if r["details"] else {},
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def record_feedback(
        self, query: str, selected_id: str, skipped: list[str], query_type: str = "general"
    ) -> None:
        import uuid

        self._conn.execute(
            """INSERT INTO feedback_log (id, query, selected_memory_id, skipped_memory_ids, query_type)
               VALUES (?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                query,
                selected_id,
                json.dumps(skipped),
                query_type,
            ),
        )
        self._conn.commit()

    def update_fusion_params(
        self, query_type: str, alpha_bm25: float, alpha_vector: float, alpha_graph: float
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO fusion_params (query_type, alpha_bm25, alpha_vector, alpha_graph, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (query_type, alpha_bm25, alpha_vector, alpha_graph, time.time()),
        )
        self._conn.commit()

    def _extract_and_link_concepts(self, memory_id: str, content: str, memory_type: str) -> None:
        tokens = _jieba_tokenize(content)
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "的",
            "了",
            "是",
            "在",
            "有",
            "和",
            "与",
            "或",
            "但",
            "而",
            "如果",
            "this",
            "that",
            "it",
            "for",
            "to",
            "of",
            "and",
            "or",
            "but",
            "not",
        }
        concepts = [t for t in tokens if len(t) > 1 and t.lower() not in stop_words]
        if not concepts:
            return
        import hashlib

        for concept in concepts[:10]:
            cid = hashlib.md5(concept.lower().encode()).hexdigest()[:12]
            existing = self._conn.execute(
                "SELECT memory_ids FROM concepts WHERE id = ?", (cid,)
            ).fetchone()
            if existing:
                current_ids = json.loads(existing["memory_ids"]) if existing["memory_ids"] else []
                if memory_id not in current_ids:
                    current_ids.append(memory_id)
                    self._conn.execute(
                        "UPDATE concepts SET memory_ids = ? WHERE id = ?",
                        (json.dumps(current_ids), cid),
                    )
            else:
                self._conn.execute(
                    "INSERT OR IGNORE INTO concepts (id, name, category, memory_ids) VALUES (?, ?, ?, ?)",
                    (cid, concept.lower(), memory_type, json.dumps([memory_id])),
                )
        if len(concepts) >= 2:
            for i in range(min(len(concepts) - 1, 5)):
                src = hashlib.md5(concepts[i].lower().encode()).hexdigest()[:12]
                tgt = hashlib.md5(concepts[i + 1].lower().encode()).hexdigest()[:12]
                self._conn.execute(
                    "INSERT OR IGNORE INTO concept_links (source_concept, target_concept, weight) VALUES (?, ?, ?)",
                    (src, tgt, 0.5),
                )
        self._conn.commit()

    def get_stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()["cnt"]
        total_concepts = self._conn.execute("SELECT COUNT(*) as cnt FROM concepts").fetchone()[
            "cnt"
        ]
        total_events = self._conn.execute("SELECT COUNT(*) as cnt FROM timeline").fetchone()["cnt"]
        types = {}
        for row in self._conn.execute(
            "SELECT memory_type, COUNT(*) as cnt FROM memories GROUP BY memory_type"
        ):
            types[row["memory_type"]] = row["cnt"]
        return {
            "total_memories": total,
            "total_concepts": total_concepts,
            "total_timeline_events": total_events,
            "memory_types": types,
            "db_path": str(self._db_path),
        }

    def get_recent(self, limit: int = 20) -> list[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def get_by_type(self, memory_type: str, limit: int = 50) -> list[MemoryRecord]:
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE memory_type = ? ORDER BY importance DESC LIMIT ?",
            (memory_type, limit),
        ).fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            key = str(self._db_path)
            if key in SQLiteMemoryStore._instances:
                del SQLiteMemoryStore._instances[key]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
