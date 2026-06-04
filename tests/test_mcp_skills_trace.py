"""Tests for the MCP, subagent, trace, hooks, knowledge, channels, and
provider modules."""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from openlaoke.bus.queue import MessageBus
from openlaoke.channels.base import ChannelConfig
from openlaoke.channels.cli import CLIChannel
from openlaoke.hooks.lifecycle import (
    HookEvent,
    HookPayload,
    HookRegistryV2,
    HookResult,
    HookSpec,
)
from openlaoke.knowledge import KnowledgeLoader
from openlaoke.mcp.client import (
    MCPManager,
    PluginEntry,
    Tier,
    TransportType,
    sanitize_tool_name,
)
from openlaoke.mcp.config import (
    expand_env_value,
    from_mcp_json,
    from_plugins_block,
    load_mcp_json,
    merge,
)
from openlaoke.provider import (
    Chunk,
    ChunkKind,
    LLMProvider,
    ProviderRequest,
    detect_arrearage_response,
)
from openlaoke.skill.manager import SubagentManager, SubagentSpec
from openlaoke.skill.metadata import (
    parse_run_mode,
    pin_inline,
    pinned_index,
)
from openlaoke.skill.subagents import SUBAGENT_SKILLS
from openlaoke.trace import TraceRecord, TraceRecorder, bench_diff

# ---------------------------------------------------------------------------
# MCP tests
# ---------------------------------------------------------------------------


class TestMCPNameSanitizer:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("mcp__github__create_issue", "mcp__github__create_issue"),
            ("mcp__server with space__tool", "mcp__server_with_space__tool"),
            ("mcp__a__b/c", "mcp__a__b_c"),
        ],
    )
    def test_sanitize(self, name: str, expected: str) -> None:
        assert sanitize_tool_name(*name.split("__")[1:]) == expected

    def test_namespaced(self) -> None:
        assert sanitize_tool_name("gh", "create_issue").startswith("mcp__")


class TestMCPConfig:
    def test_from_mcp_json(self) -> None:
        data = {
            "mcpServers": {
                "github": {
                    "command": "gh-mcp",
                    "args": ["--port", "8080"],
                    "env": {"GITHUB_TOKEN": "x"},
                },
                "remote": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                },
            }
        }
        entries = from_mcp_json(data).entries
        names = [e.name for e in entries]
        assert "github" in names
        assert "remote" in names
        gh = next(e for e in entries if e.name == "github")
        assert gh.command == "gh-mcp"
        assert gh.args == ["--port", "8080"]
        assert gh.transport is TransportType.STDIO
        remote = next(e for e in entries if e.name == "remote")
        assert remote.transport is TransportType.STREAMABLE_HTTP

    def test_from_plugins_block(self) -> None:
        plugins = [
            {"name": "x", "command": "x-cmd", "tier": "eager"},
            {"name": "y", "type": "http", "url": "http://x", "tier": "background"},
        ]
        entries = from_plugins_block(plugins).entries
        assert entries[0].tier is Tier.EAGER
        assert entries[1].transport is TransportType.STREAMABLE_HTTP

    def test_env_expansion(self) -> None:
        os.environ["FOO_TOKEN"] = "secret"
        entry = PluginEntry(
            name="x",
            command="x",
            env={"X": "${FOO_TOKEN}"},
        )
        expanded = expand_env_value(entry)
        assert expanded.env["X"] == "secret"

    def test_merge(self) -> None:
        a = [PluginEntry(name="a", command="a")]
        b = [PluginEntry(name="a", command="b"), PluginEntry(name="c", command="c")]
        merged = merge(a, b)
        assert len(merged) == 2
        a_entry = next(e for e in merged if e.name == "a")
        assert a_entry.command == "a"

    def test_load_missing(self, tmp_path) -> None:
        assert load_mcp_json(str(tmp_path / "missing.json")) == []


class TestMCPManager:
    def test_register_and_list(self) -> None:
        mgr = MCPManager()
        entry = PluginEntry(name="x", command="x")
        mgr.register(entry)
        assert "x" not in mgr.list_servers()
        assert mgr.has_server("x") is False


# ---------------------------------------------------------------------------
# Subagent tests
# ---------------------------------------------------------------------------


