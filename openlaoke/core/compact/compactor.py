"""Context compaction system for intelligent conversation history compression."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from openlaoke.core.compact.strategies import (
    AutoCompactStrategy,
    CompactStrategy,
    MicroCompactStrategy,
    ReactiveCompactStrategy,
    SnipCompactStrategy,
)
from openlaoke.core.compact.token_budget import Allocation, TokenBudget

if TYPE_CHECKING:
    from openlaoke.core.compact.summarizer import MessageSummarizer
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.types.core_types import Message, TokenUsage


class CompactType(StrEnum):
    """Types of context compaction."""

    AUTO = "auto"
    REACTIVE = "reactive"
    SNIP = "snip"
    MICRO = "micro"
    FULL = "full"


@dataclass
class CompactConfig:
    """Configuration for context compaction."""

    enabled: bool = True
    default_type: CompactType = CompactType.AUTO
    trigger_threshold: float = 0.80
    keep_fraction: float = 0.30
    max_summary_tokens: int = 4000
    preserve_recent: int = 10
    max_tool_result_tokens: int = 5000
    auto_compact_on_overflow: bool = True
    use_summarization: bool = True
    summary_model: str | None = None

    def get_token_budget(self, max_input: int = 200000, max_output: int = 8192) -> TokenBudget:
        return TokenBudget(
            max_input_tokens=max_input,
            max_output_tokens=max_output,
            trigger_threshold=self.trigger_threshold,
            keep_fraction=self.keep_fraction,
        )


@dataclass
class CompactResult:
    """Result of context compaction."""

    messages: list[Message]
    tokens_before: int
    tokens_after: int
    messages_removed: int
    messages_preserved: int
    compact_type: CompactType
    summary: str | None = None
    compression_ratio: float = 0.0
    allocation: Allocation | None = None

    def __post_init__(self) -> None:
        if self.tokens_before > 0:
            self.compression_ratio = 1.0 - (self.tokens_after / self.tokens_before)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "messages_removed": self.messages_removed,
            "messages_preserved": self.messages_preserved,
            "compact_type": self.compact_type.value,
            "compression_ratio": self.compression_ratio,
            "summary": self.summary,
        }


class ContextCompactor:
    """Context compaction system for intelligent conversation history compression."""

    def __init__(
        self,
        config: CompactConfig,
        client: MultiProviderClient | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self._summarizer: MessageSummarizer | None = None
        self._budget: TokenBudget | None = None

        self.strategies: dict[CompactType, CompactStrategy] = {
            CompactType.AUTO: AutoCompactStrategy(config.trigger_threshold),
            CompactType.REACTIVE: ReactiveCompactStrategy(config.max_tool_result_tokens),
            CompactType.SNIP: SnipCompactStrategy(config.preserve_recent),
            CompactType.MICRO: MicroCompactStrategy(),
        }

        if client and config.use_summarization:
            from openlaoke.core.compact.summarizer import MessageSummarizer, SummaryConfig

            summary_config = SummaryConfig(
                max_summary_tokens=config.max_summary_tokens,
                summary_model=config.summary_model,
                preserve_recent_messages=config.preserve_recent,
            )
            self._summarizer = MessageSummarizer(client, summary_config)

    def set_budget(self, budget: TokenBudget) -> None:
        self._budget = budget

    def get_budget(self) -> TokenBudget:
        if self._budget is None:
            self._budget = self.config.get_token_budget()
        return self._budget

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

    def should_compact(self, messages: list[Message], budget: TokenBudget | None = None) -> bool:
        budget = budget or self.get_budget()
        current_tokens = self.estimate_tokens(messages)
        return budget.check_overflow(current_tokens)

    def allocate_budget(
        self, messages: list[Message], budget: TokenBudget | None = None
    ) -> Allocation:
        budget = budget or self.get_budget()
        current_tokens = self.estimate_tokens(messages)
        return budget.allocate(system_tokens=current_tokens // 10)

    async def compact(
        self,
        messages: list[Message],
        budget: TokenBudget | None = None,
        compact_type: CompactType | None = None,
    ) -> CompactResult:
        budget = budget or self.get_budget()
        compact_type = compact_type or self.config.default_type

        strategy = self.strategies.get(compact_type)
        if strategy is None:
            strategy = self.strategies[CompactType.AUTO]

        result = await strategy.compact(messages, budget, self._summarizer)

        allocation = self.allocate_budget(result.messages, budget)

        return CompactResult(
            messages=result.messages,
            tokens_before=result.tokens_before,
            tokens_after=result.tokens_after,
            messages_removed=result.messages_removed,
            messages_preserved=result.messages_preserved,
            compact_type=compact_type,
            summary=result.summary,
            allocation=allocation,
        )

    async def auto_compact(self, messages: list[Message]) -> CompactResult:
        if not self.should_compact(messages):
            tokens = self.estimate_tokens(messages)
            return CompactResult(
                messages=messages,
                tokens_before=tokens,
                tokens_after=tokens,
                messages_removed=0,
                messages_preserved=len(messages),
                compact_type=CompactType.AUTO,
            )

        return await self.compact(messages, compact_type=CompactType.AUTO)

    async def reactive_compact(self, messages: list[Message]) -> CompactResult:
        return await self.compact(messages, compact_type=CompactType.REACTIVE)

    async def snip_compact(self, messages: list[Message]) -> CompactResult:
        return await self.compact(messages, compact_type=CompactType.SNIP)

    async def micro_compact(self, messages: list[Message]) -> CompactResult:
        return await self.compact(messages, compact_type=CompactType.MICRO)

    async def full_compact(self, messages: list[Message]) -> CompactResult:
        budget = self.get_budget()

        result = await self.micro_compact(messages)
        if result.tokens_after <= budget.get_available_tokens():
            return result

        result = await self.snip_compact(result.messages)
        if result.tokens_after <= budget.get_available_tokens():
            return result

        result = await self.auto_compact(result.messages)
        return result

    def get_compaction_stats(self, messages: list[Message]) -> dict[str, Any]:
        budget = self.get_budget()
        current_tokens = self.estimate_tokens(messages)
        available = budget.get_available_tokens()
        threshold = budget.get_trigger_threshold()

        return {
            "current_tokens": current_tokens,
            "available_tokens": available,
            "threshold_tokens": threshold,
            "message_count": len(messages),
            "overflow": current_tokens > threshold,
            "overflow_amount": max(0, current_tokens - available),
            "recommended_action": self._get_recommended_action(
                current_tokens, threshold, available
            ),
        }

    def _get_recommended_action(self, current: int, threshold: int, available: int) -> str:
        if current <= threshold:
            return "none"
        elif current <= threshold * 1.2:
            return "micro"
        elif current <= available * 0.8:
            return "snip"
        else:
            return "auto"

    def track_usage(self, usage: TokenUsage) -> None:
        budget = self.get_budget()
        budget.update_cache_tokens(usage.cache_read_tokens, usage.cache_creation_tokens)

    def can_add_message(self, messages: list[Message], new_message: Message) -> bool:
        budget = self.get_budget()
        current_tokens = self.estimate_tokens(messages)
        new_tokens = self.estimate_tokens([new_message])
        available = budget.get_available_tokens()

        return current_tokens + new_tokens < available
