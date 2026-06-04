"""Tests for the agent context builder and memory system."""

from __future__ import annotations

from openlaoke.agent.context import (
    ContextBuilder,
    GoalState,
    compose_runtime_block,
    merge_runtime_into_user,
    render_goal_lines,
)
from openlaoke.memory.auto import AutoMemoryStore, FactType, quick_add
from openlaoke.memory.docs import load_bundle
from openlaoke.memory.dream import DreamConsolidator
from openlaoke.memory.pending import PendingMemoryQueue, render_runtime_block
from openlaoke.provider import enforce_role_alternation


class TestRoleAlternation:
    def test_alternating_kept(self) -> None:
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        out = enforce_role_alternation(msgs)
        assert [m["role"] for m in out] == ["user", "assistant", "user"]

    def test_consecutive_user_merged(self) -> None:
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
        ]
        out = enforce_role_alternation(msgs)
        assert len(out) == 1
        assert "a" in out[0]["content"]
        assert "b" in out[0]["content"]

    def test_empty(self) -> None:
        assert enforce_role_alternation([]) == []


class TestContextBuilder:
    def test_build_prefix(self) -> None:
        cb = ContextBuilder(
            identity="You are helpful.",
            tool_contract="Use tools wisely.",
        )
        prefix = cb.build_prefix()
        assert "helpful" in prefix
        assert "tools wisely" in prefix

    def test_build_messages(self) -> None:
        cb = ContextBuilder()
        msgs = cb.build_messages("hi", history=[])
        assert msgs == [{"role": "user", "content": "hi"}]

    def test_runtime_block_appended_to_user(self) -> None:
        cb = ContextBuilder()
        ctx = cb.build("hi", history=[], runtime_block="[Runtime] test")
        assert "[Runtime] test" in ctx.messages[-1]["content"]

    def test_truncation(self) -> None:
        cb = ContextBuilder(identity="x" * 20000, max_prefix_chars=100)
        prefix = cb.build_prefix()
        assert len(prefix) < 200

    def test_dyn_providers(self) -> None:
        cb = ContextBuilder(
            memory_index_provider=lambda: "facts here",
            skills_index_provider=lambda: "skill list",
        )
        prefix = cb.build_prefix()
        assert "facts here" in prefix
        assert "skill list" in prefix


class TestGoalState:
    def test_idle_no_lines(self) -> None:
        assert render_goal_lines(GoalState()) == []

    def test_active_goal(self) -> None:
        goal = GoalState(status="active", objective="build feature x", ui_summary="step 2/5")
        lines = render_goal_lines(goal)
        assert any("build feature x" in line for line in lines)

    def test_completed(self) -> None:
        goal = GoalState(status="completed", objective="done")
        lines = render_goal_lines(goal)
        assert any("done" in line for line in lines)

    def test_compose_runtime_block(self) -> None:
        goal = GoalState(status="active", objective="do x", ui_summary="u")
        block = compose_runtime_block(
            goal=goal,
            channel="cli",
            chat_id="c1",
            sender_id="u1",
            pending_notes=["a", "b"],
        )
        assert "do x" in block
        assert "a" in block
        assert "b" in block

    def test_merge_runtime_into_user(self) -> None:
        msgs = [{"role": "user", "content": "hi"}]
        merge_runtime_into_user(msgs, "[Runtime] foo")
        assert "foo" in msgs[0]["content"]


class TestDocMemory:
    def test_load_no_workspace(self) -> None:
        bundle = load_bundle("/nonexistent/path")
        assert not bundle.has_any()

    def test_load_priority_order(self, tmp_path) -> None:
        (tmp_path / "REASONIX.md").write_text("primary", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("agents", encoding="utf-8")
        bundle = load_bundle(str(tmp_path))
        assert bundle.primary is not None
        assert bundle.primary.name == "REASONIX.md"

    def test_local_md_treated_separately(self, tmp_path) -> None:
        (tmp_path / "REASONIX.md").write_text("primary", encoding="utf-8")
        (tmp_path / "REASONIX.local.md").write_text("local", encoding="utf-8")
        bundle = load_bundle(str(tmp_path))
        assert bundle.primary is not None
        assert any(d.name == "REASONIX.local.md" for d in bundle.locals_)

    def test_combined_body(self, tmp_path) -> None:
        (tmp_path / "REASONIX.md").write_text("A" * 50, encoding="utf-8")
        (tmp_path / "USER.md").write_text("B" * 50, encoding="utf-8")
        bundle = load_bundle(str(tmp_path))
        body = bundle.combined_body()
        assert "A" in body and "B" in body


class TestAutoMemory:
    def test_add_and_index(self, tmp_path) -> None:
        store = AutoMemoryStore(root=str(tmp_path / "mem"))
        f = store.add("project_layout", "Monorepo with 3 services", type=FactType.PROJECT)
        assert f.fact_id.startswith("fact_")
        idx = store.index_text()
        assert "project_layout" in idx

    def test_update(self, tmp_path) -> None:
        store = AutoMemoryStore(root=str(tmp_path / "mem"))
        f = store.add("name", "old body")
        updated = store.update(f.fact_id, body="new body")
        assert updated is not None
        assert updated.body == "new body"

    def test_delete(self, tmp_path) -> None:
        store = AutoMemoryStore(root=str(tmp_path / "mem"))
        f = store.add("name", "body")
        assert store.delete(f.fact_id)
        assert store.get(f.fact_id) is None

    def test_quick_add_parsed(self, tmp_path) -> None:
        store = AutoMemoryStore(root=str(tmp_path / "mem"))
        f = quick_add(store, "user_pref: tabs over spaces", type=FactType.USER)
        assert f.name == "user_pref"
        assert "tabs" in f.body


class TestPendingMemory:
    def test_drain(self) -> None:
        q = PendingMemoryQueue()
        q.add("s1", "first")
        q.add("s1", "second")
        assert q.drain("s1") == ["first", "second"]
        assert q.peek("s1") == []

    def test_render_block(self) -> None:
        text = render_runtime_block(["note1", "note2"])
        assert "note1" in text
        assert "Pending memory" in text


class TestDreamConsolidator:
    def test_cursor_persistence(self, tmp_path) -> None:
        dream = DreamConsolidator(memory_root=str(tmp_path))
        assert dream.cursor == 0
        dream.advance_cursor(42)
        dream2 = DreamConsolidator(memory_root=str(tmp_path))
        assert dream2.cursor == 42

    def test_build_prompt(self, tmp_path) -> None:
        dream = DreamConsolidator(memory_root=str(tmp_path))
        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
        ]
        prompt = dream.build_prompt(history)
        assert "memory-consolidation" in prompt
        assert "remember" in prompt
        assert "forget" in prompt
        assert "first" in prompt

    def test_restricted_tools(self, tmp_path) -> None:
        dream = DreamConsolidator(memory_root=str(tmp_path))
        tools = dream.restricted_tools()
        assert "remember" in tools
        assert "forget" in tools
        assert "SaveDoc" in tools
        assert "bash" not in tools
