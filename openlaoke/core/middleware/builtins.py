"""Built-in middleware implementations."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

from openlaoke.core.middleware.base import (
    ErrorEvent,
    Event,
    Middleware,
    NextMiddleware,
    ProgressEvent,
    SyncMiddleware,
)
from openlaoke.core.middleware.context import MiddlewareContext
from openlaoke.types.core_types import AssistantMessage, ToolUseBlock, UserMessage

logger = logging.getLogger(__name__)


class ThreadDataMiddleware(SyncMiddleware):
    """Middleware for managing thread-specific data directories.

    Creates and manages workspace, uploads, and outputs directories
    for each session.
    """

    def __init__(self, base_dir: str | None = None, lazy_init: bool = True) -> None:
        self.base_dir = base_dir
        self.lazy_init = lazy_init
        self._initialized_sessions: set[str] = set()

    def process(self, context: MiddlewareContext) -> list[Event]:
        session_id = context.session_id or context.state.session_id
        if not session_id:
            return []

        if session_id in self._initialized_sessions:
            return []

        base = self.base_dir or os.path.join(context.state.cwd, ".openlaoke")
        thread_dir = os.path.join(base, "sessions", session_id)

        dirs = {
            "workspace": os.path.join(thread_dir, "workspace"),
            "uploads": os.path.join(thread_dir, "uploads"),
            "outputs": os.path.join(thread_dir, "outputs"),
        }

        if not self.lazy_init:
            for dir_path in dirs.values():
                os.makedirs(dir_path, exist_ok=True)
            logger.debug(f"Created thread directories for session {session_id}")

        context.set_metadata("thread_data", dirs)
        self._initialized_sessions.add(session_id)
        return []


class UploadsMiddleware(SyncMiddleware):
    """Middleware for handling file uploads."""

    def process(self, context: MiddlewareContext) -> list[Event]:
        for message in context.messages:
            if isinstance(message, UserMessage) and message.attachments:
                attachments_info = []
                for path in message.attachments:
                    if os.path.exists(path):
                        size = os.path.getsize(path)
                        attachments_info.append(
                            {
                                "path": path,
                                "size": size,
                                "name": os.path.basename(path),
                            }
                        )
                if attachments_info:
                    context.set_metadata("uploads", attachments_info)
                    logger.debug(f"Processed {len(attachments_info)} attachments")
        return []


class SandboxMiddleware(Middleware):
    """Middleware for sandbox environment management."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._sandbox_id: str | None = None

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        if self.enabled:
            self._sandbox_id = f"sandbox_{context.session_id}"
            context.set_metadata("sandbox_id", self._sandbox_id)
            logger.debug(f"Acquired sandbox: {self._sandbox_id}")

        try:
            async for event in next_middleware(context):
                yield event
        finally:
            if self._sandbox_id:
                logger.debug(f"Released sandbox: {self._sandbox_id}")
                self._sandbox_id = None


class DanglingToolCallMiddleware(SyncMiddleware):
    """Middleware for handling dangling tool calls."""

    def process(self, context: MiddlewareContext) -> list[Event]:
        pending_calls: list[ToolUseBlock] = []

        for message in reversed(context.messages):
            if isinstance(message, AssistantMessage):
                if message.tool_uses:
                    pending_calls.extend(message.tool_uses)
                break

        if pending_calls:
            context.set_metadata("pending_tool_calls", pending_calls)
            logger.debug(f"Found {len(pending_calls)} pending tool calls")
        return []


class GuardrailMiddleware(Middleware):
    """Middleware for safety guardrails."""

    def __init__(
        self,
        blocked_tools: list[str] | None = None,
        blocked_patterns: list[str] | None = None,
    ) -> None:
        self.blocked_tools = set(blocked_tools or [])
        self.blocked_patterns = blocked_patterns or []

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        if context.current_tool:
            tool_name = context.current_tool.name
            if tool_name in self.blocked_tools:
                logger.warning(f"Blocked tool call: {tool_name}")
                yield ErrorEvent(
                    error=f"Tool '{tool_name}' is blocked by guardrail policy",
                    error_type="guardrail_blocked",
                )
                context.abort("guardrail_blocked")
                return

        async for event in next_middleware(context):
            if self._should_block_event(event):
                logger.warning(f"Blocked event: {event.type}")
                continue
            yield event

    def _should_block_event(self, event: Event) -> bool:
        return any(pattern in str(event.data) for pattern in self.blocked_patterns)


class SummarizationMiddleware(SyncMiddleware):
    """Middleware for context compression."""

    def __init__(
        self,
        max_messages: int = 100,
        summarize_threshold: int = 80,
    ) -> None:
        self.max_messages = max_messages
        self.summarize_threshold = summarize_threshold

    def process(self, context: MiddlewareContext) -> list[Event]:
        message_count = len(context.messages)

        if message_count > self.summarize_threshold:
            context.set_metadata("needs_summarization", True)
            context.set_metadata(
                "summarization_stats",
                {
                    "total_messages": message_count,
                    "threshold": self.summarize_threshold,
                    "max_messages": self.max_messages,
                },
            )
            logger.debug(f"Marked for summarization: {message_count} messages")
        return []


