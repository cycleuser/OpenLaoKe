"""AsyncGenerator QueryEngine - stream-based query execution."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openlaoke.core.query.context import QueryContext, create_query_context
from openlaoke.core.query.events import (
    ContentDeltaEvent,
    ErrorEvent,
    MessageEndEvent,
    MessageStartEvent,
    QueryEvent,
    QueryEventType,
    QueryResult,
    StopReason,
    StreamRequestStartEvent,
    ToolProgressEvent,
    ToolResultEvent,
    ToolUseEvent,
    TurnEndEvent,
)
from openlaoke.core.query.recovery import (
    MaxOutputTokensError,
    PromptTooLongError,
    RecoveryError,
    RecoveryHandler,
    TimeoutHandler,
    categorize_error,
)
from openlaoke.core.query.stream import StreamProcessor
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    Message,
    MessageRole,
    PermissionResult,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

if TYPE_CHECKING:
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.core.state import AppState


class QueryEngine:
    """AsyncGenerator查询引擎 - 流式处理用户请求。

    Core implementation of the agentic loop using AsyncGenerator pattern.
    Handles streaming responses, tool execution, context management,
    and error recovery in a single unified flow.
    """

    def __init__(
        self,
        app_state: AppState,
        tool_registry: ToolRegistry,
        api_client: MultiProviderClient,
        system_prompt: str = "",
        model: str = "gemma3:1b",
        fallback_model: str | None = None,
        max_tokens: int = 8192,
        max_turns: int | None = None,
        max_budget_usd: float | None = None,
        temperature: float = 1.0,
        thinking_budget: int = 0,
        verbose: bool = False,
    ) -> None:
        self.app_state = app_state
        self.tool_registry = tool_registry
        self.api_client = api_client
        self.system_prompt = system_prompt
        self.model = model
        self.fallback_model = fallback_model
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd
        self.temperature = temperature
        self.thinking_budget = thinking_budget
        self.verbose = verbose

        self._abort_event = asyncio.Event()
        self._recovery_handler = RecoveryHandler()
        self._timeout_handler = TimeoutHandler()
        self._stream_processor = StreamProcessor()
        self._total_usage = TokenUsage()
        self._total_cost = CostInfo()
        self._turn_count = 0
        self._messages: list[Message] = []

    async def query(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[QueryEvent, None]:
        """流式查询循环 - 主入口点。

        Yields QueryEvent for each step in the agentic loop:
        - MESSAGE_START: when API call begins
        - CONTENT_DELTA: for streaming text
        - TOOL_USE: when tool call detected
        - TOOL_RESULT: when tool execution completes
        - MESSAGE_END: when assistant message complete
        - TURN_END: when turn ends (may continue)
        - ERROR: for recoverable/terminal errors
        """
        self._messages = list(messages)
        tools = tools or self.tool_registry.get_all()
        tool_schemas = self._build_tool_schemas(tools)

        context = create_query_context(
            app_state=self.app_state,
            tool_registry=self.tool_registry,
            messages=self._messages,
            system_prompt=self.system_prompt,
            model=self.model,
            fallback_model=self.fallback_model,
            max_tokens=self.max_tokens,
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            abort_controller=self._abort_event,
        )

        while True:
            yield StreamRequestStartEvent()

            if context.is_aborted():
                yield ErrorEvent(
                    error_message="Query aborted by user",
                    error_type="aborted",
                    is_retryable=False,
                )
                return

            async for event in self._prepare_context(context):
                yield event

            tool_calls: list[ToolUseBlock] = []
            assistant_msg: AssistantMessage | None = None

            try:
                async for event in self._sampling(
                    context,
                    tool_schemas,
                ):
                    yield event
                    if event.type == QueryEventType.TOOL_USE:
                        tool_calls.append(
                            ToolUseBlock(
                                id=event.data.get("tool_use_id", ""),
                                name=event.data.get("tool_name", ""),
                                input=event.data.get("tool_input", {}),
                            )
                        )
                    if event.type == QueryEventType.MESSAGE_END:
                        msg = event.data
                        if msg and isinstance(msg, dict):
                            role = msg.get("role")
                            if role == "assistant":
                                assistant_msg = AssistantMessage(
                                    role=MessageRole.ASSISTANT,
                                    content=msg.get("content", ""),
                                    tool_uses=tool_calls,
                                    stop_reason=msg.get("stop_reason"),
                                )
                                context.accumulate_usage(TokenUsage())
                                context.accumulate_cost(CostInfo())

            except RecoveryError as e:
                async for event in self._handle_recovery(context, e):
                    yield event
                if context.should_continue():
                    continue
                return

            except Exception as e:
                categorized = categorize_error(e)
                yield ErrorEvent(
                    error_message=str(e),
                    error_type=categorized.error_type,
                    is_retryable=categorized.is_retryable,
                )
                if categorized.is_retryable and self._recovery_handler.can_retry():
                    continue
                return

            if tool_calls:
                async for event in self._run_tools(context, tool_calls, tools):
                    yield event
                    if event.type == QueryEventType.TOOL_RESULT:
                        result_block = event.data.get("result")
                        if result_block:
                            tool_result_msg: Message = UserMessage(
                                role=MessageRole.USER,
                                content=json.dumps(result_block),
                            )
                            context.messages.append(tool_result_msg)

            self._turn_count += 1
            yield TurnEndEvent(
                turn_count=self._turn_count,
                total_usage=context.turn_state.accumulated_usage,
                total_cost=context.turn_state.accumulated_cost,
                stop_reason=self._determine_stop_reason(context, assistant_msg),
            )

            if self._should_terminate(context, assistant_msg):
                return

            context.clear_turn_state()

    async def _prepare_context(
        self,
        context: QueryContext,
    ) -> AsyncGenerator[QueryEvent, None]:
        """Prepare messages and context for API call."""
        messages_for_api = self._format_messages_for_api(context.messages)

        if len(messages_for_api) > self._estimate_token_limit(context):
            async for event in self._recovery_handler.handle_prompt_too_long(
                context.messages,
                len(json.dumps(messages_for_api)) // 4,
                context.max_tokens,
            ):
                yield event

            recovered = self._recovery_handler.get_recovery_messages()
            if recovered:
                context.messages = recovered

    async def _sampling(
        self,
        context: QueryContext,
        tool_schemas: list[dict[str, Any]],
    ) -> AsyncGenerator[QueryEvent, None]:
        """API调用流式采样."""
        messages_for_api = self._format_messages_for_api(context.messages)

        yield MessageStartEvent(
            message_id=uuid4().hex,
            role="assistant",
            model=context.model,
        )

        self._stream_processor.reset()

        current_max_tokens = context.max_tokens
        if self._recovery_handler.should_escalate_tokens():
            current_max_tokens = self._recovery_handler.get_escalated_max_tokens()

        try:
            async for chunk in self.api_client.stream_message(
                system_prompt=self.system_prompt,
                messages=messages_for_api,
                tools=tool_schemas,
                model=context.model,
                max_tokens=current_max_tokens,
                temperature=self.temperature,
                thinking_budget=self.thinking_budget,
            ):
                from openlaoke.types.core_types import StreamEventType

                if chunk.event_type == StreamEventType.TEXT and chunk.text:
                    yield ContentDeltaEvent(
                        message_id=self._stream_processor.state.message_id,
                        content=chunk.text,
                        index=0,
                    )
                    self._stream_processor.state.current_content += chunk.text

                if chunk.event_type == StreamEventType.USAGE and chunk.usage:
                    self._stream_processor.state.usage = chunk.usage
                    self._total_usage.accumulate(chunk.usage)

                if chunk.event_type == StreamEventType.USAGE and chunk.cost:
                    self._total_cost.input_cost += chunk.cost.input_cost
                    self._total_cost.output_cost += chunk.cost.output_cost

                if chunk.event_type == StreamEventType.TOOL_CALL_START:
                    self._stream_processor.state.tool_uses.append(
                        ToolUseBlock(
                            id=chunk.tool_call_id,
                            name=chunk.tool_call_name,
                            input=json.loads(chunk.tool_call_arguments)
                            if chunk.tool_call_arguments
                            else {},
                        )
                    )

            tool_uses = self._stream_processor.get_tool_uses()
            for i, tu in enumerate(tool_uses):
                yield ToolUseEvent.from_block(
                    tu,
                    self._stream_processor.state.message_id,
                    i,
                )

            final_message: Message = AssistantMessage(
                role=MessageRole.ASSISTANT,
                content=self._stream_processor.state.current_content,
                tool_uses=tool_uses,
                stop_reason="end_turn" if not tool_uses else "tool_use",
            )

            yield MessageEndEvent(message=final_message)

        except TimeoutError:
            yield ErrorEvent(
                error_message="API call timed out",
                error_type="timeout",
                is_retryable=True,
            )

    async def _run_tools(
        self,
        context: QueryContext,
        tool_calls: list[ToolUseBlock],
        tools: list[Tool],
    ) -> AsyncGenerator[QueryEvent, None]:
        """执行工具调用."""
        for tool_call in tool_calls:
            tool = self._find_tool(tool_call.name, tools)
            if not tool:
                yield ToolResultEvent(
                    tool_use_id=tool_call.id,
                    tool_name=tool_call.name,
                    result=ToolResultBlock(
                        tool_use_id=tool_call.id,
                        content=f"Tool '{tool_call.name}' not found",
                        is_error=True,
                    ),
                )
                continue

            permission_result = tool.check_permissions(
                tool_call.input,
                context.permission_config,
            )

            if permission_result != PermissionResult.ALLOW:
                yield ToolResultEvent(
                    tool_use_id=tool_call.id,
                    tool_name=tool_call.name,
                    result=ToolResultBlock(
                        tool_use_id=tool_call.id,
                        content=tool.get_deny_message(tool_call.input),
                        is_error=True,
                    ),
                )
                continue

            tool_ctx = ToolContext(
                app_state=context.app_state,
                tool_use_id=tool_call.id,
                abort_signal=context.abort_controller,
            )

            try:
                progress = tool.get_progress(tool_ctx, **tool_call.input)
                if progress:
                    yield ToolProgressEvent(progress=progress)

                result = await self._timeout_handler.with_timeout(
                    tool.call(tool_ctx, **tool_call.input),
                    timeout_override=120.0,
                )

                yield ToolResultEvent(
                    tool_use_id=tool_call.id,
                    tool_name=tool_call.name,
                    result=result,
                )

            except TimeoutError:
                yield ToolResultEvent(
                    tool_use_id=tool_call.id,
                    tool_name=tool_call.name,
                    result=ToolResultBlock(
                        tool_use_id=tool_call.id,
                        content="Tool execution timed out",
                        is_error=True,
                    ),
                )
            except Exception as e:
                yield ToolResultEvent(
                    tool_use_id=tool_call.id,
                    tool_name=tool_call.name,
                    result=ToolResultBlock(
                        tool_use_id=tool_call.id,
                        content=str(e),
                        is_error=True,
                    ),
                )

    async def _handle_recovery(
        self,
        context: QueryContext,
        error: RecoveryError,
    ) -> AsyncGenerator[QueryEvent, None]:
        """Handle recovery from error."""
        yield ErrorEvent(
            error_message=str(error),
            error_type=error.error_type,
            is_retryable=error.is_retryable,
        )

        if isinstance(error, PromptTooLongError):
            async for event in self._recovery_handler.handle_prompt_too_long(
                context.messages,
                error.token_count,
                error.max_tokens,
            ):
                yield event

        elif isinstance(error, MaxOutputTokensError):
            async for event in self._recovery_handler.handle_max_output_tokens(
                context.messages,
                context.max_tokens,
            ):
                yield event

            if self._recovery_handler.should_escalate_tokens():
                context.max_tokens = self._recovery_handler.get_escalated_max_tokens()

    def _should_terminate(
        self,
        context: QueryContext,
        last_message: AssistantMessage | None,
    ) -> bool:
        """Determine if query loop should terminate."""
        if context.is_aborted():
            return True

        if context.check_budget_exceeded():
            return True

        if context.check_max_turns_exceeded():
            return True

        if last_message:
            if last_message.stop_reason in ("end_turn", "stop_sequence"):
                return True
            if not last_message.tool_uses:
                return True

        return False

    def _determine_stop_reason(
        self,
        context: QueryContext,
        last_message: AssistantMessage | None,
    ) -> StopReason:
        """Determine the stop reason for turn end."""
        if context.is_aborted():
            return StopReason.ABORTED

        if context.check_budget_exceeded():
            return StopReason.MAX_BUDGET

        if context.check_max_turns_exceeded():
            return StopReason.MAX_TURNS

        if last_message:
            if last_message.stop_reason == "tool_use":
                return StopReason.TOOL_USE
            if last_message.stop_reason == "end_turn":
                return StopReason.END_TURN
            if last_message.stop_reason == "max_tokens":
                return StopReason.MAX_TOKENS

        return StopReason.END_TURN

    def _find_tool(self, name: str, tools: list[Tool]) -> Tool | None:
        """Find tool by name."""
        for tool in tools:
            if tool.name == name:
                return tool
        return None

    def _build_tool_schemas(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Build tool schemas for API."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.get_input_schema(),
            }
            for tool in tools
        ]

    def _format_messages_for_api(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for API request."""
        result = []
        for msg in messages:
            result.append(msg.to_dict())
        return result

    def _estimate_token_limit(self, context: QueryContext) -> int:
        """Estimate safe token limit for context."""
        return context.max_tokens - 1024

    def interrupt(self) -> None:
        """Interrupt the query loop."""
        self._abort_event.set()

    def get_result(self) -> QueryResult:
        """Get final result after query completes."""
        return QueryResult(
            reason=StopReason.END_TURN,
            messages=self._messages,
            total_usage=self._total_usage,
            total_cost=self._total_cost,
            turn_count=self._turn_count,
        )

    def get_messages(self) -> list[Message]:
        """Get accumulated messages."""
        return list(self._messages)

    def get_usage(self) -> TokenUsage:
        """Get total token usage."""
        return self._total_usage

    def get_cost(self) -> CostInfo:
        """Get total cost."""
        return self._total_cost


async def run_query(
    app_state: AppState,
    tool_registry: ToolRegistry,
    api_client: MultiProviderClient,
    messages: list[Message],
    system_prompt: str = "",
    **kwargs: Any,
) -> AsyncGenerator[QueryEvent, None]:
    """Convenience wrapper for QueryEngine."""
    engine = QueryEngine(
        app_state=app_state,
        tool_registry=tool_registry,
        api_client=api_client,
        system_prompt=system_prompt,
        **kwargs,
    )

    async for event in engine.query(messages):
        yield event
