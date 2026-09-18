"""Pure-algorithm context compression (<5ms, no LLM call).

Uses keyword extraction from middle section instead of LLM summarization.

Design constraints (harness-correctness):

- Message ORDER is never rearranged.  An assistant message carrying
  ``tool_calls`` and its ``tool`` result messages must stay adjacent, or the
  provider rejects the request (dangling tool_call_id).  The previous
  implementation hoisted "protected" messages into a separate bucket which
  broke this pairing.

- Tool results are truncated, not dropped.  Evidence (file contents, command
  output, error messages) stays in context in head+tail form so the model can
  still cite it later.  Dropping them silently caused read-loop behaviour.

- User requirements are never compressed.  Only assistant prose may be
  summarized into a keyword digest.

- The summarizer never *grows* the context: if the keyword digest would be
  larger than the elided middle, the middle is kept as-is.
"""

from __future__ import annotations

import contextlib
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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

# Decision/constraint phrases worth keeping verbatim in summaries.
# Anchored on the keyword itself (linear scan, no backtracking).
_DECISION_PATTERN = re.compile(
    r"\b(?:decisions?|decided|chosen|constraints?|must not|must be|requirement|"
    r"rejected|won't do|will not)[^\n]{0,200}",
    re.IGNORECASE,
)

_extract_content_fn = None


def _extract_content(message: Message) -> str:
    global _extract_content_fn
    if _extract_content_fn is None:
        from openlaoke.core.compact import extract_content

        _extract_content_fn = extract_content
    return _extract_content_fn(message)


def _message_role(message: object) -> str:
    role: Any = getattr(message, "role", None)
    if isinstance(message, dict):
        role = message.get("role", role)
    if role is not None and hasattr(role, "value"):
        return str(role.value)
    return str(role or "")


def _is_user_requirement(message: object) -> bool:
    """True for user messages (requirements) and system-injected turns."""
    role = _message_role(message)
    if role == "user":
        return True
    return bool(isinstance(message, dict) and message.get("system_injected"))


def _is_tool_result(message: object) -> bool:
    """True for tool result messages (dict ``role:"tool"`` or SystemMessage
    with a tool_use_id)."""
    role = _message_role(message)
    if role == "tool":
        return True
    if role == "system" and getattr(message, "tool_use_id", None):
        return True
    return isinstance(message, dict) and role == "system" and bool(message.get("tool_use_id"))


def _is_assistant_tool_call(message: object) -> bool:
    role = _message_role(message)
    if role != "assistant":
        return False
    if getattr(message, "tool_uses", None):
        return True
    return isinstance(message, dict) and bool(message.get("tool_calls"))


def _strip_prose(message: Any) -> Any:
    """Return a copy of an assistant tool-call message with content emptied.

    The tool_calls/tool_uses structure is preserved so the request stays
    provider-valid (no dangling tool_call_id) while the prose is elided.
    """
    if isinstance(message, dict):
        stripped = dict(message)
        stripped["content"] = ""
        return stripped
    with contextlib.suppress(AttributeError):
        message.content = ""
    return message


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


def extract_decisions(text: str, max_lines: int = 12) -> list[str]:
    """Pull decision/constraint sentences out of assistant prose.

    Keeps confirmed decisions and implementation constraints so they are not
    re-litigated after compaction.
    """
    lines: list[str] = []
    for match in _DECISION_PATTERN.finditer(text):
        line = match.group(0).strip()
        if 20 < len(line) < 300:
            lines.append(line)
            if len(lines) >= max_lines:
                break
    return lines