class TestSubagentManager:
    def test_filter_tools_excludes_delegation(self) -> None:
        mgr = SubagentManager()
        available = [
            "read_file",
            "write_file",
            "bash",
            "task",
            "subagent",
            "spawn",
            "run_skill",
            "install_skill",
            "explore",
            "research",
            "review",
            "security_review",
        ]
        spec = SubagentSpec(
            name="explore",
            description="",
            system_prompt="",
            allowed_tools=["read_file", "bash", "task"],
        )
        filtered = mgr.filter_tools(available, spec)
        assert "task" not in filtered
        assert "subagent" not in filtered
        assert "explore" not in filtered
        assert "read_file" in filtered
        assert "bash" in filtered

    def test_spawn_returns_job(self) -> None:
        mgr = SubagentManager()
        spec = SUBAGENT_SKILLS["explore"]
        job = mgr.spawn("parent_s1", "call_abc", spec, "investigate x", run_in_background=True)
        assert job.spec_name == "explore"
        assert job.run_in_background
        assert job.status == "pending"
        assert mgr.get(job.job_id) is job

    def test_filter_respects_allowed_tools(self) -> None:
        mgr = SubagentManager()
        spec = SubagentSpec(
            name="custom",
            description="",
            system_prompt="",
            allowed_tools=["read_file"],
        )
        filtered = mgr.filter_tools(["read_file", "write_file", "bash"], spec)
        assert filtered == ["read_file"]

    def test_cancel_running(self) -> None:
        mgr = SubagentManager()
        spec = SUBAGENT_SKILLS["explore"]
        job = mgr.spawn("s1", "c1", spec, "x")
        mgr.update(job.job_id, status="running")
        assert mgr.cancel(job.job_id)
        assert job.status == "cancelled"


# ---------------------------------------------------------------------------
# Trace + bench tests
# ---------------------------------------------------------------------------


class TestTraceRecorder:
    def test_record_and_list(self, tmp_path) -> None:
        rec = TraceRecorder(base_dir=str(tmp_path))
        rec.record(
            TraceRecord(
                trace_id="t1",
                session_id="s1",
                turn_index=0,
                started_at=time.time(),
                finished_at=time.time(),
                user_text="hi",
            )
        )
        rec.record(
            TraceRecord(
                trace_id="t2",
                session_id="s1",
                turn_index=1,
                started_at=time.time(),
                finished_at=time.time(),
                user_text="next",
            )
        )
        traces = rec.list_traces("s1")
        assert len(traces) == 2
        assert traces[0].trace_id == "t2"

    def test_get_by_id(self, tmp_path) -> None:
        rec = TraceRecorder(base_dir=str(tmp_path))
        rec.record(
            TraceRecord(
                trace_id="t1",
                session_id="s1",
                turn_index=0,
                started_at=time.time(),
                finished_at=time.time(),
                user_text="hi",
            )
        )
        assert rec.get("t1") is not None
        assert rec.get("nonexistent") is None


class TestBenchDiff:
    def test_improved_pass_rate(self) -> None:
        before = {"pass_rate": 0.5, "avg_duration_ms": 100.0, "avg_tokens": 100.0}
        after = {"pass_rate": 0.8, "avg_duration_ms": 100.0, "avg_tokens": 100.0}
        out = bench_diff(before, after)
        assert out["verdict"] == "improved"
        assert out["exit_code"] == 0

    def test_regressed_pass_rate(self) -> None:
        before = {"pass_rate": 0.9, "avg_duration_ms": 100.0, "avg_tokens": 100.0}
        after = {"pass_rate": 0.4, "avg_duration_ms": 100.0, "avg_tokens": 100.0}
        out = bench_diff(before, after)
        assert out["verdict"] == "regressed"
        assert out["exit_code"] == 1

    def test_noise(self) -> None:
        before = {"pass_rate": 0.5, "avg_duration_ms": 100.0, "avg_tokens": 100.0}
        after = {"pass_rate": 0.51, "avg_duration_ms": 101.0, "avg_tokens": 102.0}
        out = bench_diff(before, after)
        assert out["verdict"] == "noise"
        assert out["exit_code"] == 2


