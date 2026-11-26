"""Behavioral tests for REPL._run_api_loop (the interactive agent loop).

The REPL had zero coverage, so this file builds a deterministic harness that
drives the real loop with a fake provider stream, a real AppState, a real tool
registry with fake tools, and a fake console. It exists to pin the loop's
orchestration (stream accumulation, tool dispatch, repeat-breaking, parallel
reads, DONE/stop handling, error paths) before refactoring it, so behaviour is
provably preserved.
"""

from __future__ import annotations

import asyncio
from io import StringIO

from rich.console import Console

from openlaoke.core.cache_monitor import CacheMonitor
from openlaoke.core.repl import REPL
from openlaoke.core.result_ledger import ResultLedger
from openlaoke.core.small_model_optimizations import (
    ReadLoopTracker,
    TerminalOutputCompressor,
    ToolCallValidator,
)
from openlaoke.core.state import AppState
from openlaoke.core.tool import Tool, ToolRegistry
from openlaoke.types.core_types import (
    PermissionMode,
    StreamChunk,
    StreamEventType,
    ToolResultBlock,
)


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeTool(Tool):
    def __init__(
        self, name: str, *, readonly: bool = True, result: str = "ok", is_error: bool = False
    ):
        self.name = name
        self.description = name
        self.input_schema = {"type": "object", "properties": {}}
        self.is_read_only = readonly
        self._result = result
        self._is_error = is_error
        self.calls: list[dict] = []

    async def call(self, ctx, **kwargs):
        self.calls.append(kwargs)
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id, content=self._result, is_error=self._is_error
        )


class FakeAPI:
    """Serves a pre-scripted list of turns; each turn is a list of StreamChunk."""

    config = None

    def __init__(self, turns):
        self._turns = turns
        self.turn_index = 0
        self.send_calls = 0
        self.close_called = False
        self.requests: list[list[dict]] = []

    async def stream_message(self, **kwargs):
        self.requests.append([dict(m) for m in kwargs.get("messages", [])])
        chunks = self._turns[self.turn_index] if self.turn_index < len(self._turns) else []
        self.turn_index += 1
        for ch in chunks:
            if isinstance(ch, BaseException):
                raise ch
            yield ch

    async def send_message(self, **_kwargs):
        self.send_calls += 1
        self.turn_index += 1
        return None, None, None

    async def close(self):
        self.close_called = True


class FakeHooks:
    def has_hooks(self, _name):
        return False

    def execute_hooks(self, *_a, **_k):
        return None

    async def execute_hooks_async(self, *_a, **_k):
        return None

    def gate(self, *_a, **_k):
        return None


class FakeTheme:
    def color(self, _name):
        return "white"

    def style(self, _name):
        return "white"

    def format_text(self, text, _style_name):
        from rich.text import Text

        return Text(str(text))


class FakeCacheGuard:
    system_prompt = "SYSTEM PROMPT"

    def ensure_session_context(self, model=""):
        return ""

    @staticmethod
    def apply_cache_markers(messages):
        return messages


def make_repl(
    turns, tools=None, *, harness_mode="balanced", max_steps=0, running=True, model="gpt-4o"
):
    app = AppState(session_id="test-session", cwd="/tmp")
    app.session_config.model = model  # default large -> minimal guard interference
    app.harness_mode = harness_mode
    if max_steps:
        app.max_steps = max_steps
    app.permission_config.mode = PermissionMode.BYPASS  # never prompt
    app._persist_path = None  # _persist() becomes a no-op

    r = REPL.__new__(REPL)
    r.app_state = app
    r.console = Console(file=StringIO(), force_terminal=False, width=123, color_system=None)
    r.registry = ToolRegistry()
    for t in tools or []:
        r.registry.register(t)
    r.registry.freeze()
    r.api = FakeAPI(turns)
    r._running = running
    r._last_thinking = ""
    r._thinking_duration = 0.0
    r._turn_start = 0.0
    r._artifact_written = set()
    r._artifact_verified = False
    r._force_final = False
    r._active_tasks = set()
    r._current_task_id = None
    r._theme = FakeTheme()
    r._read_loop_tracker = ReadLoopTracker()
    r._guard = None
    r._budget = None
    r._ledger = ResultLedger()
    r._poke_budget = 3
    r._poke_signature = ""
    r._output_compressor = TerminalOutputCompressor()
    r._tool_validator = ToolCallValidator()
    r._tool_validator.set_tools(r.registry)
    r._hook_system = FakeHooks()
    r._world_sensor = None
    r._cache_guard = FakeCacheGuard()
    r._cache_monitor = CacheMonitor()
    r._mcp_runtime = None
    r._scheduler_task = None
    r._last_usage = None
    r._agent_task = None
    r._interrupt_requested = False
    r._input_queue = []
    r._notified_tasks = set()
    # Isolate helpers that would touch disk / unrelated subsystems.
    r._memory_digest = lambda: ""
    r._todo_auto_continue = lambda _messages: False
    r._patch_dangling_tool_calls = lambda: None
    app._tool_registry = r.registry
    return r


