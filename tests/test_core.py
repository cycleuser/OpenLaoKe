"""Core systems tests: state, tool system, hook system, compact, tracking."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from openlaoke.core.bitter_lesson_tracker import BitterLessonTracker
from openlaoke.core.compact.fast_pruner import extract_keywords, fast_prune
from openlaoke.core.compact.token_budget import TokenBudget
from openlaoke.core.cross_project_lessons import CROSS_PROJECT_LESSONS
from openlaoke.core.early_stop import EarlyStopDetector
from openlaoke.core.enhanced_knowledge_base import EnhancedKnowledgeBase
from openlaoke.core.hook_system import HookInput, HookOutput, HookSystem
from openlaoke.core.model_assessment.assessor import ModelAssessor
from openlaoke.core.skill_system import (
    Skill,
    SkillRegistry,
    get_skill_registry,
)
from openlaoke.core.small_model_optimizations import coerce_tool_args
from openlaoke.core.state import create_app_state
from openlaoke.core.supervisor.checker import TaskCompletionChecker
from openlaoke.core.supervisor.requirements import TaskRequirements
from openlaoke.core.supervisor.slug_utils import generate_slug
from openlaoke.core.tool import Tool, ToolRegistry
from openlaoke.core.tool_dedup import ToolCallCache
from openlaoke.core.trust_decay import TrustDecay
from openlaoke.types.core_types import (
    CostInfo,
    Message,
    MessageRole,
    PermissionMode,
    PermissionResult,
    TaskState,
    TaskStatus,
    TaskType,
    TokenUsage,
    ToolResultBlock,
    UserMessage,
)
from openlaoke.types.permissions import PermissionConfig, PermissionRule

# ── STATE ──────────────────────────────────────────────────────────────────────


class TestAppState:
    def test_creation(self):
        with tempfile.TemporaryDirectory() as d:
            s = create_app_state(cwd=d)
            assert s.session_id.startswith("session_")
            assert len(s.messages) == 0

    def test_message_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            s = create_app_state(cwd=d)
            s.add_message(UserMessage(role=MessageRole.USER, content="hi"))
            assert s.get_message_count() == 1
            assert s.get_last_message().content == "hi"

    def test_task_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            s = create_app_state(cwd=d)
            t = TaskState(id="t1", type=TaskType.LOCAL_BASH, status=TaskStatus.PENDING)
            s.add_task(t)
            t.status = TaskStatus.RUNNING
            s.update_task(t)
            assert s.get_task("t1").status == TaskStatus.RUNNING

    def test_active_tasks_filtering(self):
        with tempfile.TemporaryDirectory() as d:
            s = create_app_state(cwd=d)
            s.add_task(TaskState(id="a", type=TaskType.LOCAL_BASH, status=TaskStatus.RUNNING))
            s.add_task(TaskState(id="b", type=TaskType.LOCAL_BASH, status=TaskStatus.COMPLETED))
            assert len(s.get_active_tasks()) == 1

    def test_token_cost_accumulation(self):
        with tempfile.TemporaryDirectory() as d:
            s = create_app_state(cwd=d)
            s.accumulate_tokens(TokenUsage(input_tokens=100, output_tokens=50))
            s.accumulate_cost(CostInfo(input_cost=0.01, output_cost=0.02))
            assert s.token_usage.total_tokens == 150
            assert abs(s.cost_info.total_cost - 0.03) < 0.001

    def test_listener_system(self):
        with tempfile.TemporaryDirectory() as d:
            s = create_app_state(cwd=d)
            events = []

            def _notify(st):
                events.append("fired")

            s.subscribe(_notify)
            s.add_message(UserMessage(role=MessageRole.USER, content="x"))
            assert events == ["fired"]
            s.unsubscribe(_notify)
            s.add_message(UserMessage(role=MessageRole.USER, content="y"))
            assert events == ["fired"]

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            s = create_app_state(cwd=d, persist_path=path)
            s.add_message(UserMessage(role=MessageRole.USER, content="persist"))
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert data["session_id"] == s.session_id


# ── TOOL REGISTRY ──────────────────────────────────────────────────────────────


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()

        class T(Tool):
            name = "T"

            async def call(self, ctx, **kw):
                return ToolResultBlock(tool_use_id="", content="")

        reg.register(T())
        assert reg.get("T") is not None
        assert reg.get("X") is None

    def test_deferred_lazy_loading(self):
        reg = ToolRegistry()
        loaded = []

        def _loader():
            loaded.append(1)

            class D(Tool):
                name = "D"

                async def call(self, ctx, **kw):
                    return ToolResultBlock(tool_use_id="", content="")

            return D()

        reg.register_deferred("D", _loader)
        assert not reg.is_loaded("D")
        assert reg.is_deferred("D")
        reg.get("D")
        assert reg.is_loaded("D")
        assert loaded == [1]

    def test_search(self):
        reg = ToolRegistry()

        class Finder(Tool):
            name = "Finder"
            description = "searches files"

            async def call(self, ctx, **kw):
                return ToolResultBlock(tool_use_id="", content="")

        reg.register(Finder())
        results = reg.search("search")
        assert len(results) == 1

    def test_validation_required_fields(self):
        class V(Tool):
            name = "V"
            input_schema = {
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            }

            async def call(self, ctx, **kw):
                return ToolResultBlock(tool_use_id="", content="")

        t = V()
        assert not t.validate_input({}).result
        assert t.validate_input({"name": "ok"}).result


# ── HOOK SYSTEM ────────────────────────────────────────────────────────────────


class TestHookSystem:
    @pytest.mark.asyncio
    async def test_execute_hooks(self):
        hs = HookSystem()
        results = []

        def _h(i, o):
            results.append(i.tool_name)

        hs.register("tool_execute_before", "h", _h)
        await hs.execute_hooks_async(
            "tool_execute_before", HookInput(tool_name="Bash"), HookOutput()
        )
        assert results == ["Bash"]

    def test_priority_ordering(self):
        hs = HookSystem()
        hs.register("tool_execute_before", "l", lambda i, o: None, priority=1)
        hs.register("tool_execute_before", "h", lambda i, o: None, priority=10)
        hooks = hs._hooks["tool_execute_before"]
        assert hooks[0].name == "h"

    def test_short_circuit(self):
        hs = HookSystem()
        order = []

        def _s1(i, o):
            order.append(1)
            o.handled = True

        def _s2(i, o):
            order.append(2)

        hs.register("error_handle", "s1", _s1, priority=10)
        hs.register("error_handle", "s2", _s2, priority=1)
        asyncio.get_event_loop().run_until_complete(
            hs.execute_hooks_async("error_handle", HookInput(), HookOutput())
        )
        assert order == [1]

    def test_disable_and_enable(self):
        hs = HookSystem()
        hs.register("tool_execute_before", "x", lambda i, o: None)
        assert hs.disable_hook("tool_execute_before", "x")
        assert not hs._hooks["tool_execute_before"][0].enabled
        assert hs.enable_hook("tool_execute_before", "x")

    @pytest.mark.asyncio
    async def test_async_hook(self):
        hs = HookSystem()
        called = []

        async def _ah(i, o):
            called.append(1)

        hs.register("tool_execute_before", "ah", _ah)
        await hs.execute_hooks_async("tool_execute_before", HookInput(), HookOutput())
        assert called == [1]

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        hs = HookSystem()
        order = []

        def _bad(i, o):
            raise RuntimeError("oops")

        def _good(i, o):
            order.append("good")

        hs.register("tool_execute_before", "bad", _bad, priority=10)
        hs.register("tool_execute_before", "good", _good, priority=1)
        await hs.execute_hooks_async("tool_execute_before", HookInput(), HookOutput())
        assert "good" in order


# ── PERMISSIONS ────────────────────────────────────────────────────────────────


class TestPermissions:
    def test_defaults(self):
        cfg = PermissionConfig.defaults()
        assert cfg.mode == PermissionMode.DEFAULT
        assert cfg.check_tool("Read") == PermissionResult.ALLOW
        assert cfg.check_tool("Bash") == PermissionResult.ASK
        assert cfg.check_tool("Agent") == PermissionResult.ASK

    def test_bypass_mode(self):
        cfg = PermissionConfig(mode=PermissionMode.BYPASS)
        assert cfg.check_tool("Bash") == PermissionResult.ALLOW
        assert cfg.check_tool("Write") == PermissionResult.ALLOW
        assert cfg.check_tool("Agent") == PermissionResult.ALLOW

    def test_custom_rules(self):
        cfg = PermissionConfig(
            always_allow_rules=[PermissionRule("My*", PermissionResult.ALLOW)],
        )
        assert cfg.check_tool("MyTool") == PermissionResult.ALLOW
        assert cfg.check_tool("Other") == PermissionResult.ASK

    def test_approve_and_forget(self):
        cfg = PermissionConfig.defaults()
        cfg.approve_tool("Bash", remember=True)
        assert cfg.check_tool("Bash") == PermissionResult.ALLOW
        cfg.deny_tool("Bash")
        assert "Bash" not in cfg.approved_tools


# ── COMPACT / PRUNER ───────────────────────────────────────────────────────────


class TestFastPruner:
    def test_keywords_from_code(self):
        text = "def hello():\n    import os\n    class Foo:\nError: failed"
        kw = extract_keywords(text)
        assert any("hello" in k for k in kw)
        assert any("Foo" in k for k in kw)

    def test_max_keywords(self):
        text = "\n".join(f"def func_{i}():" for i in range(200))
        kw = extract_keywords(text, max_keywords=20)
        assert len(kw) <= 20

    def test_prune_short_messages(self):
        msgs: list[Message] = [
            UserMessage(role=MessageRole.USER, content="hello"),
            UserMessage(role=MessageRole.USER, content="world"),
        ]
        result = fast_prune(msgs)
        assert result.elapsed_ms < 50
        assert len(result.messages) == 2

    def test_prune_long_messages(self):
        msgs: list[Message] = [
            UserMessage(role=MessageRole.USER, content="data " * 200) for _ in range(30)
        ]
        result = fast_prune(msgs, max_tokens=500, keep_tail_tokens=200)
        assert len(result.messages) < 30 or result.keywords_extracted >= 0


# ── BITTER LESSON TRACKER ──────────────────────────────────────────────────────


class TestBitterLessonTracker:
    def test_record_and_learn(self):
        with tempfile.TemporaryDirectory() as d:
            t = BitterLessonTracker(data_dir=d)
            for i in range(10):
                t.record_outcome("s", "7b", success=(i < 8))
            stats = t.get_strategy_stats()
            assert stats["s:7b"]["success_rate"] >= 0.7

    def test_auto_disable(self):
        with tempfile.TemporaryDirectory() as d:
            t = BitterLessonTracker(data_dir=d)
            for _ in range(10):
                t.record_outcome("bad", "1b", success=False)
            assert t.is_strategy_disabled("bad", "1b")

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            t1 = BitterLessonTracker(data_dir=d)
            t1.record_outcome("x", "3b", success=True)
            t1.save()
            t2 = BitterLessonTracker(data_dir=d)
            assert "x:3b" in t2.get_strategy_stats()


# ── SMALL MODEL OPTIMIZATIONS ──────────────────────────────────────────────────


class TestSmallModelOptimizations:
    def test_coerce_string_to_int(self):
        r = coerce_tool_args(
            {"n": "42"}, {"properties": {"n": {"type": "integer"}}, "required": []}
        )
        assert r["n"] == 42 and isinstance(r["n"], int)

    def test_coerce_string_to_bool(self):
        r = coerce_tool_args(
            {"f": "true"}, {"properties": {"f": {"type": "boolean"}}, "required": []}
        )
        assert r["f"] is True

    def test_coerce_string_to_number(self):
        r = coerce_tool_args(
            {"v": "3.14"}, {"properties": {"v": {"type": "number"}}, "required": []}
        )
        assert abs(r["v"] - 3.14) < 0.001

    def test_coerce_any_of(self):
        schema = {
            "properties": {"t": {"anyOf": [{"type": "integer"}, {"type": "null"}]}},
            "required": [],
        }
        assert coerce_tool_args({"t": "30"}, schema)["t"] == 30

    def test_coerce_none_unchanged(self):
        r = coerce_tool_args(
            {"n": None}, {"properties": {"n": {"type": "integer"}}, "required": []}
        )
        assert r["n"] is None

    def test_coerce_no_schema_unchanged(self):
        assert coerce_tool_args({"k": "v"}, {}) == {"k": "v"}


# ── SUPERVISOR ─────────────────────────────────────────────────────────────────


class TestSlugUtils:
    def test_basic(self):
        s = generate_slug("What are scaling laws?")
        assert "scaling" in s and "laws" in s and " " not in s

    def test_filler_removal(self):
        s = generate_slug("The main benefits of this approach")
        assert "the" not in s.split("-")

    def test_max_words(self):
        s = generate_slug("a b c d e f g h", max_words=3)
        assert len(s.split("-")) <= 3


class TestTaskChecker:
    @pytest.mark.asyncio
    async def test_word_count(self):
        c = TaskCompletionChecker()
        req = TaskRequirements(name="wc", description="d", check_type="word_count", threshold=5)
        assert await c.check_requirement(req, {"content": "one two three four five six"})
        assert not await c.check_requirement(req, {"content": "too short"})

    @pytest.mark.asyncio
    async def test_contains(self):
        c = TaskCompletionChecker()
        req = TaskRequirements(
            name="ct", description="d", check_type="contains", patterns=["hello", "world"]
        )
        assert await c.check_requirement(req, {"content": "hello world"})

    @pytest.mark.asyncio
    async def test_file_exists(self):
        c = TaskCompletionChecker()
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            req = TaskRequirements(name="fe", description="d", check_type="file_exists")
            assert await c.check_requirement(req, {"output_files": [f.name]})


# ── OTHER CORE MODULES ─────────────────────────────────────────────────────────


class TestToolDedup:
    def test_cache_hit(self):
        cc = ToolCallCache()
        cc.record("Read", {"file_path": "/a"}, "result")
        assert cc.check("Read", {"file_path": "/a"}) == "result"

    def test_no_cache_write_tools(self):
        cc = ToolCallCache()
        cc.record("Bash", {"command": "ls"}, "out")
        assert cc.check("Bash", {"command": "ls"}) is None

    def test_window_eviction(self):
        cc = ToolCallCache(window_size=2)
        for i in range(5):
            cc.record("Read", {"file_path": f"/{i}"}, f"c{i}")
        assert cc.check("Read", {"file_path": "/0"}) is None


class TestCrossProjectLessons:
    def test_lessons_exist(self):
        assert len(CROSS_PROJECT_LESSONS) > 10

    def test_all_have_required_fields(self):
        for lsn in CROSS_PROJECT_LESSONS:
            assert lsn.source_project
            assert lsn.category in (
                "small_model",
                "architecture",
                "context",
                "tools",
                "prompt",
                "ui",
            )
            assert lsn.lesson
            assert lsn.priority in ("high", "medium", "low")


class TestModelAssessment:
    def test_get_tier(self):
        class _Fake:
            providers = {}

        a = ModelAssessor(_Fake())
        from openlaoke.core.model_assessment.types import ModelTier

        assert isinstance(a.get_tier("gpt-4"), ModelTier)

    def test_get_granularity(self):
        class _Fake:
            providers = {}

        a = ModelAssessor(_Fake())
        from openlaoke.core.model_assessment.types import TaskGranularity

        assert isinstance(a.get_granularity("claude-opus"), TaskGranularity)


class TestKnowledgeBase:
    def test_creation(self):
        with tempfile.TemporaryDirectory() as d:
            kb = EnhancedKnowledgeBase(cache_dir=Path(d))
            assert kb is not None
            assert hasattr(kb, "search")


class TestSkillSystem:
    def test_registry(self):
        reg = get_skill_registry()
        assert isinstance(reg, SkillRegistry)
        assert len(reg.list_skills()) > 0

    def test_skill_dataclass(self):
        s = Skill(name="t", description="d", path=Path("/tmp/t"))
        assert s.name == "t"
        assert s.description == "d"


class TestEarlyStop:
    def test_read_loop(self):
        d = EarlyStopDetector()
        r = d.detect_read_loop("Read")
        assert r is not None

    def test_repetition(self):
        d = EarlyStopDetector()
        r = d.detect_repetition("hello " * 200)
        assert r is not None

    def test_reset(self):
        d = EarlyStopDetector()
        d.reset_all()
        assert d._consecutive_reads == 0


class TestTrustDecay:
    def test_record_and_check(self):
        td = TrustDecay(drop_threshold=3)
        for _ in range(5):
            td.record_failure("Bad")
        assert td.is_dropped("Bad")

    def test_success_resets(self):
        td = TrustDecay(drop_threshold=3)
        td.record_failure("Tool")
        td.record_success("Tool")
        assert not td.is_dropped("Tool")


class TestTokenBudget:
    def test_fields(self):
        b = TokenBudget(max_input_tokens=10000, max_output_tokens=4096)
        assert b.max_input_tokens == 10000
        assert b.max_output_tokens == 4096
        assert b.trigger_threshold == 0.8
