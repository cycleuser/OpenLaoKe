"""Pure-algorithm context compression (<5ms, no LLM call).

Adapted from kwcode's context_pruner.py - uses keyword extraction
from middle section instead of LLM summarization.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.types.core_types import Message


@dataclass
class PruneResult:
    messages: list[Message]
    tokens_before: int
    tokens_after: int
    elapsed_ms: float = 0.0
    keywords_extracted: int = 0


KEYWORD_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("file_path", re.compile(r'[/\\][\w./\\-]+[\w](?=\s|["\')]|$)')),
    ("function_def", re.compile(r"(?:def|func|function)\s+(\w+)")),
    ("class_def", re.compile(r"(?:class|struct|type)\s+(\w+)")),
    ("error_msg", re.compile(r"(?:Error|Exception|Failed|error|failed):\s*(.+)")),
    ("import", re.compile(r"(?:import|from)\s+([\w.]+)")),
    ("tool_call", re.compile(r"Tool:\s*(\w+)")),
]


def _extract_content(message: Message) -> str:
    from openlaoke.core.compact import extract_content

    return extract_content(message)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def extract_keywords(text: str, max_keywords: int = 50) -> list[str]:
    """Extract key information from text using regex patterns."""
    keywords: list[str] = []
    seen: set[str] = set()

    for _name, pattern in KEYWORD_PATTERNS:
        for match in pattern.finditer(text):
            keyword = match.group(0).strip()
            if keyword and keyword not in seen and len(keyword) > 2:
                seen.add(keyword)
                keywords.append(keyword)
                if len(keywords) >= max_keywords:
                    return keywords

    return keywords


def fast_prune(
    messages: list[Message],
    max_tokens: int = 8192,
    keep_tail_tokens: int = 8192,
) -> PruneResult:
    """Pure-algorithm context compression with head-tail preservation.

    Strategy:
    1. Keep system prompt + first turn (head)
    2. Keep last N tokens (tail)
    3. Extract keywords from middle section via regex patterns
    4. Replace middle with keyword summary

    Runs in <5ms, no LLM call needed.
    """
    start = time.monotonic()

    if not messages:
        return PruneResult(messages=[], tokens_before=0, tokens_after=0)

    total_tokens = sum(_estimate_tokens(_extract_content(m)) for m in messages)
    if total_tokens <= max_tokens:
        return PruneResult(
            messages=messages,
            tokens_before=total_tokens,
            tokens_after=total_tokens,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    head_messages: list[Message] = []
    tail_messages: list[Message] = []
    middle_messages: list[Message] = []

    head_tokens = 0
    tail_tokens = 0

    for i, msg in enumerate(messages):
        tokens = _estimate_tokens(_extract_content(msg))

        if i == 0 or (i < 3 and head_tokens < 2000):
            head_messages.append(msg)
            head_tokens += tokens
        elif total_tokens - head_tokens - tail_tokens - tokens < keep_tail_tokens:
            tail_messages.insert(0, msg)
            tail_tokens += tokens
        else:
            middle_messages.append(msg)

    if not middle_messages:
        return PruneResult(
            messages=messages,
            tokens_before=total_tokens,
            tokens_after=total_tokens,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    all_keywords: list[str] = []
    for msg in middle_messages:
        content = _extract_content(msg)
        keywords = extract_keywords(content)
        all_keywords.extend(keywords)

    keyword_lines = "\n".join(f"- {kw}" for kw in all_keywords[:80])
    summary_content = (
        f"[Compressed: {len(middle_messages)} messages, {sum(_estimate_tokens(_extract_content(m)) for m in middle_messages)} tokens -> keywords]\n"
        f"Key information preserved:\n{keyword_lines}"
    )

    from openlaoke.types.core_types import MessageRole, SystemMessage

    summary_msg = SystemMessage(
        role=MessageRole.SYSTEM,
        content=summary_content,
        subtype="compact",
    )

    new_messages = head_messages + [summary_msg] + tail_messages
    new_tokens = sum(_estimate_tokens(_extract_content(m)) for m in new_messages)

    elapsed = (time.monotonic() - start) * 1000

    return PruneResult(
        messages=new_messages,
        tokens_before=total_tokens,
        tokens_after=new_tokens,
        elapsed_ms=elapsed,
        keywords_extracted=len(all_keywords),
    )
