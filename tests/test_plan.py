"""Tests for the plan-mode system."""

from __future__ import annotations

from openlaoke.plan.heuristic import PlanHeuristic, should_auto_plan
from openlaoke.plan.state import (
    Evidence,
    Ledger,
    PlanState,
    ReadinessCheck,
    plan_mode_block_message,
)
from openlaoke.plan.storm_breaker import StormBreaker


class TestHeuristic:
    def test_short_text_low_score(self) -> None:
        score = PlanHeuristic("fix the bug").evaluate()
        assert score.score < 3

    def test_long_numbered_text(self) -> None:
        text = (
            "Implement the new feature:\n"
            "1. Add a new database table\n"
            "2. Create an API endpoint\n"
            "3. Add a frontend page"
        )
        score = PlanHeuristic(text).evaluate()
        assert score.score >= 3

    def test_complex_terms(self) -> None:
        score = PlanHeuristic("Please refactor the API service").evaluate()
        assert any("complex" in r for r in score.reasons)

    def test_references(self) -> None:
        text = "Update src/foo.py and tests/test_foo.py"
        score = PlanHeuristic(text).evaluate()
        assert any("references" in r for r in score.reasons)

    def test_off_mode_returns_false(self) -> None:
        assert should_auto_plan("Implement everything 1. 2. 3.", mode="off") is False

    def test_on_mode_returns_true(self) -> None:
        assert should_auto_plan("anything", mode="on") is True

    def test_ask_mode_borderline(self) -> None:
        text = "Implement the system"
        assert isinstance(should_auto_plan(text, mode="ask"), bool)


class TestPlanState:
    def test_begin_approve_exit(self) -> None:
        state = PlanState()
        state.begin_plan("plan text")
        assert state.enabled
        assert state.plan_text == "plan text"
        assert not state.is_writer_allowed()

        state.approve()
        assert not state.enabled
        assert state.auto_approve
        assert state.is_writer_allowed()

        state.exit()
        assert not state.enabled
        assert not state.auto_approve

    def test_block_message_mentions_tool(self) -> None:
        msg = plan_mode_block_message("write_file")
        assert "write_file" in msg
        assert "read-only" in msg


class TestLedger:
    def test_latest_write(self) -> None:
        ledger = Ledger(session_id="s1")
        ledger.record(Evidence(tool_name="read_file", success=True, read_only=True))
        ledger.record(Evidence(tool_name="write_file", success=True, read_only=False, path="/x"))
        assert ledger.latest_write() is not None
        assert ledger.latest_write().path == "/x"

    def test_no_write_yet(self) -> None:
        ledger = Ledger(session_id="s1")
        ledger.record(Evidence(tool_name="read_file", success=True, read_only=True))
        assert ledger.latest_write() is None

    def test_has_project_check_after_write(self) -> None:
        ledger = Ledger(session_id="s1")
        ledger.record(Evidence(tool_name="write_file", success=True, read_only=False))
        assert not ledger.has_project_check_after_write()
        ledger.record(
            Evidence(
                tool_name="project_check",
                success=True,
                read_only=True,
                project_check="pytest",
            )
        )
        assert ledger.has_project_check_after_write()

    def test_has_complete_step_after_write(self) -> None:
        ledger = Ledger(session_id="s1")
        ledger.record(Evidence(tool_name="write_file", success=True, read_only=False))
        assert not ledger.has_complete_step_after_write()
        ledger.record(
            Evidence(
                tool_name="complete_step",
                success=True,
                read_only=True,
                complete_step=True,
            )
        )
        assert ledger.has_complete_step_after_write()


class TestReadinessCheck:
    def test_no_missing_evidence_when_no_write(self) -> None:
        ledger = Ledger(session_id="s1")
        check = ReadinessCheck()
        assert check.missing_evidence(ledger) == []

    def test_missing_complete_step(self) -> None:
        ledger = Ledger(session_id="s1")
        ledger.record(Evidence(tool_name="write_file", success=True, read_only=False))
        check = ReadinessCheck(require_complete_step=True)
        missing = check.missing_evidence(ledger)
        assert "complete_step" in missing

    def test_missing_project_check(self) -> None:
        ledger = Ledger(session_id="s1")
        ledger.record(Evidence(tool_name="write_file", success=True, read_only=False))
        check = ReadinessCheck(project_checks=[{"name": "lint"}])
        missing = check.missing_evidence(ledger)
        assert any("lint" in m for m in missing)


class TestStormBreaker:
    def test_no_fire_below_threshold(self) -> None:
        breaker = StormBreaker(threshold=3)
        assert not breaker.record("s1", "bash", "Error: permission denied")
        assert not breaker.record("s1", "bash", "Error: permission denied")
        assert breaker.record("s1", "bash", "Error: permission denied")

    def test_fire_at_threshold(self) -> None:
        breaker = StormBreaker(threshold=3)
        for _ in range(2):
            breaker.record("s1", "bash", "Error: permission denied")
        assert breaker.record("s1", "bash", "Error: permission denied")

    def test_different_errors_dont_fire(self) -> None:
        breaker = StormBreaker(threshold=3)
        breaker.record("s1", "bash", "Error: permission denied")
        breaker.record("s1", "bash", "Error: not found")
        breaker.record("s1", "bash", "Error: timeout")
        assert not breaker.record("s1", "bash", "Error: not found")

    def test_only_fires_once_per_error_class(self) -> None:
        breaker = StormBreaker(threshold=3)
        for _ in range(2):
            breaker.record("s1", "bash", "Error: permission denied")
        assert breaker.record("s1", "bash", "Error: permission denied")
        assert not breaker.record("s1", "bash", "Error: permission denied")

    def test_reset_session(self) -> None:
        breaker = StormBreaker(threshold=3)
        for _ in range(3):
            breaker.record("s1", "bash", "Error: permission denied")
        breaker.reset("s1")
        assert not breaker.record("s1", "bash", "Error: permission denied")

    def test_message_format(self) -> None:
        breaker = StormBreaker(threshold=3)
        for _ in range(3):
            breaker.record("s1", "bash", "Error: permission denied")
        msg = breaker.message("bash", "Error: permission denied", 3)
        assert "loop guard" in msg
        assert "bash" in msg
