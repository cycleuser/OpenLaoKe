"""Tests for the controller and command router."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from openlaoke.bus.runtime_events import EventKind
from openlaoke.control.commands import (
    BranchCommand,
    ForgetMemoryCommand,
    ForkCommand,
    NewSessionCommand,
    QuickAddCommand,
    RewindCommand,
    SaveDocCommand,
    SetBypassCommand,
    SetPlanModeCommand,
    SubmitCommand,
    SummarizeFromCommand,
    SummarizeUpToCommand,
    SwitchCommand,
)
from openlaoke.control.orchestrator import AgentLoopConfig, Orchestrator
from openlaoke.control.phase import RunResult, TurnPhase
from openlaoke.core.state import create_app_state
from openlaoke.permission.gate import Gate
from openlaoke.snapshot.store import SnapshotStore


@pytest.fixture
def orch_with_store(tmp_path) -> Orchestrator:
    orch = Orchestrator()
    orch.set_snapshot_store(SnapshotStore(base_dir=str(tmp_path / "snap")))
    return orch


class TestOrchestrator:
    def test_register_session(self) -> None:
        orch = Orchestrator()
        state = orch.register_session("s1")
        assert state.session_id == "s1"
        assert orch.session("s1") is state

    def test_submit_empty_text(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            result = await orch.submit("s1", "   ")
            assert result.result is RunResult.OK
            assert result.turn_id == ""

        asyncio.run(scenario())

    def test_submit_emits_phase_events(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            kinds: list[EventKind] = []
            orch.subscribe(lambda ev: kinds.append(ev.kind) or None)
            await orch.submit("s1", "hello")
            assert EventKind.TURN_STARTED in kinds
            assert EventKind.TURN_DONE in kinds
            assert EventKind.PHASE in kinds

        asyncio.run(scenario())

    def test_set_plan_mode(self) -> None:
        orch = Orchestrator()
        orch.set_plan_mode("s1", True)
        assert orch.is_plan_mode("s1")
        orch.set_plan_mode("s1", False)
        assert not orch.is_plan_mode("s1")

    def test_bypass(self) -> None:
        orch = Orchestrator()
        orch.set_bypass("s1", True)
        assert orch.is_bypass("s1")

    def test_pending_memory(self) -> None:
        orch = Orchestrator()
        orch.queue_pending_memory("s1", "user prefers tabs")
        orch.queue_pending_memory("s1", "builds with uv")
        notes = orch.drain_pending_memory("s1")
        assert notes == ["user prefers tabs", "builds with uv"]
        assert orch.drain_pending_memory("s1") == []

    def test_approval_ticket(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            future = orch.request_approval("s1", "bash", {"command": "rm -rf /"})
            assert isinstance(future, asyncio.Future)
            tickets = orch.pending_approvals()
            assert len(tickets) == 1
            ok = orch.resolve_approval("s1", tickets[0].ticket_id, "deny")
            assert ok
            assert future.result() == "deny"
            assert orch.pending_approvals() == []

        asyncio.run(scenario())

    def test_dispatch_submit(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            cmd = SubmitCommand("hello")
            result = await orch.dispatch("s1", cmd)
            assert result.session_id == "s1"
            assert result.result is RunResult.OK

        asyncio.run(scenario())

    def test_dispatch_set_plan_mode(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            await orch.dispatch("s1", SetPlanModeCommand(enabled=True))
            assert orch.is_plan_mode("s1")

        asyncio.run(scenario())

    def test_dispatch_new_session(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            new_id = await orch.dispatch("s1", NewSessionCommand())
            assert new_id.startswith("session_")
            assert new_id in orch.active_sessions()

        asyncio.run(scenario())

    def test_dispatch_quick_add(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            await orch.dispatch("s1", QuickAddCommand(note="user prefers dark theme"))
            assert orch.drain_pending_memory("s1") == ["user prefers dark theme"]

        asyncio.run(scenario())

    def test_dispatch_rewind(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            result = await orch.dispatch("s1", RewindCommand(target=3, scope="code+conversation"))
            assert result["rewound"] is True
            assert result["target_turn"] == 3
            assert result["scope"] == "code+conversation"

        asyncio.run(scenario())

    def test_dispatch_fork(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            new_id = await orch.dispatch("s1", ForkCommand(target=2))
            assert new_id in orch.active_sessions()
            assert new_id.startswith("s1_fork_")

        asyncio.run(scenario())

    def test_dispatch_branch(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            new_id = await orch.dispatch("s1", BranchCommand(label="exp"))
            assert new_id in orch.active_sessions()
            assert new_id.startswith("s1_fork_")

        asyncio.run(scenario())

    def test_dispatch_switch(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            new_id = await orch.dispatch("s1", BranchCommand())
            switched = await orch.dispatch("s1", SwitchCommand(target=new_id))
            assert switched == new_id

        asyncio.run(scenario())

    def test_dispatch_switch_unknown_returns_empty(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            switched = await orch.dispatch("s1", SwitchCommand(target="never_registered"))
            assert switched == ""
            assert "never_registered" not in orch.active_sessions()

        asyncio.run(scenario())

    def test_dispatch_summarize(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            info = await orch.dispatch("s1", SummarizeFromCommand(target=2))
            assert info["scope"] == "from"
            assert info["turn"] == 2
            info2 = await orch.dispatch("s1", SummarizeUpToCommand(target=2))
            assert info2["scope"] == "up_to"

        asyncio.run(scenario())

    def test_dispatch_set_bypass(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            await orch.dispatch("s1", SetBypassCommand(enabled=True))
            assert orch.is_bypass("s1")

        asyncio.run(scenario())

    def test_dispatch_forget_memory(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()

            class FakeMemory:
                def store(self, record: Any) -> str:
                    return record.id

                def delete(self, memory_id: str) -> bool:
                    return memory_id == "mem_1"

            orch.set_memory_store(FakeMemory())
            assert await orch.dispatch("s1", ForgetMemoryCommand(fact_id="mem_1")) is True
            assert await orch.dispatch("s1", ForgetMemoryCommand(fact_id="mem_x")) is False

        asyncio.run(scenario())

    def test_dispatch_save_doc(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()

            class FakeMemory:
                stored: list[dict[str, Any]] = []

                def store(self, record: Any) -> str:
                    FakeMemory.stored.append(record.__dict__)
                    return record.id

                def delete(self, memory_id: str) -> bool:
                    return True

            orch.set_memory_store(FakeMemory())
            doc_id = await orch.dispatch(
                "s1", SaveDocCommand(text="project conventions", target="project")
            )
            assert doc_id.startswith("doc_")
            assert FakeMemory.stored[0]["memory_type"] == "doc"

        asyncio.run(scenario())

    def test_submit_captures_conversation(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            app_state = create_app_state()
            orch.configure(AgentLoopConfig(app_state=app_state))
            await orch.submit("s1", "hello world")
            turns = orch._snapshot_store().all_turns("s1")
            assert turns
            assert turns[-1].conversation

        asyncio.run(scenario())

    def test_rewind_truncates_app_state_messages(self, orch_with_store: Orchestrator) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            app_state = create_app_state()
            orch.configure(AgentLoopConfig(app_state=app_state))
            await orch.submit("s1", "first")
            await orch.submit("s1", "second")
            before = len(app_state.messages)
            assert before >= 2
            result = await orch.rewind("s1", 1, "conversation")
            assert result["turns_dropped"] >= 1
            assert len(app_state.messages) < before

        asyncio.run(scenario())

    def test_cancel_no_turn(self) -> None:
        orch = Orchestrator()
        assert orch.cancel("s1") is False

    def test_fork_continues_turn_index_without_overwrite(
        self, orch_with_store: Orchestrator
    ) -> None:
        async def scenario() -> None:
            orch = orch_with_store
            app_state = create_app_state()
            orch.configure(AgentLoopConfig(app_state=app_state))
            await orch.submit("s1", "first")
            await orch.submit("s1", "second")
            new_id = await orch.fork("s1", 1, "")
            await orch.submit(new_id, "third")
            store = orch._snapshot_store()
            turns = store.all_turns(new_id)
            assert [t.turn_index for t in turns] == [0, 1, 2]
            # fork 继承的 turn 0 记录未被新会话覆盖
            assert turns[0].conversation

        asyncio.run(scenario())

    def test_run_agent_loop_captures_conversation(self, orch_with_store: Orchestrator) -> None:
        import json

        from openlaoke.types.core_types import StreamChunk, StreamEventType

        class FakeStreamAPI:
            def __init__(self) -> None:
                self._calls = 0

            async def stream_message(
                self,
                system_prompt: str = "",
                messages: list[dict[str, Any]] | None = None,
                tools: list[dict[str, Any]] | None = None,
                thinking_budget: int = 0,
            ):
                self._calls += 1
                if self._calls == 1:
                    yield StreamChunk(
                        event_type=StreamEventType.TOOL_CALL_START,
                        tool_call_id="call_9",
                        tool_call_name="read_file",
                        tool_call_arguments=json.dumps({}),
                    )
                else:
                    yield StreamChunk(event_type=StreamEventType.TEXT, text="done")

        class FakeRegistry:
            def is_readonly(self, name: str) -> bool:
                return name == "read_file"

            async def execute(self, name: str, args: dict[str, Any]) -> Any:
                class Block:
                    output = "file content"

                return Block()

        async def scenario() -> None:
            orch = orch_with_store
            app_state = create_app_state()
            orch.configure(
                AgentLoopConfig(
                    api=FakeStreamAPI(),
                    registry=FakeRegistry(),
                    gate=Gate(),
                    app_state=app_state,
                )
            )
            await orch.submit("s1", "hello")
            await orch.run_agent_loop("s1", tools=[{"name": "read_file"}])
            store = orch._snapshot_store()
            turns = store.all_turns("s1")
            assert [t.turn_index for t in turns] == [0, 1]
            # turn 1 包含 agent 循环产生的 assistant/tool 消息
            assert len(turns[1].conversation) > len(turns[0].conversation)

        asyncio.run(scenario())


class TestPlanModeGating:
    def _make_registry(self) -> Any:
        class FakeRegistry:
            def is_readonly(self, name: str) -> bool:
                return name in {"read_file", "grep"}

            async def execute(self, name: str, args: dict[str, Any]) -> Any:
                class Block:
                    output = f"ran {name}"

                return Block()

        return FakeRegistry()

    def _make_api(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> Any:
        import json

        from openlaoke.types.core_types import StreamChunk, StreamEventType

        class FakeStreamAPI:
            def __init__(self) -> None:
                self._calls = 0

            async def stream_message(
                self,
                system_prompt: str = "",
                messages: list[dict[str, Any]] | None = None,
                tools: list[dict[str, Any]] | None = None,
                thinking_budget: int = 0,
            ):
                self._calls += 1
                if self._calls == 1:
                    yield StreamChunk(
                        event_type=StreamEventType.TOOL_CALL_START,
                        tool_call_id="call_1",
                        tool_call_name=tool_name,
                        tool_call_arguments=json.dumps(tool_args or {}),
                    )
                else:
                    yield StreamChunk(event_type=StreamEventType.TEXT, text="done")

        return FakeStreamAPI()

    def _configure(self, orch: Orchestrator, tool_name: str) -> Orchestrator:
        orch.configure(
            AgentLoopConfig(
                api=self._make_api(tool_name),
                registry=self._make_registry(),
                gate=Gate(),
            )
        )
        return orch

    def test_plan_mode_blocks_writer_tool(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            orch.set_plan_mode("s1", True)
            self._configure(orch, "write_file")
            messages = await orch.run_agent_loop("s1", tools=[{"name": "write_file"}])
            tool_msgs = [m for m in messages if m.get("role") == "tool"]
            assert tool_msgs
            assert "read-only" in tool_msgs[-1]["content"]
            assert "write_file" in tool_msgs[-1]["content"]

        asyncio.run(scenario())

    def test_plan_mode_allows_readonly_tool(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            orch.set_plan_mode("s1", True)
            self._configure(orch, "read_file")
            messages = await orch.run_agent_loop("s1", tools=[{"name": "read_file"}])
            assert any("ran read_file" in m.get("content", "") for m in messages)

        asyncio.run(scenario())

    def test_plan_mode_allows_plan_tool(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            orch.set_plan_mode("s1", True)
            self._configure(orch, "Plan")
            messages = await orch.run_agent_loop("s1", tools=[{"name": "Plan"}])
            assert any("ran Plan" in m.get("content", "") for m in messages)

        asyncio.run(scenario())

    def test_plan_approval_unblocks_writer(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            orch.set_plan_mode("s1", True)
            state = orch.session("s1")
            assert state is not None
            state.plan.begin_plan("do the work")
            state.plan.approve()
            self._configure(orch, "write_file")
            messages = await orch.run_agent_loop("s1", tools=[{"name": "write_file"}])
            assert any("ran write_file" in m.get("content", "") for m in messages)

        asyncio.run(scenario())

    def test_plan_block_precedes_permission_gate(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            orch.set_plan_mode("s1", True)

            class RecordingGate(Gate):
                check_calls: list[str] = []

                async def check(self, tool_name: str, tool_args: dict[str, Any]):
                    RecordingGate.check_calls.append(tool_name)
                    from openlaoke.permission.policy import Decision

                    return type("R", (), {"decision": Decision.ALLOW, "reason": ""})()

            gate = RecordingGate()
            orch.configure(
                AgentLoopConfig(
                    api=self._make_api("write_file"),
                    registry=self._make_registry(),
                    gate=gate,
                )
            )
            messages = await orch.run_agent_loop("s1", tools=[{"name": "write_file"}])
            tool_msgs = [m for m in messages if m.get("role") == "tool"]
            assert tool_msgs
            assert "read-only" in tool_msgs[-1]["content"]
            assert RecordingGate.check_calls == []

        asyncio.run(scenario())


class TestPhaseTransitions:
    def test_valid_transition(self) -> None:
        from openlaoke.control.phase import can_transition

        assert can_transition(TurnPhase.RESTORE, TurnPhase.COMPACT)
        assert can_transition(TurnPhase.RUN, TurnPhase.SAVE)
        assert not can_transition(TurnPhase.DONE, TurnPhase.RUN)


class TestCommandRouter:
    def test_priority_dispatch(self) -> None:
        from openlaoke.commands.router import CommandResult, CommandRouter, CommandSpec

        async def scenario() -> None:
            router = CommandRouter()

            async def stop(_c: str, _a: dict[str, Any]) -> CommandResult:
                return CommandResult(text="stopped")

            router.register(CommandSpec(name="stop", handler=stop, tier="priority"))
            result = await router.dispatch("/stop")
            assert result.success
            assert result.text == "stopped"

        asyncio.run(scenario())

    def test_exact_dispatch(self) -> None:
        from openlaoke.commands.router import CommandResult, CommandRouter, CommandSpec

        async def scenario() -> None:
            router = CommandRouter()

            async def h(_c: str, _a: dict[str, Any]) -> CommandResult:
                return CommandResult(text="ok")

            router.register(CommandSpec(name="new", handler=h, tier="exact"))
            result = await router.dispatch("/new")
            assert result.success

        asyncio.run(scenario())

    def test_prefix_dispatch(self) -> None:
        from openlaoke.commands.router import CommandResult, CommandRouter, CommandSpec

        async def scenario() -> None:
            router = CommandRouter()

            async def h(cmd: str, args: dict[str, Any]) -> CommandResult:
                return CommandResult(text=f"got {args}")

            router.register(CommandSpec(name="model", handler=h, tier="prefix"))
            result = await router.dispatch("/model preset=opus")
            assert result.success

        asyncio.run(scenario())

    def test_unknown_command(self) -> None:
        from openlaoke.commands.router import CommandRouter

        async def scenario() -> None:
            router = CommandRouter()
            result = await router.dispatch("/nope")
            assert not result.success
            assert "unknown" in result.error

        asyncio.run(scenario())

    def test_unregister(self) -> None:
        from openlaoke.commands.router import CommandResult, CommandRouter, CommandSpec

        async def h(_c: str, _a: dict[str, Any]) -> CommandResult:
            return CommandResult(text="ok")

        router = CommandRouter()
        router.register(CommandSpec(name="x", handler=h, tier="exact"))
        assert "x" in router.list_commands()
        router.unregister("x")
        assert "x" not in router.list_commands()

    def test_make_router(self) -> None:
        from openlaoke.commands.router import make_router

        router = make_router()
        cmds = router.list_commands()
        for name in ("stop", "status", "help", "new", "dream"):
            assert name in cmds
