"""Tests for the controller and command router."""

from __future__ import annotations

import asyncio
from typing import Any

from openlaoke.bus.runtime_events import EventKind
from openlaoke.control.commands import (
    ForkCommand,
    NewSessionCommand,
    QuickAddCommand,
    RewindCommand,
    SetPlanModeCommand,
    SubmitCommand,
)
from openlaoke.control.orchestrator import Orchestrator
from openlaoke.control.phase import RunResult, TurnPhase


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

    def test_dispatch_rewind(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            result = await orch.dispatch("s1", RewindCommand(target=3, scope="code+conversation"))
            assert result["rewound"] is True
            assert result["target_turn"] == 3

        asyncio.run(scenario())

    def test_dispatch_fork(self) -> None:
        async def scenario() -> None:
            orch = Orchestrator()
            new_id = await orch.dispatch("s1", ForkCommand(target=2))
            assert new_id in orch.active_sessions()

        asyncio.run(scenario())

    def test_cancel_no_turn(self) -> None:
        orch = Orchestrator()
        assert orch.cancel("s1") is False


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
