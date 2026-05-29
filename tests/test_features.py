"""Feature and integration tests: memory, read tracker, commands, safety."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from openlaoke.commands.registry import _commands, register_all
from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore
from openlaoke.core.quality_monitor import QualityMonitor
from openlaoke.core.read_tracker import ReadTracker
from openlaoke.core.state import create_app_state
from openlaoke.core.supervisor.context_hygiene import WriteBuffer, extract_key_quotes
from openlaoke.core.tool import ToolContext
from openlaoke.core.tool_call_parser import extract_tool_calls
from openlaoke.tools.edit_tool import EditTool
from openlaoke.tools.glob_tool import GlobTool
from openlaoke.tools.grep_tool import GrepTool
from openlaoke.tools.read_tool import ReadTool
from openlaoke.tools.register import register_all_tools
from openlaoke.tools.write_tool import WriteTool
from openlaoke.utils.permissions.bash_classifier import (
    CommandSafetyLevel,
    classify_bash_command,
)


def _ctx(d: str) -> ToolContext:
    s = create_app_state(cwd=d)
    return ToolContext(app_state=s, tool_use_id="tx")


@pytest.fixture
def tmp():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── MEMORY STORE ───────────────────────────────────────────────────────────────


class TestMemory:
    def test_store_recall_delete(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "m.db"
            store = SQLiteMemoryStore(db_path=db)
            r = MemoryRecord(id="m1", content="test value")
            mid = store.store(r)
            assert store.recall(mid).content == "test value"
            assert store.delete(mid)
            assert store.recall(mid) is None
            store.close()

    def test_search_and_stats(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "m.db"
            store = SQLiteMemoryStore(db_path=db)
            store.store(MemoryRecord(id="a", content="Python lang", key="py"))
            store.store(MemoryRecord(id="b", content="Rust lang", key="rs"))
            hits = store.search_bm25("Python")
            assert len(hits) > 0
            s = store.get_stats()
            assert s["total_memories"] >= 2
            store.close()


# ── BASH CLASSIFIER ────────────────────────────────────────────────────────────


class TestBashClassifier:
    def test_safe(self):
        for cmd in ("ls -la", "echo hello", "git status", "npm test"):
            assert classify_bash_command(cmd).safety_level == CommandSafetyLevel.SAFE

    def test_destructive(self):
        for cmd in ("rm -rf /", "mkfs.ext4 /dev/sda"):
            assert classify_bash_command(cmd).safety_level == CommandSafetyLevel.DESTRUCTIVE

    def test_fields(self):
        r = classify_bash_command("ls")
        assert r.safety_level == CommandSafetyLevel.SAFE
        assert hasattr(r, "confidence") and hasattr(r, "reason")


# ── COMMANDS REGISTRY ──────────────────────────────────────────────────────────


class TestCommands:
    def test_register_all(self):
        register_all()
        assert len(_commands) > 10

    def test_essential_commands(self):
        register_all()
        for cmd in ("help", "exit", "clear", "model", "history"):
            assert cmd in _commands


# ── READ TRACKER ───────────────────────────────────────────────────────────────


class TestReadTracker:
    def test_track_and_guard(self):
        rt = ReadTracker()
        rt.record_read("/f.txt")
        assert rt.has_read("/f.txt")
        assert isinstance(rt.should_guard_read(file_size=500), bool)

    def test_reset(self):
        rt = ReadTracker()
        rt.record_read("/f.txt")
        rt.reset()
        assert not rt.has_read("/f.txt")


# ── CONTEXT HYGIENE ────────────────────────────────────────────────────────────


class TestContextHygiene:
    def test_write_buffer(self, tmp):
        p = os.path.join(tmp, "out.md")
        wb = WriteBuffer(file_path=p)
        assert wb is not None

    def test_extract_quotes(self):
        r = extract_key_quotes('said "hello" and "world"')
        assert isinstance(r, str) and len(r) > 0


# ── TOOL CALL PARSER ───────────────────────────────────────────────────────────


class TestToolCallParser:
    def test_extract(self):
        text = '```json\n{"name": "Bash", "arguments": {"command": "ls"}}\n```'
        calls = extract_tool_calls(text)
        assert isinstance(calls, list)


# ── QUALITY MONITOR ────────────────────────────────────────────────────────────


class TestQualityMonitor:
    def test_exists(self):
        assert QualityMonitor() is not None


# ── INTEGRATION ────────────────────────────────────────────────────────────────


class TestIntegration:
    @pytest.mark.asyncio
    async def test_read_write_edit_cycle(self, tmp):
        ctx = _ctx(tmp)
        p = os.path.join(tmp, "cycle.txt")
        await WriteTool().call(ctx, file_path=p, content="alpha beta gamma")
        await EditTool().call(ctx, file_path=p, old_text="beta", new_text="BETA")
        r = await ReadTool().call(ctx, file_path=p)
        assert "alpha BETA gamma" in r.content

    @pytest.mark.asyncio
    async def test_glob_grep_pipeline(self, tmp):
        ctx = _ctx(tmp)
        os.makedirs(os.path.join(tmp, "src"))
        with open(os.path.join(tmp, "src", "main.py"), "w") as f:
            f.write("def main():\n    print('hi')\n")
        with open(os.path.join(tmp, "src", "data.txt"), "w") as f:
            f.write("no funcs\n")

        g = await GlobTool().call(ctx, pattern="**/*.py", path=tmp)
        assert "main.py" in g.content and "data.txt" not in g.content

        r = await GrepTool().call(ctx, pattern="def main", path=tmp, glob="*.py")
        assert "main" in r.content

    @pytest.mark.asyncio
    async def test_tool_registry_loads(self):
        from openlaoke.core.tool import ToolRegistry

        reg = ToolRegistry()
        register_all_tools(reg)
        names = [t.name for t in reg.get_loaded()]
        for expect in ("Bash", "Read", "Write", "Edit", "Glob", "Grep"):
            assert expect in names
