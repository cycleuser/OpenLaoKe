"""Compaction strategies for different compression needs."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.compact.summarizer import MessageSummarizer
    from openlaoke.core.compact.token_budget import TokenBudget
    from openlaoke.types.core_types import Message


@dataclass
class StrategyResult:
    """Result of a compaction strategy."""

    messages: list[Message]
    tokens_before: int
    tokens_after: int
    messages_removed: int
    messages_preserved: int
    summary: str | None = None
    compression_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.tokens_before > 0:
            self.compression_ratio = 1.0 - (self.tokens_after / self.tokens_before)


class CompactStrategy(ABC):
    """Base class for compaction strategies."""

    @abstractmethod
    async def compact(
        self,
        messages: list[Message],
        budget: TokenBudget,
        summarizer: MessageSummarizer | None = None,
    ) -> StrategyResult:
        """Execute the compaction strategy."""

    @abstractmethod
    def should_apply(self, messages: list[Message], budget: TokenBudget) -> bool:
        """Check if this strategy should be applied."""

    def estimate_tokens(self, messages: list[Message]) -> int:
        total = 0
        for msg in messages:
            content = self._extract_content(msg)
            total += int(len(content) / 4)
        return total

    def _extract_content(self, message: Message) -> str:
        from openlaoke.types.core_types import (
            AssistantMessage,
            AttachmentMessage,
            ProgressMessage,
            SystemMessage,
            UserMessage,
        )

        if isinstance(message, UserMessage):
            return message.content
        elif isinstance(message, AssistantMessage):
            parts = [message.content]
            for tu in message.tool_uses:
                parts.append(f"Tool: {tu.name}")
                parts.append(json.dumps(tu.input))
            return "\n".join(parts)
        elif isinstance(message, SystemMessage):
            return message.content
        elif isinstance(message, ProgressMessage):
            return ""
        elif isinstance(message, AttachmentMessage):
            return f"{message.content} Files: {', '.join(message.file_paths)}"
        return ""

    def get_message_importance(self, message: Message, index: int, total: int) -> float:
        from openlaoke.types.core_types import AssistantMessage, SystemMessage, UserMessage

        score = 0.0

        recency_score = index / total
        score += recency_score * 0.5

        if isinstance(message, UserMessage):
            score += 0.3
            if len(message.content) < 500:
                score += 0.1

        elif isinstance(message, AssistantMessage):
            score += 0.2
            if message.tool_uses:
                score += 0.2
            if message.stop_reason == "tool_use":
                score += 0.1

        elif isinstance(message, SystemMessage):
            if message.subtype in ("error", "warning"):
                score += 0.4
            elif message.subtype == "compact":
                score += 0.1
            else:
                score += 0.1

        return min(1.0, score)


class AutoCompactStrategy(CompactStrategy):
    """Automatic compaction triggered by token threshold."""

    def __init__(self, threshold_fraction: float = 0.80) -> None:
        self.threshold_fraction = threshold_fraction

    def should_apply(self, messages: list[Message], budget: TokenBudget) -> bool:
        current_tokens = self.estimate_tokens(messages)
        return budget.check_overflow(current_tokens)

    async def compact(
        self,
        messages: list[Message],
        budget: TokenBudget,
        summarizer: MessageSummarizer | None = None,
    ) -> StrategyResult:
        tokens_before = self.estimate_tokens(messages)

        if not self.should_apply(messages, budget):
            return StrategyResult(
                messages=messages,
                tokens_before=tokens_before,
                tokens_after=tokens_before,
                messages_removed=0,
                messages_preserved=len(messages),
            )

        if summarizer:
            result = await summarizer.summarize_with_preserve(messages)
            summary_msg = summarizer.create_summary_message(result.summary)

            to_preserve, _ = summarizer.split_messages(messages)
            new_messages = [summary_msg] + to_preserve

            tokens_after = self.estimate_tokens(new_messages)

            return StrategyResult(
                messages=new_messages,
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                messages_removed=len(messages) - len(to_preserve),
                messages_preserved=len(to_preserve),
                summary=result.summary,
            )

        target_tokens = budget.get_target_tokens(tokens_before)

        new_messages = self._trim_by_importance(messages, target_tokens)
        tokens_after = self.estimate_tokens(new_messages)

        return StrategyResult(
            messages=new_messages,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            messages_removed=len(messages) - len(new_messages),
            messages_preserved=len(new_messages),
        )

    def _trim_by_importance(self, messages: list[Message], target_tokens: int) -> list[Message]:
        if not messages:
            return messages

        scored = []
        for i, msg in enumerate(messages):
            score = self.get_message_importance(msg, i, len(messages))
            scored.append((score, i, msg))

        scored.sort(key=lambda x: x[0], reverse=True)

        selected = []
        current_tokens = 0

        for _score, idx, msg in scored:
            msg_tokens = self.estimate_tokens([msg])
            if current_tokens + msg_tokens <= target_tokens:
                selected.append((idx, msg))
                current_tokens += msg_tokens

        selected.sort(key=lambda x: x[0])

        return [msg for _, msg in selected]


class ReactiveCompactStrategy(CompactStrategy):
    """Reactive compaction for real-time tool result compression."""

    def __init__(self, max_tool_result_tokens: int = 5000) -> None:
        self.max_tool_result_tokens = max_tool_result_tokens

    def should_apply(self, messages: list[Message], budget: TokenBudget) -> bool:
        return True

    async def compact(
        self,
        messages: list[Message],
        budget: TokenBudget,
        summarizer: MessageSummarizer | None = None,
    ) -> StrategyResult:
        tokens_before = self.estimate_tokens(messages)

        new_messages = self._compress_tool_results(messages)
        tokens_after = self.estimate_tokens(new_messages)

        return StrategyResult(
            messages=new_messages,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            messages_removed=len(messages) - len(new_messages),
            messages_preserved=len(new_messages),
        )

    def _compress_tool_results(self, messages: list[Message]) -> list[Message]:
        from openlaoke.types.core_types import (
            AssistantMessage,
            SystemMessage,
        )

        result: list[Message] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                content = msg.content
                if len(content) > self.max_tool_result_tokens:
                    truncated = self._truncate_tool_result(content)
                    result.append(
                        SystemMessage(
                            role=msg.role,
                            content=truncated,
                            subtype=msg.subtype,
                            timestamp=msg.timestamp,
                        )
                    )
                else:
                    result.append(msg)
            elif isinstance(msg, AssistantMessage):
                result.append(msg)
            else:
                result.append(msg)

        return result

    def _truncate_tool_result(self, content: str) -> str:
        max_len = self.max_tool_result_tokens * 4

        if len(content) <= max_len:
            return content

        lines = content.split("\n")
        if len(lines) > 100:
            head = "\n".join(lines[:50])
            tail = "\n".join(lines[-20:])
            return f"{head}\n... [truncated {len(lines) - 70} lines] ...\n{tail}"

        return content[:max_len] + "\n... [truncated] ..."


class SnipCompactStrategy(CompactStrategy):
    """Snip compaction removing older messages."""

    def __init__(self, keep_recent: int = 20) -> None:
        self.keep_recent = keep_recent

    def should_apply(self, messages: list[Message], budget: TokenBudget) -> bool:
        return len(messages) > self.keep_recent

    async def compact(
        self,
        messages: list[Message],
        budget: TokenBudget,
        summarizer: MessageSummarizer | None = None,
    ) -> StrategyResult:
        tokens_before = self.estimate_tokens(messages)

        if not self.should_apply(messages, budget):
            return StrategyResult(
                messages=messages,
                tokens_before=tokens_before,
                tokens_after=tokens_before,
                messages_removed=0,
                messages_preserved=len(messages),
            )

        new_messages = self._snip_messages(messages)
        tokens_after = self.estimate_tokens(new_messages)

        return StrategyResult(
            messages=new_messages,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            messages_removed=len(messages) - len(new_messages),
            messages_preserved=len(new_messages),
        )

    def _snip_messages(self, messages: list[Message]) -> list[Message]:
        if len(messages) <= self.keep_recent:
            return messages

        return messages[-self.keep_recent :]


class MicroCompactStrategy(CompactStrategy):
    """Micro compaction removing only redundant content."""

    def __init__(self, dedupe_threshold: int = 200) -> None:
        self.dedupe_threshold = dedupe_threshold

    def should_apply(self, messages: list[Message], budget: TokenBudget) -> bool:
        current_tokens = self.estimate_tokens(messages)
        return current_tokens > budget.get_available_tokens() * 0.5

    async def compact(
        self,
        messages: list[Message],
        budget: TokenBudget,
        summarizer: MessageSummarizer | None = None,
    ) -> StrategyResult:
        tokens_before = self.estimate_tokens(messages)

        new_messages = self._dedupe_messages(messages)
        tokens_after = self.estimate_tokens(new_messages)

        return StrategyResult(
            messages=new_messages,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            messages_removed=len(messages) - len(new_messages),
            messages_preserved=len(new_messages),
        )

    def _dedupe_messages(self, messages: list[Message]) -> list[Message]:
        if len(messages) < 2:
            return messages

        result: list[Message] = []
        seen_content: dict[str, int] = {}

        for msg in messages:
            content = self._extract_content(msg)
            content_hash = content[: self.dedupe_threshold]

            if content_hash in seen_content:
                prev_idx = seen_content[content_hash]
                prev_msg = result[prev_idx]

                if self._is_same_message_type(msg, prev_msg):
                    continue

            seen_content[content_hash] = len(result)
            result.append(msg)

        return result

    def _is_same_message_type(self, msg1: Message, msg2: Message) -> bool:
        from openlaoke.types.core_types import SystemMessage

        if msg1.role != msg2.role:
            return False

        if (
            isinstance(msg1, SystemMessage)
            and isinstance(msg2, SystemMessage)
            and msg1.subtype == msg2.subtype
        ):
            content1 = msg1.content[: self.dedupe_threshold]
            content2 = msg2.content[: self.dedupe_threshold]
            if content1 == content2:
                return True

        return False
