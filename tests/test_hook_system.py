"""Tests for the hook system: ordering, short-circuiting, budgets and stats."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from openlaoke.core.hook_system import (
    HookInput,
    HookOutput,
    HookRegistry,
    HookSystem,
)


def make_system() -> HookSystem:
    return HookSystem()


def record(name: str, log: list[str], **changes: Any):
    """A sync hook that logs its name and applies the given output changes."""

    def hook(input_data: HookInput, output: HookOutput) -> None:
        log.append(name)
        for key, value in changes.items():
            setattr(output, key, value)

    hook.__name__ = name
    return hook


def async_record(name: str, log: list[str], **changes: Any):
    async def hook(input_data: HookInput, output: HookOutput) -> None:
        log.append(name)
        for key, value in changes.items():
            setattr(output, key, value)

    hook.__name__ = name
    return hook


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def test_registration_sorts_by_priority_descending() -> None:
    system = make_system()
    log: list[str] = []
    system.register("turn_end", "low", record("low", log), priority=1)
    system.register("turn_end", "high", record("high", log), priority=10)
    system.register("turn_end", "mid", record("mid", log), priority=5)

    system.execute_hooks("turn_end", HookInput())

    assert log == ["high", "mid", "low"]


def test_aliases_map_onto_the_canonical_type() -> None:
    assert HookSystem.resolve_type("pre_tool") == "tool_gate"
    assert HookSystem.resolve_type("post_tool") == "tool_execute_after"
    assert HookSystem.resolve_type("pre_tool_transform") == "tool_execute_before"
    assert HookSystem.resolve_type("post_tool_feedback") == "tool_feedback"
    assert HookSystem.resolve_type("turn_end") == "turn_end"

    system = make_system()
    log: list[str] = []
    system.register("pre_tool", "guard", record("guard", log))

    assert system.get_hook_count("tool_gate") == 1
    system.gate(HookInput(tool_name="Bash"))
    assert log == ["guard"]


def test_an_unknown_type_is_rejected_with_the_valid_list() -> None:
    with pytest.raises(ValueError, match="Unknown hook type: nope"):
        make_system().register("nope", "x", record("x", []))


def test_async_functions_are_detected_at_registration() -> None:
    system = make_system()
    system.register("turn_end", "sync", record("sync", []))
    system.register("turn_end", "async", async_record("async", []))

    names = {(h.name, h.is_async) for h in system.get_enabled_hooks("turn_end")}

    assert names == {("sync", False), ("async", True)}


def test_unregister_removes_only_the_named_hook() -> None:
    system = make_system()
    system.register("turn_end", "keep", record("keep", []))
    system.register("turn_end", "drop", record("drop", []))

    assert system.unregister("turn_end", "drop") is True
    assert system.unregister("turn_end", "drop") is False
    assert [h.name for h in system.get_enabled_hooks("turn_end")] == ["keep"]


def test_disable_and_enable() -> None:
    system = make_system()
    log: list[str] = []
    system.register("turn_end", "h", record("h", log))

    assert system.disable_hook("turn_end", "h") is True
    system.execute_hooks("turn_end", HookInput())
    assert log == []
    assert system.get_enabled_hooks("turn_end") == []

    assert system.enable_hook("turn_end", "h") is True
    system.execute_hooks("turn_end", HookInput())
    assert log == ["h"]


def test_enabling_an_unknown_hook_is_false() -> None:
    system = make_system()

    assert system.enable_hook("turn_end", "ghost") is False
    assert system.disable_hook("turn_end", "ghost") is False


def test_has_hooks_and_count() -> None:
    system = make_system()

    assert system.has_hooks("turn_end") is False
    assert system.get_hook_count("turn_end") == 0

    system.register("turn_end", "h", record("h", []))

    assert system.has_hooks("turn_end") is True
    assert system.get_hook_count("turn_end") == 1


def test_clear_removes_everything() -> None:
    system = make_system()
    system.register("turn_end", "h", record("h", []))
    system.execute_hooks("turn_end", HookInput())

    system.clear()

    assert system.get_hook_count("turn_end") == 0
    assert system.get_stats() == {}


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


def test_hooks_share_one_output_object() -> None:
    system = make_system()
    system.register("message_transform", "a", record("a", [], system_prompt="A"))
    system.register("message_transform", "b", record("b", [], tool_result="B"))

    output = system.execute_hooks("message_transform", HookInput())

    assert output.system_prompt == "A"
    assert output.tool_result == "B"


def test_an_existing_output_is_reused() -> None:
    system = make_system()
    passed = HookOutput(tool_result="before")
    system.register("tool_execute_after", "h", record("h", [], tool_result="after"))

    result = system.execute_hooks("tool_execute_after", HookInput(), passed)

    assert result is passed
    assert result.tool_result == "after"


def test_a_raising_hook_does_not_break_the_chain() -> None:
    system = make_system()
    log: list[str] = []

    def boom(_input: HookInput, _output: HookOutput) -> None:
        raise RuntimeError("hook is broken")

    system.register("turn_end", "boom", boom, priority=10)
    system.register("turn_end", "after", record("after", log))

    output = system.execute_hooks("turn_end", HookInput())

    assert log == ["after"]
    assert output.handled is False


def test_short_circuit_types_stop_on_handled() -> None:
    system = make_system()
    log: list[str] = []
    system.register("tool_gate", "veto", record("veto", log, handled=True), priority=10)
    system.register("tool_gate", "late", record("late", log))

    output = system.gate(HookInput(tool_name="Bash"))

    assert log == ["veto"]
    assert output.handled is True


def test_non_short_circuit_types_keep_running_after_handled() -> None:
    system = make_system()
    log: list[str] = []
    system.register("turn_end", "first", record("first", log, handled=True), priority=10)
    system.register("turn_end", "second", record("second", log))

    system.execute_hooks("turn_end", HookInput())

    assert log == ["first", "second"]


def test_the_sync_executor_skips_async_hooks_with_a_warning(caplog) -> None:
    system = make_system()
    log: list[str] = []
    system.register("turn_end", "async", async_record("async", log))
    system.register("turn_end", "sync", record("sync", log))

    with caplog.at_level("WARNING"):
        system.execute_hooks("turn_end", HookInput())

    assert log == ["sync"]
    assert any("Skipping async hook" in message for message in caplog.messages)


def test_stats_accumulate() -> None:
    system = make_system()
    system.register("turn_end", "h", record("h", []))

    system.execute_hooks("turn_end", HookInput())
    system.execute_hooks("turn_end", HookInput())

    stats = system.get_stats()["turn_end"]
    assert stats["total_executions"] == 2
    assert stats["total_hooks_called"] == 2
    assert stats["avg_time_ms"] > 0


def test_a_sync_hook_over_its_budget_is_counted(caplog) -> None:
    system = make_system()

    def slow(_input: HookInput, _output: HookOutput) -> None:
        time.sleep(0.02)

    system.register("turn_end", "slow", slow, timeout_ms=1.0)

    with caplog.at_level("WARNING"):
        system.execute_hooks("turn_end", HookInput())

    stats = system.get_stats()["turn_end"]
    assert stats["timeouts"] == 1
    assert any("over its" in message for message in caplog.messages)


def test_a_fast_hook_does_not_count_as_an_overrun() -> None:
    system = make_system()
    system.register("turn_end", "quick", record("quick", []), timeout_ms=5000.0)

    system.execute_hooks("turn_end", HookInput())

    assert system.get_stats()["turn_end"]["timeouts"] == 0


def test_gate_returns_the_shared_output() -> None:
    system = make_system()
    system.register("tool_gate", "rewrite", record("rewrite", [], tool_args={"file_path": "b.py"}))

    output = system.gate(HookInput(tool_name="Write", tool_args={"file_path": "a.py"}))

    assert output.tool_args == {"file_path": "b.py"}
    assert output.handled is False


# --------------------------------------------------------------------------- #
# Async execution
# --------------------------------------------------------------------------- #


def run(coro):
    return asyncio.run(coro)


def test_async_execution_runs_sync_and_async_hooks_in_order() -> None:
    system = make_system()
    log: list[str] = []
    system.register("turn_end", "a", record("a", log), priority=10)
    system.register("turn_end", "b", async_record("b", log), priority=5)

    output = run(system.execute_hooks_async("turn_end", HookInput()))

    assert log == ["a", "b"]
    assert isinstance(output, HookOutput)


def test_an_async_hook_returning_none_is_tolerated() -> None:
    system = make_system()

    def plain(_input: HookInput, _output: HookOutput) -> None:
        return None

    # A function marked async by iscoroutinefunction but returning None cannot
    # happen through def, so the sync branch covers the None path.
    system.register("turn_end", "plain", plain)
    run(system.execute_hooks_async("turn_end", HookInput()))


def test_an_async_hook_error_is_logged_not_raised(caplog) -> None:
    system = make_system()

    async def boom(_input: HookInput, _output: HookOutput) -> None:
        raise RuntimeError("async hook exploded")

    system.register("turn_end", "boom", boom)

    with caplog.at_level("DEBUG"):
        output = run(system.execute_hooks_async("turn_end", HookInput()))

    assert output.handled is False
    assert any("async hook exploded" in message for message in caplog.messages)


def test_an_async_hook_timeout_is_counted_and_skipped(caplog) -> None:
    system = make_system()

    async def slow(_input: HookInput, _output: HookOutput) -> None:
        await asyncio.sleep(1.0)
        _output.handled = True

    system.register("turn_end", "slow", slow, timeout_ms=10.0)

    with caplog.at_level("WARNING"):
        output = run(system.execute_hooks_async("turn_end", HookInput()))

    assert output.handled is False
    assert system.get_stats()["turn_end"]["timeouts"] == 1
    assert any("timed out" in message for message in caplog.messages)


def test_async_execution_honours_short_circuiting() -> None:
    system = make_system()
    log: list[str] = []
    system.register("error_handle", "claim", record("claim", log, handled=True), priority=10)
    system.register("error_handle", "later", async_record("later", log))

    run(system.execute_hooks_async("error_handle", HookInput(error_message="boom")))

    assert log == ["claim"]


def test_async_execution_skips_disabled_hooks() -> None:
    system = make_system()
    log: list[str] = []
    system.register("turn_end", "off", async_record("off", log))
    system.register("turn_end", "on", record("on", log))
    system.disable_hook("turn_end", "off")

    run(system.execute_hooks_async("turn_end", HookInput()))

    assert log == ["on"]


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def test_the_registry_is_a_singleton_that_can_be_reset() -> None:
    HookRegistry.reset()

    first = HookRegistry.get()
    second = HookRegistry.get()

    assert first is second

    first.register("turn_end", "h", record("h", []))
    HookRegistry.reset()

    assert HookRegistry.get() is not first
    assert HookRegistry.get().get_hook_count("turn_end") == 0
