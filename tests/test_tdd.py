"""Tests for the TDD state machine."""

from __future__ import annotations

from openlaoke.tdd import TDDLoop, TDDPhase, TDDState, init_requirements


class TestTDDLoop:
    def test_initial_state(self) -> None:
        loop = TDDLoop()
        assert loop.current_cycle() is None
        assert not loop.finished

    def test_describe_idle(self) -> None:
        loop = TDDLoop()
        assert "idle" in loop.describe().lower()

    def test_describe_with_requirements(self) -> None:
        loop = TDDLoop(requirements=["login works", "logout works"])
        loop.cycles = [
            TDDState(cycle_id="c1", phase=TDDPhase.RED),
        ]
        text = loop.describe()
        assert "red" in text
        assert "login works" in text

    def test_red_phase_blocks_writes_to_impl(self) -> None:
        loop = TDDLoop(requirements=["x"])
        state = TDDState(cycle_id="c1", phase=TDDPhase.RED, test_path="t.py", impl_path="i.py")
        loop.cycles = [state]
        assert not loop.is_writer_allowed("i.py")
        assert loop.is_writer_allowed("t.py")
        assert loop.is_writer_allowed("unrelated.py")

    def test_green_phase_blocks_writes_to_test(self) -> None:
        loop = TDDLoop(requirements=["x"])
        state = TDDState(cycle_id="c1", phase=TDDPhase.GREEN, test_path="t.py", impl_path="i.py")
        loop.cycles = [state]
        assert loop.is_writer_allowed("i.py")
        assert not loop.is_writer_allowed("t.py")

    def test_refactor_allows_either(self) -> None:
        loop = TDDLoop(requirements=["x"])
        state = TDDState(cycle_id="c1", phase=TDDPhase.REFACTOR, test_path="t.py", impl_path="i.py")
        loop.cycles = [state]
        assert loop.is_writer_allowed("t.py")
        assert loop.is_writer_allowed("i.py")

    def test_advance(self) -> None:
        loop = TDDLoop(requirements=["a", "b"])
        loop.cycles = [
            TDDState(cycle_id="c1", phase=TDDPhase.RED),
            TDDState(cycle_id="c2", phase=TDDPhase.IDLE),
        ]
        assert loop.current == 0
        loop.advance()
        assert loop.current == 1
        loop.advance()
        assert loop.finished

    def test_idle_allows_everything(self) -> None:
        loop = TDDLoop()
        loop.cycles = [TDDState(cycle_id="c1", phase=TDDPhase.IDLE)]
        assert loop.is_writer_allowed("anything.py")


class TestInitRequirements:
    def test_init_starts_in_red(self) -> None:
        state = TDDState(cycle_id="c1")
        init_requirements(state, ["req1", "req2"], "test.py", "impl.py")
        assert state.phase is TDDPhase.RED
        assert state.test_path == "test.py"
        assert state.impl_path == "impl.py"
