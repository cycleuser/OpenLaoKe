"""Regression tests for bugs fixed during the comprehensive improvement pass.

Covers:
- EditTool uniqueness check crash (str.index ValueError)
- EditTool overlapping-match detection
- ToolCallCache idempotent-write dedup
- DecisionEngine category mapping (DecisionType.CODE_GENERATION)
- control.commands.parse_command (unknown command / SubmitCommand)
- Contract tools (previously crashed with result_for_assistant kwarg)
- CacheGuard.build_compact_prompt (ContextBuilder.build_runtime_block crash)
- cron next_cron_time step parsing
- make_event with string kind
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.types.core_types import ToolResultBlock


def _ctx(d: str) -> ToolContext:
    s = create_app_state(cwd=d)
    return ToolContext(app_state=s, tool_use_id="t_reg")


@pytest.fixture
def tmp():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestEditToolRegressions:
    @pytest.mark.asyncio
    async def test_single_occurrence_no_crash(self, tmp):
        """The old uniqueness check used str.index() and raised ValueError
        ('substring not found') whenever old_text appeared exactly once."""
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "single.txt")
        with open(p, "w") as f:
            f.write("hello world\nfoo bar\n")
        r = await EditTool().call(
            _ctx(tmp), file_path=p, old_text="hello world", new_text="goodbye world"
        )
        assert not r.is_error
        with open(p) as f:
            assert "goodbye world" in f.read()

    @pytest.mark.asyncio
    async def test_single_char_single_occurrence(self, tmp):
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "one_char.txt")
        with open(p, "w") as f:
            f.write("abc")
        r = await EditTool().call(_ctx(tmp), file_path=p, old_text="b", new_text="B")
        assert not r.is_error
        with open(p) as f:
            assert f.read() == "aBc"

    @pytest.mark.asyncio
    async def test_overlapping_matches_rejected(self, tmp):
        """Overlapping occurrences must be detected as non-unique."""
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "overlap.txt")
        with open(p, "w") as f:
            f.write("aaa")
        r = await EditTool().call(_ctx(tmp), file_path=p, old_text="aa", new_text="b")
        assert r.is_error
        assert "multiple locations" in r.content

    @pytest.mark.asyncio
    async def test_two_separate_occurrences_rejected(self, tmp):
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "two.txt")
        with open(p, "w") as f:
            f.write("foo bar foo baz")
        r = await EditTool().call(_ctx(tmp), file_path=p, old_text="foo", new_text="qux")
        assert r.is_error
        assert "multiple locations" in r.content


class TestIdempotentWriteDedup:
    def test_check_idempotent_write_after_record(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        args = {"file_path": "/tmp/x.py", "content": "print(1)"}
        assert cache.check_idempotent_write("Write", args) is None
        cache.record("Write", args, "ok")
        msg = cache.check_idempotent_write("Write", args)
        assert msg is not None and "already applied" in msg

    def test_non_idempotent_tools_not_tracked(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        args = {"command": "echo hi"}
        cache.record("Bash", args, "hi")
        assert cache.check_idempotent_write("Bash", args) is None

    def test_read_tools_still_cached(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        args = {"file_path": "/tmp/x.py"}
        cache.record("Read", args, "content-here")
        assert cache.check("Read", args) == "content-here"

    def test_clear_resets_write_tracking(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        args = {"file_path": "/tmp/x.py", "content": "1"}
        cache.record("Write", args, "ok")
        cache.clear()
        assert cache.check_idempotent_write("Write", args) is None

    def test_guard_coordinator_idempotent_write(self):
        from openlaoke.core.guard_coordinator import GuardCoordinator

        gc = GuardCoordinator()
        args = {"file_path": "/tmp/y.py", "old_text": "a", "new_text": "b"}
        assert gc.check_idempotent_write_dedup("Edit", args) is None
        gc.record_tool_result("Edit", args, "edited")
        assert gc.check_idempotent_write_dedup("Edit", args) is not None


class TestDecisionEngineMapping:
    def test_map_category_no_crash(self):
        from openlaoke.core.hyperauto.decision_engine import DecisionCategory, DecisionEngine
        from openlaoke.core.hyperauto.types import DecisionType

        engine = DecisionEngine()
        assert (
            engine._map_category_to_decision_type(DecisionCategory.EXECUTION_STRATEGY)
            == DecisionType.CODE_GENERATION
        )
        assert (
            engine._map_category_to_decision_type(DecisionCategory.TOOL_SELECTION)
            == DecisionType.CODE_SEARCH
        )
        assert (
            engine._map_category_to_decision_type(DecisionCategory.ERROR_HANDLING)
            == DecisionType.ABORT
        )


class TestParseCommand:
    def test_unknown_command(self):
        from openlaoke.control.commands import parse_command

        cmd = parse_command("no_such_cmd", {"a": 1})
        assert cmd.name == "no_such_cmd"
        assert cmd.args == {"a": 1}

    def test_submit_command(self):
        from openlaoke.control.commands import SubmitCommand, parse_command

        cmd = parse_command("submit", {"text": "hello"})
        assert isinstance(cmd, SubmitCommand)
        assert cmd.text == "hello"

    def test_approve_command_filters_kwargs(self):
        from openlaoke.control.commands import ApproveCommand, parse_command

        cmd = parse_command("approve", {"decision": "deny", "bogus_key": 1})
        assert isinstance(cmd, ApproveCommand)
        assert cmd.decision == "deny"

    def test_cancel_command_no_args(self):
        from openlaoke.control.commands import CancelCommand, parse_command

        cmd = parse_command("cancel")
        assert isinstance(cmd, CancelCommand)


class TestContractTools:
    @pytest.mark.asyncio
    async def test_full_contract_lifecycle(self, tmp):
        """Contract tools previously crashed with TypeError because
        ToolResultBlock was called with a non-existent kwarg."""
        from openlaoke.core.contract_tools import (
            ContractAssertPassTool,
            ContractCreateTool,
            ContractStatusTool,
        )

        ctx = _ctx(tmp)
        create = await ContractCreateTool().call(
            ctx,
            description="demo contract",
            assertions=[{"description": "tests pass"}],
        )
        assert not create.is_error
        assert "Contract created" in create.content

        contract_id = create.content.splitlines()[0].split(": ")[1]

        passed = await ContractAssertPassTool().call(
            ctx, contract_id=contract_id, assertion_id="1", evidence="pytest ok"
        )
        assert not passed.is_error
        assert "passed" in passed.content

        status = await ContractStatusTool().call(ctx, contract_id=contract_id)
        assert not status.is_error
        assert "demo contract" in status.content

    @pytest.mark.asyncio
    async def test_contract_not_found(self, tmp):
        from openlaoke.core.contract_tools import ContractStatusTool

        r = await ContractStatusTool().call(_ctx(tmp), contract_id="missing")
        assert "not found" in r.content


class TestBuildCompactPrompt:
    def test_compact_prompt_with_user_input(self):
        """build_compact_prompt used to call a non-existent
        ContextBuilder.build_runtime_block and silently lost context."""
        from openlaoke.core.cache_guard import CacheGuard

        state = create_app_state(cwd=os.getcwd())
        prompt = CacheGuard.build_compact_prompt(state, user_input="fix the login bug")
        assert "OpenLaoKe" in prompt
        assert "Working directory" in prompt

    def test_compact_prompt_without_input(self):
        from openlaoke.core.cache_guard import CacheGuard

        state = create_app_state(cwd=os.getcwd())
        prompt = CacheGuard.build_compact_prompt(state)
        assert "OpenLaoKe" in prompt


class TestCronScheduler:
    def test_step_field_parsing(self):
        """_parse_cron_field used to reassign int to a str-typed variable."""
        from openlaoke.cron.scheduler import _parse_cron_field

        assert _parse_cron_field("*/15", 0, 59) == {0, 15, 30, 45}
        assert _parse_cron_field("1-5", 0, 59) == {1, 2, 3, 4, 5}
        assert _parse_cron_field("7,14", 0, 59) == {7, 14}
        assert _parse_cron_field("*", 0, 23) == set(range(24))

    def test_next_cron_time(self):
        from openlaoke.cron.scheduler import next_cron_time

        t = next_cron_time("*/5 * * * *", "UTC", 1000000.0)
        assert t > 1000000.0


class TestMakeEvent:
    def test_string_kind_converted(self):
        from openlaoke.bus.runtime_events import EventKind, make_event

        ev = make_event("text", "sess1", text="hi")
        assert ev.kind is EventKind.TEXT
        assert ev.session_id == "sess1"

    def test_enum_kind_passthrough(self):
        from openlaoke.bus.runtime_events import EventKind, make_event

        ev = make_event(EventKind.TURN_DONE, "s")
        assert ev.kind is EventKind.TURN_DONE


class TestToolRouterTyping:
    def test_route_categories(self):
        from openlaoke.core.tool_router import ToolRouter

        router = ToolRouter()
        r = router.route("read the file main.py")
        assert r.category in ("read", "search", "respond")
        assert isinstance(r.tools, list)

    def test_get_tools_for_category(self):
        from openlaoke.core.tool_router import ToolRouter

        router = ToolRouter()
        assert "Read" in router.get_tools_for_category("read")
        assert router.get_tools_for_category("nope") == []


class TestSafeCall:
    @pytest.mark.asyncio
    async def test_safe_call_catches_exception(self, tmp):
        """safe_call must catch unhandled exceptions and return is_error."""
        from openlaoke.core.tool import Tool

        class CrashTool(Tool):
            name = "Crash"
            description = "Always crashes"
            is_read_only = True

            async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
                raise RuntimeError("boom")

        ctx = _ctx(tmp)
        result = await CrashTool().safe_call(ctx)
        assert result.is_error is True
        assert "boom" in result.content
        assert "Crash" in result.content

    @pytest.mark.asyncio
    async def test_safe_call_passes_through_normal(self, tmp):
        from openlaoke.core.tool import Tool

        class OkTool(Tool):
            name = "Ok"
            description = "Always ok"
            is_read_only = True

            async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
                return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="ok", is_error=False)

        ctx = _ctx(tmp)
        result = await OkTool().safe_call(ctx)
        assert not result.is_error
        assert result.content == "ok"


class TestEnforceRoleAlternation:
    def test_tool_messages_not_merged(self):
        """Multiple consecutive tool messages must stay separate — merging
        them breaks the one-tool-message-per-tool_call_id contract on
        strict OpenAI-compatible providers (DeepSeek, etc.)."""
        from openlaoke.provider import enforce_role_alternation

        msgs = [
            {"role": "user", "content": "do two things"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Write", "arguments": "{}"},
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "Write", "arguments": "{}"},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "wrote a"},
            {"role": "tool", "tool_call_id": "call_2", "content": "wrote b"},
        ]
        result = enforce_role_alternation(msgs)
        tool_msgs = [m for m in result if m["role"] == "tool"]
        assert len(tool_msgs) == 2, f"expected 2 tool msgs, got {len(tool_msgs)}"
        assert tool_msgs[0]["tool_call_id"] == "call_1"
        assert tool_msgs[1]["tool_call_id"] == "call_2"

    def test_user_messages_still_merged(self):
        from openlaoke.provider import enforce_role_alternation

        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "user", "content": "world"},
        ]
        result = enforce_role_alternation(msgs)
        assert len(result) == 1
        assert "hello" in result[0]["content"]
        assert "world" in result[0]["content"]


class TestStreamToolCallPreservation:
    def test_openai_stream_does_not_clear_pending(self):
        """_parse_openai_stream_events must NOT clear pending_tool_calls on
        finish_reason — stream_message consumes them after the stream ends."""
        from openlaoke.core.multi_provider_api import MultiProviderClient

        client = MultiProviderClient.__new__(MultiProviderClient)
        pending: dict[int, dict[str, Any]] = {
            0: {"id": "call_1", "name": "Write", "arguments": '{"file_path":"x"}'},
        }
        event = {"choices": [{"finish_reason": "tool_calls", "delta": {}}]}
        client._parse_openai_stream_events(event, pending, "test-model")
        assert 0 in pending, "pending_tool_calls was cleared — tool calls would be lost!"

    def test_anthropic_message_stop_does_not_clear(self):
        from openlaoke.core.multi_provider_api import MultiProviderClient

        client = MultiProviderClient.__new__(MultiProviderClient)
        pending: dict[int, dict[str, Any]] = {
            0: {"id": "tool_1", "name": "Read", "arguments": ""},
        }
        event = {"type": "message_stop"}
        client._parse_anthropic_stream_events(event, pending, "test-model")
        assert 0 in pending, "pending_tool_calls was cleared on message_stop!"


class TestPathSafety:
    def test_validate_path_workspace(self, tmp):
        from openlaoke.utils.path_safety import validate_path

        assert validate_path(os.path.join(tmp, "x.py"), tmp) is None
        assert validate_path(os.path.join(tmp, "sub", "deep.txt"), tmp) is None

    def test_validate_path_rejects_outside(self, tmp):
        from openlaoke.utils.path_safety import validate_path

        err = validate_path("/etc/passwd", tmp)
        assert err is not None
        assert "outside" in err

    def test_validate_path_allows_home(self, tmp):
        from openlaoke.utils.path_safety import validate_path

        home = os.path.expanduser("~")
        assert validate_path(os.path.join(home, "x.txt"), tmp) is None


class TestEditSchemaAliases:
    @pytest.mark.asyncio
    async def test_old_string_alias(self, tmp):
        """Edit accepts old_string/new_string (Claude Code convention)."""
        from openlaoke.tools.edit_tool import EditTool

        p = os.path.join(tmp, "alias.txt")
        with open(p, "w") as f:
            f.write("hello world")
        r = await EditTool().call(_ctx(tmp), file_path=p, old_string="hello", new_string="hi")
        assert not r.is_error
        with open(p) as f:
            assert f.read() == "hi world"


class TestAntiStall:
    def test_no_false_positive_mid_text(self):
        """'step 1' appearing mid-explanation must not trigger a nudge."""
        from openlaoke.core.anti_stall import should_continue_for_promised_tool_use

        assert not should_continue_for_promised_tool_use(
            "The algorithm works as follows. In step 1 we initialize the array. "
            "In step 2 we iterate. This is a complete answer."
        )

    def test_planning_trigger(self):
        from openlaoke.core.anti_stall import should_continue_for_promised_tool_use

        assert should_continue_for_promised_tool_use(
            "Step 1: Read the config file. Step 2: modify it."
        )


class TestBashTruncation:
    @pytest.mark.asyncio
    async def test_truncation_notes_loss(self, tmp):
        from openlaoke.tools.bash_tool import BashTool

        r = await BashTool().call(_ctx(tmp), command="yes 'x' | head -c 50000")
        assert not r.is_error
        assert "truncated" in r.content


class TestImportValidationNoExec:
    def test_import_check_uses_ast_not_exec(self, tmp):
        """test_imports must NOT exec untrusted code — a malicious import line
        with a side effect must not run."""
        from openlaoke.core.code_validator import ExecutionValidator

        v = ExecutionValidator()
        target = os.path.join(tmp, "pwned.txt")
        result = v.test_imports(f"import os\nos.system('touch {target}')")
        assert result.is_valid  # os is importable; the system() call must be ignored
        assert not os.path.exists(target), "exec RAN untrusted code!"

    def test_import_check_rejects_missing_module(self):
        from openlaoke.core.code_validator import ExecutionValidator

        v = ExecutionValidator()
        result = v.test_imports("import definitely_not_a_real_module_xyz")
        assert not result.is_valid
        assert "Unimportable" in " ".join(result.errors)


class TestWebFetchSSRF:
    def test_blocks_metadata_host(self):
        from openlaoke.tools.webfetch_tool import _is_safe_url

        ok, reason = _is_safe_url("http://169.254.169.254/latest/meta-data/")
        assert not ok
        assert "Blocked" in reason

    def test_blocks_localhost(self):
        from openlaoke.tools.webfetch_tool import _is_safe_url

        ok, _ = _is_safe_url("http://127.0.0.1:8080/admin")
        assert not ok

    def test_blocks_private_range(self):
        from openlaoke.tools.webfetch_tool import _is_safe_url

        ok, _ = _is_safe_url("http://192.168.1.1/config")
        assert not ok

    def test_allows_public(self):
        from openlaoke.tools.webfetch_tool import _is_safe_url

        ok, _ = _is_safe_url("https://example.com/page")
        assert ok


class TestServerAgentLoop:
    @pytest.mark.asyncio
    async def test_stream_chat_runs_tools(self, tmp):
        """The streaming chat endpoint must execute tool calls and feed
        results back to the model (agent loop), not just stream text."""
        from openlaoke.core.state import create_app_state
        from openlaoke.core.tool import ToolRegistry
        from openlaoke.server.server import ActiveSession, Server
        from openlaoke.tools.register import register_all_tools

        # Minimal harness: a server with a fake session that always returns
        # a Write tool call then stops. We assert tool execution happened.
        class FakeAPI:
            def __init__(self):
                self.calls = 0

            async def stream_message(self, **kwargs):
                self.calls += 1
                from openlaoke.types.core_types import StreamChunk, StreamEventType

                if self.calls == 1:
                    yield StreamChunk(
                        event_type=StreamEventType.TOOL_CALL_START,
                        tool_call_id="tc_1",
                        tool_call_name="Write",
                        tool_call_arguments=json.dumps(
                            {"file_path": "out.txt", "content": "hello"}
                        ),
                    )
                else:
                    yield StreamChunk(event_type=StreamEventType.USAGE)

        state = create_app_state(cwd=tmp)
        registry = ToolRegistry()
        register_all_tools(registry)
        session = ActiveSession(
            app_state=state,
            registry=registry,
            api=FakeAPI(),
            config=state.session_config,
        )
        # Bypass __init__ (which builds the FastAPI app) — we only exercise
        # the streaming agent loop directly.
        server = Server.__new__(Server)
        chunks = []
        async for line in server._stream_chat(session, "write out.txt"):
            chunks.append(line)
        assert os.path.exists(os.path.join(tmp, "out.txt")), "tool was not executed"
        assert any("tool_result" in c for c in chunks)