# ---------------------------------------------------------------------------
# Hooks tests
# ---------------------------------------------------------------------------


class TestHookRegistryV2:
    def test_register_and_fire(self) -> None:
        async def scenario() -> None:
            registry = HookRegistryV2()
            seen: list[str] = []

            def handler(payload: HookPayload) -> HookResult:
                seen.append(payload.tool_name)
                return HookResult(output="ok")

            registry.register(
                HookSpec(
                    name="audit",
                    event=HookEvent.POST_TOOL_USE,
                    handler=handler,
                )
            )
            result, _ = await registry.fire(
                HookEvent.POST_TOOL_USE,
                HookPayload(event="PostToolUse", session_id="s1", tool_name="write_file"),
            )
            assert seen == ["write_file"]
            assert "ok" in result.output

        asyncio.run(scenario())

    def test_blocking_exit_code_2(self) -> None:
        async def scenario() -> None:
            registry = HookRegistryV2()

            def block_handler(payload: HookPayload) -> HookResult:
                return HookResult(exit_code=2, output="denied")

            registry.register(
                HookSpec(
                    name="blocker",
                    event=HookEvent.PRE_TOOL_USE,
                    handler=block_handler,
                )
            )
            result, _ = await registry.fire(
                HookEvent.PRE_TOOL_USE,
                HookPayload(event="PreToolUse", session_id="s1", tool_name="bash"),
            )
            assert result.exit_code == 2

        asyncio.run(scenario())

    def test_short_circuit_on_block(self) -> None:
        async def scenario() -> None:
            registry = HookRegistryV2()
            calls: list[str] = []

            def first(payload: HookPayload) -> HookResult:
                calls.append("first")
                return HookResult(exit_code=2)

            def second(payload: HookPayload) -> HookResult:
                calls.append("second")
                return HookResult()

            registry.register(
                HookSpec(name="a", event=HookEvent.PRE_TOOL_USE, handler=first, priority=10)
            )
            registry.register(
                HookSpec(name="b", event=HookEvent.PRE_TOOL_USE, handler=second, priority=0)
            )
            await registry.fire(
                HookEvent.PRE_TOOL_USE,
                HookPayload(event="PreToolUse", session_id="s1", tool_name="x"),
            )
            assert calls == ["first"]

        asyncio.run(scenario())

    def test_handler_error_isolated(self) -> None:
        async def scenario() -> None:
            registry = HookRegistryV2()
            seen: list[str] = []

            def bad(payload: HookPayload) -> HookResult:
                raise RuntimeError("oops")

            def good(payload: HookPayload) -> HookResult:
                seen.append("good")
                return HookResult()

            registry.register(
                HookSpec(name="bad", event=HookEvent.POST_TOOL_USE, handler=bad, priority=10)
            )
            registry.register(HookSpec(name="good", event=HookEvent.POST_TOOL_USE, handler=good))
            await registry.fire(
                HookEvent.POST_TOOL_USE,
                HookPayload(event="PostToolUse", session_id="s1", tool_name="x"),
            )
            assert seen == ["good"]

        asyncio.run(scenario())


# ---------------------------------------------------------------------------
# Knowledge tests
# ---------------------------------------------------------------------------


class TestKnowledgeLoader:
    def test_load_and_search(self, tmp_path) -> None:
        (tmp_path / "algos").mkdir()
        (tmp_path / "algos" / "sorting.md").write_text(
            "Quick sort: divide and conquer algorithm. O(n log n) average.",
            encoding="utf-8",
        )
        loader = KnowledgeLoader(base_dirs=[str(tmp_path)])
        assert "sorting" in loader.entries
        out = loader.format_for_prompt("I need a sorting algorithm")
        assert "Quick sort" in out or "sort" in out

    def test_budget_enforcement(self, tmp_path) -> None:
        for i in range(10):
            (tmp_path / f"note_{i}.md").write_text(
                f"note {i} " + ("x" * 100),
                encoding="utf-8",
            )
        loader = KnowledgeLoader(base_dirs=[str(tmp_path)], max_tokens=200)
        out = loader.format_for_prompt("note x y z w", top_k=10)
        assert "<knowledge>" in out
        assert "</knowledge>" in out

    def test_per_entry_cap(self, tmp_path) -> None:
        (tmp_path / "big.md").write_text("alpha beta gamma " * 3000, encoding="utf-8")
        loader = KnowledgeLoader(
            base_dirs=[str(tmp_path)],
            per_entry_cap=10,
        )
        out = loader.format_for_prompt("alpha beta gamma", top_k=5)
        assert "..." in out


