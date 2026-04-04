"""Error recovery mechanisms for query execution."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from openlaoke.core.query.events import (
    CompactBoundaryEvent,
    ErrorEvent,
    QueryEvent,
)
from openlaoke.types.core_types import (
    Message,
    MessageRole,
    UserMessage,
)


class RecoveryError(Exception):
    """Error that may be recoverable."""

    def __init__(
        self,
        message: str,
        error_type: str = "unknown",
        is_retryable: bool = False,
        recovery_hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.is_retryable = is_retryable
        self.recovery_hint = recovery_hint


class PromptTooLongError(RecoveryError):
    """Context exceeds model limits."""

    def __init__(self, token_count: int, max_tokens: int) -> None:
        super().__init__(
            f"Prompt too long: {token_count} tokens exceeds {max_tokens}",
            error_type="prompt_too_long",
            is_retryable=True,
            recovery_hint="compact_context",
        )
        self.token_count = token_count
        self.max_tokens = max_tokens


class MaxOutputTokensError(RecoveryError):
    """Output exceeded max_tokens limit."""

    def __init__(self) -> None:
        super().__init__(
            "Output exceeded max_tokens limit",
            error_type="max_output_tokens",
            is_retryable=True,
            recovery_hint="increase_max_tokens",
        )


class ModelFallbackError(RecoveryError):
    """Fallback to alternate model needed."""

    def __init__(self, original_model: str, fallback_model: str) -> None:
        super().__init__(
            f"Fallback from {original_model} to {fallback_model}",
            error_type="model_fallback",
            is_retryable=True,
            recovery_hint="switch_model",
        )
        self.original_model = original_model
        self.fallback_model = fallback_model


@dataclass
class RecoveryState:
    """State for recovery attempt."""

    attempt_count: int = 0
    max_attempts: int = 3
    last_error: RecoveryError | None = None
    recovery_messages: list[Message] | None = None
    escalated_max_tokens: int = 0


class RecoveryHandler:
    """Handle various recovery scenarios."""

    MAX_OUTPUT_TOKENS_RECOVERY_LIMIT = 3
    ESCALATED_MAX_TOKENS = 65536
    DEFAULT_MAX_TOKENS = 8192

    def __init__(self) -> None:
        self.state = RecoveryState()

    def reset(self) -> None:
        self.state = RecoveryState()

    async def handle_prompt_too_long(
        self,
        messages: list[Message],
        context_tokens: int,
        max_context_tokens: int,
    ) -> AsyncGenerator[QueryEvent, None]:
        """Handle context overflow via compacting."""
        self.state.attempt_count += 1
        self.state.last_error = PromptTooLongError(context_tokens, max_context_tokens)

        if self.state.attempt_count > self.state.max_attempts:
            yield ErrorEvent(
                error_message=f"Context overflow after {self.state.attempt_count} attempts",
                error_type="prompt_too_long",
                is_retryable=False,
            )
            return

        compacted = await self._compact_messages(messages, max_context_tokens)

        yield CompactBoundaryEvent(
            pre_compact_tokens=context_tokens,
            post_compact_tokens=len(json.dumps([m.to_dict() for m in compacted])) // 4,
            compacted_message_count=len(messages) - len(compacted),
        )

        self.state.recovery_messages = compacted

    async def handle_max_output_tokens(
        self,
        messages: list[Message],
        current_max_tokens: int,
    ) -> AsyncGenerator[QueryEvent, None]:
        """Handle output token limit hit."""
        self.state.attempt_count += 1
        self.state.last_error = MaxOutputTokensError()

        if self.state.attempt_count > self.MAX_OUTPUT_TOKENS_RECOVERY_LIMIT:
            yield ErrorEvent(
                error_message="Max output tokens recovery limit reached",
                error_type="max_output_tokens",
                is_retryable=False,
            )
            return

        if current_max_tokens == self.DEFAULT_MAX_TOKENS:
            self.state.escalated_max_tokens = self.ESCALATED_MAX_TOKENS
        else:
            recovery_message: Message = UserMessage(
                role=MessageRole.USER,
                content=(
                    "Output token limit hit. Resume directly - no apology, "
                    "no recap of what you were doing. Pick up mid-thought "
                    "if that is where the cut happened. Break remaining "
                    "work into smaller pieces."
                ),
            )
            messages.append(recovery_message)
            self.state.recovery_messages = messages

    async def handle_model_fallback(
        self,
        original_model: str,
        fallback_model: str,
    ) -> AsyncGenerator[QueryEvent, None]:
        """Handle model fallback scenario."""
        self.state.last_error = ModelFallbackError(original_model, fallback_model)
        yield ErrorEvent(
            error_message=f"Switching to {fallback_model} due to error with {original_model}",
            error_type="model_fallback",
            is_retryable=True,
        )

    async def _compact_messages(
        self,
        messages: list[Message],
        target_tokens: int,
    ) -> list[Message]:
        """Compact messages to target token count."""
        if not messages:
            return []

        estimated_tokens = len(json.dumps([m.to_dict() for m in messages])) // 4
        if estimated_tokens <= target_tokens:
            return messages

        keep_ratio = target_tokens / estimated_tokens
        keep_count = max(1, int(len(messages) * keep_ratio))

        preserved = messages[-keep_count:]
        return preserved

    def get_recovery_messages(self) -> list[Message] | None:
        return self.state.recovery_messages

    def get_escalated_max_tokens(self) -> int:
        return self.state.escalated_max_tokens

    def should_escalate_tokens(self) -> bool:
        return self.state.escalated_max_tokens > 0

    def can_retry(self) -> bool:
        return self.state.attempt_count < self.state.max_attempts


class TimeoutHandler:
    """Handle timeout scenarios with retry."""

    def __init__(self, base_timeout: float = 300.0, max_retries: int = 3) -> None:
        self.base_timeout = base_timeout
        self.max_retries = max_retries
        self.retry_count = 0

    async def with_timeout(
        self,
        coro: Any,
        timeout_override: float | None = None,
    ) -> Any:
        """Execute with timeout and retry on timeout error."""
        timeout = timeout_override or self.base_timeout

        while self.retry_count < self.max_retries:
            try:
                async with asyncio.timeout(timeout):
                    return await coro
            except TimeoutError:
                self.retry_count += 1
                if self.retry_count < self.max_retries:
                    await asyncio.sleep(self.retry_count * 2.0)
                    timeout = min(timeout * 1.5, 600.0)
                else:
                    raise RecoveryError(
                        f"Operation timed out after {self.retry_count} retries",
                        error_type="timeout",
                        is_retryable=False,
                    ) from None

        raise RecoveryError(
            "Max retries exceeded",
            error_type="timeout",
            is_retryable=False,
        )

    def reset(self) -> None:
        self.retry_count = 0


async def create_missing_tool_result_blocks(
    tool_use_ids: list[str],
    error_message: str,
) -> list[Message]:
    """Create error tool results for orphaned tool uses."""
    results: list[Message] = []
    for tool_id in tool_use_ids:
        msg: Message = UserMessage(
            role=MessageRole.USER,
            content=json.dumps(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": error_message,
                    "is_error": True,
                }
            ),
        )
        results.append(msg)
    return results


def categorize_error(error: Exception) -> RecoveryError:
    """Categorize an error for recovery handling."""
    error_str = str(error)

    if "prompt too long" in error_str.lower() or "context length" in error_str.lower():
        return PromptTooLongError(0, 0)

    if "max_tokens" in error_str.lower() or "output limit" in error_str.lower():
        return MaxOutputTokensError()

    if "timeout" in error_str.lower():
        return RecoveryError(
            error_str,
            error_type="timeout",
            is_retryable=True,
            recovery_hint="retry_with_delay",
        )

    if "rate limit" in error_str.lower() or "429" in error_str:
        return RecoveryError(
            error_str,
            error_type="rate_limit",
            is_retryable=True,
            recovery_hint="retry_with_backoff",
        )

    if "model" in error_str.lower() and "fallback" in error_str.lower():
        return ModelFallbackError("unknown", "unknown")

    return RecoveryError(
        error_str,
        error_type="unknown",
        is_retryable=False,
    )
