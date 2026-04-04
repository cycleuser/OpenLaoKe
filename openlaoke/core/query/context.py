"""Context management for query execution."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openlaoke.types.core_types import (
    CostInfo,
    Message,
    TokenUsage,
    ToolUseBlock,
)
from openlaoke.types.permissions import PermissionConfig

if TYPE_CHECKING:
    from openlaoke.core.state import AppState
    from openlaoke.core.tool import Tool, ToolRegistry


@dataclass
class QueryTracking:
    """Tracking information for query chain."""

    chain_id: str = field(default_factory=lambda: uuid4().hex)
    depth: int = 0


@dataclass
class TurnState:
    """State for a single turn in the query loop."""

    turn_count: int = 1
    tool_use_blocks: list[ToolUseBlock] = field(default_factory=list)
    assistant_messages: list[Message] = field(default_factory=list)
    user_messages: list[Message] = field(default_factory=list)
    needs_follow_up: bool = False
    current_stop_reason: str | None = None
    current_usage: TokenUsage = field(default_factory=TokenUsage)
    accumulated_usage: TokenUsage = field(default_factory=TokenUsage)
    accumulated_cost: CostInfo = field(default_factory=CostInfo)
    max_output_tokens_recovery_count: int = 0
    has_attempted_reactive_compact: bool = False


@dataclass
class QueryContext:
    """Context for a query execution session."""

    app_state: AppState
    tool_registry: ToolRegistry
    messages: list[Message] = field(default_factory=list)
    system_prompt: str = ""
    user_context: dict[str, str] = field(default_factory=dict)
    system_context: dict[str, str] = field(default_factory=dict)
    permission_config: PermissionConfig = field(default_factory=PermissionConfig.defaults)
    model: str = "gemma3:1b"
    fallback_model: str | None = None
    max_tokens: int = 8192
    max_turns: int | None = None
    max_budget_usd: float | None = None
    temperature: float = 1.0
    thinking_budget: int = 0
    query_source: str = "repl"
    abort_controller: asyncio.Event = field(default_factory=asyncio.Event)
    query_tracking: QueryTracking = field(default_factory=QueryTracking)
    turn_state: TurnState = field(default_factory=TurnState)
    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    verbose: bool = False

    _start_time: float = field(default_factory=time.time)
    _pending_tool_summaries: dict[str, str] = field(default_factory=dict)

    def get_elapsed_ms(self) -> int:
        return int((time.time() - self._start_time) * 1000)

    def get_active_tools(self) -> list[Tool]:
        return self.tool_registry.get_all()

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return self.tool_registry.get_all_for_prompt()

    def is_aborted(self) -> bool:
        return self.abort_controller.is_set()

    def check_budget_exceeded(self) -> bool:
        if self.max_budget_usd is None:
            return False
        return self.turn_state.accumulated_cost.total_cost >= self.max_budget_usd

    def check_max_turns_exceeded(self) -> bool:
        if self.max_turns is None:
            return False
        return self.turn_state.turn_count >= self.max_turns

    def add_tool_use_block(self, block: ToolUseBlock) -> None:
        self.turn_state.tool_use_blocks.append(block)
        self.turn_state.needs_follow_up = True

    def clear_turn_state(self) -> None:
        self.turn_state = TurnState(turn_count=self.turn_state.turn_count + 1)

    def accumulate_usage(self, usage: TokenUsage) -> None:
        self.turn_state.current_usage = usage
        self.turn_state.accumulated_usage.accumulate(usage)

    def accumulate_cost(self, cost: CostInfo) -> None:
        self.turn_state.accumulated_cost.input_cost += cost.input_cost
        self.turn_state.accumulated_cost.output_cost += cost.output_cost
        self.turn_state.accumulated_cost.cache_read_cost += cost.cache_read_cost
        self.turn_state.accumulated_cost.cache_creation_cost += cost.cache_creation_cost

    def get_total_cost(self) -> float:
        return self.turn_state.accumulated_cost.total_cost

    def should_continue(self) -> bool:
        if self.is_aborted():
            return False
        if self.check_budget_exceeded():
            return False
        if self.check_max_turns_exceeded():
            return False
        return self.turn_state.needs_follow_up

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "model": self.model,
            "turn_count": self.turn_state.turn_count,
            "message_count": len(self.messages),
            "total_cost": self.get_total_cost(),
            "total_tokens": self.turn_state.accumulated_usage.total_tokens,
            "is_aborted": self.is_aborted(),
            "elapsed_ms": self.get_elapsed_ms(),
        }


def create_query_context(
    app_state: AppState,
    tool_registry: ToolRegistry,
    messages: list[Message] | None = None,
    system_prompt: str = "",
    model: str = "gemma3:1b",
    **kwargs: Any,
) -> QueryContext:
    """Factory for creating QueryContext with defaults."""
    return QueryContext(
        app_state=app_state,
        tool_registry=tool_registry,
        messages=messages or [],
        system_prompt=system_prompt,
        model=model,
        **kwargs,
    )