class TodoListMiddleware(SyncMiddleware):
    """Middleware for task tracking."""

    def __init__(self) -> None:
        self._todos: dict[str, list[dict[str, Any]]] = {}

    def process(self, context: MiddlewareContext) -> list[Event]:
        todos = []
        todo_pattern = re.compile(
            r"(?:TODO|FIXME|XXX|HACK):\s*(.+)",
            re.IGNORECASE,
        )

        for message in context.messages:
            if isinstance(message, (UserMessage, AssistantMessage)):
                content = message.content
                matches = todo_pattern.findall(content)
                for match in matches:
                    todos.append(
                        {
                            "text": match.strip(),
                            "role": message.role.value,
                            "timestamp": message.timestamp,
                        }
                    )

        if todos:
            self._todos[context.session_id] = todos
            context.set_metadata("todos", todos)
            logger.debug(f"Found {len(todos)} TODO items")
        return []


class TitleMiddleware(SyncMiddleware):
    """Middleware for generating conversation titles."""

    def __init__(self, min_messages: int = 2) -> None:
        self.min_messages = min_messages
        self._titles: dict[str, str] = {}

    def process(self, context: MiddlewareContext) -> list[Event]:
        if len(context.messages) < self.min_messages:
            return []

        existing_title = context.get_metadata("title")
        if existing_title:
            return []

        first_user_message = None
        for message in context.messages:
            if isinstance(message, UserMessage) and message.content.strip():
                first_user_message = message.content
                break

        if first_user_message:
            title = self._generate_title(first_user_message)
            self._titles[context.session_id] = title
            context.set_metadata("title", title)
            logger.debug(f"Generated title: {title}")
        return []

    def _generate_title(self, content: str) -> str:
        title = content.split("\n")[0].strip()
        title = re.sub(r"[^\w\s-]", "", title)
        title = " ".join(title.split()[:10])
        return title[:100] if len(title) > 100 else title


class MemoryMiddleware(SyncMiddleware):
    """Middleware for memory queue management."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._queue: list[dict[str, Any]] = []

    def process(self, context: MiddlewareContext) -> list[Event]:
        if not self.enabled:
            return []

        if len(context.messages) < 2:
            return []

        memory_entry = {
            "session_id": context.session_id,
            "message_count": len(context.messages),
            "timestamp": time.time(),
            "metadata": context.metadata,
        }

        self._queue.append(memory_entry)
        context.set_metadata("memory_queued", True)
        logger.debug("Queued conversation for memory update")
        return []


class ViewImageMiddleware(SyncMiddleware):
    """Middleware for image injection."""

    def process(self, context: MiddlewareContext) -> list[Event]:
        import base64

        images_info = []

        for message in context.messages:
            if isinstance(message, UserMessage) and message.images:
                for img_path in message.images:
                    if os.path.exists(img_path):
                        try:
                            with open(img_path, "rb") as f:
                                img_data = base64.b64encode(f.read()).decode()
                            images_info.append(
                                {
                                    "path": img_path,
                                    "size": os.path.getsize(img_path),
                                    "data_preview": img_data[:100] + "...",
                                }
                            )
                        except Exception as e:
                            logger.warning(f"Failed to process image {img_path}: {e}")

        if images_info:
            context.set_metadata("images", images_info)
            logger.debug(f"Processed {len(images_info)} images")
        return []


class SubagentLimitMiddleware(Middleware):
    """Middleware for concurrency limiting."""

    def __init__(self, max_concurrent: int = 5) -> None:
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        async with self._semaphore:
            self._active_count += 1
            context.set_metadata("subagent_slot", self._active_count)
            logger.debug(f"Subagent slot acquired: {self._active_count}/{self.max_concurrent}")

            try:
                async for event in next_middleware(context):
                    yield event
            finally:
                self._active_count -= 1
                logger.debug(f"Subagent slot released: {self._active_count}/{self.max_concurrent}")


class ClarificationMiddleware(Middleware):
    """Middleware for clarification requests."""

    def __init__(
        self,
        clarification_threshold: float = 0.5,
        auto_clarify: bool = False,
    ) -> None:
        self.clarification_threshold = clarification_threshold
        self.auto_clarify = auto_clarify

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        clarification_needed = context.get_metadata("clarification_needed", False)

        if clarification_needed:
            question = context.get_metadata(
                "clarification_question", "Please provide more details."
            )
            yield ProgressEvent(message=f"Clarification needed: {question}")

        async for event in next_middleware(context):
            yield event

    def request_clarification(
        self,
        context: MiddlewareContext,
        question: str,
    ) -> None:
        context.set_metadata("clarification_needed", True)
        context.set_metadata("clarification_question", question)


class LoggingMiddleware(Middleware):
    """Middleware for request/response logging."""

    def __init__(self, log_level: int = logging.DEBUG) -> None:
        self.log_level = log_level

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        logger.log(self.log_level, f"[{context.session_id}] Processing request")

        event_count = 0
        start_time = time.time()

        async for event in next_middleware(context):
            event_count += 1
            logger.log(
                self.log_level,
                f"[{context.session_id}] Event: {event.type}",
            )
            yield event

        elapsed = time.time() - start_time
        logger.log(
            self.log_level,
            f"[{context.session_id}] Completed: {event_count} events in {elapsed:.3f}s",
        )


class ErrorHandlingMiddleware(Middleware):
    """Middleware for centralized error handling."""

    async def __call__(
        self,
        context: MiddlewareContext,
        next_middleware: NextMiddleware,
    ) -> AsyncGenerator[Event, None]:
        try:
            async for event in next_middleware(context):
                yield event
        except asyncio.CancelledError:
            logger.info(f"Request cancelled: {context.session_id}")
            yield ErrorEvent(error="Request cancelled", error_type="cancelled")
        except Exception as e:
            logger.exception(f"Error in middleware chain: {e}")
            context.error = e
            yield ErrorEvent(error=str(e), error_type=type(e).__name__)