def text(s: str) -> StreamChunk:
    return StreamChunk(event_type=StreamEventType.TEXT, text=s)


def tool_call(cid: str, name: str, args: str = '{"intent": "test"}') -> StreamChunk:
    return StreamChunk(
        event_type=StreamEventType.TOOL_CALL_START,
        tool_call_id=cid,
        tool_call_name=name,
        tool_call_arguments=args,
    )


def run(repl: REPL):
    asyncio.run(repl._run_api_loop())


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_text_only_single_turn():
    r = make_repl([[text("hello "), text("world")]])
    run(r)
    assert r.api.turn_index == 1
    # One assistant message recorded in history.
    assistants = [m for m in r.app_state.messages if getattr(m, "role", "") == "assistant"]
    assert len(assistants) == 1
    assert "hello world" in assistants[0].content


def test_tool_call_then_done_executes_tool():
    echo = FakeTool("Echo")
    r = make_repl([[tool_call("c1", "Echo")], [text("all done")]], tools=[echo])
    run(r)
    assert len(echo.calls) == 1
    assert r.api.turn_index == 2  # tool turn + final turn
    # A tool result message must be in the conversation built for the model.
    # (It lives in the local `messages` list, but the tool also recorded a call.)


def test_repeat_breaker_caps_identical_calls():
    # Same identical call five turns in a row, then a text turn.
    turns = [[tool_call("c1", "Echo")] for _ in range(5)] + [[text("done")]]
    echo = FakeTool("Echo")
    r = make_repl(turns, tools=[echo], harness_mode="balanced")  # balanced -> max_repeat_calls=3
    run(r)
    # After the 4th identical call the loop refuses, so at most 3 executions.
    assert len(echo.calls) == 3


def test_parallel_readonly_batch_runs_both():
    a = FakeTool("ReadA", readonly=True)
    b = FakeTool("ReadB", readonly=True)
    turn0 = [tool_call("c1", "ReadA"), tool_call("c2", "ReadB")]
    r = make_repl([turn0, [text("done")]], tools=[a, b])
    run(r)
    assert len(a.calls) == 1 and len(b.calls) == 1


def test_done_stops_loop():
    r = make_repl([[text("DONE")]])
    run(r)
    assert r.api.turn_index == 1


def test_empty_response_then_stop():
    # A turn with no chunks: nothing to do, loop should stop without crashing.
    r = make_repl([[]])
    run(r)
    assert r.api.turn_index == 1


def test_stream_error_is_reported_not_raised():
    r = make_repl([[text("partial"), RuntimeError("boom")]])
    run(r)  # must not raise
    assert r.api.turn_index == 1


def test_max_steps_reached_without_tool_stop():
    # Always asks for a tool; balanced max_steps=50 would be long, so pin max_steps=2.
    turns = [[tool_call(f"c{i}", "Echo")] for i in range(10)]
    echo = FakeTool("Echo")
    r = make_repl(turns, tools=[echo], max_steps=2)
    run(r)
    assert r.api.turn_index == 2  # capped by max_steps


def test_not_running_skips_loop():
    r = make_repl([[text("should not run")]], running=False)
    run(r)
    assert r.api.turn_index == 0


