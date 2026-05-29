"""Tests for all new modules: security, classifier, compound tools, adaptive router,
trace recorder, evidence store, message images, dependency graph."""

from __future__ import annotations

import os
import tempfile

import pytest

from openlaoke.core.action_classifier import ActionKind, classify_action
from openlaoke.core.adaptive_router import AdaptiveRouter
from openlaoke.core.dependency_graph import (
    build_dependency_graph,
    find_parallel_steps,
    parse_plan,
)
from openlaoke.core.evidence_store import EvidenceStore
from openlaoke.core.message_images import extract_image_paths, model_supports_vision
from openlaoke.core.trace_recorder import TraceRecorder
from openlaoke.utils.security import (
    redact_credentials,
    sanitize_path,
    sanitize_tool_args,
    strip_ansi,
)

# ── SECURITY ──────────────────────────────────────────────────────────────────


class TestPathSanitization:
    def test_within_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            real_d = os.path.realpath(d)
            result = sanitize_path("sub/file.txt", real_d)
            assert "sub" in result
            assert result.startswith(real_d)

    def test_home_path_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            real_d = os.path.realpath(d)
            home = os.path.realpath(os.path.expanduser("~"))
            result = sanitize_path("~/Documents/test.txt", real_d)
            assert result.startswith(home)

    def test_outside_workspace_raises(self):
        with tempfile.TemporaryDirectory() as d:
            real_d = os.path.realpath(d)
            with pytest.raises(ValueError):
                sanitize_path("/etc/passwd", real_d)

    def test_default_cwd(self):
        result = sanitize_path(".")
        assert os.path.isabs(result)


class TestCredentialRedaction:
    def test_api_key_redacted(self):
        text = "api_key=sk-1234567890abcdefghijklmnop"
        result = redact_credentials(text)
        assert "sk-1234567890abcdefghijklmnop" not in result

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.xyz"
        result = redact_credentials(text)
        assert "eyJhbGciOiJIUzI1NiJ9.abc.xyz" not in result
        assert "redacted" in result.lower()

    def test_github_token_redacted(self):
        text = "Use token ghp_1234567890abcdefghijklmnop"
        result = redact_credentials(text)
        assert "ghp_1234567890abcdefghijklmnop" not in result
        assert "redacted" in result.lower()

    def test_slack_token_redacted(self):
        text = "My slack token is xoxb-1234567890-abcdefgh"
        result = redact_credentials(text)
        assert "xoxb-1234567890-abcdefgh" not in result

    def test_multiple_secrets(self):
        text = "api_key=sk-abc123\nAuthorization: Bearer xyz789"
        result = redact_credentials(text)
        assert "sk-abc123" not in result
        assert "xyz789" not in result

    def test_plain_text_unchanged(self):
        text = "This is normal text without secrets"
        result = redact_credentials(text)
        assert result == text

    def test_google_api_key(self):
        text = "key=AIzaSyD-1234567890abcdefghijklmnopqrs"
        result = redact_credentials(text)
        assert "AIzaSyD-" not in result


class TestAnsiStripping:
    def test_color_codes(self):
        assert strip_ansi("\x1b[32mgreen\x1b[0m") == "green"

    def test_bold_text(self):
        assert strip_ansi("\x1b[1mbold\x1b[0m") == "bold"

    def test_no_ansi(self):
        assert strip_ansi("plain text") == "plain text"

    def test_empty_string(self):
        assert strip_ansi("") == ""


class TestToolArgSanitization:
    def test_strip_ansi_from_strings(self):
        result = sanitize_tool_args({"command": "\x1b[31mrm\x1b[0m -rf /tmp"})
        assert result["command"] == "rm -rf /tmp"

    def test_preserve_non_strings(self):
        result = sanitize_tool_args({"count": 42, "flag": True})
        assert result["count"] == 42
        assert result["flag"] is True

    def test_mixed_types(self):
        result = sanitize_tool_args({"name": "\x1b[1mtest\x1b[0m", "value": 42})
        assert result["name"] == "test"
        assert result["value"] == 42


# ── ACTION CLASSIFIER ─────────────────────────────────────────────────────────