# ---------------------------------------------------------------------------
# Channel tests (no actual network)
# ---------------------------------------------------------------------------


class TestChannelConfig:
    def test_is_allowed_wildcard(self) -> None:
        cfg = ChannelConfig(name="x", allow_from=["*"])
        bus = MessageBus()
        ch = CLIChannel(cfg, bus)
        assert ch.is_allowed("anyone")

    def test_is_allowed_specific(self) -> None:
        cfg = ChannelConfig(name="x", allow_from=["alice"])
        bus = MessageBus()
        ch = CLIChannel(cfg, bus)
        assert ch.is_allowed("alice")
        assert not ch.is_allowed("bob")


# ---------------------------------------------------------------------------
# Provider tests
# ---------------------------------------------------------------------------


class _StubProvider(LLMProvider):
    """Trivial provider that yields one chunk."""

    def __init__(self, **config: object) -> None:
        super().__init__("stub", **config)

    async def stream(self, request: ProviderRequest):  # type: ignore[override]
        yield Chunk(kind=ChunkKind.TEXT, text="hi")
        yield Chunk(
            kind=ChunkKind.USAGE,
            input_tokens=10,
            output_tokens=5,
            cache_hit_tokens=4,
            cache_miss_tokens=6,
        )
        yield Chunk(kind=ChunkKind.DONE)


class TestProvider:
    def test_chat_aggregates(self) -> None:
        async def scenario() -> None:
            prov = _StubProvider()
            out = await prov.chat(ProviderRequest())
            assert out["text"] == "hi"
            assert out["usage"]["input_tokens"] == 10

        asyncio.run(scenario())

    def test_chat_with_retry_succeeds(self) -> None:
        async def scenario() -> None:
            prov = _StubProvider()
            out = await prov.chat_with_retry(ProviderRequest())
            assert out["text"] == "hi"

        asyncio.run(scenario())

    def test_error_classification(self) -> None:
        prov = _StubProvider()
        err = prov._classify_error(RuntimeError("insufficient_quota"))
        assert err.arrearage

        err2 = prov._classify_error(RuntimeError("rate limit hit 429"))
        assert err2.code == "rate_limit"

        err3 = prov._classify_error(RuntimeError("retry after: 5.5"))
        assert err3.retry_after == 5.5

    def test_detect_arrearage(self) -> None:
        assert detect_arrearage_response(RuntimeError("insufficient_quota"))
        assert not detect_arrearage_response(RuntimeError("other"))


# ---------------------------------------------------------------------------
# Skill metadata tests
# ---------------------------------------------------------------------------


class TestSkillMetadata:
    def test_parse_run_mode_default_inline(self) -> None:
        from openlaoke.core.skill_system import Skill

        skill = Skill(name="x", content="", metadata={})
        assert parse_run_mode(skill) == "inline"

    def test_parse_run_mode_subagent(self) -> None:
        from openlaoke.core.skill_system import Skill

        skill = Skill(name="x", content="", metadata={"runAs": "subagent"})
        assert parse_run_mode(skill) == "subagent"

    def test_pinned_index_marks_subagent(self) -> None:
        from openlaoke.core.skill_system import Skill

        skills = [
            Skill(name="inline", content="x", description="inline skill"),
            Skill(
                name="sub",
                content="x",
                description="sub skill",
                metadata={"runAs": "subagent"},
            ),
        ]
        text = pinned_index(skills)
        assert "inline:" in text
        assert "sub:" in text
        assert "[subagent]" in text

    def test_pin_inline_wraps_with_sentinel(self) -> None:
        from openlaoke.core.skill_system import Skill

        skill = Skill(name="x", content="body content")
        text = pin_inline(skill, body="body content")
        assert '<skill-pin name="x">' in text
        assert "body content" in text
        assert "</skill-pin>" in text