def test_artifact_gate_forces_final_after_verify():
    # Write a file, run it (verifies), then the gate should force a final
    # text-only turn and stop.
    w = FakeTool("Write")
    b = FakeTool("Bash")
    turns = [
        [tool_call("c1", "Write", '{"intent": "t", "file_path": "x.py"}')],
        [tool_call("c2", "Bash", '{"intent": "t", "command": "python x.py"}')],
        [text("finished")],
    ]
    r = make_repl(turns, tools=[w, b])
    run(r)
    assert len(w.calls) == 1 and len(b.calls) == 1
    assert r.api.turn_index == 3  # write turn, run turn, forced final turn


def test_stream_provider_turn_captures_reasoning():
    from openlaoke.types.core_types import StreamChunk, StreamEventType

    r = make_repl([])
    r.api._turns = [
        [
            StreamChunk(event_type=StreamEventType.REASONING, text="think "),
            StreamChunk(event_type=StreamEventType.REASONING, text="hard"),
        ]
    ]
    turn = asyncio.run(r._stream_provider_turn(system_prompt="s", messages=[], tools=None))
    assert turn.reasoning == "think hard"
    assert turn.token_count == 0 and turn.reasoning_count == 2
    assert turn.stream_error is None


def test_prepare_turn_context_prunes_long_history():
    r = make_repl([])
    msgs = []
    for i in range(20):
        msgs.append({"role": "user", "content": f"u{i} " + "x" * 400})
        msgs.append({"role": "assistant", "content": f"a{i} " + "y" * 400})
    out_msgs, tools, model_size = r._prepare_turn_context(msgs, "sys", None, 8192)
    assert isinstance(out_msgs, list)
    assert isinstance(tools, list)
    assert model_size in ("tiny", "small", "medium", "large")


def test_history_to_messages_shapes():
    from openlaoke.types.core_types import (
        AssistantMessage,
        MessageRole,
        SystemMessage,
        ToolUseBlock,
        UserMessage,
    )

    r = make_repl([])
    r.app_state.messages = [
        UserMessage(role=MessageRole.USER, content="hi"),
        AssistantMessage(
            role=MessageRole.ASSISTANT,
            content="ok",
            tool_uses=[ToolUseBlock(id="t1", name="Read", input={"file_path": "a"})],
        ),
        SystemMessage(role=MessageRole.SYSTEM, content="result", tool_use_id="t1"),
    ]
    out = r._history_to_messages()
    assert out[0] == {"role": "user", "content": "hi"}
    assert out[1]["role"] == "assistant"
    assert out[1]["tool_calls"][0]["id"] == "t1"
    assert out[1]["tool_calls"][0]["function"]["name"] == "Read"
    assert out[2] == {"role": "tool", "tool_call_id": "t1", "content": "result"}


def test_plan_response_triggers_retry():
    # A clear "I will now..." promise with no tool call should be retried,
    # then the next turn's plain answer ends the loop.
    turns = [[text("I will now create the file.")], [text("all finished")]]
    r = make_repl(turns)
    run(r)
    assert r.api.turn_index == 2
    retried = any(
        "Do NOT describe steps" in m.get("content", "") for req in r.api.requests for m in req
    )
    assert retried


def test_queued_input_is_injected_mid_run():
    r = make_repl([[text("ok")]])
    r._input_queue.append("please also do X")
    run(r)
    injected = any(m.get("content") == "please also do X" for req in r.api.requests for m in req)
    assert injected


def test_runtime_context_injected_for_small_model():
    # gemma-3-1b -> tiny -> small-model guidance is non-empty, so the runtime
    # context block must be appended as a system-injected message.
    r = make_repl([[text("done")]], model="gemma-3-1b")
    run(r)
    assert r.api.requests
    assert any(m.get("system_injected") for m in r.api.requests[0])


# --------------------------------------------------------------------------- #
# streamed turns: usage, display refresh, transport errors
# --------------------------------------------------------------------------- #
def usage_chunk(prompt=11, completion=7):
    from openlaoke.types.core_types import CostInfo, StreamChunk, StreamEventType, TokenUsage

    return StreamChunk(
        event_type=StreamEventType.USAGE,
        usage=TokenUsage(input_tokens=prompt, output_tokens=completion),
        cost=CostInfo(input_cost=0.5, output_cost=0.25),
    )


def test_stream_provider_turn_records_usage_and_cost():
    r = make_repl([[text("hi"), usage_chunk()]])
    turn = asyncio.run(r._stream_provider_turn(system_prompt="s", messages=[], tools=None))

    assert turn.content == "hi"
    assert turn.usage.input_tokens == 11
    assert turn.usage.output_tokens == 7
    assert turn.cost.total_cost == 0.75


