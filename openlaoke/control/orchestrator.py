"""The main Controller implementation.

The :class:`Orchestrator` is the transport-agnostic agent driver.  It
owns the full agent turn lifecycle — model call, tool execution,
permission gating, context compaction, save/restore — and emits
everything that happens as typed events to a single :class:`EventSink`.

Frontends (TUI, Web UI, API Server) drive it identically: issue
commands, render events.  None of them re-implement the agent loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openlaoke.bus.progress import ProgressBus
from openlaoke.bus.queue import MessageBus
from openlaoke.bus.runtime_events import AgentEvent, EventKind, EventSink, make_event
from openlaoke.control.commands import (
    ApproveCommand,
    BranchCommand,
    CancelCommand,
    CompactCommand,
    ControllerCommand,
    ForgetMemoryCommand,
    ForkCommand,
    NewSessionCommand,
    QuickAddCommand,
    ResumeSessionCommand,
    RewindCommand,
    SaveDocCommand,
    SetBypassCommand,
    SetPlanModeCommand,
    SubmitCommand,
    SummarizeFromCommand,
    SummarizeUpToCommand,
    SwitchCommand,
)
from openlaoke.control.controller import ApprovalTicket, SessionState, TurnHandle
from openlaoke.control.phase import RunResult, TurnPhase, can_transition
from openlaoke.core.tool_dedup import ToolDedup
from openlaoke.permission.policy import Decision
from openlaoke.plan.state import plan_mode_block_message
from openlaoke.snapshot.rewind import (
    rewind_both,
    rewind_code,
    rewind_conversation,
    summarize_from,
    summarize_up_to,
)
from openlaoke.snapshot.store import SnapshotStore
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    StreamEventType,
    SystemMessage,
    TokenUsage,
    ToolUseBlock,
    UserMessage,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    """Summary of a single agent turn."""

    session_id: str
    turn_id: str
    phase: TurnPhase
    result: RunResult
    text: str = ""
    tool_calls: int = 0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentLoopConfig:
    """Dependencies injected into the Orchestrator for the agent loop."""

    api: Any = None  # MultiProviderClient
    registry: Any = None  # ToolRegistry
    app_state: Any = None  # AppState
    gate: Any = None  # Gate

    build_system_prompt: Callable[[], str] | None = None
    build_tool_list: Callable[[], list[dict[str, Any]]] | None = None
    on_stream_chunk: Callable[[Any, str], Awaitable[None]] | None = None

    max_iterations: int = 100
    max_retries: int = 3


class Orchestrator:
    """Transport-agnostic agent orchestrator.

    Owns the agent turn lifecycle. Frontends call ``submit`` and
    observe events via ``sink``.
    """

    def __init__(
        self,
        message_bus: MessageBus | None = None,
        progress_bus: ProgressBus | None = None,
    ) -> None:
        self.bus = message_bus or MessageBus()
        self.progress = progress_bus or ProgressBus()
        self.sink = EventSink()
        self._sessions: dict[str, SessionState] = {}
        self._turns: dict[str, TurnHandle] = {}
        self._approvals: dict[str, ApprovalTicket] = {}
        self._pending_memory: dict[str, list[str]] = {}
        self._turn_counters: dict[str, int] = {}
        self._snapshot_store_instance: SnapshotStore | None = None
        self._memory_store_instance: Any = None
        self._closed = False
        self._cfg: AgentLoopConfig | None = None

    def configure(self, cfg: AgentLoopConfig) -> None:
        self._cfg = cfg

    def set_snapshot_store(self, store: SnapshotStore) -> None:
        """Inject a SnapshotStore (e.g. a temp-dir store in tests)."""
        self._snapshot_store_instance = store

    def set_memory_store(self, store: Any) -> None:
        """Inject a memory store (must expose store()/delete())."""
        self._memory_store_instance = store

    @property
    def cfg(self) -> AgentLoopConfig:
        if self._cfg is None:
            self._cfg = AgentLoopConfig()
        return self._cfg

    # -- session management --------------------------------------------------

    def register_session(self, session_id: str, session_key: str = "") -> SessionState:
        if not session_key:
            session_key = session_id
        state = SessionState(session_id=session_id, session_key=session_key)
        self._sessions[session_id] = state
        return state

    def session(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def sessions_for(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self.register_session(session_id)
        return self._sessions[session_id]

    def active_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def new_session(self) -> str:
        session_id = f"session_{uuid.uuid4().hex[:10]}"
        self.register_session(session_id)
        return session_id

    def resume_session(self, target: str) -> str:
        if target in self._sessions:
            return target
        return self.new_session()

    # -- event bus -----------------------------------------------------------

    def subscribe(self, callback: Callable[[AgentEvent], Awaitable[None] | None]) -> None:
        self.sink.subscribe(callback)

    async def emit(self, event: AgentEvent) -> None:
        await self.sink.emit(event)

    # -- command dispatch ----------------------------------------------------

    async def dispatch(self, session_id: str, command: ControllerCommand) -> Any:
        if isinstance(command, SubmitCommand):
            return await self.submit(session_id, command.text)
        if isinstance(command, CancelCommand):
            return self.cancel(session_id)
        if isinstance(command, ApproveCommand):
            return self.resolve_approval(
                session_id, command.target, command.decision, command.remember
            )
        if isinstance(command, SetPlanModeCommand):
            return self.set_plan_mode(session_id, command.enabled)
        if isinstance(command, CompactCommand):
            return await self.compact(session_id)
        if isinstance(command, NewSessionCommand):
            return self.new_session()
        if isinstance(command, ResumeSessionCommand):
            return self.resume_session(command.target)
        if isinstance(command, RewindCommand):
            return await self.rewind(session_id, command.target, command.scope)
        if isinstance(command, ForkCommand):
            return await self.fork(session_id, command.target, command.label)
        if isinstance(command, BranchCommand):
            return await self.branch(session_id, command.label)
        if isinstance(command, SwitchCommand):
            return await self.switch(session_id, command.target)
        if isinstance(command, SummarizeFromCommand):
            return await self.summarize_from(session_id, command.target)
        if isinstance(command, SummarizeUpToCommand):
            return await self.summarize_up_to(session_id, command.target)
        if isinstance(command, SetBypassCommand):
            return self.set_bypass(session_id, command.enabled)
        if isinstance(command, ForgetMemoryCommand):
            return self.forget_memory(session_id, command.fact_id)
        if isinstance(command, SaveDocCommand):
            return self.save_doc(session_id, command.text, command.target)
        if isinstance(command, QuickAddCommand):
            return self.queue_pending_memory(session_id, command.note)
        return None

    # -- turn lifecycle ------------------------------------------------------

    async def submit(self, session_id: str, text: str) -> TurnResult:
        """Run a full turn on a session."""
        if not text.strip():
            return TurnResult(
                session_id=session_id,
                turn_id="",
                phase=TurnPhase.DONE,
                result=RunResult.OK,
            )
        turn_id = uuid.uuid4().hex[:10]
        state = self.sessions_for(session_id)
        turn_index = self._next_turn_index(session_id)
        start = time.time()

        await self.emit(make_event(EventKind.TURN_STARTED, session_id, turn_id=turn_id, text=text))

        app_state = self.cfg.app_state
        if app_state:
            app_state.is_running = True
            app_state.set_error(None)
            user_msg = UserMessage(role=MessageRole.USER, content=text)
            app_state.add_message(user_msg)

        try:
            await self._run_phase(state, TurnPhase.COMMAND)
            await self._run_phase(state, TurnPhase.BUILD)
            await self._run_phase(state, TurnPhase.RUN)
            await self._run_phase(state, TurnPhase.SAVE)
            await self._run_phase(state, TurnPhase.RESPOND)
            await self._run_phase(state, TurnPhase.DONE)
            return TurnResult(
                session_id=session_id,
                turn_id=turn_id,
                phase=TurnPhase.DONE,
                result=RunResult.OK,
                duration_ms=(time.time() - start) * 1000,
            )
        except asyncio.CancelledError:
            return TurnResult(
                session_id=session_id,
                turn_id=turn_id,
                phase=TurnPhase.DONE,
                result=RunResult.CANCELLED,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            logger.exception("Turn %s failed", turn_id)
            await self.emit(
                make_event(
                    EventKind.NOTICE,
                    session_id,
                    level="error",
                    message=f"Turn error: {exc}",
                )
            )
            return TurnResult(
                session_id=session_id,
                turn_id=turn_id,
                phase=TurnPhase.DONE,
                result=RunResult.ERROR,
                duration_ms=(time.time() - start) * 1000,
            )
        finally:
            if app_state:
                app_state.is_running = False
            await self._capture_turn(session_id, turn_index)
            await self.emit(make_event(EventKind.TURN_DONE, session_id, turn_id=turn_id))

    # -- agent loop core -----------------------------------------------------

    async def run_agent_loop(
        self,
        session_id: str,
        system_prompt: str = "",
        tools: list[dict[str, Any]] | None = None,
        thinking_budget: int = 0,
    ) -> list[dict[str, Any]]:
        """Execute the core agent loop: model call → tool exec → repeat.

        Returns the final message list suitable for appending to history.
        """
        api = self.cfg.api
        if api is None:
            await self.emit(
                make_event(EventKind.NOTICE, session_id, level="error", message="No API client")
            )
            return []

        app_state = self.cfg.app_state
        gate = self.cfg.gate

        messages: list[dict[str, Any]] = []
        if app_state:
            messages = _messages_from_app_state(app_state)

        tools = tools or []
        max_iters = self.cfg.max_iterations
        iteration = 0
        failed_tool_calls: dict[str, int] = {}
        total_tool_calls = 0
        dedup = ToolDedup()

        while iteration < max_iters:
            iteration += 1

            if self._closed:
                break

            sp = system_prompt
            if self.cfg.build_system_prompt:
                sp = self.cfg.build_system_prompt()
            if self.cfg.build_tool_list:
                tools = self.cfg.build_tool_list()

            content_text = ""
            reasoning_text = ""
            tool_uses: list[ToolUseBlock] = []
            usage: TokenUsage | None = None

            try:
                async for chunk in api.stream_message(
                    system_prompt=sp,
                    messages=messages,
                    tools=tools if tools else None,
                    thinking_budget=thinking_budget,
                ):
                    if chunk.event_type == StreamEventType.TEXT:
                        content_text += chunk.text
                    elif chunk.event_type == StreamEventType.REASONING:
                        reasoning_text += chunk.text
                    elif chunk.event_type == StreamEventType.TOOL_CALL_START:
                        try:
                            args = (
                                json.loads(chunk.tool_call_arguments)
                                if chunk.tool_call_arguments
                                else {}
                            )
                        except json.JSONDecodeError:
                            args = {}
                        tool_uses.append(
                            ToolUseBlock(
                                id=chunk.tool_call_id,
                                name=chunk.tool_call_name,
                                input=args,
                            )
                        )
                    elif chunk.event_type == StreamEventType.USAGE and chunk.usage:
                        usage = chunk.usage

                    if self.cfg.on_stream_chunk:
                        await self.cfg.on_stream_chunk(chunk, session_id)

            except Exception as exc:
                logger.exception("Model call failed iteration %d", iteration)
                await self.emit(
                    make_event(
                        EventKind.NOTICE,
                        session_id,
                        level="error",
                        message=f"Model error: {exc}",
                    )
                )
                break

            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content_text}
            if tool_uses:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tu.id,
                        "type": "function",
                        "function": {"name": tu.name, "arguments": json.dumps(tu.input)},
                    }
                    for tu in tool_uses
                ]
            messages.append(assistant_msg)

            if not tool_uses:
                if app_state:
                    assistant = AssistantMessage(
                        role=MessageRole.ASSISTANT,
                        content=content_text,
                        thinking=reasoning_text or "",
                    )
                    if usage:
                        app_state.add_token_usage(usage)
                    app_state.add_message(assistant)
                break

            for tu in tool_uses:
                total_tool_calls += 1

                dedup_block = dedup.check(tu.name, _safe_dict(tu.input))
                if dedup_block:
                    messages.append({"role": "tool", "tool_call_id": tu.id, "content": dedup_block})
                    continue

                session_state = self._sessions.get(session_id)
                if (
                    session_state is not None
                    and session_state.plan.enabled
                    and not session_state.plan.is_writer_allowed()
                    and not self._is_plan_exempt(tu.name)
                ):
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tu.id,
                            "content": plan_mode_block_message(tu.name),
                        }
                    )
                    continue

                if gate:
                    result = await gate.check(tu.name, _safe_dict(tu.input))
                    if result.decision == Decision.DENY:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tu.id,
                                "content": f"Denied: {result.reason}",
                            }
                        )
                        continue
                    if result.decision == Decision.ASK:
                        await self.emit(
                            make_event(
                                EventKind.APPROVAL_REQUEST,
                                session_id,
                                tool_name=tu.name,
                                tool_args=_safe_dict(tu.input),
                            )
                        )
                        future = self.request_approval(session_id, tu.name, _safe_dict(tu.input))
                        try:
                            decision = await asyncio.wait_for(future, timeout=300)
                        except TimeoutError:
                            decision = "deny"
                        if decision == "deny":
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tu.id,
                                    "content": "User denied this tool call.",
                                }
                            )
                            continue

                try:
                    registry = self.cfg.registry
                    if registry and hasattr(registry, "execute"):
                        result_block = await registry.execute(tu.name, _safe_dict(tu.input))
                        tool_output = (
                            result_block.output
                            if hasattr(result_block, "output")
                            else str(result_block)
                        )
                    else:
                        tool_output = f"Tool '{tu.name}' not found in registry"
                except Exception as exc:
                    logger.exception("Tool %s failed", tu.name)
                    tool_output = f"Error executing {tu.name}: {exc}"
                    failed_tool_calls[tu.name] = failed_tool_calls.get(tu.name, 0) + 1

                max_out = 32000
                if len(tool_output) > max_out:
                    tool_output = (
                        tool_output[:max_out]
                        + f"\n\n... (truncated {len(tool_output) - max_out} bytes)"
                    )

                messages.append({"role": "tool", "tool_call_id": tu.id, "content": tool_output})

                if app_state:
                    app_state.add_message(
                        SystemMessage(
                            role=MessageRole.SYSTEM,
                            content=tool_output,
                            subtype="tool_result",
                            tool_use_id=tu.id,
                        )
                    )

            if total_tool_calls > 50:
                messages.append(
                    {
                        "role": "user",
                        "content": "[System] You have made 50 tool calls. Respond concisely now.",
                    }
                )

        await self._capture_turn(session_id, self._next_turn_index(session_id))
        return messages

    # -- permissions ---------------------------------------------------------

    def request_approval(
        self,
        session_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> asyncio.Future[str]:
        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        ticket = ApprovalTicket(
            ticket_id=uuid.uuid4().hex[:10],
            tool_name=tool_name,
            tool_args=tool_args,
            future=future,
        )
        self._approvals[ticket.ticket_id] = ticket
        return future

    def resolve_approval(
        self,
        session_id: str,
        ticket_id: str,
        decision: str,
        remember: bool = False,
    ) -> bool:
        ticket = self._approvals.pop(ticket_id, None)
        if ticket is None:
            return False
        if not ticket.future.done():
            ticket.future.set_result(decision)
        return True

    def pending_approvals(self, session_id: str = "") -> list[ApprovalTicket]:
        return list(self._approvals.values())

    # -- session control -----------------------------------------------------

    def cancel(self, session_id: str) -> bool:
        turn = self._turns.pop(session_id, None)
        if turn is not None:
            turn.cancelled = True
            if not turn.task.done():
                turn.task.cancel()
            return True
        return False

    def set_plan_mode(self, session_id: str, enabled: bool) -> None:
        state = self.sessions_for(session_id)
        state.plan_mode = enabled
        state.plan.enabled = enabled
        if not enabled:
            state.plan.auto_approve = False

    def is_plan_mode(self, session_id: str) -> bool:
        state = self._sessions.get(session_id)
        return bool(state and (state.plan_mode or state.plan.enabled))

    def is_bypass(self, session_id: str) -> bool:
        state = self._sessions.get(session_id)
        return bool(state and state.bypass)

    def set_bypass(self, session_id: str, enabled: bool) -> None:
        state = self.sessions_for(session_id)
        state.bypass = enabled

    async def compact(self, session_id: str) -> None:
        state = self.sessions_for(session_id)
        await self._run_phase(state, TurnPhase.COMPACT)

    async def rewind(self, session_id: str, target_turn: int, scope: str) -> dict[str, Any]:
        store = self._snapshot_store()
        app_state = self.cfg.app_state
        messages = app_state.messages if app_state is not None else None

        if scope == "code":
            report = rewind_code(store, session_id, target_turn)
        elif scope == "conversation":
            report = rewind_conversation(store, session_id, target_turn, messages=messages)
        else:
            report = rewind_both(store, session_id, target_turn, messages=messages)

        await self.emit(
            make_event(
                EventKind.NOTICE,
                session_id,
                level="info",
                message=(
                    f"Rewind turn={target_turn} scope={report.scope} "
                    f"files={len(report.files)} turns_dropped={report.turns_dropped}"
                ),
            )
        )
        return {
            "rewound": True,
            "target_turn": target_turn,
            "scope": report.scope,
            "files_restored": len(report.files),
            "turns_dropped": report.turns_dropped,
            "files": report.files,
        }

    async def fork(self, session_id: str, target_turn: int | None, label: str) -> str:
        store = self._snapshot_store()
        effective = target_turn if target_turn is not None else -1
        new_id, meta_path = store.fork_session(session_id, effective)
        state = self.register_session(new_id)
        parent = self._sessions.get(session_id)
        if parent is not None:
            state.bypass = parent.bypass
            state.plan_mode = parent.plan_mode
            state.plan.enabled = parent.plan.enabled
        self._init_fork_turn_counter(store, new_id, effective)
        await self.emit(
            make_event(
                EventKind.NOTICE,
                session_id,
                level="info",
                message=f"Forked into {new_id} at turn {effective}",
            )
        )
        return new_id

    async def branch(self, session_id: str, label: str) -> str:
        store = self._snapshot_store()
        new_id, meta_path = store.fork_session(session_id, -1)
        state = self.register_session(new_id)
        parent = self._sessions.get(session_id)
        if parent is not None:
            state.bypass = parent.bypass
            state.plan_mode = parent.plan_mode
            state.plan.enabled = parent.plan.enabled
        self._init_fork_turn_counter(store, new_id, -1)
        await self.emit(
            make_event(
                EventKind.NOTICE,
                session_id,
                level="info",
                message=f"Branch {label or new_id} created from {session_id} tip",
            )
        )
        return new_id

    async def switch(self, session_id: str, target: str) -> str:
        if target in self._sessions:
            await self.emit(
                make_event(
                    EventKind.NOTICE,
                    session_id,
                    level="info",
                    message=f"Switched active session to {target}",
                )
            )
            return target
        await self.emit(
            make_event(
                EventKind.NOTICE,
                session_id,
                level="error",
                message=f"Cannot switch to unknown session '{target}'",
            )
        )
        return ""

    async def summarize_from(self, session_id: str, target_turn: int) -> dict[str, Any]:
        store = self._snapshot_store()
        info = summarize_from(store, session_id, target_turn)
        await self.emit(
            make_event(
                EventKind.NOTICE,
                session_id,
                level="info",
                message=f"Summarized from turn {target_turn}: {info['compacted']} turns",
            )
        )
        return info

    async def summarize_up_to(self, session_id: str, target_turn: int) -> dict[str, Any]:
        store = self._snapshot_store()
        info = summarize_up_to(store, session_id, target_turn)
        await self.emit(
            make_event(
                EventKind.NOTICE,
                session_id,
                level="info",
                message=f"Summarized up to turn {target_turn}: {info['compacted']} turns",
            )
        )
        return info

    # -- memory ---------------------------------------------------------------

    def forget_memory(self, session_id: str, fact_id: str) -> bool:
        store = self._memory_store()
        if store is None:
            return False
        try:
            return bool(store.delete(fact_id))
        except Exception as exc:
            logger.warning("Failed to forget memory %s: %s", fact_id, exc)
            return False

    def save_doc(self, session_id: str, text: str, target: str) -> str:
        store = self._memory_store()
        if store is None:
            return ""
        try:
            from openlaoke.core.memory.sqlite_store import MemoryRecord

            record = MemoryRecord(
                id=f"doc_{uuid.uuid4().hex[:8]}",
                content=text,
                memory_type="doc",
                key=target or "project",
            )
            doc_id = store.store(record)
            return str(doc_id) if doc_id else ""
        except Exception as exc:
            logger.warning("Failed to save doc: %s", exc)
            return ""

    # -- memory ---------------------------------------------------------------

    def queue_pending_memory(self, session_id: str, note: str) -> None:
        if not note.strip():
            return
        self._pending_memory.setdefault(session_id, []).append(note)

    def drain_pending_memory(self, session_id: str) -> list[str]:
        notes = self._pending_memory.pop(session_id, [])
        return list(notes)

    # -- internals -----------------------------------------------------------

    def _next_turn_index(self, session_id: str) -> int:
        idx = self._turn_counters.get(session_id, 0)
        self._turn_counters[session_id] = idx + 1
        return idx

    def _init_fork_turn_counter(self, store: SnapshotStore, new_id: str, effective: int) -> None:
        """Seed the forked session's turn counter past the fork point so
        the inherited snapshot records are never overwritten."""
        existing = store.all_turns(new_id)
        next_idx = max((t.turn_index for t in existing), default=-1) + 1
        self._turn_counters[new_id] = max(next_idx, effective + 1)

    async def _capture_turn(self, session_id: str, turn_index: int) -> None:
        app_state = self.cfg.app_state
        if app_state is None:
            return
        try:
            store = self._snapshot_store()
            store.capture_conversation(session_id, turn_index, app_state.messages)
        except Exception as exc:
            logger.warning("Failed to capture conversation for %s: %s", session_id, exc)

    def _snapshot_store(self) -> SnapshotStore:
        if self._snapshot_store_instance is not None:
            return self._snapshot_store_instance
        app_state = self.cfg.app_state
        if app_state is not None:
            try:
                store = app_state.snapshot_store
                if isinstance(store, SnapshotStore):
                    return store
            except Exception:
                pass
        self._snapshot_store_instance = SnapshotStore()
        return self._snapshot_store_instance

    def _memory_store(self) -> Any:
        if self._memory_store_instance is None:
            try:
                from openlaoke.core.memory.sqlite_store import SQLiteMemoryStore

                self._memory_store_instance = SQLiteMemoryStore()
            except Exception as exc:
                logger.warning("Memory store unavailable: %s", exc)
                self._memory_store_instance = False
        return self._memory_store_instance or None

    def _is_plan_exempt(self, tool_name: str) -> bool:
        """Tools allowed while plan mode blocks writers."""
        if tool_name == "Plan":
            return True
        registry = self.cfg.registry
        if registry is not None and hasattr(registry, "is_readonly"):
            try:
                return bool(registry.is_readonly(tool_name))
            except Exception:
                return False
        return False

    async def _run_phase(self, state: SessionState, phase: TurnPhase) -> None:
        current = getattr(state, "phase", TurnPhase.RESTORE)
        if not can_transition(current, phase) and phase != TurnPhase.RESTORE:
            return
        state.phase = phase
        await self.emit(make_event(EventKind.PHASE, state.session_id, phase=phase.value))

    async def shutdown(self) -> None:
        self._closed = True
        for turn in self._turns.values():
            if not turn.task.done():
                turn.task.cancel()
        await self.bus.shutdown()


def _messages_from_app_state(app_state: Any) -> list[dict[str, Any]]:
    """Convert AppState messages to provider dict format."""
    messages: list[dict[str, Any]] = []
    for msg in app_state.messages:
        if msg.role == MessageRole.USER:
            messages.append({"role": "user", "content": msg.content})
        elif msg.role == MessageRole.ASSISTANT:
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content}
            if hasattr(msg, "tool_uses") and msg.tool_uses:
                entry["tool_calls"] = [
                    {
                        "id": tu.id,
                        "type": "function",
                        "function": {"name": tu.name, "arguments": json.dumps(tu.input)},
                    }
                    for tu in msg.tool_uses
                ]
            messages.append(entry)
        elif msg.role == MessageRole.SYSTEM and hasattr(msg, "tool_use_id") and msg.tool_use_id:
            messages.append(
                {"role": "tool", "tool_call_id": msg.tool_use_id, "content": msg.content}
            )
    return messages


def _safe_dict(value: Any) -> dict[str, Any]:
    """Coerce a value to dict."""
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
    return {}