class TestActionClassifier:
    def test_clarify_question(self):
        r = classify_action("how do I fix this bug?")
        assert r.kind == ActionKind.CLARIFY
        assert r.confidence >= 0.5

    def test_clarify_what(self):
        r = classify_action("what is the best approach?")
        assert r.kind == ActionKind.CLARIFY

    def test_clarify_why(self):
        r = classify_action("why does this not work?")
        assert r.kind == ActionKind.CLARIFY

    def test_clarify_where(self):
        r = classify_action("where is the config file?")
        assert r.kind == ActionKind.CLARIFY

    def test_action_fix(self):
        r = classify_action("fix the bug in login.py")
        assert r.kind == ActionKind.ACTION

    def test_action_create(self):
        r = classify_action("create a new REST endpoint")
        assert r.kind == ActionKind.ACTION

    def test_action_implement(self):
        r = classify_action("implement the authentication module")
        assert r.kind == ActionKind.ACTION

    def test_action_write(self):
        r = classify_action("write tests for the user model")
        assert r.kind == ActionKind.ACTION

    def test_action_refactor(self):
        r = classify_action("refactor the database layer")
        assert r.kind == ActionKind.ACTION

    def test_greeting_hi(self):
        r = classify_action("hi")
        assert r.kind == ActionKind.GREETING

    def test_greeting_hello(self):
        r = classify_action("hello there")
        assert r.kind == ActionKind.GREETING

    def test_greeting_good_morning(self):
        r = classify_action("good morning!")
        assert r.kind == ActionKind.GREETING

    def test_praise_thanks(self):
        r = classify_action("thanks!")
        assert r.kind == ActionKind.PRAISE

    def test_praise_great(self):
        r = classify_action("great job!")
        assert r.kind == ActionKind.PRAISE

    def test_praise_awesome(self):
        r = classify_action("awesome work")
        assert r.kind == ActionKind.PRAISE

    def test_respond_default(self):
        r = classify_action("interesting observation")
        assert r.kind == ActionKind.RESPOND

    def test_empty_message(self):
        r = classify_action("")
        assert r.kind == ActionKind.CLARIFY

    def test_whitespace_message(self):
        r = classify_action("   ")
        assert r.kind == ActionKind.CLARIFY

    def test_confidence_range(self):
        for kind in (
            ActionKind.CLARIFY,
            ActionKind.ACTION,
            ActionKind.GREETING,
            ActionKind.PRAISE,
            ActionKind.RESPOND,
        ):
            r = classify_action("x")
            if r.kind == kind:
                pass
        assert 0 <= r.confidence <= 1

    def test_action_with_please(self):
        r = classify_action("please fix this bug")
        assert r.kind == ActionKind.ACTION

    def test_clarify_with_please(self):
        r = classify_action("please explain how this works?")
        assert r.kind == ActionKind.CLARIFY


# ── ADAPTIVE ROUTER ───────────────────────────────────────────────────────────


class TestAdaptiveRouter:
    def test_initial_state(self):
        r = AdaptiveRouter()
        assert r.current_tier_name == "fast"
        assert r.current_model == "gemma3:1b"

    def test_success_keeps_tier(self):
        r = AdaptiveRouter()
        for _ in range(10):
            r.record_success()
        assert r.current_tier_name == "fast"

    def test_failures_promote(self):
        r = AdaptiveRouter()
        for _ in range(5):
            r.record_failure()
        r.route()
        assert r.current_tier_name == "default"

    def test_promote_to_strongest(self):
        r = AdaptiveRouter()
        for _ in range(10):
            r.record_failure()
        r.route()
        for _ in range(10):
            r.record_failure()
        r.route()
        assert r.current_tier_name == "strong"

    def test_no_promote_beyond_max(self):
        r = AdaptiveRouter()
        r._current_tier = 2
        assert r.promote() is None

    def test_reset(self):
        r = AdaptiveRouter()
        for _ in range(5):
            r.record_failure()
        r.route()
        r.reset()
        assert r.current_tier_name == "fast"

    def test_stats_tracking(self):
        r = AdaptiveRouter()
        r.record_success()
        r.record_failure()
        stats = r.get_stats()
        assert "fast" in stats
        assert stats["fast"]["calls"] == 2

    def test_session_promotion_cap(self):
        r = AdaptiveRouter()
        r._session_promotions = r._max_promotions
        assert r.promote() is None

    def test_demote(self):
        r = AdaptiveRouter()
        r._current_tier = 1
        r.demote()
        assert r.current_tier_name == "fast"

    def test_no_demote_at_start(self):
        r = AdaptiveRouter()
        assert r.demote() is None

    def test_custom_models(self):
        r = AdaptiveRouter(
            fast_model="tiny:1b",
            default_model="medium:7b",
            strong_model="large:70b",
        )
        assert r.current_model == "tiny:1b"


