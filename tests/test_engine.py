"""Tests for the shared agent loop (P1) with a scripted fake provider."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from openlaoke.core.engine import (
    STOP_ABORTED,
    STOP_DONE,
    STOP_ERROR,
    STOP_MAX_ITERATIONS,
    EnginePolicy,
    assistant_message,
    assistant_turn,
    execute_tool,
    run_loop,
    tool_result_message,
    verifies_artifact,
)
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.tools.read_tool import ReadTool
from openlaoke.types.core_types import TokenUsage, ToolResultBlock, ToolUseBlock


class StubTool(Tool):
    def __init__(self, name: str, *, error: bool = False) -> None:
        self.name = name
        self.error = error
        self.input_schema = {"type": "object", "properties": {}}

    async def call(self, ctx: ToolContext, **kwargs) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="ok", is_error=self.error)


class FakeAPI:
    """Returns scripted responses and records what it was asked."""

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict] = []
        self.closed = False

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


def response(content: str = "", tool_uses: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_uses=tool_uses or [])


def usage() -> TokenUsage:
    return TokenUsage(input_tokens=10, output_tokens=5)


def registry_with(*tools) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def run(script, *, registry=None, policy=None, messages=None, prompt="go"):
    app_state = create_app_state(cwd=".")
    api = FakeAPI(script)
    return (
        asyncio.run(
            run_loop(
                app_state=app_state,
                api=api,
                registry=registry or registry_with(ReadTool()),
                system_prompt="sys",
                messages=messages
                if messages is not None
                else [{"role": "user", "content": prompt}],
                policy=policy or EnginePolicy(max_iterations=5),
                model="test-model",
            )
        ),
        api,
        app_state,
    )


def test_a_single_text_turn_finishes(tmp_path) -> None:
    result, api, _state = run([(response("hello"), usage(), None)])
    assert result.stop_reason == STOP_DONE
    assert result.text == "hello"
    assert result.iterations == 1
    assert api.calls[0]["model"] == "test-model"
    assert api.calls[0]["messages"][0]["content"] == "go"


def test_tool_call_is_executed_and_result_is_attached(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": str(tmp_path / "a.txt")})
    script = [
        (response("", [tool_use]), usage(), None),
        (response("done reading"), usage(), None),
    ]
    result, _api, _state = run(script, registry=registry_with(ReadTool()))
    assert result.stop_reason == STOP_DONE
    assert result.text == "done reading"
    tool_rows = [message for message in result.messages if message.get("role") == "tool"]
    assert tool_rows and tool_rows[0]["tool_call_id"] == "t1"
    assert "alpha" in tool_rows[0]["content"]
    assistant_rows = [m for m in result.messages if m.get("role") == "assistant"]
    assert assistant_rows[0]["tool_calls"][0]["function"]["name"] == "Read"


def test_final_iteration_gets_no_tools(tmp_path) -> None:
    script = [
        (
            response("", [ToolUseBlock(id="t1", name="Read", input={"file_path": "x"})]),
            usage(),
            None,
        ),
        (response("stop"), usage(), None),
    ]
    policy = EnginePolicy(max_iterations=2, tools=[{"name": "Read"}])
    result, api, _state = run(script, policy=policy)
    assert result.stop_reason == STOP_DONE
    assert api.calls[0]["tools"] is not None
    assert api.calls[1]["tools"] is None, "the last turn must not invite more work"


def test_unknown_tool_is_reported_without_crashing(tmp_path) -> None:
    script = [
        (response("", [ToolUseBlock(id="t1", name="Nope", input={})]), usage(), None),
        (response("ok"), usage(), None),
    ]
    result, _api, _state = run(script)
    row = next(m for m in result.messages if m.get("role") == "tool")
    assert "Unknown tool" in row["content"]


def test_allow_list_blocks_other_tools(tmp_path) -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "x"})
    script = [
        (response("", [tool_use]), usage(), None),
        (response("ok"), usage(), None),
    ]
    result, _api, _state = run(script, policy=EnginePolicy(max_iterations=3, allow_tools={"Glob"}))
    row = next(m for m in result.messages if m.get("role") == "tool")
    assert "not enabled" in row["content"]


def test_permission_callback_can_refuse(tmp_path) -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "x"})
    seen: list[tuple[str, dict]] = []

    def deny(name: str, args: dict) -> bool:
        seen.append((name, args))
        return False

    script = [
        (response("", [tool_use]), usage(), None),
        (response("ok"), usage(), None),
    ]
    result, _api, _state = run(script, policy=EnginePolicy(max_iterations=3, check_tool=deny))
    assert seen == [("Read", {"file_path": "x"})]
    assert (
        "Permission denied"
        in next(m for m in result.messages if m.get("role") == "tool")["content"]
    )


def test_missing_required_argument_fails_validation(tmp_path) -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={})
    script = [
        (response("", [tool_use]), usage(), None),
        (response("ok"), usage(), None),
    ]
    result, _api, _state = run(script)
    assert (
        "Validation error" in next(m for m in result.messages if m.get("role") == "tool")["content"]
    )


def test_abort_signal_stops_before_the_next_request(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": str(tmp_path / "a.txt")})
    stop_after_first = {"stop": False}

    def should_stop() -> bool:
        return stop_after_first["stop"]

    def text_hook(_text: str) -> None:
        stop_after_first["stop"] = True

    async def scenario():
        app_state = create_app_state(cwd=str(tmp_path))
        api = FakeAPI(
            [(response("first", [tool_use]), usage(), None), (response("second"), usage(), None)]
        )
        policy = EnginePolicy(max_iterations=5, should_stop=should_stop, on_text=text_hook)
        result = await run_loop(
            app_state=app_state,
            api=api,
            registry=registry_with(ReadTool()),
            system_prompt="sys",
            messages=[{"role": "user", "content": "go"}],
            policy=policy,
        )
        return result, api

    result, api = asyncio.run(scenario())
    assert result.stop_reason == STOP_ABORTED
    assert result.text == "first"
    assert len(api.calls) == 1, "the flag was set during the first turn, so no second request"
    assert any(m.get("role") == "tool" for m in result.messages)


def test_provider_exception_becomes_an_error_result() -> None:
    result, _api, _state = run([RuntimeError("provider exploded")])
    assert result.stop_reason == STOP_ERROR
    assert "provider exploded" in result.error


def test_usage_is_accumulated_on_the_state() -> None:
    result, _api, state = run([(response("hi"), usage(), None)])
    assert result.stop_reason == STOP_DONE
    assert state.token_usage.input_tokens == 10
    assert state.token_usage.output_tokens == 5


def test_state_save_callback_sees_every_step() -> None:
    saves: list[tuple[int, str]] = []
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "nope"})
    script = [
        (response("thinking", [tool_use]), usage(), None),
        (response("done"), usage(), None),
    ]
    policy = EnginePolicy(
        max_iterations=4,
        save_state=lambda iteration, messages, parts, status: saves.append((iteration, status)),
    )
    run(script, policy=policy)
    assert len(saves) >= 3
    assert {status for _iteration, status in saves} == {"running"}


def test_execute_tool_returns_a_block_with_the_right_id(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    result = asyncio.run(
        execute_tool(
            state,
            registry_with(ReadTool()),
            ToolUseBlock(id="abc", name="Read", input={"file_path": "a.txt"}),
        )
    )
    assert result.tool_use_id == "abc"
    assert "alpha" in result.content


def test_message_shapes_are_canonical() -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a"})
    assistant = assistant_message(SimpleNamespace(content="hi", tool_uses=[tool_use]))
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["function"]["name"] == "Read"
    assert assistant["tool_calls"][0]["type"] == "function"
    assert tool_result_message("t1", "out") == {
        "role": "tool",
        "tool_call_id": "t1",
        "content": "out",
    }


def test_empty_content_is_not_included() -> None:
    assert assistant_turn("", []) == {"role": "assistant"}
    assert assistant_turn("text") == {"role": "assistant", "content": "text"}


def test_verified_artifact_forces_a_final_text_turn() -> None:
    write = StubTool("Write")
    bash = StubTool("Bash")
    script = [
        (
            response(
                "",
                [
                    ToolUseBlock(id="w1", name="Write", input={"file_path": "answer.py"}),
                    ToolUseBlock(id="b1", name="Bash", input={"command": "python answer.py"}),
                ],
            ),
            usage(),
            None,
        ),
        (response("done"), usage(), None),
    ]
    result, api, _state = run(
        script,
        registry=registry_with(write, bash),
        policy=EnginePolicy(max_iterations=5),
    )
    assert result.stop_reason == STOP_DONE
    assert result.iterations == 2
    assert api.calls[1]["tools"] is None
    assert result.text == "done"


def test_verification_helper_requires_a_runner_and_the_written_file() -> None:
    assert verifies_artifact("python answer.py", {"answer.py"})
    assert verifies_artifact("cd /tmp && python3 answer.py", {"answer.py"})
    assert not verifies_artifact("cat answer.py", {"answer.py"})
    assert not verifies_artifact("rm answer.py", {"answer.py"})
    assert not verifies_artifact("python answer.py", set())


# --------------------------------------------------------------------------- #
# text tool-call recovery, artifact nudges, limits and callbacks
# --------------------------------------------------------------------------- #
def test_a_text_tool_call_is_recovered_instead_of_ending_the_turn() -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a.py"})
    script = [
        (response('<tool_call>{"name": "Read", "input": {"file_path": "a.py"}}</tool_call>'), None, None),
        (response("done"), None, None),
    ]
    result, api, _state = run(script, registry=registry_with(StubTool("Read")))

    assert result.ok
    assert result.text == "done"
    assert any(m.get("role") == "tool" for m in result.messages)
    assert tool_use.id != ""


def test_an_unverified_script_gets_one_nudge() -> None:
    write = ToolUseBlock(id="t1", name="Write", input={"file_path": "run.py", "content": "print(1)"})
    script = [
        (response("", [write]), None, None),
        (response("all done"), None, None),
        (response("still done"), None, None),
    ]
    policy = EnginePolicy(max_iterations=6)

    result, api, _state = run(script, registry=registry_with(StubTool("Write")), policy=policy)

    nudges = [m for m in result.messages if "never ran it" in str(m.get("content"))]
    assert len(nudges) == 1
    assert "run.py" in nudges[0]["content"]
    # The nudge costs exactly one extra turn.
    assert api.calls and result.iterations == 3
    assert result.stop_reason == STOP_DONE


def test_the_nudge_can_be_switched_off() -> None:
    write = ToolUseBlock(id="t1", name="Write", input={"file_path": "run.py", "content": "x"})
    script = [(response("", [write]), None, None), (response("done"), None, None)]
    policy = EnginePolicy(max_iterations=4, nudge_unverified_artifacts=False)

    result, api, _state = run(script, registry=registry_with(StubTool("Write")), policy=policy)

    assert not any("never ran it" in str(m.get("content")) for m in result.messages)
    assert result.stop_reason == STOP_DONE


def test_a_truncated_answer_is_an_error_not_a_success() -> None:
    truncated = SimpleNamespace(content="", tool_uses=[], stop_reason="length")

    result, _api, _state = run([(truncated, None, None)])

    assert result.stop_reason == STOP_ERROR
    assert "output token limit" in result.error


def test_running_out_of_iterations_is_reported() -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a.py"})
    script = [(response("", [tool_use]), None, None)] * 3
    policy = EnginePolicy(max_iterations=2)

    result, api, _state = run(script, registry=registry_with(StubTool("Read")), policy=policy)

    assert result.stop_reason == STOP_MAX_ITERATIONS
    assert result.iterations == 2
    assert result.ok is True


def test_on_usage_receives_every_turn() -> None:
    seen: list[tuple[object, object]] = []
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a"})
    script = [
        (response("a", [tool_use]), usage(), None),
        (response("b"), usage(), None),
    ]

    from openlaoke.core.engine import run_loop
    from openlaoke.core.state import create_app_state

    asyncio.run(
        run_loop(
            app_state=create_app_state(cwd="."),
            api=FakeAPI(script),
            registry=registry_with(StubTool("Read")),
            system_prompt="sys",
            messages=[{"role": "user", "content": "go"}],
            policy=EnginePolicy(max_iterations=3),
            on_usage=lambda u, c: seen.append((u, c)),
        )
    )

    assert len(seen) == 2
    assert seen[0][0].input_tokens == 10


def test_cost_is_accumulated_when_the_provider_reports_it() -> None:
    from openlaoke.types.core_types import CostInfo

    script = [(response("hi"), usage(), CostInfo(input_cost=0.5, output_cost=0.25))]

    _result, _api, state = run(script)

    assert state.cost_info.total_cost == 0.75


def test_tool_callbacks_see_the_round_trip() -> None:
    events: list[tuple[str, str]] = []
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a"})
    policy = EnginePolicy(
        max_iterations=4,
        on_tool_start=lambda tu: events.append(("start", tu.name)),
        transform_result=lambda tu, res: ToolResultBlock(
            tool_use_id=res.tool_use_id, content="transformed", is_error=False
        ),
        on_tool_end=lambda tu, res: events.append(("end", str(res.content))),
        on_text=lambda text: events.append(("text", text)),
    )

    run(
        [(response("", [tool_use]), None, None), (response("done"), None, None)],
        registry=registry_with(StubTool("Read")),
        policy=policy,
    )

    assert events[0] == ("start", "Read")
    assert events[1] == ("end", "transformed")
    assert events[-1] == ("text", "done")


def test_a_coercion_failure_falls_back_to_the_raw_arguments() -> None:
    class Exploding:
        def __call__(self, *_a, **_k):
            raise RuntimeError("cannot coerce")

    import openlaoke.core.small_model_optimizations as smo

    original = smo.coerce_tool_args
    smo.coerce_tool_args = Exploding()
    try:
        tool = StubTool("Read")
        result = asyncio.run(
            execute_tool(
                create_app_state(cwd="."),
                registry_with(tool),
                ToolUseBlock(id="t1", name="Read", input={}),
            )
        )
    finally:
        smo.coerce_tool_args = original

    assert result.content == "ok"


def test_the_trace_and_debug_env_vars_only_add_diagnostics(tmp_path, capsys) -> None:
    import os

    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a"})
    script = [(response("hi", [tool_use]), None, None), (response("done"), None, None)]

    os.environ["OPENLAOKE_DEBUG_RAW"] = "1"
    os.environ["OPENLAOKE_TRACE_TOOLS"] = "1"
    try:
        result, _api, _state = run(script, registry=registry_with(StubTool("Read")))
    finally:
        del os.environ["OPENLAOKE_DEBUG_RAW"]
        del os.environ["OPENLAOKE_TRACE_TOOLS"]

    err = capsys.readouterr().err
    assert "[raw]" in err
    assert "[trace] step=" in err
    assert result.ok


def test_ok_is_true_only_for_done_and_max_iterations() -> None:
    from openlaoke.core.engine import STOP_ABORTED, STOP_MAX_ITERATIONS, EngineResult

    assert EngineResult(stop_reason=STOP_DONE).ok is True
    assert EngineResult(stop_reason=STOP_MAX_ITERATIONS).ok is True
    assert EngineResult(stop_reason=STOP_ABORTED).ok is False
    assert EngineResult(stop_reason=STOP_ERROR).ok is False


def test_a_broken_repair_validator_does_not_stop_the_loop(monkeypatch) -> None:
    import openlaoke.core.small_model_optimizations as smo

    monkeypatch.setattr(smo, "ToolCallValidator", type("Boom", (), {"__init__": lambda s: 1 / 0}))

    result, _api, _state = run([(response("hi"), None, None)])

    assert result.stop_reason == STOP_DONE


def test_an_identical_failing_call_is_refused_after_the_limit() -> None:
    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "missing.py"})
    script = [(response("", [tool_use]), None, None) for _ in range(5)]
    policy = EnginePolicy(max_iterations=6, max_repeat_calls=1)

    result, _api, _state = run(
        script, registry=registry_with(StubTool("Read", error=True)), policy=policy
    )

    refusals = [m for m in result.messages if "Refused:" in str(m.get("content"))]
    assert refusals
    assert "identical arguments" in refusals[0]["content"]
    assert "ok" in refusals[0]["content"]


def test_parallel_reads_survive_one_exploding_tool(tmp_path) -> None:
    def on_start(tu):
        if tu.name == "Glob":
            raise RuntimeError("boom")

    first = ToolUseBlock(id="t1", name="Read", input={"file_path": "a.py"})
    second = ToolUseBlock(id="t2", name="Glob", input={"pattern": "*.py"})
    script = [(response("", [first, second]), None, None), (response("done"), None, None)]
    policy = EnginePolicy(max_iterations=4, max_repeat_calls=0, on_tool_start=on_start)

    class ReadOnlyStub(StubTool):
        is_read_only = True

    result, _api, _state = run(
        script,
        registry=registry_with(ReadOnlyStub("Read"), ReadOnlyStub("Glob")),
        policy=policy,
    )

    assert any("Error: boom" in str(m.get("content")) for m in result.messages)
    assert result.ok


def test_a_structured_tool_result_is_json_encoded(tmp_path) -> None:
    class Structured(StubTool):
        async def call(self, ctx, **kwargs):
            return ToolResultBlock(tool_use_id=ctx.tool_use_id, content={"total": 2})

    tool_use = ToolUseBlock(id="t1", name="Read", input={"file_path": "a.py"})
    script = [(response("", [tool_use]), None, None), (response("done"), None, None)]

    result, _api, _state = run(script, registry=registry_with(Structured("Read")))

    assert any(m.get("content") == '{"total": 2}' for m in result.messages)
