"""Cache-respecting context builder.

The :class:`ContextBuilder` produces three pieces:

* **prefix** — system prompt + tool index + memory index. Stable across
  turns; cache hit on subsequent calls. Byte-stable: only rebuilt when
  ``invalidate()`` is called (model switch, memory update, tool change).
* **messages** — the conversation history (already trimmed/summarized
  by the compactor).
* **runtime_block** — short, tag-bounded metadata appended to the
  outgoing user content. Survives a cache miss but is bounded.

This module also handles:

* **CompactSummary** — a structured six-section summary (Goal / Decisions /
  Files / Commands / Errors / Pending) injected into the prefix after
  LLM-based compaction.
* **Thinking Budget** — provider-aware thinking-token caps wired into
  the request params to prevent small models from burning context on
  reasoning.
* **Window-adaptive routing** — on very small windows (<16K), the
  tool contract and system prompt are trimmed to keep the prefix
  compact.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from openlaoke.memory.docs import DocMemoryBundle


@dataclass
class BuiltContext:
    """The three-part LLM context."""

    prefix: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    runtime_block: str = ""
    cache_anchor: str = ""

    def to_request(self) -> dict[str, Any]:
        return {
            "system": self.prefix,
            "messages": self.messages,
            "metadata": {"cache_anchor": self.cache_anchor},
        }


@dataclass
class GoalState:
    """An active sustained goal on the main agent."""

    status: str = "idle"
    objective: str = ""
    ui_summary: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    recap: str = ""


@dataclass
class CompactSummary:
    """Structured six-section compaction summary.

    Injected into the prefix after LLM-based context compaction.
    The model resumes from this alone; original messages are dropped.
    """

    goal: str = ""
    decisions: str = ""
    files: str = ""
    commands: str = ""
    errors: str = ""
    pending: str = ""

    def render(self) -> str:
        parts: list[str] = []
        if self.goal:
            parts.append(f"## Goal\n{self.goal}")
        if self.decisions:
            parts.append(f"## Decisions & rationale\n{self.decisions}")
        if self.files:
            parts.append(f"## Files & code\n{self.files}")
        if self.commands:
            parts.append(f"## Commands & outcomes\n{self.commands}")
        if self.errors:
            parts.append(f"## Errors & fixes\n{self.errors}")
        if self.pending:
            parts.append(f"## Pending & next step\n{self.pending}")
        return "\n\n".join(parts) if parts else ""

    @classmethod
    def parse(cls, text: str) -> CompactSummary:
        """Parse a structured summary from the compaction LLM output."""
        result = cls()
        current_key: str = ""
        current_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## Goal"):
                cls._assign(result, current_key, current_lines)
                current_key, current_lines = "goal", []
            elif stripped.startswith("## Decisions"):
                cls._assign(result, current_key, current_lines)
                current_key, current_lines = "decisions", []
            elif stripped.startswith("## Files"):
                cls._assign(result, current_key, current_lines)
                current_key, current_lines = "files", []
            elif stripped.startswith("## Commands"):
                cls._assign(result, current_key, current_lines)
                current_key, current_lines = "commands", []
            elif stripped.startswith("## Errors"):
                cls._assign(result, current_key, current_lines)
                current_key, current_lines = "errors", []
            elif stripped.startswith("## Pending"):
                cls._assign(result, current_key, current_lines)
                current_key, current_lines = "pending", []
            elif current_key and stripped:
                current_lines.append(line)
        cls._assign(result, current_key, current_lines)
        return result

    @staticmethod
    def _assign(result: CompactSummary, key: str, lines: list[str]) -> None:
        if key and hasattr(result, key):
            setattr(result, key, "\n".join(lines).strip())

    def has_any(self) -> bool:
        return bool(self.goal or self.decisions or self.files or self.commands or self.errors or self.pending)


COMPACTION_SYSTEM_PROMPT = """You are compacting the earlier part of a coding agent's conversation to save context.
The agent will keep ONLY your summary (the original messages are dropped), so it must be able to resume the task from it alone.
Write a briefing under these exact headings, omitting a heading only if it has no content:

