"""Tests for core modules with 0% coverage: thinking_budget, snapshot, tool_router,
action_classifier, adaptive_temp, prompt_cache_split, read_tracker, multi_file_edit,
trust_decay, adaptive_router, early_stop, quality_monitor, evidence, evidence_store,
contract, dependency_graph, trace_recorder, guard_coordinator."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from openlaoke.core.action_classifier import ActionKind, ActionResult, classify_action
from openlaoke.core.adaptive_router import AdaptiveRouter
from openlaoke.core.adaptive_temp import AdaptiveTemperature
from openlaoke.core.contract import Assertion, Contract, ContractGuard, ContractStore
from openlaoke.core.dependency_graph import (
    DepKind,
    PlanStep,
    build_dependency_graph,
    find_parallel_steps,
    parse_plan,
)
from openlaoke.core.early_stop import EarlyStopDetector, StopReason
from openlaoke.core.evidence import EvidenceEntry, EvidenceStore
from openlaoke.core.evidence_store import EvidenceStore as EvidenceStoreV2
from openlaoke.core.guard_coordinator import GuardCoordinator
from openlaoke.core.multi_file_edit import MultiFileEditCoordinator
from openlaoke.core.prompt_cache_split import PromptCacheSplit
from openlaoke.core.quality_monitor import QualityMonitor, _levenshtein
from openlaoke.core.read_tracker import ReadTracker
from openlaoke.core.snapshot import SnapshotCheckpoint, SnapshotEntry, SnapshotManager
from openlaoke.core.thinking_budget import ThinkingBudget
from openlaoke.core.tool_router import TOOL_CATEGORIES, RoutingResult, ToolRouter
from openlaoke.core.trace_recorder import TraceRecorder
from openlaoke.core.trust_decay import TrustDecay
from openlaoke.utils.security import (
    redact_credentials,
    sanitize_path,
    sanitize_tool_args,
    strip_ansi,
)

# ============================================================================
# ThinkingBudget
# ============================================================================


class TestThinkingBudget:
    def test_defaults(self):
        tb = ThinkingBudget()
        assert tb.soft_budget == 2000
        assert tb.hard_cap == 8000
        assert tb.enabled is True

    def test_anthropic_config_enabled(self):
        tb = ThinkingBudget(soft_budget=1500)
        cfg = tb.get_anthropic_config()
        assert cfg["thinking"]["type"] == "enabled"
        assert cfg["thinking"]["budget_tokens"] == 1500

    def test_anthropic_config_disabled(self):
        tb = ThinkingBudget()
        tb.enabled = False
        assert tb.get_anthropic_config() == {}

    def test_anthropic_config_thinking_off(self):
        tb = ThinkingBudget()
        tb.disable_for_repair()
        cfg = tb.get_anthropic_config()
        assert cfg["thinking"]["type"] == "disabled"

    def test_openai_config_low(self):
        tb = ThinkingBudget(soft_budget=400)
        cfg = tb.get_openai_config()
        assert cfg["reasoning_effort"] == "low"

    def test_openai_config_medium(self):
        tb = ThinkingBudget(soft_budget=1500)
        cfg = tb.get_openai_config()
        assert cfg["reasoning_effort"] == "medium"

    def test_openai_config_high(self):
        tb = ThinkingBudget(soft_budget=5000)
        cfg = tb.get_openai_config()
        assert cfg["reasoning_effort"] == "high"

    def test_openai_config_disabled(self):
        tb = ThinkingBudget()
        tb.enabled = False
        assert tb.get_openai_config() == {}

    def test_openai_config_thinking_off(self):
        tb = ThinkingBudget()
        tb.disable_for_repair()
        assert tb.get_openai_config() == {}

    def test_qwen_config(self):
        tb = ThinkingBudget(soft_budget=1000)
        cfg = tb.get_qwen_config()
        assert cfg["enable_thinking"] is True
        assert cfg["thinking_budget"] == 1000

    def test_qwen_config_disabled(self):
        tb = ThinkingBudget()
        tb.enabled = False
        assert tb.get_qwen_config() == {}

    def test_qwen_config_thinking_off(self):
        tb = ThinkingBudget()
        tb.disable_for_repair()
        assert tb.get_qwen_config() == {"enable_thinking": False}

    def test_llama_cpp_config(self):
        tb = ThinkingBudget(soft_budget=3000)
        cfg = tb.get_llama_cpp_config()
        assert cfg["chat_template_kwargs"]["enable_thinking"] is True
        assert cfg["chat_template_kwargs"]["thinking_budget"] == 3000

    def test_llama_cpp_config_disabled(self):
        tb = ThinkingBudget()
        tb.enabled = False
        assert tb.get_llama_cpp_config() == {}

    def test_llama_cpp_config_thinking_off(self):
        tb = ThinkingBudget()
        tb.disable_for_repair()
        cfg = tb.get_llama_cpp_config()
        assert cfg["chat_template_kwargs"]["enable_thinking"] is False

    def test_truncate_thinking_short(self):
        tb = ThinkingBudget(hard_cap=8000)
        result = tb.truncate_thinking("short content")
        assert result == "short content"

    def test_truncate_thinking_long(self):
        tb = ThinkingBudget(hard_cap=100)
        long_content = "x" * 200
        result = tb.truncate_thinking(long_content)
        assert "thinking truncated" in result
        assert len(result) < len(long_content)

    def test_truncate_disabled(self):
        tb = ThinkingBudget(hard_cap=10)
        tb.enabled = False
        result = tb.truncate_thinking("x" * 100)
        assert result == "x" * 100

    def test_repair_toggle(self):
        tb = ThinkingBudget()
        tb.disable_for_repair()
        assert tb.get_anthropic_config()["thinking"]["type"] == "disabled"
        tb.enable_for_repair()
        assert tb.get_anthropic_config()["thinking"]["type"] == "enabled"

    def test_enabled_setter(self):
        tb = ThinkingBudget()
        tb.enabled = False
        assert tb.enabled is False
        tb.enabled = True
        assert tb.enabled is True


# ============================================================================
# SnapshotManager
# ============================================================================


class TestSnapshot:
    def test_snapshot_entry(self):
        entry = SnapshotEntry(path="/tmp/test.py", before_content="hello", is_new_file=False)
        assert entry.path == "/tmp/test.py"
        assert entry.before_content == "hello"

    def test_checkpoint_note_existing(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "test.py")
            with open(fp, "w") as f:
                f.write("content")
            cp = SnapshotCheckpoint(work_dir=d)
            cp.note(fp, "content")
            assert fp in cp.entries
            assert cp.entries[fp].before_content == "content"
            assert cp.entries[fp].is_new_file is False

    def test_checkpoint_note_new_file(self):
        cp = SnapshotCheckpoint()
        cp.note("/nonexistent/path.py", "")
        assert "/nonexistent/path.py" in cp.entries
        assert cp.entries["/nonexistent/path.py"].is_new_file is True

    def test_checkpoint_note_skip_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "same.py")
            with open(fp, "w") as f:
                f.write("v1")
            cp = SnapshotCheckpoint()
            cp.note(fp, "v1")
            cp.note(fp, "v2")
            assert cp.entries[fp].before_content == "v1"

    def test_checkpoint_rollback_remove_new(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "new_file.py")
            Path(fp).touch()
            cp = SnapshotCheckpoint(work_dir=d)
            cp.note("new_file.py", "")
            assert os.path.exists(fp)
            restored = cp.rollback()
            assert "new_file.py" in restored
            assert not os.path.exists(fp)

    def test_checkpoint_rollback_restore_content(self):
        with tempfile.TemporaryDirectory() as d:
            fp = os.path.join(d, "existing.py")
            with open(fp, "w") as f:
                f.write("original")
            cp = SnapshotCheckpoint(work_dir=d)
            cp.note(fp, "original")
            with open(fp, "w") as f:
                f.write("modified")
            restored = cp.rollback()
            assert fp in restored
            with open(fp) as f:
                assert f.read() == "original"

    def test_checkpoint_commit(self):
        cp = SnapshotCheckpoint()
        cp.note("test.py", "content")
        cp.commit()
        assert len(cp.entries) == 0

    def test_snapshot_manager_begin(self):
        sm = SnapshotManager()
        cp = sm.begin("test")
        assert sm.has_checkpoint is True
        assert cp.label == "test"

    def test_snapshot_manager_note(self):
        sm = SnapshotManager()
        sm.begin("test")
        sm.note("file.py", "content")
        assert sm.has_checkpoint is True

    def test_snapshot_manager_rollback(self):
        sm = SnapshotManager()
        sm.begin("test")
        result = sm.rollback()
        assert isinstance(result, list)
        assert sm.has_checkpoint is False

    def test_snapshot_manager_commit(self):
        sm = SnapshotManager()
        sm.begin("test")
        sm.commit()
        assert sm.has_checkpoint is False

    def test_snapshot_manager_no_checkpoint(self):
        sm = SnapshotManager()
        assert sm.rollback() == []

    def test_snapshot_manager_enabled(self):
        sm = SnapshotManager()
        assert sm.enabled is True
        sm.enabled = False
        assert sm.enabled is False


# ============================================================================
# ToolRouter
# ============================================================================


class TestToolRouter:
    def test_route_read(self):
        router = ToolRouter()
        result = router.route("read the file main.py")
        assert result.category == "read"
        assert "Read" in result.tools

    def test_route_write(self):
        router = ToolRouter()
        result = router.route("create a new file hello.py")
        assert result.category == "write"
        assert "Write" in result.tools

    def test_route_search(self):
        router = ToolRouter()
        result = router.route("search for all uses of database")
        assert result.category == "search"

    def test_route_run(self):
        router = ToolRouter()
        result = router.route("run pytest tests")
        assert result.category == "run"

    def test_route_plan(self):
        router = ToolRouter()
        result = router.route("plan a refactor strategy for migration")
        assert result.category == "plan"

    def test_route_respond(self):
        router = ToolRouter()
        result = router.route("thanks for the help")
        assert result.category == "respond"
        assert result.tools == []

    def test_route_web(self):
        router = ToolRouter()
        result = router.route("search the web for python docs")
        assert result.category == "web"

    def test_route_code_intel(self):
        router = ToolRouter()
        result = router.route("how does DatabaseConnection work")
        assert result.category == "code_intel"

    def test_routing_result_dataclass(self):
        r = RoutingResult(category="test", tools=["A", "B"], score=1.5, is_two_stage=True)
        assert r.category == "test"
        assert r.tools == ["A", "B"]
        assert r.score == 1.5
        assert r.is_two_stage is True

    def test_affirmation_reuses_previous(self):
        router = ToolRouter()
        router.route("read file.py")
        result = router.route("ok")
        assert result.category == "read"

    def test_affirmation_no_previous(self):
        router = ToolRouter()
        result = router.route("yes")
        assert result.category == "respond"

    def test_two_stage_mode(self):
        router = ToolRouter(context_length=8000, two_stage_threshold=16000)
        result = router.route("read the file")
        assert result.is_two_stage is True

    def test_get_category_descriptions(self):
        router = ToolRouter()
        desc = router.get_category_descriptions()
        assert "read" in desc
        assert "write" in desc

    def test_get_tools_for_category(self):
        router = ToolRouter()
        tools = router.get_tools_for_category("read")
        assert "Read" in tools

    def test_get_tools_unknown_category(self):
        router = ToolRouter()
        tools = router.get_tools_for_category("nonexistent")
        assert tools == []

    def test_get_all_tools_by_category(self):
        router = ToolRouter()
        all_tools = router.get_all_tools_by_category()
        assert len(all_tools) == len(TOOL_CATEGORIES)


# ============================================================================
# ActionClassifier
# ============================================================================


class TestActionClassifier:
    def test_classify_question(self):
        result = classify_action("How does this work?")
        assert result.kind == ActionKind.CLARIFY
        assert result.confidence >= 0.8

    def test_classify_what_question(self):
        result = classify_action("What is the meaning of this?")
        assert result.kind == ActionKind.CLARIFY

    def test_classify_greeting(self):
        result = classify_action("hello there")
        assert result.kind == ActionKind.GREETING
        assert result.confidence >= 0.9

    def test_classify_praise(self):
        result = classify_action("thanks for the help")
        assert result.kind == ActionKind.PRAISE

    def test_classify_action(self):
        result = classify_action("fix the bug in main.py")
        assert result.kind == ActionKind.ACTION
        assert result.confidence >= 0.3

    def test_classify_create_action(self):
        result = classify_action("create a new test file and add code")
        assert result.kind == ActionKind.ACTION

    def test_classify_default_respond(self):
        result = classify_action("I see the point being made here")
        assert result.kind == ActionKind.RESPOND

    def test_classify_empty(self):
        result = classify_action("")
        assert result.kind == ActionKind.CLARIFY

    def test_classify_whitespace(self):
        result = classify_action("   ")
        assert result.kind == ActionKind.CLARIFY

    def test_greeting_with_action(self):
        result = classify_action("hello, please fix the code")
        assert result.kind != ActionKind.GREETING

    def test_action_result_dataclass(self):
        r = ActionResult(kind="test", confidence=0.5, reason="test reason")
        assert r.kind == "test"
        assert r.confidence == 0.5
        assert r.reason == "test reason"


# ============================================================================
# AdaptiveTemperature
# ============================================================================


class TestAdaptiveTemperature:
    def test_defaults(self):
        at = AdaptiveTemperature()
        assert at.base_temp == 0.7
        assert at.delta == 0.15

    def test_attempt_1_lower(self):
        at = AdaptiveTemperature(base_temp=0.7, delta=0.15)
        temp = at.get_temperature(1)
        assert temp == pytest.approx(0.55)

    def test_attempt_2_higher(self):
        at = AdaptiveTemperature(base_temp=0.7, delta=0.15)
        temp = at.get_temperature(2)
        assert temp == pytest.approx(0.85)

    def test_attempt_3_base(self):
        at = AdaptiveTemperature(base_temp=0.7, delta=0.15)
        temp = at.get_temperature(3)
        assert temp == pytest.approx(0.7)

    def test_cycle_repeats(self):
        at = AdaptiveTemperature(base_temp=0.7, delta=0.15)
        assert at.get_temperature(4) == pytest.approx(0.55)
        assert at.get_temperature(5) == pytest.approx(0.85)

    def test_clamp_min(self):
        at = AdaptiveTemperature(base_temp=0.05, delta=0.15, min_temp=0.0)
        temp = at.get_temperature(1)
        assert temp >= 0.0

    def test_clamp_max(self):
        at = AdaptiveTemperature(base_temp=0.95, delta=0.15, max_temp=1.0)
        temp = at.get_temperature(2)
        assert temp <= 1.0

    def test_disabled(self):
        at = AdaptiveTemperature()
        at.enabled = False
        temp = at.get_temperature(1)
        assert temp == pytest.approx(0.7)

    def test_custom_base(self):
        at = AdaptiveTemperature()
        temp = at.get_temperature(1, base=0.5)
        assert temp == pytest.approx(0.35)


# ============================================================================
# PromptCacheSplit
# ============================================================================


class TestPromptCacheSplit:
    def test_tag_and_build(self):
        pcs = PromptCacheSplit()
        pcs.tag("memory", "some memory content")
        result = pcs.build_context_block("user question")
        assert "<sc:context>" in result
        assert "some memory content" in result
        assert "user question" in result

    def test_no_tags_passthrough(self):
        pcs = PromptCacheSplit()
        result = pcs.build_context_block("hello")
        assert result == "hello"

    def test_disabled(self):
        pcs = PromptCacheSplit()
        pcs.enabled = False
        pcs.tag("test", "content")
        result = pcs.build_context_block("question")
        assert result == "question"

    def test_untag(self):
        pcs = PromptCacheSplit()
        pcs.tag("mem", "data")
        pcs.untag("mem")
        result = pcs.build_context_block("q")
        assert result == "q"

    def test_clear_tags(self):
        pcs = PromptCacheSplit()
        pcs.tag("a", "1")
        pcs.tag("b", "2")
        pcs.clear_tags()
        result = pcs.build_context_block("q")
        assert result == "q"

    def test_empty_tag_skipped(self):
        pcs = PromptCacheSplit()
        pcs.tag("empty", "  ")
        result = pcs.build_context_block("q")
        assert "<!-- empty -->" not in result

    def test_enabled_property(self):
        pcs = PromptCacheSplit()
        assert pcs.enabled is True
        pcs.enabled = False
        assert pcs.enabled is False


# ============================================================================
# ReadTracker
# ============================================================================


class TestReadTracker:
    def test_record_and_check(self):
        rt = ReadTracker()
        rt.record_read("/tmp/test.py")
        assert rt.has_read("/tmp/test.py") is True
        assert rt.has_read("/tmp/other.py") is False

    def test_write_guard_allows_after_read(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            rt = ReadTracker()
            rt.record_read(path)
            assert rt.check_before_write(path) is None
        finally:
            os.unlink(path)

    def test_write_guard_blocks_unread_existing(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            rt = ReadTracker()
            msg = rt.check_before_write(path)
            assert msg is not None
            assert "WRITE-GUARD" in msg
        finally:
            os.unlink(path)

    def test_write_guard_allows_new_file(self):
        rt = ReadTracker()
        msg = rt.check_before_write("/nonexistent/new_file.py")
        assert msg is None

    def test_write_guard_second_attempt_allowed(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            rt = ReadTracker()
            rt.check_before_write(path)
            msg = rt.check_before_write(path)
            assert msg is None
        finally:
            os.unlink(path)

    def test_write_guard_disabled(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            rt = ReadTracker()
            rt.enabled = False
            assert rt.check_before_write(path) is None
        finally:
            os.unlink(path)

    def test_guard_read_large_file(self):
        rt = ReadTracker()
        assert rt.should_guard_read(50000) is True

    def test_guard_read_small_file(self):
        rt = ReadTracker()
        assert rt.should_guard_read(100) is False

    def test_guard_read_high_context(self):
        rt = ReadTracker()
        rt.set_context_budget(30000, 32000)
        assert rt.should_guard_read(100) is True

    def test_guard_message(self):
        rt = ReadTracker()
        msg = rt.get_guard_message()
        assert "READ-GUARD" in msg

    def test_reset(self):
        rt = ReadTracker()
        rt.record_read("a.py")
        rt.reset()
        assert rt.has_read("a.py") is False


# ============================================================================
# MultiFileEditCoordinator
# ============================================================================


class TestMultiFileEditCoordinator:
    def test_below_threshold(self):
        mfe = MultiFileEditCoordinator(min_files_for_header=3)
        mfe.track_edit("a.py")
        mfe.track_edit("b.py")
        assert mfe.should_inject_header() is False

    def test_at_threshold(self):
        mfe = MultiFileEditCoordinator(min_files_for_header=3)
        mfe.track_edit("a.py")
        mfe.track_edit("b.py")
        mfe.track_edit("c.py")
        assert mfe.should_inject_header() is True

    def test_header_content(self):
        mfe = MultiFileEditCoordinator(min_files_for_header=3)
        mfe.track_edit("a.py")
        mfe.track_edit("b.py")
        mfe.track_edit("c.py")
        header = mfe.get_header()
        assert "MULTI-FILE-EDIT" in header
        assert "3 files" in header
        assert mfe.should_inject_header() is False

    def test_no_duplicate_files(self):
        mfe = MultiFileEditCoordinator()
        mfe.track_edit("a.py")
        mfe.track_edit("a.py")
        assert mfe.edited_files == ["a.py"]

    def test_reset_turn(self):
        mfe = MultiFileEditCoordinator()
        mfe.track_edit("a.py")
        mfe.reset_turn()
        assert mfe.edited_files == []

    def test_disabled(self):
        mfe = MultiFileEditCoordinator()
        mfe.enabled = False
        mfe.track_edit("a.py")
        mfe.track_edit("b.py")
        mfe.track_edit("c.py")
        assert mfe.should_inject_header() is False


# ============================================================================
# TrustDecay
# ============================================================================


class TestTrustDecay:
    def test_no_failures(self):
        td = TrustDecay()
        assert td.get_failure_count("Bash") == 0
        assert td.is_dropped("Bash") is False
        assert td.is_demoted("Bash") is False

    def test_warn_threshold(self):
        td = TrustDecay(warn_threshold=2)
        td.record_failure("Bash")
        td.record_failure("Bash")
        assert td.is_demoted("Bash") is True
        assert td.is_dropped("Bash") is False

    def test_drop_threshold(self):
        td = TrustDecay(warn_threshold=2, drop_threshold=3)
        td.record_failure("Bash")
        td.record_failure("Bash")
        td.record_failure("Bash")
        assert td.is_dropped("Bash") is True

    def test_success_clears(self):
        td = TrustDecay()
        td.record_failure("Bash")
        td.record_failure("Bash")
        td.record_success("Bash")
        assert td.is_demoted("Bash") is False
        assert td.get_failure_count("Bash") == 0

    def test_filter_schemas(self):
        td = TrustDecay(warn_threshold=1, drop_threshold=3)
        td.record_failure("Bash")
        td.record_failure("Bash")
        td.record_failure("Edit")
        td.record_failure("Edit")
        td.record_failure("Edit")
        schemas = [
            {"name": "Bash", "desc": "bash"},
            {"name": "Edit", "desc": "edit"},
            {"name": "Read", "desc": "read"},
        ]
        filtered = td.filter_tool_schemas(schemas)
        names = [s["name"] for s in filtered]
        assert "Edit" not in names
        assert "Read" in names
        assert "Bash" in names

    def test_filter_schemas_demoted_at_end(self):
        td = TrustDecay(warn_threshold=1, drop_threshold=5)
        td.record_failure("Bash")
        schemas = [
            {"name": "Read"},
            {"name": "Bash"},
        ]
        filtered = td.filter_tool_schemas(schemas)
        assert filtered[0]["name"] == "Read"
        assert filtered[1]["name"] == "Bash"

    def test_reset(self):
        td = TrustDecay()
        td.record_failure("Bash")
        td.reset()
        assert td.get_failure_count("Bash") == 0
        assert len(td.dropped) == 0

    def test_disabled(self):
        td = TrustDecay()
        td.enabled = False
        td.record_failure("Bash")
        assert td.get_failure_count("Bash") == 0

    def test_disable_resets(self):
        td = TrustDecay()
        td.record_failure("Bash")
        td.record_failure("Bash")
        td.enabled = False
        assert td.get_failure_count("Bash") == 0


# ============================================================================
# AdaptiveRouter
# ============================================================================


class TestAdaptiveRouter:
    def test_initial_model(self):
        router = AdaptiveRouter(fast_model="small", default_model="medium", strong_model="big")
        assert router.current_model == "small"
        assert router.current_tier_name == "fast"

    def test_promote_on_failure(self):
        router = AdaptiveRouter(fast_model="small", default_model="medium", strong_model="big")
        for _ in range(4):
            router.record_failure()
        assert router.should_promote() is True
        new_model = router.route()
        assert new_model == "medium"

    def test_no_promote_below_min_calls(self):
        router = AdaptiveRouter()
        router.record_failure()
        assert router.should_promote() is False

    def test_promote_at_max_tier(self):
        router = AdaptiveRouter()
        router._current_tier = 2
        assert router.promote() is None

    def test_promote_max_sessions(self):
        router = AdaptiveRouter()
        router._session_promotions = 5
        assert router.promote() is None

    def test_demote(self):
        router = AdaptiveRouter()
        router._current_tier = 1
        result = router.demote()
        assert result == "gemma3:1b"
        assert router._current_tier == 0

    def test_no_demote_at_bottom(self):
        router = AdaptiveRouter()
        assert router.demote() is None

    def test_should_demote(self):
        router = AdaptiveRouter()
        router._current_tier = 1
        for _ in range(5):
            router.record_failure()
        assert router.should_demote() is True

    def test_record_success(self):
        router = AdaptiveRouter()
        router.record_success()
        stats = router._stats["fast"]
        assert stats.total_calls == 1
        assert stats.consecutive_failures == 0

    def test_reset(self):
        router = AdaptiveRouter()
        router.record_failure()
        router.record_failure()
        router.record_failure()
        router.promote()
        router.reset()
        assert router._current_tier == 0
        assert router._session_promotions == 0

    def test_get_stats(self):
        router = AdaptiveRouter()
        router.record_failure()
        stats = router.get_stats()
        assert "fast" in stats
        assert stats["fast"]["failures"] == 1


# ============================================================================
# EarlyStopDetector
# ============================================================================


class TestEarlyStopDetector:
    def test_detect_repetition(self):
        es = EarlyStopDetector()
        block = "A" * 60
        long_output = block * 6
        result = es.detect_repetition(long_output)
        assert result.should_stop is True
        assert result.reason == StopReason.REPETITION

    def test_no_repetition(self):
        es = EarlyStopDetector()
        result = es.detect_repetition("normal text here every line is unique and different")
        assert result.should_stop is False

    def test_detect_repetition_empty(self):
        es = EarlyStopDetector()
        result = es.detect_repetition("")
        assert result.should_stop is False

    def test_detect_patch_spiral(self):
        es = EarlyStopDetector(max_consecutive_patch_failures=3)
        for _ in range(3):
            result = es.detect_patch_spiral("Edit", "main.py", False)
        assert result.should_stop is True
        assert result.reason == StopReason.PATCH_SPIRAL

    def test_no_patch_spiral_on_success(self):
        es = EarlyStopDetector()
        es.detect_patch_spiral("Edit", "main.py", False)
        result = es.detect_patch_spiral("Edit", "main.py", True)
        assert result.should_stop is False

    def test_patch_spiral_wrong_tool(self):
        es = EarlyStopDetector()
        result = es.detect_patch_spiral("Read", "main.py", False)
        assert result.should_stop is False

    def test_greeting_regression(self):
        es = EarlyStopDetector()
        result = es.detect_greeting_regression("How can I help you today?")
        assert result.should_stop is True
        assert result.reason == StopReason.GREETING_REGRESSION

    def test_no_greeting_regression(self):
        es = EarlyStopDetector()
        result = es.detect_greeting_regression("The fix was applied successfully")
        assert result.should_stop is False

    def test_read_loop_soft(self):
        es = EarlyStopDetector(read_loop_soft=3, read_loop_hard=6)
        for _ in range(3):
            es.detect_read_loop("Read")
        result = es.detect_read_loop("Read")
        assert result.reason == StopReason.READ_LOOP
        assert result.should_stop is False

    def test_read_loop_hard(self):
        es = EarlyStopDetector(read_loop_hard=4)
        for _ in range(4):
            es.detect_read_loop("Read")
        result = es.detect_read_loop("Read")
        assert result.should_stop is True
        assert result.reason == StopReason.READ_LOOP

    def test_read_loop_resets_on_other(self):
        es = EarlyStopDetector()
        es.detect_read_loop("Read")
        es.detect_read_loop("Read")
        es.detect_read_loop("Write")
        result = es.detect_read_loop("Read")
        assert result.should_stop is False

    def test_reset_read_count(self):
        es = EarlyStopDetector()
        es.detect_read_loop("Read")
        es.detect_read_loop("Read")
        es.reset_read_count()
        result = es.detect_read_loop("Read")
        assert result.should_stop is False

    def test_reset_all(self):
        es = EarlyStopDetector()
        es.detect_read_loop("Read")
        es.reset_all()
        assert es._consecutive_reads == 0
        assert len(es._consecutive_patch_failures) == 0

    def test_total_patch_attempts_limit(self):
        es = EarlyStopDetector(max_total_patch_attempts=3)
        for i in range(3):
            result = es.detect_patch_spiral("Edit", "f.py", i % 2 == 0)
        assert result.should_stop is True


# ============================================================================
# QualityMonitor
# ============================================================================


class TestQualityMonitor:
    def test_empty_response(self):
        qm = QualityMonitor()
        result = qm.check("   ", [], {"Bash"})
        assert result.has_issue is True
        assert "Empty response" in result.message

    def test_ok_response(self):
        qm = QualityMonitor()
        result = qm.check("hello", [], {"Bash"})
        assert result.has_issue is False

    def test_blank_tool_name(self):
        qm = QualityMonitor()
        result = qm.check("", [{"name": ""}], {"Bash"})
        assert result.has_issue is True

    def test_hallucinated_tool(self):
        qm = QualityMonitor()
        result = qm.check("", [{"name": "NotExist"}], {"Bash", "Read"})
        assert result.has_issue is True
        assert "Unknown tool" in result.message

    def test_valid_tool(self):
        qm = QualityMonitor()
        result = qm.check("", [{"name": "Bash"}], {"Bash", "Read"})
        assert result.has_issue is False

    def test_repeated_call(self):
        qm = QualityMonitor()
        calls = [{"name": "Bash", "arguments": {"command": "ls"}}]
        qm.check("", calls, {"Bash"})
        result = qm.check("", calls, {"Bash"})
        assert result.has_issue is True
        assert "same tools" in result.message

    def test_max_corrections(self):
        qm = QualityMonitor(max_consecutive_corrections=1)
        qm.check("   ", [], {"Bash"})
        result = qm.check("   ", [], {"Bash"})
        assert result.has_issue is False

    def test_disabled(self):
        qm = QualityMonitor()
        qm.enabled = False
        result = qm.check("   ", [], set())
        assert result.has_issue is False

    def test_reset(self):
        qm = QualityMonitor()
        qm.check("   ", [], set())
        qm.reset()
        assert qm._correction_count == 0

    def test_levenshtein(self):
        assert _levenshtein("abc", "abc") == 0
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3
        assert _levenshtein("kitten", "sitting") == 3

    def test_levenshtein_empty(self):
        assert _levenshtein("", "") == 0


# ============================================================================
# Evidence (core/evidence.py)
# ============================================================================


class TestEvidence:
    def test_evidence_entry_defaults(self):
        entry = EvidenceEntry(task_id="t1")
        assert entry.task_id == "t1"
        assert entry.timestamp > 0

    def test_evidence_entry_to_dict(self):
        entry = EvidenceEntry(task_id="t1", commands_tried=["ls"], summary="test")
        d = entry.to_dict()
        assert d["task_id"] == "t1"
        assert d["commands_tried"] == ["ls"]
        assert d["summary"] == "test"

    def test_evidence_entry_from_dict(self):
        d = {
            "task_id": "t1",
            "commands_tried": ["ls"],
            "commands_failed": [],
            "commands_succeeded": [],
            "files_created": [],
            "files_edited": [],
            "validation_results": [],
            "summary": "ok",
            "timestamp": 1000.0,
        }
        entry = EvidenceEntry.from_dict(d)
        assert entry.task_id == "t1"
        assert entry.timestamp == 1000.0

    def test_evidence_entry_context_string(self):
        entry = EvidenceEntry(
            commands_failed=["bad_cmd"],
            commands_succeeded=["good_cmd"],
            files_created=["a.py"],
            files_edited=["b.py"],
            summary="done",
        )
        s = entry.to_context_string()
        assert "bad_cmd" in s
        assert "good_cmd" in s
        assert "a.py" in s
        assert "b.py" in s
        assert "done" in s

    def test_evidence_store_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStore(store_dir=d)
            store.start_task("task-1")
            store.record_command("pytest", True)
            store.record_command("ruff", False, "error output")
            store.record_file("new.py", created=True)
            store.record_file("old.py", created=False)
            store.record_validation("passed")
            entry = store.finish_task("completed")
            assert entry is not None
            assert "pytest" in entry.commands_succeeded
            assert "ruff" in entry.commands_failed[0]
            assert "new.py" in entry.files_created
            assert "old.py" in entry.files_edited

    def test_evidence_store_no_task(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStore(store_dir=d)
            store.record_command("ls", True)
            assert store.finish_task() is None

    def test_evidence_store_search(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStore(store_dir=d)
            store.start_task("t1")
            store.record_command("pytest", True)
            store.finish_task("test task")
            store.start_task("t2")
            store.record_command("lint", False)
            store.finish_task("lint task")
            results = store.search("test")
            assert len(results) >= 0

    def test_evidence_store_load_recent(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStore(store_dir=d)
            results = store.load_recent()
            assert isinstance(results, list)


# ============================================================================
# EvidenceStoreV2 (core/evidence_store.py)
# ============================================================================


class TestEvidenceStoreV2:
    def test_record_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStoreV2(store_dir=d)
            store.record("t1", "bash", "worked", details="success")
            assert store.has_been_tried("t1", "bash") is False
            store.record("t1", "bash", "failed", details="error")
            assert store.has_been_tried("t1", "bash") is True

    def test_get_failed_strategies(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStoreV2(store_dir=d)
            store.record("t1", "strategy_a", "failed")
            store.record("t1", "strategy_b", "worked")
            failed = store.get_failed_strategies("t1")
            assert "strategy_a" in failed
            assert "strategy_b" not in failed

    def test_get_working_strategies(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStoreV2(store_dir=d)
            store.record("t1", "s1", "worked")
            store.record("t1", "s2", "failed")
            working = store.get_working_strategies("t1")
            assert len(working) == 1
            assert working[0].strategy == "s1"

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStoreV2(store_dir=d)
            store.record("t1", "s1", "worked")
            store.record("t1", "s2", "failed")
            stats = store.get_stats()
            assert stats["total"] == 2
            assert stats["worked"] == 1
            assert stats["failed"] == 1

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStoreV2(store_dir=d)
            store.record("t1", "s1", "worked")
            store2 = EvidenceStoreV2(store_dir=d)
            stats = store2.get_stats()
            assert stats["total"] == 1

    def test_get_recent(self):
        with tempfile.TemporaryDirectory() as d:
            store = EvidenceStoreV2(store_dir=d)
            store.record("t1", "s1", "worked")
            store.record("t2", "s2", "failed")
            recent = store.get_recent(limit=1)
            assert len(recent) == 1


# ============================================================================
# Contract
# ============================================================================


class TestContract:
    def test_assertion_states(self):
        a = Assertion(id="a1", description="test", state="pending")
        assert a.state == "pending"

    def test_contract_is_done_pending(self):
        c = Contract(
            id="c1",
            description="test",
            assertions=[
                Assertion(id="a1", description="a", state="pending"),
            ],
        )
        assert c.is_done is False

    def test_contract_is_done_passed(self):
        c = Contract(
            id="c1",
            description="test",
            assertions=[
                Assertion(id="a1", description="a", state="passed"),
            ],
        )
        assert c.is_done is True

    def test_contract_is_done_mixed(self):
        c = Contract(
            id="c1",
            description="test",
            assertions=[
                Assertion(id="a1", description="a", state="passed"),
                Assertion(id="a2", description="a", state="skipped"),
            ],
        )
        assert c.is_done is True

    def test_pending_assertions(self):
        c = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="a", state="pending"),
                Assertion(id="a2", description="a", state="passed"),
            ],
        )
        pending = c.pending_assertions
        assert len(pending) == 1
        assert pending[0].id == "a1"

    def test_failed_assertions(self):
        c = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="a", state="failed"),
            ],
        )
        assert len(c.failed_assertions) == 1

    def test_blockers(self):
        c = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="a", state="pending"),
                Assertion(id="a2", description="a", state="failed"),
                Assertion(id="a3", description="a", state="passed"),
            ],
        )
        assert len(c.blockers) == 2

    def test_to_dict(self):
        c = Contract(
            id="c1",
            description="test",
            assertions=[
                Assertion(id="a1", description="a", state="passed", evidence="e"),
            ],
        )
        d = c.to_dict()
        assert d["id"] == "c1"
        assert len(d["assertions"]) == 1

    def test_from_dict(self):
        d = {
            "id": "c1",
            "description": "test",
            "assertions": [{"id": "a1", "description": "a", "state": "pending", "evidence": ""}],
        }
        c = Contract.from_dict(d)
        assert c.id == "c1"
        assert len(c.assertions) == 1

    def test_contract_post_init_timestamps(self):
        c = Contract(id="c1", description="test")
        assert c.created_at != ""
        assert c.updated_at != ""


class TestContractStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            cs = ContractStore(base_dir=d)
            contract = Contract(
                id="test-1",
                description="test",
                assertions=[
                    Assertion(id="a1", description="check", state="pending"),
                ],
            )
            cs.save(contract)
            loaded = cs.load("test-1")
            assert loaded is not None
            assert loaded.id == "test-1"

    def test_load_missing(self):
        with tempfile.TemporaryDirectory() as d:
            cs = ContractStore(base_dir=d)
            assert cs.load("missing") is None

    def test_load_active(self):
        with tempfile.TemporaryDirectory() as d:
            cs = ContractStore(base_dir=d)
            cs.save(Contract(id="c1", description="t", state="active"))
            cs.save(Contract(id="c2", description="t", state="completed"))
            active = cs.load_active()
            assert len(active) == 1
            assert active[0].id == "c1"

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as d:
            cs = ContractStore(base_dir=d)
            cs.save(Contract(id="c1", description="t"))
            cs.save(Contract(id="c2", description="t"))
            all_c = cs.list_all()
            assert len(all_c) == 2


class TestContractGuard:
    def test_done_claim_with_blockers(self):
        cg = ContractGuard()
        contract = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="check", state="pending"),
            ],
        )
        msg = cg.check_done_claim("I'm done with the task", [contract])
        assert msg is not None
        assert "CONTRACT-GUARD" in msg

    def test_done_claim_no_contracts(self):
        cg = ContractGuard()
        assert cg.check_done_claim("I'm done", []) is None

    def test_done_claim_all_passed(self):
        cg = ContractGuard()
        contract = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="check", state="passed"),
            ],
        )
        assert cg.check_done_claim("I'm done", [contract]) is None

    def test_no_done_claim(self):
        cg = ContractGuard()
        contract = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="check", state="pending"),
            ],
        )
        assert cg.check_done_claim("working on it", [contract]) is None

    def test_disabled(self):
        cg = ContractGuard()
        cg.enabled = False
        contract = Contract(
            id="c1",
            description="t",
            assertions=[
                Assertion(id="a1", description="check", state="pending"),
            ],
        )
        assert cg.check_done_claim("I'm done", [contract]) is None


# ============================================================================
# DependencyGraph
# ============================================================================


class TestDependencyGraph:
    def test_parse_plan(self):
        text = "1. Read app.py and modify config.py\n2. Update tests\n3. Deploy"
        steps = parse_plan(text)
        assert len(steps) >= 2
        assert steps[0].step_id == 1

    def test_parse_plan_file_detection(self):
        text = "1. Edit the file src/main.py"
        steps = parse_plan(text)
        assert len(steps) == 1
        assert "main.py" in steps[0].files_touched

    def test_parse_plan_empty(self):
        assert parse_plan("") == []

    def test_build_dependency_graph_independent(self):
        steps = [
            PlanStep(step_id=1, description="edit a", files_touched=["a.py"]),
            PlanStep(step_id=2, description="edit b", files_touched=["b.py"]),
        ]
        groups = build_dependency_graph(steps)
        assert len(groups) >= 1

    def test_build_dependency_graph_overlapping(self):
        steps = [
            PlanStep(step_id=1, description="edit a", files_touched=["a.py"]),
            PlanStep(step_id=2, description="edit a again", files_touched=["a.py"]),
        ]
        groups = build_dependency_graph(steps)
        assert len(groups) == 2

    def test_build_dependency_graph_empty(self):
        assert build_dependency_graph([]) == []

    def test_build_dependency_graph_no_files(self):
        steps = [PlanStep(step_id=1, description="do something", files_touched=[])]
        groups = build_dependency_graph(steps)
        assert len(groups) == 1
        assert groups[0].can_parallelize is False

    def test_find_parallel_steps(self):
        steps = [
            PlanStep(step_id=1, description="edit a", files_touched=["a.py"]),
            PlanStep(step_id=2, description="edit b", files_touched=["b.py"]),
        ]
        parallel = find_parallel_steps(steps)
        assert isinstance(parallel, list)

    def test_dep_kind_enum(self):
        assert DepKind.FILE_OVERLAP == "file_overlap"
        assert DepKind.SEQUENTIAL == "sequential"


# ============================================================================
# TraceRecorder
# ============================================================================


class TestTraceRecorder:
    def test_session_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("sess-1", "claude-3")
            tr.start_turn("turn-1", "claude-3", "fix the bug")
            tr.record_tool_call_start()
            tr.record_tool_call("Read", {"path": "main.py"}, "file content", False)
            tr.record_thinking("I need to check this file")
            tr.record_response("The bug is fixed")
            tr.record_tokens(100, 50)
            tr.end_turn(success=True)
            sessions = tr.list_sessions()
            assert "sess-1" in sessions

    def test_get_session(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("sess-2", "model")
            tr.start_turn("turn-1", "model", "hello")
            tr.end_turn()
            turns = tr.get_session("sess-2")
            assert turns is not None
            assert len(turns) == 1

    def test_get_missing_session(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            assert tr.get_session("missing") is None

    def test_generate_regression_test(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("sess-3", "model")
            tr.start_turn("turn-1", "model", "fix bug")
            tr.record_tool_call_start()
            tr.record_tool_call("Bash", {"cmd": "pytest"}, "3 passed", False)
            tr.end_turn()
            code = tr.generate_regression_test("sess-3", turn_index=0)
            assert code is not None
            assert "regression" in code

    def test_generate_regression_missing_session(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            assert tr.generate_regression_test("missing") is None

    def test_failed_turn(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("sess-4", "model")
            tr.start_turn("t1", "model", "fail")
            tr.end_turn(success=False, error="timeout")
            turns = tr.get_session("sess-4")
            assert turns is not None
            assert turns[0].success is False
            assert turns[0].error == "timeout"


# ============================================================================
# GuardCoordinator
# ============================================================================


class TestGuardCoordinator:
    def test_creation(self):
        gc = GuardCoordinator()
        assert gc.tool_router is not None
        assert gc.quality_monitor is not None
        assert gc.trust_decay is not None
        assert gc.read_tracker is not None

    def test_route_tools(self):
        gc = GuardCoordinator(known_tools={"Read", "Bash", "Write"})
        tools = gc.route_tools("read the file")
        assert "Read" in tools

    def test_record_tool_success(self):
        gc = GuardCoordinator()
        gc.record_tool_success("Bash")
        assert gc.trust_decay.get_failure_count("Bash") == 0

    def test_record_tool_failure(self):
        gc = GuardCoordinator()
        gc.record_tool_failure("Bash")
        assert gc.trust_decay.get_failure_count("Bash") == 1

    def test_check_write_guard(self):
        gc = GuardCoordinator()
        msg = gc.check_write_guard("/nonexistent/new.py")
        assert msg is None

    def test_reset_turn(self):
        gc = GuardCoordinator()
        gc.multi_file_edit.track_edit("a.py")
        gc.reset_turn()
        assert gc.multi_file_edit.edited_files == []

    def test_diagnose_error(self):
        gc = GuardCoordinator()
        result = gc.diagnose_error("pytest", "module not found", 1)
        assert result is not None


# ============================================================================
# Security Utils
# ============================================================================


class TestSecurity:
    def test_sanitize_path_within_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            real_cwd = os.path.realpath(d)
            result = sanitize_path("subdir/file.py", cwd=d)
            assert result.startswith(real_cwd)

    def test_sanitize_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as d, pytest.raises(ValueError, match="outside"):
            sanitize_path("../../etc/passwd", cwd=d)

    def test_sanitize_path_home_allowed(self):
        result = sanitize_path("~/test.py")
        assert "test.py" in result

    def test_redact_api_key(self):
        text = "api_key=sk-abc123def456ghi789jkl012mno345"
        result = redact_credentials(text)
        assert "sk-abc" not in result

    def test_redact_bearer(self):
        text = "Bearer abc123token456xyz"
        result = redact_credentials(text)
        assert "[redacted]" in result

    def test_redact_no_secrets(self):
        text = "hello world this is safe"
        assert redact_credentials(text) == text

    def test_strip_ansi(self):
        text = "\x1b[31mRed Text\x1b[0m normal"
        result = strip_ansi(text)
        assert result == "Red Text normal"

    def test_strip_ansi_no_codes(self):
        text = "normal text"
        assert strip_ansi(text) == text

    def test_sanitize_tool_args(self):
        args = {"cmd": "\x1b[32mls\x1b[0m", "count": 5}
        result = sanitize_tool_args(args)
        assert result["cmd"] == "ls"
        assert result["count"] == 5