def test_stream_provider_turn_reports_an_http_error_with_its_body():
    import httpx

    r = make_repl([])
    request = httpx.Request("POST", "https://api.example.com/v1/chat")
    response = httpx.Response(429, text="  rate limited  ", request=request)
    r.api._turns = [[httpx.HTTPStatusError("boom", request=request, response=response)]]

    turn = asyncio.run(r._stream_provider_turn(system_prompt="s", messages=[], tools=None))

    assert turn.stream_error == "API 429: rate limited"
    assert turn.content == ""


def test_stream_provider_turn_reports_an_http_error_without_a_body():
    import httpx

    r = make_repl([])
    request = httpx.Request("POST", "https://api.example.com/v1/chat")
    response = httpx.Response(503, content=b"", request=request)
    r.api._turns = [[httpx.HTTPStatusError("boom", request=request, response=response)]]

    turn = asyncio.run(r._stream_provider_turn(system_prompt="s", messages=[], tools=None))

    assert turn.stream_error == "API 503"


def test_stream_provider_turn_reports_a_generic_failure():
    r = make_repl([])
    r.api._turns = [[RuntimeError("socket vanished")]]

    turn = asyncio.run(r._stream_provider_turn(system_prompt="s", messages=[], tools=None))

    assert turn.stream_error == "socket vanished"


# --------------------------------------------------------------------------- #
# loop: empty replies, inline tool calls, reasoning, API errors, cancellation
# --------------------------------------------------------------------------- #
def turn(**fields):
    from openlaoke.core.repl import StreamedTurn

    base = StreamedTurn()
    for key, value in fields.items():
        setattr(base, key, value)
    return base


def test_a_silent_model_is_called_out_instead_of_hanging():
    r = make_repl([])
    r._stream_provider_turn = lambda **_k: _return(turn(elapsed=6.0))

    run(r)

    assert "Model returned no output" in r.console.file.getvalue()
    assert r.api.turn_index == 0


def _return(value):
    async def _coro():
        return value

    return _coro()


def test_inline_tool_calls_in_prose_are_recovered():
    from openlaoke.types.core_types import ToolUseBlock

    tool = FakeTool("Read", readonly=True, result="contents")
    r = make_repl([], tools=[tool])
    scripted = [
        turn(
            content='let me look <tool_call>{"name": "Read", "args": {"file_path": "a"}}</tool_call>'
        ),
        turn(content="DONE"),
    ]
    r._stream_provider_turn = lambda **_k: _return(scripted.pop(0))
    r._parse_inline_tool_calls = lambda _t: [
        ToolUseBlock(id="c1", name="Read", input={"file_path": "a"})
    ]
    r._strip_tool_calls = lambda _t: "let me look"

    run(r)

    assert tool.calls == [{"file_path": "a"}]


def test_a_failed_inline_parse_asks_the_model_to_try_again():
    r = make_repl([])
    scripted = [turn(content="<tool_call>not json</tool_call>"), turn(content="DONE")]
    seen: list[list[dict]] = []

    def stream(**_k):
        seen.append(list(_k.get("messages") or []))
        return _return(scripted.pop(0) if scripted else turn(content="DONE"))

    r._stream_provider_turn = stream
    r._parse_inline_tool_calls = lambda _t: []

    class Guard:
        model_size = "large"
        max_parse_failures = 3
        consecutive_parse_failures = 0

        def check_after_api_call(self, *_a):
            return ""

        def notify_parse_failure(self, _text):
            Guard.consecutive_parse_failures += 1
            return "use the tool_call format"

        def notify_parse_success(self):
            return None

    r._guard = Guard()

    run(r)

    # The loop builds its own guard from the model size on the next iteration,
    # so match the text that guard produces rather than the stub's.
    assert any(
        "tool call format was incorrect" in str(m.get("content")) for req in seen for m in req
    )
    # The nudge is only useful if the model gets another turn to act on it.
    assert len(seen) == 2
    assert "(auto-retry: that tool call could not be parsed)" in r.console.file.getvalue()