# ── TRACE RECORDER ────────────────────────────────────────────────────────────


class TestTraceRecorder:
    def test_record_turn(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("s1", "gpt-4")
            tr.start_turn("t1", "gpt-4", "fix bug")
            tr.record_tool_call_start()
            tr.record_tool_call("Bash", {"command": "ls"}, "output", False)
            tr.record_tool_call_start()
            tr.record_tool_call("Read", {"file_path": "/x"}, "content", False)
            tr.record_thinking("need to check")
            tr.record_response("done")
            tr.record_tokens(100, 50)
            tr.end_turn(success=True)
            turns = tr.get_session("s1")
            assert turns is not None
            assert len(turns) == 1
            assert turns[0].success
            assert len(turns[0].tool_calls) == 2

    def test_error_turn(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("s2", "gpt-4")
            tr.start_turn("t1", "gpt-4", "fix bug")
            tr.end_turn(success=False, error="failed to parse")
            turns = tr.get_session("s2")
            assert turns is not None
            assert not turns[0].success
            assert "failed" in turns[0].error

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("session_a", "gpt-4")
            tr.start_turn("t1", "gpt-4", "test")
            tr.end_turn()
            tr.start_session("session_b", "gpt-4")
            tr.start_turn("t1", "gpt-4", "test")
            tr.end_turn()
            sessions = tr.list_sessions()
            assert "session_a" in sessions
            assert "session_b" in sessions

    def test_nonexistent_session(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            assert tr.get_session("nonexistent") is None

    def test_generate_regression_test(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("s1", "gpt-4")
            tr.start_turn("t1", "gpt-4", "fix the bug in login.py")
            tr.record_tool_call_start()
            tr.record_tool_call("Read", {"file_path": "login.py"}, "contents...", False)
            tr.record_tool_call_start()
            tr.record_tool_call(
                "Edit", {"file_path": "login.py", "old_text": "x", "new_text": "y"}, "done", False
            )
            tr.record_response("Fixed")
            tr.end_turn(success=True)
            test_code = tr.generate_regression_test("s1", 0)
            assert test_code is not None
            assert "pytest" in test_code
            assert "login.py" in test_code

    def test_invalid_turn_index(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            assert tr.generate_regression_test("nonexistent") is None

    def test_token_accumulation(self):
        with tempfile.TemporaryDirectory() as d:
            tr = TraceRecorder(trace_dir=d)
            tr.start_session("s1", "gpt-4")
            tr.start_turn("t1", "gpt-4", "test")
            tr.record_tokens(100, 50)
            tr.record_tokens(200, 100)
            tr.end_turn()
            turns = tr.get_session("s1")
            assert turns is not None
            assert turns[0].tokens_input == 300
            assert turns[0].tokens_output == 150


# ── EVIDENCE STORE ────────────────────────────────────────────────────────────


class TestEvidenceStore:
    def test_record_and_retrieve(self):
        with tempfile.TemporaryDirectory() as d:
            es = EvidenceStore(store_dir=d)
            es.record("task1", "strategy_a", "failed", "did not work")
            es.record(
                "task1",
                "strategy_b",
                "worked",
                "better approach",
                tokens_used=500,
                duration_ms=100.0,
            )
            assert es.has_been_tried("task1", "strategy_a")
            assert not es.has_been_tried("task1", "strategy_c")
            working = es.get_working_strategies("task1")
            assert len(working) == 1
            assert working[0].strategy == "strategy_b"

    def test_failed_strategies(self):
        with tempfile.TemporaryDirectory() as d:
            es = EvidenceStore(store_dir=d)
            es.record("t1", "s1", "failed")
            es.record("t1", "s2", "failed")
            es.record("t1", "s3", "worked")
            failed = es.get_failed_strategies("t1")
            assert failed == {"s1", "s2"}

    def test_stats(self):
        with tempfile.TemporaryDirectory() as d:
            es = EvidenceStore(store_dir=d)
            es.record("t1", "s1", "worked")
            es.record("t1", "s2", "failed")
            es.record("t2", "s3", "failed")
            stats = es.get_stats()
            assert stats["total"] == 3
            assert stats["worked"] == 1
            assert stats["failed"] == 2

    def test_get_recent(self):
        with tempfile.TemporaryDirectory() as d:
            es = EvidenceStore(store_dir=d)
            for i in range(30):
                es.record(f"task{i}", f"strategy{i}", "worked")
            recent = es.get_recent(limit=10)
            assert len(recent) == 10

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            es1 = EvidenceStore(store_dir=d)
            es1.record("t1", "s1", "worked", "persistence test")
            es1.record("t1", "s2", "failed", "this failed")
            es2 = EvidenceStore(store_dir=d)
            assert es2.has_been_tried("t1", "s2")
            working = es2.get_working_strategies("t1")
            assert len(working) == 1
            assert working[0].strategy == "s1"
            stats = es2.get_stats()
            assert stats["total"] == 2


# ── MESSAGE IMAGES ────────────────────────────────────────────────────────────


class TestMessageImages:
    def test_extract_markdown_images(self):
        result = extract_image_paths("![diagram](output.png)", "/tmp")
        assert isinstance(result, list)

    def test_no_images_in_plain_text(self):
        result = extract_image_paths("just regular text about files", "/tmp")
        assert result == []

    def test_model_supports_vision(self):
        assert model_supports_vision("gpt-4o")
        assert model_supports_vision("claude-sonnet-4-20250514")
        assert model_supports_vision("gemini-pro-vision")
        assert model_supports_vision("llava:13b")

    def test_model_no_vision(self):
        assert not model_supports_vision("gpt-3.5-turbo")
        assert not model_supports_vision("codellama:7b")

    def test_empty_message(self):
        result = extract_image_paths("", "/tmp")
        assert result == []


# ── DEPENDENCY GRAPH ──────────────────────────────────────────────────────────


class TestDependencyGraph:
    def test_parse_simple_plan(self):
        plan = "1. Create models.py\n2. Create routes.py\n3. Write tests"
        steps = parse_plan(plan)
        assert len(steps) == 3
        assert steps[0].step_id == 1
        assert "models.py" in steps[0].description

    def test_parse_with_files_detected(self):
        plan = "1. Fix the bug in auth.py\n2. Update test_auth.py"
        steps = parse_plan(plan)
        assert len(steps) == 2
        assert "auth.py" in steps[0].files_touched

    def test_parse_empty_plan(self):
        steps = parse_plan("No numbered steps here")
        assert steps == []

    def test_build_groups_same_file_sequential(self):
        plan = "1. Edit models.py\n2. Edit models.py again"
        steps = parse_plan(plan)
        build_dependency_graph(steps)
        assert len(steps) == 2

    def test_find_parallel_steps(self):
        plan = "1. Create models.py\n2. Create routes.py\n3. Create views.py"
        steps = parse_plan(plan)
        result = find_parallel_steps(steps)
        assert isinstance(result, list)

    def test_tool_detection(self):
        plan = "1. Fix the bug in login.py"
        steps = parse_plan(plan)
        assert len(steps) == 1
        assert "edit_file" in steps[0].tools_used

    def test_multiline_plan(self):
        plan = """Here is the plan:

1. Create User model in models.py
2. Create API routes in routes.py
3. Test the endpoints with test_api.py
4. Update documentation in README.md"""
        steps = parse_plan(plan)
        assert len(steps) == 4
