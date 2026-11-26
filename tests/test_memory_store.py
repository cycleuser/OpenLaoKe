"""Tests for the local memory store and the Memory tool (P9)."""

from __future__ import annotations

import asyncio

from openlaoke.core.memory_store import MemoryStore, tokenize
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.memory_tool import MemoryTool


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path), path=str(tmp_path / "memory.json"))


def _ctx(tmp_path, store: MemoryStore) -> ToolContext:
    state = create_app_state(cwd=str(tmp_path))
    state._memory_store = store
    return ToolContext(app_state=state, tool_use_id="m1")


def test_tokenizer_splits_words_and_breaks_chinese_into_bigrams() -> None:
    tokens = tokenize("Use pytest, 不要用硅片")
    assert "pytest" in tokens
    assert "不要" in tokens and "硅片" in tokens
    assert "the" not in tokenize("the build")


def test_remember_and_recall_by_keyword(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("The release gate is pytest, ruff and mypy.", tags=["ci"], kind="convention")
    store.remember("Do not say 硅片; write 芯片.", tags=["wording"], kind="convention")

    results = store.recall("mypy")
    assert results and "release gate" in results[0].text

    chinese = store.recall("芯片")
    assert chinese and "芯片" in chinese[0].text
    assert chinese[0].uses == 1


def test_remember_is_idempotent_for_identical_text(tmp_path) -> None:
    store = _store(tmp_path)
    first = store.remember("build with uv", tags=["a"])
    second = store.remember("build with uv", tags=["b"])
    assert first.id == second.id
    assert len(store.entries) == 1
    assert second.tags == ["a", "b"]


def test_store_persists_to_disk_and_reloads(tmp_path) -> None:
    path = str(tmp_path / "memory.json")
    store = MemoryStore(str(tmp_path), path=path)
    entry = store.remember("the answer is 42")
    reloaded = MemoryStore(str(tmp_path), path=path)
    assert [item.id for item in reloaded.entries] == [entry.id]
    assert reloaded.get(entry.id).text == "the answer is 42"


def test_forget_removes_and_search_stops_finding_it(tmp_path) -> None:
    store = _store(tmp_path)
    entry = store.remember("temporary fact about walrus")
    assert store.forget(entry.id) is not None
    assert store.search("walrus") == []
    assert store.forget(entry.id) is None


def test_link_and_related(tmp_path) -> None:
    store = _store(tmp_path)
    left = store.remember("use ruff for linting")
    right = store.remember("mypy checks types")
    assert store.link(left.id, right.id) is not None
    related = store.related(left.id)
    assert [item.id for item in related] == [right.id]


def test_tag_add_and_remove(tmp_path) -> None:
    store = _store(tmp_path)
    entry = store.remember("deploy via make release")
    store.tag(entry.id, ["ops", "release"])
    assert store.get(entry.id).tags == ["ops", "release"]
    store.tag(entry.id, ["ops"], remove=True)
    assert store.get(entry.id).tags == ["release"]


def test_recent_filters_by_tag(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("one", tags=["alpha"])
    store.remember("two", tags=["beta"])
    assert [entry.text for entry in store.recent(tag="beta")] == ["two"]


def test_clear_empties_the_store(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("a")
    store.remember("b")
    assert store.clear() == 2
    assert store.entries == []
    assert store.search("a") == []


def test_tool_round_trip(tmp_path) -> None:
    store = _store(tmp_path)
    ctx = _ctx(tmp_path, store)

    remembered = asyncio.run(
        MemoryTool().call(
            ctx,
            action="remember",
            text="gate is pytest + ruff + mypy",
            tags=["ci"],
            kind="convention",
        )
    )
    assert not remembered.is_error
    entry_id = remembered.content.split()[2].rstrip(":")

    recalled = asyncio.run(MemoryTool().call(ctx, action="recall", text="ruff"))
    assert "pytest + ruff + mypy" in recalled.content

    listed = asyncio.run(MemoryTool().call(ctx, action="list", limit=5))
    assert "gate is" in listed.content

    scored = asyncio.run(MemoryTool().call(ctx, action="search", text="mypy"))
    assert entry_id in scored.content

    forgotten = asyncio.run(MemoryTool().call(ctx, action="forget", id=entry_id))
    assert "Forgot" in forgotten.content
    assert asyncio.run(MemoryTool().call(ctx, action="stats")).content.startswith("Memory is empty")


def test_tool_rejects_empty_text_and_unknown_actions(tmp_path) -> None:
    ctx = _ctx(tmp_path, _store(tmp_path))
    assert asyncio.run(MemoryTool().call(ctx, action="remember", text="  ")).is_error
    assert asyncio.run(MemoryTool().call(ctx, action="explode")).is_error
    assert asyncio.run(MemoryTool().call(ctx, action="forget", id="nope")).is_error


def test_tool_related_falls_back_to_text_when_unlinked(tmp_path) -> None:
    store = _store(tmp_path)
    entry = store.remember("the deployment uses a blue-green switch")
    store.remember("a deployment rollback needs the previous colour")
    store.remember("unrelated note about fonts")
    ctx = _ctx(tmp_path, store)
    result = asyncio.run(MemoryTool().call(ctx, action="related", id=entry.id))
    assert "deployment" in result.content
    assert "fonts" not in result.content


def test_memory_command_lists_and_searches(tmp_path) -> None:
    from openlaoke.commands.base import MemoryCommand

    store = _store(tmp_path)

    class Ctx:
        def __init__(self, state, args: str) -> None:
            self.app_state = state
            self.args = args

    ctx = _ctx(tmp_path, store)
    store.remember("remember the milk", tags=["errand"])
    listing = asyncio.run(MemoryCommand().execute(Ctx(ctx.app_state, "")))
    assert "remember the milk" in listing.message
    found = asyncio.run(MemoryCommand().execute(Ctx(ctx.app_state, "milk")))
    assert "milk" in found.message
    cleared = asyncio.run(MemoryCommand().execute(Ctx(ctx.app_state, "clear")))
    assert "Cleared 1" in cleared.message


def test_digest_lists_ids_not_full_text(tmp_path) -> None:
    from openlaoke.core.repl import REPL

    store = _store(tmp_path)
    entry = store.remember("a very long note " + "x" * 300)
    state = create_app_state(cwd=str(tmp_path))
    state._memory_store = store
    repl = object.__new__(REPL)
    repl.app_state = state
    digest = REPL._memory_digest(repl)
    assert "<memory-index>" in digest
    assert entry.id in digest
    assert "x" * 200 not in digest


# --------------------------------------------------------------------------- #
# MemoryTool: the actions the round trip did not touch
# --------------------------------------------------------------------------- #
def test_recall_and_search_need_a_query(tmp_path) -> None:
    ctx = _ctx(tmp_path, _store(tmp_path))

    for action in ("recall", "search"):
        result = asyncio.run(MemoryTool().call(ctx, action=action, text="  "))
        assert result.is_error
        assert "text is required" in result.content


def test_search_without_matches_says_so(tmp_path) -> None:
    ctx = _ctx(tmp_path, _store(tmp_path))

    result = asyncio.run(MemoryTool().call(ctx, action="search", text="nothing here"))

    assert not result.is_error
    assert result.content == "No matching notes."


def test_recall_without_matches_suggests_remembering(tmp_path) -> None:
    ctx = _ctx(tmp_path, _store(tmp_path))

    result = asyncio.run(MemoryTool().call(ctx, action="recall", text="nothing"))

    assert "store it with action='remember'" in result.content


def test_list_falls_back_to_the_stats_when_nothing_matches(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("one note", tags=["ci"])
    ctx = _ctx(tmp_path, store)

    result = asyncio.run(MemoryTool().call(ctx, action="list", kind="missing-tag"))

    assert result.content.startswith("Memory is empty") or "1 note" in result.content


def test_an_action_that_needs_an_id_says_so(tmp_path) -> None:
    ctx = _ctx(tmp_path, _store(tmp_path))

    for action in ("forget", "tag", "link", "related"):
        result = asyncio.run(MemoryTool().call(ctx, action=action))
        assert result.is_error, action
        assert f"id is required for action={action}" in result.content


def test_tagging_adds_and_removes_tags(tmp_path) -> None:
    store = _store(tmp_path)
    entry = store.remember("keep the gate green")
    ctx = _ctx(tmp_path, store)

    tagged = asyncio.run(
        MemoryTool().call(ctx, action="tag", id=entry.id, tags=["ci", "gate"])
    )
    assert "ci" in tagged.content

    untagged = asyncio.run(MemoryTool().call(ctx, action="tag", id=entry.id, tags=["ci"], remove=True))
    assert "ci" not in untagged.content
    assert "gate" in untagged.content

    missing = asyncio.run(MemoryTool().call(ctx, action="tag", id="nope", tags=["x"]))
    assert missing.is_error
    assert "no note with id" in missing.content


def test_tagging_everything_away_reports_none(tmp_path) -> None:
    store = _store(tmp_path)
    entry = store.remember("note", tags=["a"])
    ctx = _ctx(tmp_path, store)

    result = asyncio.run(MemoryTool().call(ctx, action="tag", id=entry.id, tags=["a"], remove=True))

    assert result.content.endswith("(none)")


def test_link_needs_another_id_and_an_existing_pair(tmp_path) -> None:
    store = _store(tmp_path)
    first = store.remember("first note")
    ctx = _ctx(tmp_path, store)

    missing = asyncio.run(MemoryTool().call(ctx, action="link", id=first.id))
    assert missing.is_error
    assert "other_id is required" in missing.content

    second = store.remember("second note")
    linked = asyncio.run(MemoryTool().call(ctx, action="link", id=first.id, other_id=second.id))
    assert not linked.is_error
    assert f"Linked {first.id} <-> {second.id}." == linked.content

    broken = asyncio.run(MemoryTool().call(ctx, action="link", id=first.id, other_id="ghost"))
    assert broken.is_error
    assert "one of the two ids does not exist" in broken.content


def test_related_lists_a_linked_note_and_says_nothing_when_alone(tmp_path) -> None:
    lonely_store = _store(tmp_path / "lonely")
    lonely_store.remember("apple")
    lonely = asyncio.run(
        MemoryTool().call(_ctx(tmp_path, lonely_store), action="related", id="m0001")
    )
    assert "No notes related" in lonely.content or not lonely.is_error

    store = _store(tmp_path)
    first = store.remember("apple")
    second = store.remember("zebra")
    ctx = _ctx(tmp_path, store)

    store.link(first.id, second.id)
    neighbours = asyncio.run(MemoryTool().call(ctx, action="related", id=first.id))

    assert second.id in neighbours.content


def test_register_adds_the_memory_tool(tmp_path) -> None:
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools import memory_tool

    registry = ToolRegistry()
    memory_tool.register(registry)

    assert registry.get("Memory") is not None
