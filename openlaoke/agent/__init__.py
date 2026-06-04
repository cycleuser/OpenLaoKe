"""Cache-respecting context builder.

The :class:`ContextBuilder` assembles the LLM context each turn. The
key invariant: the cache-stable prefix (system prompt + tools + memory
index) does not mutate mid-session. Runtime metadata (pending memory
notes, active goal, runtime context) is appended to the user content
turn-tail, not the prefix.

The result is that the provider's automatic prefix cache stays warm
across many turns.
"""

from __future__ import annotations

from openlaoke.agent.context import (
    COMPACTION_SYSTEM_PROMPT,
    BuiltContext,
    CompactSummary,
    ContextBuilder,
    GoalState,
    compose_runtime_block,
    merge_runtime_into_user,
    render_channel_lines,
    render_goal_lines,
    render_time_lines,
)
from openlaoke.agent.references import resolve_references

__all__ = [
    "BuiltContext",
    "CompactSummary",
    "COMPACTION_SYSTEM_PROMPT",
    "ContextBuilder",
    "GoalState",
    "compose_runtime_block",
    "merge_runtime_into_user",
    "render_channel_lines",
    "render_goal_lines",
    "render_time_lines",
    "resolve_references",
]
