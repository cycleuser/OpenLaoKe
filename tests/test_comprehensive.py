"""Comprehensive test suite for all OpenLaoKe features.

Covers: core types, state, tool system, tools (bash/read/write/edit/glob/grep),
hook system, fast pruner, bitter lesson tracker, small model optimizations,
supervisor/checker, slug utils, bash classifier, tool dedup, cross-project lessons,
model assessment, memory sqlite, commands registry, permissions.

Run with: pytest tests/test_comprehensive.py -v --tb=short
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from openlaoke.core.state import SessionConfig, create_app_state
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import (
    AssistantMessage,
    AttachmentMessage,
    CostInfo,
    Message,
    MessageRole,
    PermissionResult,
    ProgressMessage,
    StreamChunk,
    StreamEventType,
    SystemMessage,
    TaskId,
    TaskState,
    TaskStatus,
    TaskType,
    TokenUsage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    ValidationResult,
    is_terminal_task_status,
    message_from_dict,
)
from openlaoke.types.permissions import PermissionConfig

# ============================================================================
# SECTION 1: Core Types Tests
# ============================================================================


class TestTokenUsage:
    def test_initial_values(self):
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_creation_tokens == 0
        assert usage.total_tokens == 0

    def test_total_tokens(self):
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_accumulate(self):
        u1 = TokenUsage(input_tokens=100, output_tokens=50)
        u2 = TokenUsage(input_tokens=200, output_tokens=100, cache_read_tokens=30)
        u1.accumulate(u2)
        assert u1.input_tokens == 300
        assert u1.output_tokens == 150
        assert u1.cache_read_tokens == 30

    def test_to_dict(self):
        usage = TokenUsage(input_tokens=10, output_tokens=20)
        d = usage.to_dict()
        assert d["input_tokens"] == 10
        assert d["output_tokens"] == 20
        assert "cache_read_tokens" in d


class TestCostInfo:
    def test_initial_values(self):
        cost = CostInfo()
        assert cost.total_cost == 0.0

    def test_total_cost_calculation(self):
        cost = CostInfo(input_cost=0.1, output_cost=0.2, cache_read_cost=0.05)
        assert abs(cost.total_cost - 0.35) < 1e-9

    def test_to_dict(self):
        cost = CostInfo(input_cost=1.0, output_cost=2.0)
        d = cost.to_dict()
        assert d["input_cost"] == 1.0
        assert d["total_cost"] == 3.0


class TestTaskId:
    def test_generate_local_bash(self):
        tid = TaskId()
        result = tid.generate(TaskType.LOCAL_BASH)
        assert result.startswith("b_")
        assert len(result) == 10

    def test_generate_local_agent(self):
        tid = TaskId()
        result = tid.generate(TaskType.LOCAL_AGENT)
        assert result.startswith("a_")

    def test_parse_type(self):
        tid = TaskId()
        assert tid.parse_type("b_12345678") == TaskType.LOCAL_BASH
        assert tid.parse_type("a_12345678") == TaskType.LOCAL_AGENT
        assert tid.parse_type("r_12345678") == TaskType.REMOTE_AGENT


class TestTaskStatus:
    def test_terminal_statuses(self):
        assert is_terminal_task_status(TaskStatus.COMPLETED) is True
        assert is_terminal_task_status(TaskStatus.FAILED) is True
        assert is_terminal_task_status(TaskStatus.KILLED) is True
        assert is_terminal_task_status(TaskStatus.PENDING) is False
        assert is_terminal_task_status(TaskStatus.RUNNING) is False


class TestToolUseBlock:
    def test_creation(self):
        block = ToolUseBlock(id="tu_1", name="Bash", input={"command": "ls"})
        assert block.id == "tu_1"
        assert block.name == "Bash"
        assert block.input == {"command": "ls"}

    def test_to_dict(self):
        block = ToolUseBlock(id="tu_1", name="Read", input={"file_path": "/tmp/test"})
        d = block.to_dict()
        assert d["type"] == "tool_use"
        assert d["id"] == "tu_1"
        assert d["name"] == "Read"


class TestToolResultBlock:
    def test_success_result(self):
        result = ToolResultBlock(tool_use_id="tu_1", content="output", is_error=False)
        assert result.tool_use_id == "tu_1"
        assert result.content == "output"
        assert result.is_error is False

    def test_error_result(self):
        result = ToolResultBlock(tool_use_id="tu_1", content="Error: not found", is_error=True)
        assert result.is_error is True

    def test_to_dict(self):
        result = ToolResultBlock(tool_use_id="tu_1", content="hello", is_error=False)
        d = result.to_dict()
        assert d["type"] == "tool_result"
        assert d["tool_use_id"] == "tu_1"
        assert d["content"] == "hello"
        assert d["is_error"] is False


class TestMessages:
    def test_user_message(self):
        msg = UserMessage(role=MessageRole.USER, content="hello")
        assert msg.content == "hello"
        d = msg.to_dict()
        assert d["type"] == "user"
        assert d["content"] == "hello"

    def test_assistant_message(self):
        msg = AssistantMessage(
            role=MessageRole.ASSISTANT,
            content="response",
            thinking="I think...",
        )
        assert msg.content == "response"
        assert msg.thinking == "I think..."
        d = msg.to_dict()
        assert d["type"] == "assistant"

    def test_system_message(self):
        msg = SystemMessage(role=MessageRole.SYSTEM, content="info", subtype="warning")
        d = msg.to_dict()
        assert d["type"] == "system"
        assert d["subtype"] == "warning"

    def test_progress_message(self):
        msg = ProgressMessage(
            role=MessageRole.SYSTEM,
            content="Processing...",
            tool_use_id="tu_1",
            tool_name="Bash",
            percentage=50.0,
        )
        d = msg.to_dict()
        assert d["type"] == "progress"
        assert d["percentage"] == 50.0

    def test_attachment_message(self):
        msg = AttachmentMessage(
            role=MessageRole.USER, content="see file", file_paths=["/tmp/a.txt"]
        )
        d = msg.to_dict()
        assert d["type"] == "attachment"
        assert "/tmp/a.txt" in d["file_paths"]


class TestMessageFromDict:
    def test_user_message(self):
        data = {"type": "user", "content": "hello", "images": [], "timestamp": 1.0}
        msg = message_from_dict(data)
        assert isinstance(msg, UserMessage)
        assert msg.content == "hello"

    def test_assistant_message(self):
        data = {
            "type": "assistant",
            "content": "reply",
            "tool_uses": [{"id": "t1", "name": "Bash", "input": {}}],
            "stop_reason": "end_turn",
            "thinking": "hmm",
            "timestamp": 2.0,
        }
        msg = message_from_dict(data)
        assert isinstance(msg, AssistantMessage)
        assert len(msg.tool_uses) == 1
        assert msg.tool_uses[0].name == "Bash"

    def test_system_message(self):
        data = {"type": "system", "content": "info", "subtype": "info"}
        msg = message_from_dict(data)
        assert isinstance(msg, SystemMessage)

    def test_progress_message(self):
        data = {
            "type": "progress",
            "content": "50%",
            "tool_use_id": "t1",
            "tool_name": "Bash",
            "percentage": 50.0,
        }
        msg = message_from_dict(data)
        assert isinstance(msg, ProgressMessage)
        assert msg.percentage == 50.0

    def test_attachment_message(self):
        data = {"type": "attachment", "content": "file", "file_paths": ["/a"]}
        msg = message_from_dict(data)
        assert isinstance(msg, AttachmentMessage)
        assert msg.file_paths == ["/a"]


class TestValidationResult:
    def test_success(self):
        r = ValidationResult(result=True)
        assert r.result is True
        assert r.message == ""

    def test_failure(self):
        r = ValidationResult(result=False, message="Missing field", error_code=400)
        assert r.result is False
        assert r.message == "Missing field"


class TestStreamChunk:
    def test_text_chunk(self):
        chunk = StreamChunk(event_type=StreamEventType.TEXT, text="hello")
        assert chunk.event_type == StreamEventType.TEXT
        assert chunk.text == "hello"

    def test_tool_call_chunk(self):
        chunk = StreamChunk(
            event_type=StreamEventType.TOOL_CALL_START,
            tool_call_id="tc1",
            tool_call_name="Bash",
        )
        assert chunk.tool_call_name == "Bash"


class TestTaskState:
    def test_creation(self):
        task = TaskState(id="b_123", type=TaskType.LOCAL_BASH, description="test cmd")
        assert task.status == TaskStatus.PENDING
        assert task.exit_code is None

    def test_to_dict(self):
        task = TaskState(
            id="b_123",
            type=TaskType.LOCAL_BASH,
            status=TaskStatus.COMPLETED,
            exit_code=0,
        )
        d = task.to_dict()
        assert d["id"] == "b_123"
        assert d["type"] == "local_bash"
        assert d["status"] == "completed"
        assert d["exit_code"] == 0


# ============================================================================
# SECTION 2: State Management Tests
# ============================================================================


class TestSessionConfig:
    def test_defaults(self):
        cfg = SessionConfig()
        assert cfg.model == "gemma3:1b"
        assert cfg.max_tokens == 8192
        assert cfg.temperature == 1.0

    def test_custom_values(self):
        cfg = SessionConfig(model="gpt-4", max_tokens=4096, temperature=0.7)
        assert cfg.model == "gpt-4"
        assert cfg.max_tokens == 4096


class TestAppState:
    def test_creation(self):
        state = create_app_state(cwd="/tmp")
        assert state.cwd == "/tmp"
        assert state.working_directory == "/tmp"
        assert state.session_id.startswith("session_")
        assert len(state.messages) == 0

    def test_set_cwd(self):
        state = create_app_state(cwd="/tmp")
        state.set_cwd("/var")
        assert state.cwd == "/var"
        assert state.working_directory == "/var"

    def test_add_message(self):
        state = create_app_state(cwd="/tmp")
        msg = UserMessage(role=MessageRole.USER, content="test")
        state.add_message(msg)
        assert state.get_message_count() == 1
        assert state.get_last_message().content == "test"

    def test_get_messages(self):
        state = create_app_state(cwd="/tmp")
        state.add_message(UserMessage(role=MessageRole.USER, content="a"))
        state.add_message(UserMessage(role=MessageRole.USER, content="b"))
        msgs = state.get_messages()
        assert len(msgs) == 2

    def test_add_task(self):
        state = create_app_state(cwd="/tmp")
        task = TaskState(id="b_001", type=TaskType.LOCAL_BASH)
        state.add_task(task)
        assert state.get_task("b_001") is not None
        assert len(state.get_all_tasks()) == 1

    def test_get_active_tasks(self):
        state = create_app_state(cwd="/tmp")
        t1 = TaskState(id="b_001", type=TaskType.LOCAL_BASH, status=TaskStatus.RUNNING)
        t2 = TaskState(id="b_002", type=TaskType.LOCAL_BASH, status=TaskStatus.COMPLETED)
        state.add_task(t1)
        state.add_task(t2)
        active = state.get_active_tasks()
        assert len(active) == 1
        assert active[0].id == "b_001"

    def test_accumulate_tokens(self):
        state = create_app_state(cwd="/tmp")
        state.accumulate_tokens(TokenUsage(input_tokens=100, output_tokens=50))
        state.accumulate_tokens(TokenUsage(input_tokens=200, output_tokens=100))
        assert state.token_usage.input_tokens == 300
        assert state.token_usage.output_tokens == 150

    def test_accumulate_cost(self):
        state = create_app_state(cwd="/tmp")
        state.accumulate_cost(CostInfo(input_cost=0.01, output_cost=0.02))
        state.accumulate_cost(CostInfo(input_cost=0.03, output_cost=0.04))
        assert abs(state.cost_info.input_cost - 0.04) < 1e-9
        assert abs(state.cost_info.output_cost - 0.06) < 1e-9

    def test_subscribe_listener(self):
        state = create_app_state(cwd="/tmp")
        events = []
        state.subscribe(lambda s: events.append("notified"))
        state.add_message(UserMessage(role=MessageRole.USER, content="x"))
        assert len(events) == 1

    def test_unsubscribe_listener(self):
        state = create_app_state(cwd="/tmp")
        events = []

        def listener(s):
            events.append("notified")

        state.subscribe(listener)
        state.unsubscribe(listener)
        state.add_message(UserMessage(role=MessageRole.USER, content="x"))
        assert len(events) == 0

    def test_persist_and_restore(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            persist_path = f.name
        try:
            state = create_app_state(cwd="/tmp", persist_path=persist_path)
            state.add_message(UserMessage(role=MessageRole.USER, content="hello"))
            with open(persist_path) as f:
                data = json.load(f)
            assert data["session_id"] == state.session_id
            assert len(data["messages"]) == 1
        finally:
            os.unlink(persist_path)

    def test_set_error(self):
        state = create_app_state(cwd="/tmp")
        state.set_error("something broke")
        assert state.error_message == "something broke"
        state.set_error(None)
        assert state.error_message is None

    def test_to_dict(self):
        state = create_app_state(cwd="/tmp")
        d = state.to_dict()
        assert "session_id" in d
        assert d["cwd"] == "/tmp"
        assert d["message_count"] == 0

    def test_env_vars(self):
        state = create_app_state(cwd="/tmp")
        state.env_vars["MY_VAR"] = "test_value"
        env = state.get_env_vars()
        assert env["MY_VAR"] == "test_value"
        assert "PATH" in env


# ============================================================================
# SECTION 3: Tool System Tests
# ============================================================================


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()

        class DummyTool(Tool):
            name = "Dummy"
            description = "A dummy tool"

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="ok")

        tool = DummyTool()
        registry.register(tool)
        assert registry.get("Dummy") is tool
        assert registry.get("NonExistent") is None

    def test_deferred_registration(self):
        registry = ToolRegistry()

        class LazyTool(Tool):
            name = "Lazy"
            description = "Lazy loaded"

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id=ctx.tool_use_id, content="lazy")

        registry.register_deferred("Lazy", lambda: LazyTool())
        assert registry.is_deferred("Lazy") is True
        assert registry.is_loaded("Lazy") is False
        tool = registry.get("Lazy")
        assert tool is not None
        assert tool.name == "Lazy"
        assert registry.is_loaded("Lazy") is True

    def test_deferred_with_info(self):
        registry = ToolRegistry()
        registry.register_deferred_with_info(
            "MyTool",
            lambda: None,
            description="A tool",
            search_hint="search me",
            aliases=["mt"],
        )
        info = registry.get_deferred_info("MyTool")
        assert info is not None
        assert info.description == "A tool"
        assert info.search_hint == "search me"
        assert "mt" in info.aliases

    def test_get_all(self):
        registry = ToolRegistry()

        class T1(Tool):
            name = "T1"

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id="", content="")

        class T2(Tool):
            name = "T2"

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id="", content="")

        registry.register(T1())
        registry.register_deferred("T2", lambda: T2())
        all_tools = registry.get_all()
        names = [t.name for t in all_tools]
        assert "T1" in names
        assert "T2" in names

    def test_search(self):
        registry = ToolRegistry()

        class SearchableTool(Tool):
            name = "SearchTool"
            description = "Find files using patterns"

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id="", content="")

        registry.register(SearchableTool())
        results = registry.search("find")
        assert len(results) == 1
        assert results[0].name == "SearchTool"

    def test_search_deferred(self):
        registry = ToolRegistry()
        registry.register_deferred_with_info(
            "HiddenTool",
            lambda: None,
            description="secret tool",
            search_hint="hidden utility",
            aliases=["ht"],
        )
        results = registry.search_deferred("hidden")
        assert len(results) == 1
        assert results[0].name == "HiddenTool"

    @pytest.mark.asyncio
    async def test_get_async(self):
        registry = ToolRegistry()

        class AsyncTool(Tool):
            name = "AsyncT"

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id="", content="")

        async def loader():
            return AsyncTool()

        registry.register_deferred("AsyncT", loader)
        tool = await registry.get_async("AsyncT")
        assert tool is not None
        assert tool.name == "AsyncT"


class TestToolValidation:
    def test_validate_required_fields(self):
        class TestTool(Tool):
            name = "Test"
            input_schema = {
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            }

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id="", content="")

        tool = TestTool()
        result = tool.validate_input({"command": "ls"})
        assert result.result is True

        result = tool.validate_input({})
        assert result.result is False
        assert "command" in result.message

    def test_validate_type_checking(self):
        class TestTool(Tool):
            name = "Test"
            input_schema = {
                "properties": {
                    "count": {"type": "integer"},
                    "name": {"type": "string"},
                },
                "required": [],
            }

            async def call(self, ctx, **kwargs):
                return ToolResultBlock(tool_use_id="", content="")

        tool = TestTool()
        result = tool.validate_input({"count": 5, "name": "test"})
        assert result.result is True

        result = tool.validate_input({"count": "not_a_number"})
        assert result.result is False
        assert "count" in result.message


# ============================================================================
# SECTION 4: Tools Tests (Bash, Read, Write, Edit, Glob, Grep)
# ============================================================================


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _make_ctx(work_dir: str) -> ToolContext:
    state = create_app_state(cwd=work_dir)
    return ToolContext(app_state=state, tool_use_id="test_ctx_1")


class TestBashToolComprehensive:
    @pytest.mark.asyncio
    async def test_echo_command(self):
        from openlaoke.tools.bash_tool import BashTool

        ctx = _make_ctx(os.getcwd())
        tool = BashTool()
        result = await tool.call(ctx, command="echo 'hello world'")
        assert not result.is_error
        assert "hello world" in result.content

    @pytest.mark.asyncio
    async def test_empty_command_error(self):
        from openlaoke.tools.bash_tool import BashTool

        ctx = _make_ctx(os.getcwd())
        tool = BashTool()
        result = await tool.call(ctx, command="")
        assert result.is_error
        assert "Empty command" in result.content

    @pytest.mark.asyncio
    async def test_whitespace_only_command(self):
        from openlaoke.tools.bash_tool import BashTool

        ctx = _make_ctx(os.getcwd())
        tool = BashTool()
        result = await tool.call(ctx, command="   ")
        assert result.is_error

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self):
        from openlaoke.tools.bash_tool import BashTool
        from openlaoke.types.core_types import PermissionMode

        state = create_app_state(cwd=os.getcwd())
        state.permission_config.mode = PermissionMode.BYPASS
        ctx = ToolContext(app_state=state, tool_use_id="test_ctx_1")
        tool = BashTool()
        result = await tool.call(ctx, command="exit 42")
        assert result.is_error
        assert "42" in result.content

    @pytest.mark.asyncio
    async def test_destructive_command_blocked(self):
        from openlaoke.tools.bash_tool import BashTool

        ctx = _make_ctx(os.getcwd())
        tool = BashTool()
        result = await tool.call(ctx, command="rm -rf /")
        assert result.is_error
        assert "blocked" in result.content.lower() or "destructive" in result.content.lower()

    @pytest.mark.asyncio
    async def test_multiline_output(self):
        from openlaoke.tools.bash_tool import BashTool
        from openlaoke.types.core_types import PermissionMode

        state = create_app_state(cwd=os.getcwd())
        state.permission_config.mode = PermissionMode.BYPASS
        ctx = ToolContext(app_state=state, tool_use_id="test_ctx_1")
        tool = BashTool()
        result = await tool.call(ctx, command="echo -e 'line1\nline2\nline3'")
        assert not result.is_error
        assert "line1" in result.content
        assert "line3" in result.content

    @pytest.mark.asyncio
    async def test_tool_metadata(self):
        from openlaoke.tools.bash_tool import BashTool

        tool = BashTool()
        assert tool.name == "Bash"
        assert tool.is_destructive is True
        assert tool.requires_approval is True
        assert tool.is_read_only is False


class TestReadToolComprehensive:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        path = os.path.join(temp_dir, "test.txt")
        with open(path, "w") as f:
            f.write("hello\nworld\n")
        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path)
        assert not result.is_error
        assert "hello" in result.content
        assert "world" in result.content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path="/nonexistent/file.txt")
        assert result.is_error
        assert "not found" in result.content.lower() or "outside" in result.content.lower()

    @pytest.mark.asyncio
    async def test_read_empty_path(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path="")
        assert result.is_error
        assert "required" in result.content.lower()

    @pytest.mark.asyncio
    async def test_read_with_offset(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        path = os.path.join(temp_dir, "multi.txt")
        with open(path, "w") as f:
            f.write("\n".join(f"line{i}" for i in range(1, 11)))
        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path, offset=5)
        assert "line5" in result.content

    @pytest.mark.asyncio
    async def test_read_with_limit(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        path = os.path.join(temp_dir, "multi.txt")
        with open(path, "w") as f:
            f.write("\n".join(f"line{i}" for i in range(1, 20)))
        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path, limit=3)
        assert "line1" in result.content
        assert "line3" in result.content

    @pytest.mark.asyncio
    async def test_read_directory(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        os.makedirs(os.path.join(temp_dir, "subdir"))
        with open(os.path.join(temp_dir, "file.txt"), "w") as f:
            f.write("x")
        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=temp_dir)
        assert not result.is_error
        assert "file.txt" in result.content
        assert "subdir/" in result.content

    @pytest.mark.asyncio
    async def test_read_utf8_file(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool

        path = os.path.join(temp_dir, "utf8.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("你好世界\nHello World\n")
        tool = ReadTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path)
        assert not result.is_error
        assert "你好世界" in result.content

    @pytest.mark.asyncio
    async def test_read_tool_metadata(self):
        from openlaoke.tools.read_tool import ReadTool

        tool = ReadTool()
        assert tool.name == "Read"
        assert tool.is_read_only is True
        assert tool.is_destructive is False


class TestWriteToolComprehensive:
    @pytest.mark.asyncio
    async def test_write_new_file(self, temp_dir):
        from openlaoke.tools.write_tool import WriteTool

        path = os.path.join(temp_dir, "new_file.txt")
        tool = WriteTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path, content="new content")
        assert not result.is_error
        with open(path) as f:
            assert f.read() == "new content"

    @pytest.mark.asyncio
    async def test_write_overwrite_file(self, temp_dir):
        from openlaoke.tools.write_tool import WriteTool

        path = os.path.join(temp_dir, "existing.txt")
        with open(path, "w") as f:
            f.write("old content")
        tool = WriteTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path, content="new content")
        assert not result.is_error
        with open(path) as f:
            assert f.read() == "new content"

    @pytest.mark.asyncio
    async def test_write_creates_dirs(self, temp_dir):
        from openlaoke.tools.write_tool import WriteTool

        path = os.path.join(temp_dir, "sub", "dir", "file.txt")
        tool = WriteTool()
        result = await tool.call(_make_ctx(temp_dir), file_path=path, content="deep file")
        assert not result.is_error
        assert os.path.exists(path)

    @pytest.mark.asyncio
    async def test_write_empty_path(self, temp_dir):
        from openlaoke.tools.write_tool import WriteTool

        tool = WriteTool()
        result = await tool.call(_make_ctx(temp_dir), file_path="", content="x")
        assert result.is_error

    @pytest.mark.asyncio
    async def test_write_tool_metadata(self):
        from openlaoke.tools.write_tool import WriteTool

        tool = WriteTool()
        assert tool.name == "Write"
        assert tool.is_destructive is True
        assert tool.requires_approval is True


class TestEditToolComprehensive:
    @pytest.mark.asyncio
    async def test_edit_replace_text(self, temp_dir):
        from openlaoke.tools.edit_tool import EditTool

        path = os.path.join(temp_dir, "edit_me.txt")
        with open(path, "w") as f:
            f.write("hello world\nfoo bar\n")
        tool = EditTool()
        result = await tool.call(
            _make_ctx(temp_dir), file_path=path, old_text="hello world", new_text="goodbye world"
        )
        assert not result.is_error
        with open(path) as f:
            content = f.read()
        assert "goodbye world" in content
        assert "hello world" not in content

    @pytest.mark.asyncio
    async def test_edit_text_not_found(self, temp_dir):
        from openlaoke.tools.edit_tool import EditTool

        path = os.path.join(temp_dir, "edit_me.txt")
        with open(path, "w") as f:
            f.write("actual content\n")
        tool = EditTool()
        result = await tool.call(
            _make_ctx(temp_dir), file_path=path, old_text="nonexistent", new_text="new"
        )
        assert result.is_error
        assert "not found" in result.content.lower()

    @pytest.mark.asyncio
    async def test_edit_empty_old_text(self, temp_dir):
        from openlaoke.tools.edit_tool import EditTool

        tool = EditTool()
        result = await tool.call(
            _make_ctx(temp_dir), file_path="test.txt", old_text="", new_text="new"
        )
        assert result.is_error

    @pytest.mark.asyncio
    async def test_edit_empty_file_path(self, temp_dir):
        from openlaoke.tools.edit_tool import EditTool

        tool = EditTool()
        result = await tool.call(_make_ctx(temp_dir), file_path="", old_text="x", new_text="y")
        assert result.is_error


class TestGlobToolComprehensive:
    @pytest.mark.asyncio
    async def test_find_python_files(self, temp_dir):
        from openlaoke.tools.glob_tool import GlobTool

        os.makedirs(os.path.join(temp_dir, "src"))
        for name in ["a.py", "b.py", "c.txt"]:
            with open(os.path.join(temp_dir, "src", name), "w") as f:
                f.write("")
        tool = GlobTool()
        result = await tool.call(_make_ctx(temp_dir), pattern="**/*.py", path=temp_dir)
        assert not result.is_error
        assert "a.py" in result.content
        assert "b.py" in result.content
        assert "c.txt" not in result.content

    @pytest.mark.asyncio
    async def test_empty_pattern(self, temp_dir):
        from openlaoke.tools.glob_tool import GlobTool

        tool = GlobTool()
        result = await tool.call(_make_ctx(temp_dir), pattern="")
        assert result.is_error

    @pytest.mark.asyncio
    async def test_no_matches(self, temp_dir):
        from openlaoke.tools.glob_tool import GlobTool

        tool = GlobTool()
        result = await tool.call(_make_ctx(temp_dir), pattern="**/*.xyz", path=temp_dir)
        assert "no files" in result.content.lower() or result.content.strip() == ""

    @pytest.mark.asyncio
    async def test_glob_tool_metadata(self):
        from openlaoke.tools.glob_tool import GlobTool

        tool = GlobTool()
        assert tool.name == "Glob"
        assert tool.is_read_only is True


class TestGrepToolComprehensive:
    @pytest.mark.asyncio
    async def test_find_pattern(self, temp_dir):
        from openlaoke.tools.grep_tool import GrepTool

        with open(os.path.join(temp_dir, "test.py"), "w") as f:
            f.write("def hello():\n    return 'world'\n\ndef foo():\n    pass\n")
        tool = GrepTool()
        result = await tool.call(_make_ctx(temp_dir), pattern="def \\w+", path=temp_dir)
        assert not result.is_error
        assert "hello" in result.content
        assert "foo" in result.content

    @pytest.mark.asyncio
    async def test_empty_pattern(self, temp_dir):
        from openlaoke.tools.grep_tool import GrepTool

        tool = GrepTool()
        result = await tool.call(_make_ctx(temp_dir), pattern="")
        assert result.is_error

    @pytest.mark.asyncio
    async def test_case_insensitive(self, temp_dir):
        from openlaoke.tools.grep_tool import GrepTool

        with open(os.path.join(temp_dir, "test.txt"), "w") as f:
            f.write("Hello World\nhello world\nHELLO WORLD\n")
        tool = GrepTool()
        result = await tool.call(
            _make_ctx(temp_dir), pattern="hello", path=temp_dir, case_sensitive=False
        )
        assert not result.is_error
        assert "Hello" in result.content or "hello" in result.content

    @pytest.mark.asyncio
    async def test_glob_filter(self, temp_dir):
        from openlaoke.tools.grep_tool import GrepTool

        with open(os.path.join(temp_dir, "code.py"), "w") as f:
            f.write("import os\n")
        with open(os.path.join(temp_dir, "readme.md"), "w") as f:
            f.write("import os\n")
        tool = GrepTool()
        result = await tool.call(_make_ctx(temp_dir), pattern="import", path=temp_dir, glob="*.py")
        assert "code.py" in result.content
        assert "readme.md" not in result.content

    @pytest.mark.asyncio
    async def test_grep_tool_metadata(self):
        from openlaoke.tools.grep_tool import GrepTool

        tool = GrepTool()
        assert tool.name == "Grep"
        assert tool.is_read_only is True


# ============================================================================
# SECTION 5: Hook System Tests
# ============================================================================


class TestHookSystemComprehensive:
    @pytest.mark.asyncio
    async def test_register_and_execute_sync(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()
        results = []

        def my_hook(inp: HookInput, out: HookOutput) -> None:
            results.append(inp.tool_name)

        system.register("tool_execute_before", "test_hook", my_hook)
        inp = HookInput(tool_name="Bash")
        out = HookOutput()
        await system.execute_hooks_async("tool_execute_before", inp, out)
        assert results == ["Bash"]

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()
        order = []

        def hook_low(inp: HookInput, out: HookOutput) -> None:
            order.append("low")

        def hook_high(inp: HookInput, out: HookOutput) -> None:
            order.append("high")

        system.register("tool_execute_before", "low", hook_low, priority=1)
        system.register("tool_execute_before", "high", hook_high, priority=10)
        await system.execute_hooks_async("tool_execute_before", HookInput(), HookOutput())
        assert order == ["high", "low"]

    @pytest.mark.asyncio
    async def test_short_circuit(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()
        calls = []

        def hook1(inp: HookInput, out: HookOutput) -> None:
            calls.append("first")
            out.handled = True

        def hook2(inp: HookInput, out: HookOutput) -> None:
            calls.append("second")

        system.register("error_handle", "h1", hook1, priority=10)
        system.register("error_handle", "h2", hook2, priority=1)
        out = HookOutput()
        await system.execute_hooks_async("error_handle", HookInput(), out)
        assert calls == ["first"]
        assert out.handled is True

    @pytest.mark.asyncio
    async def test_disabled_hook(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()
        calls = []

        def my_hook(inp: HookInput, out: HookOutput) -> None:
            calls.append("called")

        system.register("tool_execute_before", "h", my_hook)
        system.disable_hook("tool_execute_before", "h")
        await system.execute_hooks_async("tool_execute_before", HookInput(), HookOutput())
        assert calls == []

    @pytest.mark.asyncio
    async def test_async_hook(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()
        results = []

        async def async_hook(inp: HookInput, out: HookOutput) -> None:
            results.append("async_called")

        system.register("tool_execute_before", "ah", async_hook)
        await system.execute_hooks_async("tool_execute_before", HookInput(), HookOutput())
        assert results == ["async_called"]

    @pytest.mark.asyncio
    async def test_hook_modifies_output(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()

        def modifier(inp: HookInput, out: HookOutput) -> None:
            out.tool_args = {"command": "safe_command"}

        system.register("tool_execute_before", "mod", modifier)
        out = HookOutput()
        await system.execute_hooks_async(
            "tool_execute_before", HookInput(tool_args={"command": "rm -rf /"}), out
        )
        assert out.tool_args == {"command": "safe_command"}

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem

        system = HookSystem()
        calls = []

        def bad_hook(inp: HookInput, out: HookOutput) -> None:
            raise RuntimeError("oops")

        def good_hook(inp: HookInput, out: HookOutput) -> None:
            calls.append("good")

        system.register("tool_execute_before", "bad", bad_hook, priority=10)
        system.register("tool_execute_before", "good", good_hook, priority=1)
        await system.execute_hooks_async("tool_execute_before", HookInput(), HookOutput())
        assert "good" in calls


# ============================================================================
# SECTION 6: Fast Pruner Tests
# ============================================================================


class TestFastPruner:
    def test_extract_keywords(self):
        from openlaoke.core.compact.fast_pruner import extract_keywords

        text = """
        def hello_world():
            import os
            path = /usr/local/bin/python
            Error: File not found
        class MyClass:
            pass
        """
        keywords = extract_keywords(text)
        assert len(keywords) > 0
        assert any("hello_world" in k for k in keywords)

    def test_extract_keywords_max_limit(self):
        from openlaoke.core.compact.fast_pruner import extract_keywords

        text = "\n".join(f"def func_{i}():" for i in range(100))
        keywords = extract_keywords(text, max_keywords=10)
        assert len(keywords) <= 10

    def test_fast_prune_short_messages(self):
        from openlaoke.core.compact.fast_pruner import fast_prune
        from openlaoke.types.core_types import MessageRole, UserMessage

        msgs: list[Message] = [
            UserMessage(role=MessageRole.USER, content="hello"),
            UserMessage(role=MessageRole.USER, content="world"),
        ]
        result = fast_prune(msgs, max_tokens=8192)
        assert result.elapsed_ms < 100
        assert len(result.messages) == 2

    def test_fast_prune_performance(self):
        from openlaoke.core.compact.fast_pruner import fast_prune
        from openlaoke.types.core_types import MessageRole, UserMessage

        msgs: list[Message] = [
            UserMessage(role=MessageRole.USER, content=f"Message {i} " * 100) for i in range(50)
        ]
        result = fast_prune(msgs, max_tokens=1000, keep_tail_tokens=500)
        assert result.elapsed_ms < 50


# ============================================================================
# SECTION 7: Bitter Lesson Tracker Tests
# ============================================================================


class TestBitterLessonTracker:
    def test_record_outcome(self):
        from openlaoke.core.bitter_lesson_tracker import BitterLessonTracker

        with tempfile.TemporaryDirectory() as d:
            tracker = BitterLessonTracker(data_dir=d)
            tracker.record_outcome(
                strategy_name="chain_of_thought",
                model_size="7B",
                success=True,
                duration_ms=100.0,
                tokens_used=500,
            )
            assert len(tracker.outcomes) == 1
            assert tracker.outcomes[0].strategy_name == "chain_of_thought"
            assert tracker.outcomes[0].success is True

    def test_learn_from_outcomes(self):
        from openlaoke.core.bitter_lesson_tracker import BitterLessonTracker

        with tempfile.TemporaryDirectory() as d:
            tracker = BitterLessonTracker(data_dir=d)
            for i in range(10):
                tracker.record_outcome("strategy_a", "7B", success=(i < 8), duration_ms=50.0)
            stats = tracker.get_strategy_stats()
            key = "strategy_a:7B"
            assert key in stats
            assert stats[key]["success_rate"] >= 0.7

    def test_disable_failing_strategy(self):
        from openlaoke.core.bitter_lesson_tracker import BitterLessonTracker

        with tempfile.TemporaryDirectory() as d:
            tracker = BitterLessonTracker(data_dir=d)
            for _ in range(10):
                tracker.record_outcome("bad_strategy", "1B", success=False, duration_ms=200.0)
            assert tracker.is_strategy_disabled("bad_strategy", "1B")

    def test_persistence(self):
        from openlaoke.core.bitter_lesson_tracker import BitterLessonTracker

        with tempfile.TemporaryDirectory() as d:
            tracker1 = BitterLessonTracker(data_dir=d)
            tracker1.record_outcome("test_strategy", "3B", success=True)
            tracker1.save()

            tracker2 = BitterLessonTracker(data_dir=d)
            stats = tracker2.get_strategy_stats()
            assert "test_strategy:3B" in stats


# ============================================================================
# SECTION 8: Small Model Optimizations Tests
# ============================================================================


class TestSmallModelOptimizations:
    def test_coerce_string_to_int(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {"properties": {"count": {"type": "integer"}}, "required": ["count"]}
        result = coerce_tool_args({"count": "42"}, schema)
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_coerce_string_to_bool(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {"properties": {"verbose": {"type": "boolean"}}, "required": []}
        result = coerce_tool_args({"verbose": "true"}, schema)
        assert result["verbose"] is True

        result = coerce_tool_args({"verbose": "false"}, schema)
        assert result["verbose"] is False

    def test_coerce_string_to_number(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {"properties": {"rate": {"type": "number"}}, "required": []}
        result = coerce_tool_args({"rate": "3.14"}, schema)
        assert abs(result["rate"] - 3.14) < 1e-9

    def test_coerce_preserves_correct_types(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {
            "properties": {
                "count": {"type": "integer"},
                "name": {"type": "string"},
            },
            "required": [],
        }
        result = coerce_tool_args({"count": 5, "name": "hello"}, schema)
        assert result["count"] == 5
        assert result["name"] == "hello"

    def test_coerce_empty_schema(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        result = coerce_tool_args({"key": "value"}, {})
        assert result == {"key": "value"}

    def test_coerce_none_value(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {"properties": {"count": {"type": "integer"}}, "required": []}
        result = coerce_tool_args({"count": None}, schema)
        assert result["count"] is None

    def test_coerce_any_of_type(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {
            "properties": {"timeout": {"anyOf": [{"type": "integer"}, {"type": "null"}]}},
            "required": [],
        }
        result = coerce_tool_args({"timeout": "30"}, schema)
        assert result["timeout"] == 30

    def test_coerce_string_to_array(self):
        from openlaoke.core.small_model_optimizations import coerce_tool_args

        schema = {"properties": {"items": {"type": "array"}}, "required": []}
        result = coerce_tool_args({"items": '["a", "b"]'}, schema)
        assert result["items"] == ["a", "b"]


# ============================================================================
# SECTION 9: Supervisor/Checker Tests
# ============================================================================


class TestTaskCompletionChecker:
    @pytest.mark.asyncio
    async def test_word_count_check(self):
        from openlaoke.core.supervisor.checker import TaskCompletionChecker
        from openlaoke.core.supervisor.requirements import TaskRequirements

        checker = TaskCompletionChecker()
        req = TaskRequirements(
            name="word_count_test",
            description="Check word count",
            check_type="word_count",
            threshold=10,
        )
        artifacts = {"content": "This is a test with more than ten words in it here and more."}
        result = await checker.check_requirement(req, artifacts)
        assert result is True

    @pytest.mark.asyncio
    async def test_word_count_fail(self):
        from openlaoke.core.supervisor.checker import TaskCompletionChecker
        from openlaoke.core.supervisor.requirements import TaskRequirements

        checker = TaskCompletionChecker()
        req = TaskRequirements(
            name="word_count_test",
            description="Check word count",
            check_type="word_count",
            threshold=100,
        )
        artifacts = {"content": "Short text."}
        result = await checker.check_requirement(req, artifacts)
        assert result is False

    @pytest.mark.asyncio
    async def test_contains_check(self):
        from openlaoke.core.supervisor.checker import TaskCompletionChecker
        from openlaoke.core.supervisor.requirements import TaskRequirements

        checker = TaskCompletionChecker()
        req = TaskRequirements(
            name="contains_test",
            description="Check contains patterns",
            check_type="contains",
            patterns=["hello", "world"],
        )
        artifacts = {"content": "hello beautiful world"}
        result = await checker.check_requirement(req, artifacts)
        assert result is True

    @pytest.mark.asyncio
    async def test_file_exists_check(self, temp_dir):
        from openlaoke.core.supervisor.checker import TaskCompletionChecker
        from openlaoke.core.supervisor.requirements import TaskRequirements

        path = os.path.join(temp_dir, "output.txt")
        with open(path, "w") as f:
            f.write("content")
        checker = TaskCompletionChecker()
        req = TaskRequirements(
            name="file_test",
            description="Check file exists",
            check_type="file_exists",
        )
        result = await checker.check_requirement(req, {"output_files": [path]})
        assert result is True

    @pytest.mark.asyncio
    async def test_file_exists_fail(self, temp_dir):
        from openlaoke.core.supervisor.checker import TaskCompletionChecker
        from openlaoke.core.supervisor.requirements import TaskRequirements

        checker = TaskCompletionChecker()
        req = TaskRequirements(
            name="file_test",
            description="Check file exists",
            check_type="file_exists",
        )
        result = await checker.check_requirement(req, {"output_files": ["/nonexistent/file.txt"]})
        assert result is False


# ============================================================================
# SECTION 10: Slug Utils Tests
# ============================================================================


class TestSlugUtils:
    def test_basic_slug(self):
        from openlaoke.core.supervisor.slug_utils import generate_slug

        slug = generate_slug("What do we know about scaling laws?")
        assert "scaling" in slug
        assert "laws" in slug
        assert slug == slug.lower()
        assert " " not in slug

    def test_filler_word_removal(self):
        from openlaoke.core.supervisor.slug_utils import generate_slug

        slug = generate_slug("The main benefits of the new approach")
        assert "the" not in slug.split("-")
        assert "of" not in slug.split("-")

    def test_max_words(self):
        from openlaoke.core.supervisor.slug_utils import generate_slug

        slug = generate_slug("very long topic about many different things here", max_words=3)
        parts = slug.split("-")
        assert len(parts) <= 3

    def test_special_characters(self):
        from openlaoke.core.supervisor.slug_utils import generate_slug

        slug = generate_slug("RLHF alternatives (comparison)")
        assert all(c.isalnum() or c == "-" for c in slug)

    def test_empty_input(self):
        from openlaoke.core.supervisor.slug_utils import generate_slug

        slug = generate_slug("")
        assert isinstance(slug, str)


# ============================================================================
# SECTION 11: Bash Classifier Tests
# ============================================================================


class TestBashClassifier:
    def test_safe_commands(self):
        from openlaoke.utils.permissions.bash_classifier import (
            CommandSafetyLevel,
            classify_bash_command,
        )

        result = classify_bash_command("ls -la")
        assert result.safety_level == CommandSafetyLevel.SAFE

        result = classify_bash_command("echo hello")
        assert result.safety_level == CommandSafetyLevel.SAFE

        result = classify_bash_command("git status")
        assert result.safety_level == CommandSafetyLevel.SAFE

    def test_dangerous_commands(self):
        from openlaoke.utils.permissions.bash_classifier import (
            CommandSafetyLevel,
            classify_bash_command,
        )

        result = classify_bash_command("sudo rm -rf /tmp/test")
        assert result.safety_level in (CommandSafetyLevel.DANGEROUS, CommandSafetyLevel.DESTRUCTIVE)

    def test_destructive_commands(self):
        from openlaoke.utils.permissions.bash_classifier import (
            CommandSafetyLevel,
            classify_bash_command,
        )

        result = classify_bash_command("rm -rf /")
        assert result.safety_level == CommandSafetyLevel.DESTRUCTIVE

        result = classify_bash_command("mkfs.ext4 /dev/sda")
        assert result.safety_level == CommandSafetyLevel.DESTRUCTIVE

    def test_classification_result_fields(self):
        from openlaoke.utils.permissions.bash_classifier import classify_bash_command

        result = classify_bash_command("ls")
        assert hasattr(result, "safety_level")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reason")

    def test_pipe_commands(self):
        from openlaoke.utils.permissions.bash_classifier import (
            CommandSafetyLevel,
            classify_bash_command,
        )

        result = classify_bash_command("cat file.txt | grep pattern")
        assert result.safety_level == CommandSafetyLevel.SAFE

    def test_npm_commands(self):
        from openlaoke.utils.permissions.bash_classifier import (
            CommandSafetyLevel,
            classify_bash_command,
        )

        result = classify_bash_command("npm install")
        assert result.safety_level == CommandSafetyLevel.SAFE

        result = classify_bash_command("npm test")
        assert result.safety_level == CommandSafetyLevel.SAFE


# ============================================================================
# SECTION 12: Tool Dedup Tests
# ============================================================================


class TestToolDedup:
    def test_cache_read_only_tool(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        assert cache.check("Read", {"file_path": "/tmp/a.txt"}) is None
        cache.record("Read", {"file_path": "/tmp/a.txt"}, "file contents")
        result = cache.check("Read", {"file_path": "/tmp/a.txt"})
        assert result == "file contents"

    def test_no_cache_for_write_tools(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        cache.record("Bash", {"command": "ls"}, "output")
        assert cache.check("Bash", {"command": "ls"}) is None

    def test_different_args_not_cached(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        cache.record("Read", {"file_path": "/tmp/a.txt"}, "content a")
        assert cache.check("Read", {"file_path": "/tmp/b.txt"}) is None

    def test_window_size_eviction(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache(window_size=3)
        for i in range(5):
            cache.record("Read", {"file_path": f"/tmp/{i}.txt"}, f"content {i}")
        assert cache.check("Read", {"file_path": "/tmp/0.txt"}) is None
        assert cache.check("Read", {"file_path": "/tmp/4.txt"}) == "content 4"

    def test_clear(self):
        from openlaoke.core.tool_dedup import ToolCallCache

        cache = ToolCallCache()
        cache.record("Read", {"file_path": "/a"}, "result")
        cache.clear()
        assert cache.check("Read", {"file_path": "/a"}) is None


# ============================================================================
# SECTION 13: Cross-Project Lessons Tests
# ============================================================================


class TestCrossProjectLessons:
    def test_lessons_exist(self):
        from openlaoke.core.cross_project_lessons import CROSS_PROJECT_LESSONS

        assert len(CROSS_PROJECT_LESSONS) > 0

    def test_lesson_structure(self):
        from openlaoke.core.cross_project_lessons import CROSS_PROJECT_LESSONS

        for lesson in CROSS_PROJECT_LESSONS:
            assert lesson.source_project != ""
            assert lesson.category in (
                "small_model",
                "architecture",
                "context",
                "tools",
                "prompt",
                "ui",
            )
            assert lesson.lesson != ""
            assert lesson.what_works != ""
            assert lesson.what_fails != ""
            assert lesson.priority in ("high", "medium", "low")

    def test_bitter_lesson_alignment(self):
        from openlaoke.core.cross_project_lessons import CROSS_PROJECT_LESSONS

        aligned = [lsn for lsn in CROSS_PROJECT_LESSONS if lsn.bitter_lesson_alignment]
        assert len(aligned) > 0


# ============================================================================
# SECTION 14: Model Assessment Tests
# ============================================================================


class TestModelAssessment:
    def test_known_model_tiers(self):
        from openlaoke.core.model_assessment.types import ModelTier, classify_model_tier

        assert classify_model_tier("claude-sonnet-4-20250514") == ModelTier.TIER_1_ADVANCED
        assert classify_model_tier("llama-3.2-1b") == ModelTier.TIER_5_LIMITED
        assert classify_model_tier("unknown-model") == ModelTier.TIER_3_MODERATE

    def test_tier_enum(self):
        from openlaoke.core.model_assessment.types import ModelTier

        assert ModelTier.TIER_1_ADVANCED is not None
        assert ModelTier.TIER_5_LIMITED is not None

    def test_assessor_get_tier(self):
        from openlaoke.core.model_assessment.assessor import ModelAssessor
        from openlaoke.core.model_assessment.types import ModelTier

        class FakeConfig:
            providers = {}

        assessor = ModelAssessor(FakeConfig())
        tier = assessor.get_tier("gpt-4")
        assert isinstance(tier, ModelTier)

    def test_assessor_get_granularity(self):
        from openlaoke.core.model_assessment.assessor import ModelAssessor
        from openlaoke.core.model_assessment.types import TaskGranularity

        class FakeConfig:
            providers = {}

        assessor = ModelAssessor(FakeConfig())
        gran = assessor.get_granularity("gpt-4")
        assert isinstance(gran, TaskGranularity)


# ============================================================================
# SECTION 15: Memory SQLite Tests
# ============================================================================


class TestMemorySQLite:
    def test_store_and_recall(self):
        from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore

        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "test_memories.db"
            store = SQLiteMemoryStore(db_path=db_path)
            record = MemoryRecord(
                id="mem_001", content="test_value", key="test_key", memory_type="general"
            )
            record_id = store.store(record)
            assert record_id is not None
            result = store.recall(record_id)
            assert result is not None
            assert result.content == "test_value"
            store.close()

    def test_search(self):
        from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore

        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "test_memories.db"
            store = SQLiteMemoryStore(db_path=db_path)
            store.store(
                MemoryRecord(id="mem_py", content="Python is a programming language", key="python")
            )
            store.store(MemoryRecord(id="mem_rs", content="Rust is a systems language", key="rust"))
            results = store.search_bm25("programming language")
            assert isinstance(results, list)
            store.close()

    def test_delete(self):
        from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore

        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "test_memories.db"
            store = SQLiteMemoryStore(db_path=db_path)
            record = MemoryRecord(
                id="mem_tmp", content="temp_value", key="temp_key", memory_type="temp"
            )
            record_id = store.store(record)
            deleted = store.delete(record_id)
            assert deleted is True
            result = store.recall(record_id)
            assert result is None
            store.close()

    def test_stats(self):
        from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore

        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / "test_memories.db"
            store = SQLiteMemoryStore(db_path=db_path)
            store.store(MemoryRecord(id="mem_s1", content="value 1", key="k1", memory_type="cat1"))
            store.store(MemoryRecord(id="mem_s2", content="value 2", key="k2", memory_type="cat2"))
            stats = store.get_stats()
            assert isinstance(stats, dict)
            assert stats.get("total_memories", 0) >= 2
            store.close()


# ============================================================================
# SECTION 16: Commands Registry Tests
# ============================================================================


class TestCommandsRegistry:
    def test_register_all(self):
        from openlaoke.commands.registry import _commands, register_all

        register_all()
        assert len(_commands) > 0

    def test_known_commands_exist(self):
        from openlaoke.commands.registry import _commands, register_all

        register_all()
        expected_commands = ["help", "exit", "clear", "model", "history"]
        for cmd in expected_commands:
            assert cmd in _commands, f"Command '{cmd}' not found in registry"

    def test_command_has_required_fields(self):
        from openlaoke.commands.registry import _commands, register_all

        register_all()
        for _name, cmd in _commands.items():
            assert hasattr(cmd, "name")
            assert hasattr(cmd, "description")
            assert hasattr(cmd, "execute") or hasattr(cmd, "run")


# ============================================================================
# SECTION 17: Permissions Tests
# ============================================================================


class TestPermissions:
    def test_default_config(self):
        config = PermissionConfig.defaults()
        assert config is not None
        assert hasattr(config, "mode")

    def test_check_tool(self):
        config = PermissionConfig.defaults()
        result = config.check_tool("Read")
        assert result in (PermissionResult.ALLOW, PermissionResult.ASK, PermissionResult.DENY)

    def test_safe_tools_allowed(self):
        config = PermissionConfig.defaults()
        result = config.check_tool("Read")
        assert result == PermissionResult.ALLOW


# ============================================================================
# SECTION 18: Integration / End-to-End Tests
# ============================================================================


class TestIntegration:
    @pytest.mark.asyncio
    async def test_tool_registry_with_real_tools(self):
        from openlaoke.core.tool import ToolRegistry
        from openlaoke.tools.register import register_all_tools

        registry = ToolRegistry()
        register_all_tools(registry)
        loaded = registry.get_loaded()
        assert len(loaded) > 0
        tool_names = [t.name for t in loaded]
        assert "Bash" in tool_names
        assert "Read" in tool_names

    @pytest.mark.asyncio
    async def test_full_read_write_cycle(self, temp_dir):
        from openlaoke.tools.read_tool import ReadTool
        from openlaoke.tools.write_tool import WriteTool

        ctx = _make_ctx(temp_dir)
        write_tool = WriteTool()
        read_tool = ReadTool()

        path = os.path.join(temp_dir, "cycle_test.txt")
        await write_tool.call(ctx, file_path=path, content="initial content")
        result = await read_tool.call(ctx, file_path=path)
        assert "initial content" in result.content

    @pytest.mark.asyncio
    async def test_full_write_edit_read_cycle(self, temp_dir):
        from openlaoke.tools.edit_tool import EditTool
        from openlaoke.tools.read_tool import ReadTool
        from openlaoke.tools.write_tool import WriteTool

        ctx = _make_ctx(temp_dir)
        path = os.path.join(temp_dir, "edit_cycle.txt")

        write_tool = WriteTool()
        await write_tool.call(ctx, file_path=path, content="foo bar baz")

        edit_tool = EditTool()
        await edit_tool.call(ctx, file_path=path, old_text="bar", new_text="BAR")

        read_tool = ReadTool()
        result = await read_tool.call(ctx, file_path=path)
        assert "foo BAR baz" in result.content

    @pytest.mark.asyncio
    async def test_glob_and_grep_integration(self, temp_dir):
        from openlaoke.tools.glob_tool import GlobTool
        from openlaoke.tools.grep_tool import GrepTool

        os.makedirs(os.path.join(temp_dir, "src"))
        for name, content in [
            ("src/main.py", "def main():\n    print('hello')\n"),
            ("src/utils.py", "def helper():\n    pass\n"),
            ("src/data.txt", "no functions here\n"),
        ]:
            with open(os.path.join(temp_dir, name), "w") as f:
                f.write(content)

        ctx = _make_ctx(temp_dir)
        glob_tool = GlobTool()
        result = await glob_tool.call(ctx, pattern="**/*.py", path=temp_dir)
        assert "main.py" in result.content
        assert "utils.py" in result.content
        assert "data.txt" not in result.content

        grep_tool = GrepTool()
        result = await grep_tool.call(ctx, pattern="def \\w+", path=temp_dir, glob="*.py")
        assert "main" in result.content
        assert "helper" in result.content

    def test_version_exists(self):
        from openlaoke import __version__

        assert __version__ is not None
        assert len(__version__) > 0
        parts = __version__.split(".")
        assert len(parts) == 3

    def test_state_factory(self):
        state = create_app_state(model="test-model")
        assert state.session_config.model == "test-model"
        assert state.session_id.startswith("session_")


# ============================================================================
# SECTION 19: Context Hygiene Tests
# ============================================================================


class TestContextHygiene:
    def test_import_write_buffer(self, temp_dir):
        from openlaoke.core.supervisor.context_hygiene import WriteBuffer

        path = os.path.join(temp_dir, "output.md")
        buffer = WriteBuffer(file_path=path)
        assert buffer is not None

    def test_extract_key_quotes(self):
        from openlaoke.core.supervisor.context_hygiene import extract_key_quotes

        text = 'The paper says "scaling laws are universal" and also notes "compute is key".'
        result = extract_key_quotes(text)
        assert isinstance(result, str)
        assert len(result) > 0


# ============================================================================
# SECTION 20: Read Tracker Tests
# ============================================================================


class TestReadTracker:
    def test_read_tracker_creation(self):
        from openlaoke.core.read_tracker import ReadTracker

        tracker = ReadTracker()
        assert tracker is not None

    def test_record_read(self):
        from openlaoke.core.read_tracker import ReadTracker

        tracker = ReadTracker()
        tracker.record_read("/tmp/file1.txt")
        assert tracker.has_read("/tmp/file1.txt")

    def test_should_guard_read(self):
        from openlaoke.core.read_tracker import ReadTracker

        tracker = ReadTracker()
        for _ in range(20):
            tracker.record_read("/tmp/same_file.txt")
        result = tracker.should_guard_read(file_size=1000)
        assert isinstance(result, bool)

    def test_reset(self):
        from openlaoke.core.read_tracker import ReadTracker

        tracker = ReadTracker()
        tracker.record_read("/tmp/file.txt")
        tracker.reset()
        assert not tracker.has_read("/tmp/file.txt")


# ============================================================================
# SECTION 21: Tool Call Parser Tests
# ============================================================================


class TestToolCallParser:
    def test_parser_import(self):
        from openlaoke.core.tool_call_parser import extract_tool_calls

        assert callable(extract_tool_calls)

    def test_extract_tool_calls(self):
        from openlaoke.core.tool_call_parser import extract_tool_calls

        text = '```json\n{"name": "Bash", "arguments": {"command": "ls"}}\n```'
        calls = extract_tool_calls(text)
        assert isinstance(calls, list)


# ============================================================================
# SECTION 22: Early Stop Tests
# ============================================================================


class TestEarlyStop:
    def test_early_stop_import(self):
        from openlaoke.core.early_stop import EarlyStopDetector

        detector = EarlyStopDetector()
        assert detector is not None

    def test_detect_read_loop(self):
        from openlaoke.core.early_stop import EarlyStopDetector

        detector = EarlyStopDetector()
        result = detector.detect_read_loop("Read")
        assert hasattr(result, "should_stop") or isinstance(result, bool) or result is not None

    def test_detect_repetition(self):
        from openlaoke.core.early_stop import EarlyStopDetector

        detector = EarlyStopDetector()
        long_text = "hello world " * 200
        result = detector.detect_repetition(long_text)
        assert result is not None

    def test_reset_all(self):
        from openlaoke.core.early_stop import EarlyStopDetector

        detector = EarlyStopDetector()
        detector.reset_all()
        assert detector._consecutive_reads == 0


# ============================================================================
# SECTION 23: Knowledge Base Tests
# ============================================================================


class TestKnowledgeBase:
    def test_knowledge_base_creation(self):
        from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase

        with tempfile.TemporaryDirectory() as d:
            kb = EnhancedKnowledgeBase(cache_dir=Path(d))
            assert kb is not None

    def test_knowledge_base_has_methods(self):
        from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase

        with tempfile.TemporaryDirectory() as d:
            kb = EnhancedKnowledgeBase(cache_dir=Path(d))
            assert hasattr(kb, "search")


# ============================================================================
# SECTION 24: Skill System Tests
# ============================================================================


class TestSkillSystem:
    def test_skill_registry_import(self):
        from openlaoke.core.skill_system import SkillRegistry, get_skill_registry

        registry = get_skill_registry()
        assert isinstance(registry, SkillRegistry)

    def test_list_available_skills(self):
        from openlaoke.core.skill_system import list_available_skills

        skills = list_available_skills()
        assert isinstance(skills, list)

    def test_skill_dataclass(self):
        from openlaoke.core.skill_system import Skill

        skill = Skill(name="test", description="A test skill", path="/tmp/test")
        assert skill.name == "test"


# ============================================================================
# SECTION 25: Quality Monitor Tests
# ============================================================================


class TestQualityMonitor:
    def test_quality_monitor_creation(self):
        from openlaoke.core.quality_monitor import QualityMonitor

        monitor = QualityMonitor()
        assert monitor is not None


# ============================================================================
# SECTION 26: Trust Decay Tests
# ============================================================================


class TestTrustDecay:
    def test_trust_decay_import(self):
        from openlaoke.core.trust_decay import TrustDecay

        decay = TrustDecay()
        assert decay is not None

    def test_record_failure(self):
        from openlaoke.core.trust_decay import TrustDecay

        decay = TrustDecay()
        decay.record_failure("Bash")
        count = decay.get_failure_count("Bash")
        assert count >= 1

    def test_record_success(self):
        from openlaoke.core.trust_decay import TrustDecay

        decay = TrustDecay()
        decay.record_failure("Read")
        decay.record_success("Read")
        assert not decay.is_dropped("Read")

    def test_drop_threshold(self):
        from openlaoke.core.trust_decay import TrustDecay

        decay = TrustDecay(drop_threshold=3)
        for _ in range(5):
            decay.record_failure("BadTool")
        assert decay.is_dropped("BadTool")


# ============================================================================
# SECTION 27: Token Budget Tests
# ============================================================================


class TestTokenBudget:
    def test_token_budget_import(self):
        from openlaoke.core.compact.token_budget import TokenBudget

        budget = TokenBudget(max_input_tokens=8192)
        assert budget is not None
        assert budget.max_input_tokens == 8192

    def test_budget_fields(self):
        from openlaoke.core.compact.token_budget import TokenBudget

        budget = TokenBudget(max_input_tokens=10000, max_output_tokens=4096)
        assert budget.max_input_tokens == 10000
        assert budget.max_output_tokens == 4096
        assert budget.trigger_threshold == 0.8


# ==============================================================================
# SECTION 28: Security Tests
# ==============================================================================


class TestSecurityComprehensive:
    def test_sanitize_path_within_workspace(self):
        import os
        import tempfile

        from openlaoke.utils.security import sanitize_path

        with tempfile.TemporaryDirectory() as d:
            real_d = os.path.realpath(d)
            result = sanitize_path("sub/file.txt", real_d)
            assert "sub" in result

    def test_sanitize_path_outside_raises(self):
        import os
        import tempfile

        from openlaoke.utils.security import sanitize_path

        with tempfile.TemporaryDirectory() as d:
            import pytest

            with pytest.raises(ValueError):
                sanitize_path("/etc/passwd", os.path.realpath(d))

    def test_redact_api_key(self):
        from openlaoke.utils.security import redact_credentials

        result = redact_credentials("api_key=sk-1234567890abcdefghij")
        assert "sk-1234567890abcdefghij" not in result

    def test_redact_bearer_token(self):
        from openlaoke.utils.security import redact_credentials

        result = redact_credentials("Authorization: Bearer xyz.abc.123")
        assert "xyz.abc.123" not in result

    def test_redact_plain_text(self):
        from openlaoke.utils.security import redact_credentials

        text = "normal text without secrets"
        assert redact_credentials(text) == text

    def test_strip_ansi(self):
        from openlaoke.utils.security import strip_ansi

        assert strip_ansi("\x1b[32mgreen\x1b[0m") == "green"

    def test_sanitize_tool_args(self):
        from openlaoke.utils.security import sanitize_tool_args

        result = sanitize_tool_args({"cmd": "\x1b[31mrm\x1b[0m /tmp"})
        assert result["cmd"] == "rm /tmp"


# ==============================================================================
# SECTION 29: Action Classifier Tests
# ==============================================================================


class TestActionClassifierComprehensive:
    def test_classify_question(self):
        from openlaoke.core.action_classifier import ActionKind, classify_action

        assert classify_action("how do I fix this?").kind == ActionKind.CLARIFY

    def test_classify_action(self):
        from openlaoke.core.action_classifier import ActionKind, classify_action

        assert classify_action("fix the bug in login.py").kind == ActionKind.ACTION

    def test_classify_greeting(self):
        from openlaoke.core.action_classifier import ActionKind, classify_action

        assert classify_action("hello world").kind == ActionKind.GREETING

    def test_classify_praise(self):
        from openlaoke.core.action_classifier import ActionKind, classify_action

        assert classify_action("thanks!").kind == ActionKind.PRAISE

    def test_classify_respond(self):
        from openlaoke.core.action_classifier import ActionKind, classify_action

        assert classify_action("ok understood").kind == ActionKind.RESPOND


# ==============================================================================
# SECTION 30: Adaptive Router Tests
# ==============================================================================


class TestAdaptiveRouterComprehensive:
    def test_initial_state(self):
        from openlaoke.core.adaptive_router import AdaptiveRouter

        r = AdaptiveRouter()
        assert r.current_tier_name == "fast"
        assert r.current_model == "gemma3:1b"

    def test_promote_on_failures(self):
        from openlaoke.core.adaptive_router import AdaptiveRouter

        r = AdaptiveRouter()
        for _ in range(5):
            r.record_failure()
        r.route()
        assert r.current_tier_name == "default"

    def test_reset(self):
        from openlaoke.core.adaptive_router import AdaptiveRouter

        r = AdaptiveRouter()
        for _ in range(5):
            r.record_failure()
        r.route()
        r.reset()
        assert r.current_tier_name == "fast"


# ==============================================================================
# SECTION 31: Trace Recorder Tests
# ==============================================================================


class TestTraceRecorderComprehensive:
    def test_record_turn(self):
        import tempfile

        from openlaoke.core.trace_recorder import TraceRecorder

        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("s1", "gpt-4")
            tr.start_turn("t1", "gpt-4", "fix")
            tr.record_tool_call_start()
            tr.record_tool_call("Bash", {"command": "ls"}, "ok", False)
            tr.end_turn(success=True)
            turns = tr.get_session("s1")
            assert turns is not None and len(turns) == 1
            assert turns[0].success

    def test_regression_test_generation(self):
        import tempfile

        from openlaoke.core.trace_recorder import TraceRecorder

        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("s1", "gpt-4")
            tr.start_turn("t1", "gpt-4", "fix bug")
            tr.record_tool_call_start()
            tr.record_tool_call("Read", {"file_path": "x.py"}, "code", False)
            tr.end_turn(success=True)
            code = tr.generate_regression_test("s1", 0)
            assert code is not None
            assert "pytest" in code


# ==============================================================================
# SECTION 32: Evidence Store Tests
# ==============================================================================


class TestEvidenceStoreComprehensive:
    def test_record_and_stats(self):
        import tempfile

        from openlaoke.core.evidence_store import EvidenceStore

        with tempfile.TemporaryDirectory() as d:
            es = EvidenceStore(store_dir=d)
            es.record("task1", "s1", "worked")
            es.record("task1", "s2", "failed")
            stats = es.get_stats()
            assert stats["total"] == 2
            assert stats["worked"] == 1

    def test_persistence(self):
        import tempfile

        from openlaoke.core.evidence_store import EvidenceStore

        with tempfile.TemporaryDirectory() as d:
            es1 = EvidenceStore(store_dir=d)
            es1.record("t1", "s1", "worked")
            es2 = EvidenceStore(store_dir=d)
            assert any(e.strategy == "s1" for e in es2.get_working_strategies("t1"))


# ==============================================================================
# SECTION 33: Message Images Tests
# ==============================================================================


class TestMessageImagesComprehensive:
    def test_vision_model_detection(self):
        from openlaoke.core.message_images import model_supports_vision

        assert model_supports_vision("gpt-4o")
        assert model_supports_vision("claude-sonnet-4-20250514")
        assert not model_supports_vision("gpt-3.5-turbo")

    def test_extract_no_images(self):
        from openlaoke.core.message_images import extract_image_paths

        assert extract_image_paths("plain text", "/tmp") == []


# ==============================================================================
# SECTION 34: Dependency Graph Tests
# ==============================================================================


class TestDependencyGraphComprehensive:
    def test_parse_plan(self):
        from openlaoke.core.dependency_graph import parse_plan

        steps = parse_plan("1. Create models.py\n2. Create routes.py\n3. Test")
        assert len(steps) == 3

    def test_empty_plan(self):
        from openlaoke.core.dependency_graph import parse_plan

        assert parse_plan("no steps") == []

    def test_build_groups(self):
        from openlaoke.core.dependency_graph import build_dependency_graph, parse_plan

        steps = parse_plan("1. Edit models.py\n2. Edit routes.py")
        groups = build_dependency_graph(steps)
        assert len(groups) > 0


# ==============================================================================
# SECTION 35: Compound Tools Tests
# ==============================================================================


class TestCompoundToolsComprehensive:
    def test_read_and_patch_exists(self):
        from openlaoke.tools.compound_tools import ReadAndPatchTool

        t = ReadAndPatchTool()
        assert t.name == "ReadAndPatch"
        assert t.requires_approval

    def test_find_and_read_exists(self):
        from openlaoke.tools.compound_tools import FindAndReadTool

        t = FindAndReadTool()
        assert t.name == "FindAndRead"
        assert t.is_read_only

    def test_search_and_read_exists(self):
        from openlaoke.tools.compound_tools import SearchAndReadTool

        t = SearchAndReadTool()
        assert t.name == "SearchAndRead"
        assert t.is_read_only