def _sample_indices(indices: list[int], max_samples: int) -> set[int]:
    """Head-biased uniform sample of *indices* to bound regex cost."""
    n = len(indices)
    if n <= max_samples:
        return set(indices)
    stride = max(1, n // max_samples)
    sampled = set(range(0, min(10, n)))
    sampled.update(indices[::stride][:max_samples])
    return sampled


def _truncate_tool_result(content: str, head_lines: int = 30, tail_lines: int = 12) -> str:
    """Keep head+tail of a long tool result; collapse the middle."""
    lines = content.split("\n")
    if len(lines) <= head_lines + tail_lines + 2:
        return content
    omitted = len(lines) - head_lines - tail_lines
    return (
        "\n".join(lines[:head_lines])
        + f"\n... [{omitted} lines truncated, full output was {len(content)} chars] ...\n"
        + "\n".join(lines[-tail_lines:])
    )


def fast_prune(
    messages: list[Message],
    max_tokens: int = 8192,
    keep_tail_tokens: int = 8192,
    protect_read_results: bool = True,
) -> PruneResult:
    """Pure-algorithm context compression with head-tail preservation.

    Strategy (order-preserving):
    1. Head: first messages up to a small budget (never reordered).
    2. Tail: last ``keep_tail_tokens`` worth of messages (never reordered).
    3. Middle: user requirements pass through byte-identical; tool results are
       head+tail truncated; assistant prose is replaced by a keyword digest
       *in place* so tool_call/tool_result adjacency is preserved.

    Runs in <5ms, no LLM call needed.
    """
    start = time.monotonic()

    if not messages:
        return PruneResult(messages=[], tokens_before=0, tokens_after=0)

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

    from openlaoke.types.core_types import MessageRole, SystemMessage

    new_messages: list[Any] = []
    new_tokens = 0

    head_budget = min(2000, max_tokens // 8)
    head_tokens = 0
    head_end = 0
    for i, _msg in enumerate(messages):
        if head_end > 0 and head_tokens + token_list[i] > head_budget:
            break
        head_messages_guard = i < 3
        if i == 0 or (head_messages_guard and head_tokens < 2000):
            head_tokens += token_list[i]
            head_end = i + 1
        else:
            break
    new_messages.extend(messages[:head_end])
    new_tokens += head_tokens

    tail_budget = min(keep_tail_tokens, max_tokens - head_tokens)
    tail_start = len(messages)
    tail_tokens = 0
    for i in range(len(messages) - 1, head_end - 1, -1):
        if tail_tokens + token_list[i] > tail_budget and tail_start < len(messages):
            break
        tail_start = i
        tail_tokens += token_list[i]

    # The newest user requirement is never elided: extend the tail window to
    # include the last user message even if the budget was exhausted just
    # above it (the requirement is the anchor the model must still see).
    for i in range(tail_start - 1, head_end - 1, -1):
        if _is_user_requirement(messages[i]):
            tail_start = i
            break

    digest_parts: list[str] = []
    digest_tokens = 0
    elided_tokens = 0

    # Bound regex work: sample at most 40 elided messages for keywords.
    elided_indices: list[int] = []
    for i in range(head_end, tail_start):
        msg = messages[i]
        if _is_user_requirement(msg) or (protect_read_results and _is_assistant_tool_call(msg)):
            continue
        if not _is_tool_result(msg):
            elided_indices.append(i)

    sample_idx = _sample_indices(elided_indices, max_samples=40)

    for i in range(head_end, tail_start):
        msg = messages[i]
        tokens = token_list[i]
        content = contents[i]

        if _is_user_requirement(msg) or (protect_read_results and _is_assistant_tool_call(msg)):
            new_messages.append(msg)
            new_tokens += tokens
            continue

        if _is_tool_result(msg):
            truncated = _truncate_tool_result(content, head_lines=30, tail_lines=12)
            if truncated != content:
                if isinstance(msg, SystemMessage) and msg.tool_use_id:
                    truncated_msg: Any = SystemMessage(
                        role=msg.role,
                        content=truncated,
                        subtype=msg.subtype,
                        tool_use_id=msg.tool_use_id,
                    )
                else:
                    truncated_msg = dict(msg) if isinstance(msg, dict) else msg
                    if isinstance(truncated_msg, dict):
                        truncated_msg["content"] = truncated
                new_messages.append(truncated_msg)
                new_tokens += len(truncated) // 4
            else:
                new_messages.append(msg)
                new_tokens += tokens
            continue

        # Assistant prose: elide into digest, but never drop the message
        # structure when it carries tool_calls — a dangling tool_call breaks
        # the provider request.  For AssistantMessage objects keep the object
        # with empty content; for dicts set content="" but keep tool_calls.
        elided_tokens += tokens
        if i in sample_idx and digest_tokens < max_tokens // 16:
            digest_parts.extend(extract_keywords(content, max_keywords=20))
            digest_parts.extend(extract_decisions(content, max_lines=4))
            digest_tokens += sum(len(k) for k in digest_parts[-24:]) // 4

    middle_summary = None
    if elided_tokens > 0:
        unique_kw: list[str] = []
        seen_kw: set[str] = set()
        for kw in digest_parts:
            if kw not in seen_kw:
                seen_kw.add(kw)
                unique_kw.append(kw)
        summary_content = (
            f"[Context digest: {elided_tokens} tokens of assistant prose elided. "
            "Key information preserved:]\n" + "\n".join(f"- {kw}" for kw in unique_kw[:60])
        )
        summary_tokens = len(summary_content) // 4
        if summary_tokens < elided_tokens:
            middle_summary = SystemMessage(
                role=MessageRole.SYSTEM,
                content=summary_content,
                subtype="compact",
            )
            new_tokens += summary_tokens
        else:
            # Digest would not save space — keep everything as-is.
            new_messages = list(messages)
            new_tokens = total_tokens
            middle_summary = None

    if middle_summary is not None:
        # Insert digest right after the head block (before first non-head
        # message) to preserve chronology: the digest represents the elided
        # middle messages that came before everything in new_messages[head_end:].
        new_messages = (
            list(new_messages[:head_end]) + [middle_summary] + list(new_messages[head_end:])
        )

    new_messages.extend(messages[tail_start:])
    elapsed = (time.monotonic() - start) * 1000

    return PruneResult(
        messages=new_messages,
        tokens_before=total_tokens,
        tokens_after=new_tokens,
        elapsed_ms=elapsed,
        keywords_extracted=len(unique_kw) if elided_tokens > 0 and middle_summary else 0,
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
    - Preserves message order and tool_call/tool_result adjacency
    """
    from openlaoke.types.core_types import MessageRole, SystemMessage

    start = time.monotonic()

    if not messages:
        return PruneResult(messages=[], tokens_before=0, tokens_after=0)

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

    # Pass 1: truncate long system non-tool messages IN PLACE (order kept).
    truncated_messages: list[Any] = []
    truncated_tokens: list[int] = []
    truncated_contents: list[str] = []
    for msg, content, tokens in zip(messages, contents, token_list, strict=False):
        if (
            isinstance(msg, SystemMessage)
            and not getattr(msg, "tool_use_id", None)
            and msg.subtype not in ("error", "warning", "compact")
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
    total_tokens = sum(token_list)

    if total_tokens <= max_tokens:
        return PruneResult(
            messages=messages,
            tokens_before=total_tokens,
            tokens_after=total_tokens,
            elapsed_ms=(time.monotonic() - start) * 1000,
        )

    # Pass 2: head = first message only; tail = last 25% budget.
    head_end = 1
    head_tokens = token_list[0]

    tail_budget = max(512, max_tokens // 4)
    tail_start = len(messages)
    tail_tokens = 0
    for idx in range(len(messages) - 1, head_end - 1, -1):
        if tail_tokens + token_list[idx] > tail_budget and tail_start < len(messages):
            break
        tail_start = idx
        tail_tokens += token_list[idx]

    # Pass 3: walk the middle in order.  User requirements and tool results
    # stay (tool results truncated); assistant prose elides into a digest.
    new_messages: list[Any] = list(messages[:head_end])
    new_tokens = head_tokens

    digest_parts: list[str] = []
    elided_tokens = 0

    elided_indices: list[int] = []
    for i in range(head_end, tail_start):
        msg = messages[i]
        if _is_user_requirement(msg) or _is_assistant_tool_call(msg) or _is_tool_result(msg):
            continue
        elided_indices.append(i)
    sample_idx = _sample_indices(elided_indices, max_samples=30)

    for i in range(head_end, tail_start):
        msg = messages[i]
        tokens = token_list[i]
        content = contents[i]

        if _is_user_requirement(msg) or _is_assistant_tool_call(msg):
            new_messages.append(msg)
            new_tokens += tokens
            continue

        if _is_tool_result(msg):
            truncated = _truncate_tool_result(content, head_lines=20, tail_lines=10)
            if truncated != content:
                if isinstance(msg, SystemMessage) and msg.tool_use_id:
                    truncated_msg: Any = SystemMessage(
                        role=msg.role,
                        content=truncated,
                        subtype=msg.subtype,
                        tool_use_id=msg.tool_use_id,
                    )
                else:
                    truncated_msg = dict(msg) if isinstance(msg, dict) else msg
                    if isinstance(truncated_msg, dict):
                        truncated_msg["content"] = truncated
                new_messages.append(truncated_msg)
                new_tokens += len(truncated) // 4
            else:
                new_messages.append(msg)
                new_tokens += tokens
            continue

        elided_tokens += tokens
        if i in sample_idx:
            for kw in extract_keywords(content, max_keywords=15):
                digest_parts.append(kw)

    if elided_tokens > 0:
        unique_kw: list[str] = []
        seen_kw: set[str] = set()
        for kw in digest_parts:
            if kw not in seen_kw:
                seen_kw.add(kw)
                unique_kw.append(kw)
        summary_content = (
            f"[Context digest: {elided_tokens} tokens elided. Key info:]\n"
            + "\n".join(f"- {kw}" for kw in unique_kw[:40])
        )
        summary_tokens = len(summary_content) // 4
        if summary_tokens < elided_tokens:
            summary_msg = SystemMessage(
                role=MessageRole.SYSTEM,
                content=summary_content,
                subtype="compact",
            )
            new_tokens += summary_tokens
            new_messages.append(summary_msg)
        else:
            new_messages = list(messages)
            new_tokens = total_tokens

    new_messages.extend(messages[tail_start:])
    elapsed = (time.monotonic() - start) * 1000

    return PruneResult(
        messages=new_messages,
        tokens_before=total_tokens,
        tokens_after=new_tokens,
        elapsed_ms=elapsed,
        keywords_extracted=len(unique_kw) if elided_tokens > 0 and new_tokens < total_tokens else 0,
    )