def test_a_model_that_keeps_malforming_tool_calls_is_not_retried_forever():
    r = make_repl([])
    scripted = [turn(content="<tool_call>not json</tool_call>") for _ in range(20)]
    seen: list[list[dict]] = []

    def stream(**_k):
        seen.append(list(_k.get("messages") or []))
        return _return(scripted.pop(0) if scripted else turn(content="DONE"))

    r._stream_provider_turn = stream
    r._parse_inline_tool_calls = lambda _t: []

    run(r)

    # The real guard gives up after ``max_parse_failures`` attempts, so the loop
    # must stop rather than burn the whole scripted budget.
    assert len(seen) == r._guard.max_parse_failures
    assert r.console.file.getvalue().count("could not be parsed") == r._guard.max_parse_failures - 1


def test_reasoning_is_remembered_for_the_next_turn():
    r = make_repl([])
    r._stream_provider_turn = lambda **_k: _return(turn(content="answer", reasoning="why"))
    shown = []
    r._display_thinking_inline = lambda text: shown.append(text)

    run(r)

    assert r._last_thinking == "why"
    assert r.app_state.last_thinking == "why"
    assert shown == ["why"]


def test_an_api_error_prints_the_json_message_and_stops():
    import httpx

    r = make_repl([])
    request = httpx.Request("POST", "https://api.example.com/v1/chat")
    response = httpx.Response(
        400, json={"error": {"message": "bad model"}}, request=request
    )
    error = httpx.HTTPStatusError("boom", request=request, response=response)
    r._stream_provider_turn = lambda **_k: _raise(error)

    run(r)

    text_out = r.console.file.getvalue()
    assert "API Error:" in text_out
    assert "bad model" in text_out


def test_an_api_error_with_a_non_json_body_prints_the_body():
    import httpx

    r = make_repl([])
    request = httpx.Request("POST", "https://api.example.com/v1/chat")
    response = httpx.Response(500, text="upstream exploded", request=request)
    error = httpx.HTTPStatusError("boom", request=request, response=response)
    r._stream_provider_turn = lambda **_k: _raise(error)

    run(r)

    assert "upstream exploded" in r.console.file.getvalue()


def test_a_cancelled_turn_preserves_the_context():
    r = make_repl([])
    patched = []
    r._patch_dangling_tool_calls = lambda: patched.append(True)
    r.api._turns = [[asyncio.CancelledError()]]

    run(r)

    assert patched == [True]
    assert r._interrupt_requested is True
    assert "Interrupted" in r.console.file.getvalue()


def _raise(error):
    async def _coro():
        raise error

    return _coro()


# --------------------------------------------------------------------------- #
# _execute_tool: hooks, gating, truncation, output compression
# --------------------------------------------------------------------------- #
class ScriptedHooks:
    """A hook system whose per-type behaviour is set by the test."""

    def __init__(self, **outputs):
        from openlaoke.core.hook_system import HookOutput

        self._outputs = {name: value for name, value in outputs.items() if value is not None}
        self._empty = HookOutput()
        self.seen: list[tuple[str, object]] = []

    def has_hooks(self, name):
        return name in self._outputs

    def execute_hooks(self, name, hook_input, hook_output=None):
        value = self._outputs.get(name)
        self.seen.append((name, hook_input))
        if isinstance(value, Exception):
            raise value
        if hook_output is not None and value is not None:
            for field_name in (
                "tool_args",
                "tool_result",
                "tool_error",
                "feedback",
                "skip_execution",
                "handled",
                "metadata",
            ):
                setattr(hook_output, field_name, getattr(value, field_name))
        return value

    def gate(self, hook_input):
        from openlaoke.core.hook_system import HookOutput

        self.seen.append(("tool_gate", hook_input))
        return self._outputs.get("tool_gate") or HookOutput()


def hook_output(**fields):
    from openlaoke.core.hook_system import HookOutput

    return HookOutput(**fields)


def tool_use(name="Read", cid="c1", **inputs):
    from openlaoke.types.core_types import ToolUseBlock

    return ToolUseBlock(id=cid, name=name, input=inputs or {"file_path": "a.txt"})


def test_a_before_hook_can_skip_the_call():
    tool = FakeTool("Read", result="real output")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(
        tool_execute_before=hook_output(skip_execution=True, tool_result="from the hook")
    )

    result = asyncio.run(r._execute_tool(tool_use()))

    assert tool.calls == []
    assert result.content == "from the hook"
    assert result.is_error is False


