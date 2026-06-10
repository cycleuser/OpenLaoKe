"""Message summarization for context compaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.types.core_types import Message


SUMMARY_SYSTEM_PROMPT = """You are compacting the earlier part of a coding agent's conversation to save context.
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

SUMMARY_USER_PROMPT = """Messages to compact:
{messages}"""

# Inline compaction prompt — injected into the main conversation flow
# so the compression happens as part of the next normal API call,
# reusing the existing prompt cache (Insert-then-Compress pattern).
INLINE_COMPACTION_PREFIX = """[SYSTEM INSTRUCTION — COMPACT CONTEXT]
The conversation above has grown large. Before continuing, you MUST:

1. Review the conversation from the beginning
2. Extract the key information into a compact summary under these headings:
## Goal — user's request and intent
## Decisions & rationale — key choices made and why
## Files & code — files read/modified, with specific paths and facts
## Commands & outcomes — what was run, what succeeded/failed
## Errors & fixes — problems and resolutions
## Pending & next step — what remains to do

3. Output ONLY the summary. Do NOT continue the conversation until the
   summary is complete. After the summary, the original old messages will
   be dropped and you will resume from the summary alone.

--- BEGIN COMPACTION ---"""

INLINE_COMPACTION_CLOSING = """--- END COMPACTION ---

[The conversation history has been compacted. Continue from the summary above.]"""


def build_inline_compaction_messages(
    messages: list[dict[str, Any]],
    target_compact_count: int = 0,
) -> list[dict[str, Any]]:
    """Insert compaction instruction into the message flow.

    Instead of making a separate LLM call (which always cache-misses),
    we inject the compaction prompt as a user message into the main
    conversation stream. The next normal request will include the
    compaction step, reusing the existing prompt cache.

    Returns modified message list with compaction instruction injected.
    The caller should then:
    1. Send this to the model (cache hit on everything before the injection)
    2. Parse the compaction output from the model's response
    3. Replace old messages with the compacted summary
    """
    if not messages:
        return messages

    result = list(messages)

    # Determine which messages to keep (recent) vs compact (old)
    keep_count = max(4, len(messages) // 4)
    if target_compact_count > 0:
        compact_count = min(target_compact_count, len(messages) - keep_count)
    else:
        compact_count = max(0, len(messages) - keep_count)

    if compact_count <= 0:
        return result

    # Inject compaction instruction
    result.insert(
        -keep_count if keep_count < len(result) else len(result),
        {
            "role": "user",
            "content": INLINE_COMPACTION_PREFIX,
            "system_injected": True,
        },
    )

    return result



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
        from openlaoke.core.compact import extract_content

        return extract_content(message)

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
