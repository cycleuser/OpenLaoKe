"""Message summarization for context compaction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.types.core_types import Message


SUMMARY_SYSTEM_PROMPT = """You are a conversation summarizer. Your task is to create concise, informative summaries of conversation history that preserve key information while reducing token count.

Guidelines:
- Preserve important decisions, conclusions, and key facts
- Keep tool use results that are relevant to ongoing work
- Maintain context needed for understanding subsequent messages
- Remove redundant or repeated information
- Focus on actionable outcomes and results
- Keep file paths, command results, and code references"""

SUMMARY_USER_PROMPT = """Summarize the following conversation messages. Preserve:
1. Key decisions and conclusions
2. Important tool results (file reads, command outputs)
3. Context needed for ongoing work
4. File paths and code references

Messages to summarize:
{messages}

Create a concise summary that captures the essential information."""


@dataclass
class SummaryConfig:
    """Configuration for message summarization."""

    max_summary_tokens: int = 4000
    summary_model: str | None = None
    preserve_recent_messages: int = 5
    preserve_tool_results: bool = True
    preserve_user_queries: bool = True
    summary_temperature: float = 0.3
    custom_prompt: str | None = None

    def get_system_prompt(self) -> str:
        if self.custom_prompt:
            return self.custom_prompt
        return SUMMARY_SYSTEM_PROMPT


@dataclass
class SummaryResult:
    """Result of summarization."""

    summary: str
    original_tokens: int
    summary_tokens: int
    messages_summarized: int
    messages_preserved: int
    compression_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.original_tokens > 0:
            self.compression_ratio = 1.0 - (self.summary_tokens / self.original_tokens)


class MessageSummarizer:
    """Generate summaries of conversation messages."""

    def __init__(
        self,
        client: MultiProviderClient,
        config: SummaryConfig | None = None,
    ) -> None:
        self.client = client
        self.config = config or SummaryConfig()

    def estimate_tokens(self, text: str) -> int:
        chars_per_token = 4
        return int(len(text) / chars_per_token)

    def estimate_message_tokens(self, message: Message) -> int:
        content = self._extract_content(message)
        return self.estimate_tokens(content)

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
        elif isinstance(message, (SystemMessage, ProgressMessage)):
            return message.content
        elif isinstance(message, AttachmentMessage):
            return f"{message.content} Files: {', '.join(message.file_paths)}"
        return ""

    def format_messages_for_summary(self, messages: list[Message]) -> str:
        formatted = []
        for i, msg in enumerate(messages):
            role = msg.role.value
            content = self._extract_content(msg)
            formatted.append(f"[{i}] {role}: {content}")
        return "\n\n".join(formatted)

    async def summarize_messages(
        self,
        messages: list[Message],
        target_tokens: int | None = None,
    ) -> SummaryResult:
        if not messages:
            return SummaryResult(
                summary="",
                original_tokens=0,
                summary_tokens=0,
                messages_summarized=0,
                messages_preserved=0,
            )

        target_tokens = target_tokens or self.config.max_summary_tokens

        original_tokens = sum(self.estimate_message_tokens(m) for m in messages)

        formatted_messages = self.format_messages_for_summary(messages)

        user_prompt = SUMMARY_USER_PROMPT.format(messages=formatted_messages)

        messages_to_send = [{"role": "user", "content": user_prompt}]

        model = self.config.summary_model
        if model is None:
            model = self.client.config.get_active_model()

        response, usage, _ = await self.client.send_message(
            system_prompt=self.config.get_system_prompt(),
            messages=messages_to_send,
            model=model,
            max_tokens=self.config.max_summary_tokens,
            temperature=self.config.summary_temperature,
        )

        summary = response.content
        summary_tokens = usage.output_tokens

        return SummaryResult(
            summary=summary,
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            messages_summarized=len(messages),
            messages_preserved=0,
        )

    def should_preserve_message(self, message: Message, index: int, total: int) -> bool:
        from openlaoke.types.core_types import AssistantMessage, SystemMessage, UserMessage

        recent_threshold = total - self.config.preserve_recent_messages
        if index >= recent_threshold:
            return True

        if isinstance(message, UserMessage) and self.config.preserve_user_queries:
            return True

        if (
            isinstance(message, AssistantMessage)
            and message.tool_uses
            and self.config.preserve_tool_results
        ):
            return True

        return isinstance(message, SystemMessage) and message.subtype in ("error", "warning")

    def split_messages(
        self,
        messages: list[Message],
    ) -> tuple[list[Message], list[Message]]:
        to_summarize = []
        to_preserve = []

        for i, msg in enumerate(messages):
            if self.should_preserve_message(msg, i, len(messages)):
                to_preserve.append(msg)
            else:
                to_summarize.append(msg)

        return to_summarize, to_preserve

    async def summarize_with_preserve(
        self,
        messages: list[Message],
    ) -> SummaryResult:
        to_summarize, to_preserve = self.split_messages(messages)

        if not to_summarize:
            preserved_tokens = sum(self.estimate_message_tokens(m) for m in to_preserve)
            return SummaryResult(
                summary="",
                original_tokens=preserved_tokens,
                summary_tokens=preserved_tokens,
                messages_summarized=0,
                messages_preserved=len(to_preserve),
            )

        result = await self.summarize_messages(to_summarize)

        preserved_tokens = sum(self.estimate_message_tokens(m) for m in to_preserve)

        return SummaryResult(
            summary=result.summary,
            original_tokens=result.original_tokens + preserved_tokens,
            summary_tokens=result.summary_tokens + preserved_tokens,
            messages_summarized=len(to_summarize),
            messages_preserved=len(to_preserve),
        )

    def create_summary_message(self, summary: str) -> Message:
        from openlaoke.types.core_types import MessageRole, SystemMessage

        return SystemMessage(
            role=MessageRole.SYSTEM,
            content=f"[Context Summary]\n{summary}",
            subtype="compact",
        )