def test_a_before_hook_skips_the_call_with_a_default_message():
    tool = FakeTool("Read")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(tool_execute_before=hook_output(skip_execution=True))

    result = asyncio.run(r._execute_tool(tool_use()))

    assert tool.calls == []
    assert "skipped by hook" in result.content


def test_a_before_hook_can_rewrite_the_arguments():
    tool = FakeTool("Read", result="ok")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(
        tool_execute_before=hook_output(tool_args={"file_path": "rewritten.txt"})
    )

    asyncio.run(r._execute_tool(tool_use()))

    assert tool.calls == [{"file_path": "rewritten.txt"}]


def test_a_tool_gate_can_block_a_call():
    tool = FakeTool("Read")
    r = make_repl([], tools=[tool])
    hooks = ScriptedHooks(tool_gate=hook_output(handled=True, tool_result="not allowed by policy"))
    r._hook_system = hooks

    result = asyncio.run(r._execute_tool(tool_use()))

    assert tool.calls == []
    assert result.is_error is True
    assert result.content == "not allowed by policy"
    assert "Blocked:" in r.console.file.getvalue()
    # The gate sees the final arguments, after any before-hook rewrite.
    gate_input = next(payload for name, payload in hooks.seen if name == "tool_gate")
    assert gate_input.tool_args == {"file_path": "a.txt"}


def test_a_tool_gate_block_without_a_reason_says_so():
    tool = FakeTool("Read")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(tool_gate=hook_output(handled=True))

    result = asyncio.run(r._execute_tool(tool_use()))

    assert result.content == "Blocked by a tool_gate hook."


def test_a_tool_gate_block_can_carry_a_metadata_reason():
    tool = FakeTool("Read")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(tool_gate=hook_output(handled=True, metadata={"reason": "nope"}))

    result = asyncio.run(r._execute_tool(tool_use()))

    assert result.content == "nope"


def test_a_tool_gate_can_rewrite_the_arguments():
    tool = FakeTool("Read")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(tool_gate=hook_output(tool_args={"file_path": "gated.txt"}))

    asyncio.run(r._execute_tool(tool_use()))

    assert tool.calls == [{"file_path": "gated.txt"}]


def test_an_after_hook_replaces_the_result():
    tool = FakeTool("Read", result="raw")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(tool_execute_after=hook_output(tool_result="rewritten"))

    result = asyncio.run(r._execute_tool(tool_use()))

    assert result.content == "rewritten"
    assert result.is_error is False


def test_a_feedback_hook_is_queued_for_the_next_turn():
    tool = FakeTool("Read", result="ok")
    r = make_repl([], tools=[tool])
    r._hook_system = ScriptedHooks(tool_feedback=hook_output(feedback="use paging next time"))

    asyncio.run(r._execute_tool(tool_use()))

    assert r._input_queue == ["[hook feedback on Read] use paging next time"]
    assert "hook feedback queued" in r.console.file.getvalue()


def test_oversized_tool_output_is_truncated_for_history():
    tool = FakeTool("Read", result="x" * 1000)
    r = make_repl([], tools=[tool])
    r.app_state.max_tool_history = 200

    result = asyncio.run(r._execute_tool(tool_use()))

    assert "tool output compacted" in result.content
    assert len(result.content.encode()) < 1000


def test_an_accepted_large_result_keeps_four_times_the_cap():
    tool = FakeTool("Read", result="y" * 1000)
    r = make_repl([], tools=[tool])
    r.app_state.max_tool_history = 200

    plain = asyncio.run(r._execute_tool(tool_use(cid="c1")))
    accepted = asyncio.run(r._execute_tool(tool_use(cid="c2", accept_large_output=True)))

    assert "tool output compacted" in plain.content
    assert "tool output compacted" in accepted.content
    assert accepted.content.count("y") > plain.content.count("y")


def test_bash_output_is_compressed_before_it_reaches_the_model():
    class Compressor:
        def compress(self, output):
            return "compressed"

    tool = FakeTool("Bash", result="line\n" * 100)
    r = make_repl([], tools=[tool])
    r._output_compressor = Compressor()

    result = asyncio.run(r._execute_tool(tool_use("Bash", command="ls")))

    assert result.content == "compressed"
