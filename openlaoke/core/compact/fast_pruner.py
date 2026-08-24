"""Pure-algorithm context compression (<5ms, no LLM call).

Uses keyword extraction from middle section instead of LLM summarization.
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

# Combined alternation pattern: one finditer pass extracts all keyword types.
_KEYWORD_COMBINED = re.compile("|".join(f"(?:{p.pattern})" for _, p in KEYWORD_PATTERNS))


_extract_content_fn = None


def _extract_content(message: Message) -> str:
    global _extract_content_fn
    if _extract_content_fn is None:
        from openlaoke.core.compact import extract_content

        _extract_content_fn = extract_content
    return _extract_content_fn(message)


def extract_keywords(text: str, max_keywords: int = 50) -> list[str]:
    """Extract key information from text using a single combined regex pass."""
    keywords: list[str] = []
    seen: set[str] = set()

    for match in _KEYWORD_COMBINED.finditer(text):
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

    # Precompute content + tokens once for every message to avoid repeated work.
    contents = [_extract_content(m) for m in messages]
    token_list = [len(c) // 4 for c in contents]
    total_tokens = sum(token_list)
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
    middle_token_list: list[int] = []
    middle_contents: list[str] = []

    head_tokens = 0
    tail_tokens = 0

    for i, msg in enumerate(messages):
        tokens = token_list[i]
        content = contents[i]

        if i == 0 or (i < 3 and head_tokens < 2000):
            head_messages.append(msg)
            head_tokens += tokens
        elif total_tokens - head_tokens - tail_tokens - tokens < keep_tail_tokens:
            tail_messages.insert(0, msg)
            tail_tokens += tokens
        else:
            middle_messages.append(msg)
            middle_token_list.append(tokens)
            middle_contents.append(content)

    if not middle_messages:
        if total_tokens > max_tokens + keep_tail_tokens:
            head_messages = messages[:1]
            remaining = max_tokens - token_list[0]
            tail_budget = min(keep_tail_tokens, remaining)
            tail_messages = []
            tail_tokens = 0
            for idx in range(len(messages) - 1, 0, -1):
                t = token_list[idx]
                if tail_tokens + t <= tail_budget:
                    tail_messages.insert(0, messages[idx])
                    tail_tokens += t
                else:
                    break
            new_tokens = token_list[0] + tail_tokens
            return PruneResult(
                messages=head_messages + tail_messages,
                tokens_before=total_tokens,
                tokens_after=new_tokens,
                elapsed_ms=(time.monotonic() - start) * 1000,
            )
        return PruneResult(
            messages=messages,
            tokens_before=total_tokens,
            tokens_after=total_tokens,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    # Sample middle messages for keyword extraction when the set is large:
    # keep the first 20, last 10, and a uniform stride in between. This bounds
    # the cost while still covering the whole middle span.
    n_middle = len(middle_messages)
    if n_middle > 50:
        stride = max(1, n_middle // 20)
        sample_idx = sorted(
            set(
                list(range(20))
                + list(range(20, n_middle - 10, stride))
                + list(range(max(20, n_middle - 10), n_middle))
            )
        )
        sample_idx = [i for i in sample_idx if 0 <= i < n_middle]
    else:
        sample_idx = list(range(n_middle))

    all_keywords: list[str] = []
    for i in sample_idx:
        keywords = extract_keywords(middle_contents[i])
        all_keywords.extend(keywords)

    keyword_lines = "\n".join(f"- {kw}" for kw in all_keywords[:80])
    middle_tokens = sum(middle_token_list)
    summary_content = (
        f"[Compressed: {n_middle} messages, {middle_tokens} tokens -> keywords]\n"
        f"Key information preserved:\n{keyword_lines}"
    )

    from openlaoke.types.core_types import MessageRole, SystemMessage

    summary_msg = SystemMessage(
        role=MessageRole.SYSTEM,
        content=summary_content,
        subtype="compact",
    )

    new_messages = head_messages + [summary_msg] + tail_messages
    new_tokens = head_tokens + (len(summary_content) // 4) + tail_tokens

    elapsed = (time.monotonic() - start) * 1000

    return PruneResult(
        messages=new_messages,
        tokens_before=total_tokens,
        tokens_after=new_tokens,
        elapsed_ms=elapsed,
        keywords_extracted=len(all_keywords),
    )


def fast_prune_aggressive(
    messages: list[Message],
    max_tokens: int = 4096,
) -> PruneResult:
    """Aggressive pruning for local/small models where prefill dominates.

    In agent workloads, input:output is typically ≈ 13:1, and prefill time
    dominates decode time on low-compute GPUs.  This variant:

    - Keeps only the first message as head (not first 3)
    - Caps tail budget at 25% of max_tokens
    - Truncates long tool results to head 20 + tail 10 lines
    - Strips non-essential system messages entirely
    """
    from openlaoke.types.core_types import MessageRole, SystemMessage

    start = time.monotonic()

    if not messages:
        return PruneResult(messages=[], tokens_before=0, tokens_after=0)

    # Precompute content + tokens once.
    contents = [_extract_content(m) for m in messages]
    token_list = [len(c) // 4 for c in contents]
    total_tokens = sum(token_list)
    if total_tokens <= max_tokens:
        return PruneResult(
            messages=messages,
            tokens_before=total_tokens,
            tokens_after=total_tokens,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    # Apply tool-result truncation BEFORE splitting head/middle/tail
    truncated_messages: list[Message] = []
    truncated_tokens: list[int] = []
    truncated_contents: list[str] = []
    for msg, content, tokens in zip(messages, contents, token_list, strict=False):
        if (
            isinstance(msg, SystemMessage)
            and msg.subtype not in ("error", "warning")
            and len(content) > 3000
            and len(content.split("\n")) > 40
        ):
            lines = content.split("\n")
            truncated = (
                "\n".join(lines[:20])
                + "\n... [truncated "
                + str(len(lines) - 30)
                + " lines] ...\n"
                + "\n".join(lines[-10:])
            )
            truncated_messages.append(
                SystemMessage(
                    role=msg.role,
                    content=truncated,
                    subtype=msg.subtype,
                )
            )
            truncated_tokens.append(len(truncated) // 4)
            truncated_contents.append(truncated)
            continue
        truncated_messages.append(msg)
        truncated_tokens.append(tokens)
        truncated_contents.append(content)
    messages = truncated_messages
    token_list = truncated_tokens
    contents = truncated_contents

    # Keep only first message as head
    head_messages = messages[:1]
    head_tokens = token_list[0] if token_list else 0

    # Aggressive tail budget: 25% of max_tokens
    tail_budget = max(512, max_tokens // 4)
    tail_messages: list[Message] = []
    tail_tokens = 0

    for idx in range(len(messages) - 1, 0, -1):
        t = token_list[idx]
        if tail_tokens + t <= tail_budget:
            tail_messages.insert(0, messages[idx])
            tail_tokens += t
        else:
            break

    # Keyword extraction from skipped middle
    middle_start = len(head_messages)
    middle_end = len(messages) - len(tail_messages)

    # Sample large middles to bound cost.
    n_middle = middle_end - middle_start
    if n_middle > 50:
        stride = max(1, n_middle // 20)
        sample_idx = (
            list(range(middle_start, middle_start + 20, 1))
            + list(range(middle_start + 20, middle_end - 10, stride))
            + list(range(max(middle_start + 20, middle_end - 10), middle_end))
        )
        sample_idx = sorted(set(i for i in sample_idx if middle_start <= i < middle_end))
    else:
        sample_idx = list(range(middle_start, middle_end))

    all_keywords: list[str] = []
    for i in sample_idx:
        keywords = extract_keywords(contents[i], max_keywords=30)
        all_keywords.extend(keywords)

    keyword_lines = "\n".join(f"- {kw}" for kw in all_keywords[:50])
    summary_content = (
        (f"[Compressed: {n_middle} messages skipped. Key info:]\n{keyword_lines}")
        if keyword_lines
        else f"[Compressed: {n_middle} messages skipped.]"
    )

    summary_msg = SystemMessage(
        role=MessageRole.SYSTEM,
        content=summary_content,
        subtype="compact",
    )

    new_messages = head_messages + [summary_msg] + tail_messages
    new_tokens = head_tokens + (len(summary_content) // 4) + tail_tokens
    elapsed = (time.monotonic() - start) * 1000

    return PruneResult(
        messages=new_messages,
        tokens_before=total_tokens,
        tokens_after=new_tokens,
        elapsed_ms=elapsed,
        keywords_extracted=len(all_keywords),
    )
