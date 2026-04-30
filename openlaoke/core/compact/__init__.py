"""Context compaction system for intelligent conversation history compression."""

from __future__ import annotations

import json
from typing import Any

from openlaoke.core.compact.compactor import (
    CompactConfig,
    CompactResult,
    CompactType,
    ContextCompactor,
)
from openlaoke.core.compact.fast_pruner import PruneResult, extract_keywords, fast_prune
from openlaoke.core.compact.strategies import (
    AutoCompactStrategy,
    MicroCompactStrategy,
    ReactiveCompactStrategy,
    SnipCompactStrategy,
)
from openlaoke.core.compact.summarizer import MessageSummarizer, SummaryConfig
from openlaoke.core.compact.token_budget import Allocation, TokenBudget, TokenUsageTracker


def extract_content(message: Any) -> str:
    from openlaoke.types.core_types import (
        AssistantMessage,
        AttachmentMessage,
        ProgressMessage,
        SystemMessage,
        UserMessage,
    )

    if isinstance(message, UserMessage):
        return message.content
    if isinstance(message, AssistantMessage):
        parts = [message.content]
        for tu in message.tool_uses:
            parts.append(f"Tool: {tu.name}")
            parts.append(json.dumps(tu.input))
        return "\n".join(parts)
    if isinstance(message, SystemMessage):
        return message.content
    if isinstance(message, ProgressMessage):
        return ""
    if isinstance(message, AttachmentMessage):
        return message.content if hasattr(message, "content") else ""
    if hasattr(message, "content"):
        return str(message.content)
    return ""


__all__ = [
    "ContextCompactor",
    "CompactConfig",
    "CompactResult",
    "CompactType",
    "TokenBudget",
    "Allocation",
    "TokenUsageTracker",
    "AutoCompactStrategy",
    "ReactiveCompactStrategy",
    "SnipCompactStrategy",
    "MicroCompactStrategy",
    "MessageSummarizer",
    "SummaryConfig",
    "fast_prune",
    "extract_keywords",
    "PruneResult",
    "extract_content",
]
