"""Full-text search over saved sessions and the live conversation.

Two questions this answers that grep over the JSON cannot:

* "where did I work out the migration order?" - across every saved session, and
* "what did I say ten turns ago about the timeout?" - in the conversation the
  model can no longer see in full.

Both use the same BM25 scorer and the same tokeniser as the memory store, so a
Chinese query is split into character bigrams rather than being treated as one
unsearchable token. Tool results are truncated before indexing: a session file
is mostly tool output, and indexing all of it would let a single large `Read`
outrank every real discussion.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any

from openlaoke.core.memory_store import tokenize

SESSIONS_DIR = os.path.join(os.path.expanduser("~"), ".openlaoke", "sessions")
MAX_DOC_CHARS = 4000
K1, B = 1.5, 0.75


@dataclass
class Hit:
    session_id: str
    role: str
    index: int
    timestamp: float
    text: str
    score: float = 0.0

    def line(self) -> str:
        when = (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(self.timestamp))
            if self.timestamp
            else "?"
        )
        snippet = " ".join(self.text.split())[:240]
        return f"{self.session_id} #{self.index} {self.role} {when}\n    {snippet}"


def _score(query_tokens: list[str], documents: list[list[str]]) -> list[float]:
    if not query_tokens or not documents:
        return [0.0 for _ in documents]
    total = len(documents)
    average_length = sum(len(doc) for doc in documents) / max(1, total)
    frequencies: list[dict[str, int]] = []
    document_frequency: dict[str, int] = {}
    for document in documents:
        counts: dict[str, int] = {}
        for token in document:
            counts[token] = counts.get(token, 0) + 1
        frequencies.append(counts)
        for token in set(counts):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    scores: list[float] = []
    unique = set(query_tokens)
    for counts, document in zip(frequencies, documents, strict=True):
        score = 0.0
        for token in unique:
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            idf = _idf(total, document_frequency.get(token, 0))
            denominator = frequency + K1 * (1 - B + B * len(document) / max(average_length, 1e-9))
            score += idf * frequency * (K1 + 1) / denominator
        scores.append(score)
    return scores


def score_documents(query: str, documents: list[str]) -> list[float]:
    """BM25 scores for plain texts, sharing the tokeniser used everywhere else."""
    tokens = tokenize(query)
    return _score(tokens, [tokenize(document) for document in documents])


def _idf(total: int, document_frequency: int) -> float:
    return math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))


def _messages_of(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages = payload.get("messages")
    return (
        [item for item in messages if isinstance(item, dict)] if isinstance(messages, list) else []
    )


def _payloads(sessions_dir: str) -> list[dict[str, Any]]:
    """Every saved session, falling back to the journal when a snapshot is gone.

    A session recovered from its journal is listed by ``/sessions``; leaving it
    out of search would mean the conversation is back but unfindable.
    """
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        names = sorted(os.listdir(sessions_dir))
    except OSError:
        return payloads

    for filename in names:
        if not filename.endswith(".json"):
            continue
        stem = filename[: -len(".json")]
        seen.add(stem)
        path = os.path.join(sessions_dir, filename)
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            payload = _journal_payload(sessions_dir, stem)
            if payload is not None:
                payloads.append(payload)
            continue
        if isinstance(payload, dict) and "exported_at" in payload:
            # An /export JSON written next to the snapshots (older builds put it
            # there) is the same conversation under the same id; searching it
            # would return every hit twice and name a session /sessions does not
            # list.
            continue
        payload.setdefault("session_id", stem)
        payload["_path"] = path
        payloads.append(payload)

    for filename in names:
        if not filename.endswith(".jsonl"):
            continue
        stem = filename[: -len(".jsonl")]
        if stem in seen:
            continue
        payload = _journal_payload(sessions_dir, stem)
        if payload is not None:
            payloads.append(payload)
    return payloads


def _journal_payload(sessions_dir: str, session_id: str) -> dict[str, Any] | None:
    from openlaoke.core.transcript import Transcript, transcript_path_for

    journal = transcript_path_for(os.path.join(sessions_dir, f"{session_id}.json"))
    if not os.path.exists(journal):
        return None
    header, records = Transcript(journal).replay()
    if not records:
        return None
    return {
        "session_id": header.get("session_id") or session_id,
        "cwd": header.get("cwd", ""),
        "messages": [record["message"] for record in records],
        "_path": journal,
    }


def search_sessions(
    query: str,
    sessions_dir: str = SESSIONS_DIR,
    limit: int = 10,
    days: float = 0.0,
    cwd: str = "",
    role: str = "",
) -> list[Hit]:
    """Search every saved session for ``query``."""
    query_tokens = tokenize(query)
    if not query_tokens or not os.path.isdir(sessions_dir):
        return []

    cutoff = time.time() - days * 86400 if days and days > 0 else 0.0
    wanted_cwd = os.path.abspath(cwd) if cwd else ""

    hits: list[Hit] = []
    documents: list[list[str]] = []
    for payload in _payloads(sessions_dir):
        path = payload.get("_path", "")
        try:
            if cutoff and path and os.path.getmtime(path) < cutoff:
                continue
        except OSError:
            continue
        session_cwd = payload.get("cwd", "")
        if wanted_cwd and session_cwd and os.path.abspath(session_cwd) != wanted_cwd:
            continue
        session_id = payload.get("session_id") or ""
        for index, message in enumerate(_messages_of(payload)):
            message_role = str(message.get("role", ""))
            if role and message_role != role:
                continue
            text = str(message.get("content", ""))
            if not text.strip():
                continue
            hits.append(
                Hit(
                    session_id=session_id,
                    role=message_role,
                    index=index,
                    timestamp=float(message.get("timestamp", 0.0) or 0.0),
                    text=text[:MAX_DOC_CHARS],
                )
            )
            documents.append(tokenize(hits[-1].text))

    scores = _score(query_tokens, documents)
    ranked = sorted(zip(hits, scores, strict=True), key=lambda item: item[1], reverse=True)
    results: list[Hit] = []
    for hit, score in ranked:
        if score <= 0:
            continue
        hit.score = score
        results.append(hit)
        if len(results) >= limit:
            break
    return results


def search_conversation(
    query: str,
    messages: list[Any],
    limit: int = 10,
) -> list[Hit]:
    """Search just the messages of the running session."""
    query_tokens = tokenize(query)
    if not query_tokens or not messages:
        return []

    hits: list[Hit] = []
    documents: list[list[str]] = []
    for index, message in enumerate(messages):
        role = str(getattr(message, "role", "")).split(".")[-1].lower()
        content = getattr(message, "content", "")
        text = content if isinstance(content, str) else ""
        if not text.strip():
            continue
        hits.append(
            Hit(
                session_id="current",
                role=role,
                index=index,
                timestamp=float(getattr(message, "timestamp", 0.0) or 0.0),
                text=text[:MAX_DOC_CHARS],
            )
        )
        documents.append(tokenize(text))

    scores = _score(query_tokens, documents)
    ranked = sorted(zip(hits, scores, strict=True), key=lambda item: item[1], reverse=True)
    results: list[Hit] = []
    for hit, score in ranked:
        if score <= 0:
            continue
        hit.score = score
        results.append(hit)
        if len(results) >= limit:
            break
    return results