## Goal
The user's request and intent, kept close to their own words. Include explicit requirements, constraints, and preferences.

## Decisions & rationale
Key choices made so far and why — so they are not re-litigated or reversed.

## Files & code
Files read or modified, with the specific facts that matter: signatures, line locations, data shapes, and exact edits applied. Be concrete; this is what lets the agent act without re-reading everything.

## Commands & outcomes
Commands run (builds, tests, git) and their relevant results — what passed, what failed, and the error text that matters.

## Errors & fixes
Problems hit and how they were resolved (or not), so the same dead ends are not repeated.

## Pending & next step
What is still in progress or unstarted, and the single most concrete next action to take.

Rules: be terse — bullet points and fragments, not prose. Preserve identifiers, paths, and numbers exactly. Do NOT invent anything not present in the messages; if something is unknown, leave it out rather than guessing."""


def render_goal_lines(goal: GoalState | None) -> list[str]:
    if not goal or goal.status == "idle":
        return []
    if goal.status == "active":
        return [
            f"[Runtime Context] Active goal: {goal.objective}",
            f"Summary: {goal.ui_summary}",
        ]
    if goal.status == "completed":
        return [f"[Runtime Context] Last goal: {goal.objective} (completed)"]
    if goal.status == "cancelled":
        return [f"[Runtime Context] Last goal: {goal.objective} (cancelled)"]
    return []


def render_channel_lines(channel: str, chat_id: str, sender_id: str) -> list[str]:
    return [
        f"[Runtime Context] channel: {channel}",
        f"chat_id: {chat_id}" if chat_id else "",
        f"sender_id: {sender_id}" if sender_id else "",
    ]


def render_time_lines() -> list[str]:
    return [f"[Runtime Context] time: {time.strftime('%Y-%m-%d %H:%M:%S')}"]


def compose_runtime_block(
    goal: GoalState | None = None,
    channel: str = "cli",
    chat_id: str = "",
    sender_id: str = "",
    pending_notes: list[str] | None = None,
    extra: list[str] | None = None,
) -> str:
    """Compose the runtime block.

    The result is **append-only** content that goes after the user
    content, never into the system prefix.
    """
    lines: list[str] = []
    lines.extend(render_time_lines())
    lines.extend(render_channel_lines(channel, chat_id, sender_id))
    lines.extend(render_goal_lines(goal))
    if pending_notes:
        lines.append("[Runtime Context] Pending memory notes:")
        lines.extend(f"- {n}" for n in pending_notes)
    if extra:
        lines.extend(extra)
    return "\n".join(line for line in lines if line)


class ContextBuilder:
    """Assembles the LLM context each turn.

    The builder maintains a **cached prefix** — the system prompt,
    tool schemas, memory index, and skills index are combined once,
    hashed, and only rebuilt when ``invalidate()`` is called.  This
    keeps DeepSeek / OpenAI automatic prefix cache warm across turns.

    Runtime-variable content (time, goal, channel) travels in the
    **runtime block** appended to the last user message, so the prefix
    itself never changes mid-session.

    Invoke ``invalidate()`` after: model switch, memory update, tool
    set change, or skill activation/deactivation.
    """

    _COMPACT_WINDOW_THRESHOLD = 16000

    def __init__(
        self,
        identity: str = "",
        tool_contract: str = "",
        doc_bundle_provider: Callable[[], DocMemoryBundle] | None = None,
        memory_index_provider: Callable[[], str] | None = None,
        skills_index_provider: Callable[[], str] | None = None,
        recent_history_provider: Callable[[], list[dict[str, Any]]] | None = None,
        archived_summary: str = "",
        compact_summary: CompactSummary | None = None,
        max_prefix_chars: int = 12000,
        window_tokens: int = 128000,
    ) -> None:
        self.identity = identity
        self.tool_contract = tool_contract
        self.doc_bundle_provider = doc_bundle_provider or (lambda: DocMemoryBundle())
        self.memory_index_provider = memory_index_provider or (lambda: "")
        self.skills_index_provider = skills_index_provider or (lambda: "")
        self.recent_history_provider = recent_history_provider or (lambda: [])
        self.archived_summary = archived_summary
        self.compact_summary = compact_summary
        self.max_prefix_chars = max_prefix_chars
        self.window_tokens = window_tokens
        self._cached_prefix: str = ""
        self._cached_hash: str = ""
        self._prefix_dirty: bool = True

    def invalidate(self) -> None:
        """Mark the cached prefix as stale.

        Call this after any change that affects the prefix content:
        model switch, memory update, tool change, skill toggle.
        """
        self._prefix_dirty = True

    def _compute_prefix_hash(self, prefix: str) -> str:
        return hashlib.sha256(prefix.encode()).hexdigest()[:16]

    def _is_small_window(self) -> bool:
        return self.window_tokens < self._COMPACT_WINDOW_THRESHOLD

    def build_prefix(self) -> str:
        if not self._prefix_dirty and self._cached_prefix:
            return self._cached_prefix

        parts: list[str] = []
        if self.identity:
            parts.append(self.identity)
        bundle = self.doc_bundle_provider()
        if bundle.has_any():
            parts.append(bundle.combined_body())
        if self.tool_contract:
            parts.append(self.tool_contract)
        skills = self.skills_index_provider()
        if skills:
            parts.append(f"# Active Skills\n\n{skills}")
        memory = self.memory_index_provider()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        if self.compact_summary and self.compact_summary.has_any():
            parts.append(f"# Archived Summary\n\n{self.compact_summary.render()}")
        elif self.archived_summary:
            parts.append(f"# Archived Summary\n\n{self.archived_summary}")

        text = "\n\n---\n\n".join(parts)

        if self._is_small_window():
            text = self._trim_for_small_window(text)

        if len(text) > self.max_prefix_chars:
            text = text[: self.max_prefix_chars - 30] + "\n\n... (truncated)"

        self._cached_prefix = text
        self._cached_hash = self._compute_prefix_hash(text)
        self._prefix_dirty = False
        return text

    def _trim_for_small_window(self, text: str) -> str:
        lines = text.splitlines()
        kept: list[str] = []
        budget = self.window_tokens // 2
        chars_used = 0
        for line in lines:
            line_chars = len(line)
            if chars_used + line_chars > budget:
                if len(kept) < 5:
                    kept.append(line)
                break
            kept.append(line)
            chars_used += line_chars
        if len(kept) < len(lines):
            kept.append(f"\n... (window={self.window_tokens}, prefix trimmed to {chars_used} chars)")
        return "\n".join(kept)

    @property
    def prefix_hash(self) -> str:
        if self._prefix_dirty:
            self.build_prefix()
        return self._cached_hash

    @property
    def is_small_window(self) -> bool:
        return self._is_small_window()

    def build_messages(
        self,
        user_text: str,
        history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        history = history if history is not None else self.recent_history_provider()
        if user_text:
            history = list(history) + [{"role": "user", "content": user_text}]
        return history

    def build(
        self,
        user_text: str,
        history: list[dict[str, Any]] | None = None,
        runtime_block: str = "",
        cache_anchor: str = "",
    ) -> BuiltContext:
        prefix = self.build_prefix()
        messages = self.build_messages(user_text, history)
        if runtime_block and messages and messages[-1].get("role") == "user":
            last = messages[-1]
            content = last.get("content", "")
            if isinstance(content, str):
                last["content"] = content + "\n\n" + runtime_block
            else:
                last["content"] = [
                    {"type": "text", "text": runtime_block},
                    *(
                        content
                        if isinstance(content, list)
                        else [{"type": "text", "text": str(content)}]
                    ),
                ]
        return BuiltContext(
            prefix=prefix,
            messages=messages,
            runtime_block=runtime_block,
            cache_anchor=cache_anchor or self.identity[:40],
        )


def merge_runtime_into_user(messages: list[dict[str, Any]], block: str) -> None:
    """Append a runtime block to the last user message in-place.

    This is the cache-respecting pattern: the prefix never changes,
    but the user turn-tail carries short-lived metadata.
    """
    if not block or not messages:
        return
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                msg["content"] = content + "\n\n" + block
            else:
                msg["content"] = list(content) + [{"type": "text", "text": block}]
            return
