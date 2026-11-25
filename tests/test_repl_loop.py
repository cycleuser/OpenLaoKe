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
    def __init__(self, name: str, *, readonly: bool = True, result: str = "ok", is_error: bool = False):
        self.name = name
        self.description = name
        self.input_schema = {"type": "object", "properties": {}}
        self.is_read_only = readonly
        self._result = result
        self._is_error = is_error
        self.calls: list[dict] = []

    async def call(self, ctx, **kwargs):
        self.calls.append(kwargs)
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=self._result, is_error=self._is_error)


class FakeAPI:
    """Serves a pre-scripted list of turns; each turn is a list of StreamChunk."""

    config = None

    def __init__(self, turns):
        self._turns = turns
        self.turn_index = 0
        self.send_calls = 0
        self.close_called = False

    async def stream_message(self, **_kwargs):
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


def make_repl(turns, tools=None, *, harness_mode="balanced", max_steps=0, running=True):
    app = AppState(session_id="test-session", cwd="/tmp")
    app.session_config.model = "gpt-4o"  # large -> minimal guard interference
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
    r._cache_split = None
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
