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

    tagged = asyncio.run(MemoryTool().call(ctx, action="tag", id=entry.id, tags=["ci", "gate"]))
    assert "ci" in tagged.content

    untagged = asyncio.run(
        MemoryTool().call(ctx, action="tag", id=entry.id, tags=["ci"], remove=True)
    )
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


# --------------------------------------------------------------------------- #
# authority and supersession
# --------------------------------------------------------------------------- #
def test_a_user_note_outranks_a_more_relevant_agent_note(tmp_path) -> None:
    """Relevance must not decide whose fact wins."""
    store = _store(tmp_path)
    store.remember("Always run the release gate with pytest.", authority="user")
    # Scores higher on this query: it repeats the words more often.
    store.remember(
        "release gate release gate release gate unittest release gate",
        authority="agent",
    )

    results = store.recall("release gate unittest")

    assert results[0].authority == "user"
    assert "pytest" in results[0].text


def test_a_superseded_note_stops_being_retrieved_but_stays_on_disk(tmp_path) -> None:
    store = _store(tmp_path)
    old = store.remember("Deploy with the legacy rsync script.", kind="decision")
    new = store.remember(
        "Deploy with make release; the rsync script is retired.",
        kind="decision",
        supersedes=[old.id],
    )

    assert new.supersedes == [old.id]
    assert old.superseded_by == new.id
    assert [entry.id for entry in store.recall("deploy rsync script")] == [new.id]

    everything = store.recall("deploy rsync script", include_superseded=True)
    assert {entry.id for entry in everything} == {old.id, new.id}
    assert store.get(old.id) is not None  # evidence is kept, not deleted


def test_unknown_supersede_ids_are_ignored_rather_than_failing(tmp_path) -> None:
    store = _store(tmp_path)

    entry = store.remember("New fact.", supersedes=["mdoes-not-exist"])

    assert entry.supersedes == []
    assert entry.text == "New fact."


def test_an_agent_restatement_cannot_demote_a_user_note(tmp_path) -> None:
    store = _store(tmp_path)
    original = store.remember("Never say 硅片.", authority="user")

    again = store.remember("Never say 硅片.", authority="agent")

    assert again.id == original.id
    assert again.authority == "user"


def test_reasserting_at_higher_authority_upgrades_the_note(tmp_path) -> None:
    store = _store(tmp_path)
    original = store.remember("Use 芯片.", authority="agent")

    store.remember("Use 芯片.", authority="user")

    assert original.authority == "user"


def test_an_unknown_authority_is_rejected(tmp_path) -> None:
    import pytest

    store = _store(tmp_path)
    with pytest.raises(ValueError):
        store.remember("fact", authority="root")


def test_the_memory_tool_can_only_write_agent_notes(tmp_path) -> None:
    store = _store(tmp_path)
    ctx = _ctx(tmp_path, store)

    asyncio.run(MemoryTool().call(ctx, action="remember", text="Use ruff format --check."))

    assert store.entries[0].authority == "agent"


def test_the_memory_tool_can_supersede_and_says_so(tmp_path) -> None:
    store = _store(tmp_path)
    ctx = _ctx(tmp_path, store)
    old = store.remember("Gate is unittest.", kind="convention")

    result = asyncio.run(
        MemoryTool().call(
            ctx,
            action="remember",
            text="Gate is pytest.",
            kind="convention",
            supersedes=[old.id],
        )
    )

    assert result.is_error is False
    assert f"replaces {old.id}" in result.content
    assert old.superseded_by != ""


def test_the_command_writes_a_user_note_the_tool_cannot_outrank(tmp_path) -> None:
    store = _store(tmp_path)
    state = create_app_state(cwd=str(tmp_path))
    state._memory_store = store

    class Ctx:
        app_state = state
        args = "remember Always use pytest, never unittest."
        reply = None

    from openlaoke.commands.base import MemoryCommand

    result = asyncio.run(MemoryCommand().execute(Ctx()))

    assert "(user)" in result.message
    assert store.entries[0].authority == "user"
    assert store.entries[0].text == "Always use pytest, never unittest."


def test_the_digest_puts_user_notes_first_and_drops_superseded_ones(tmp_path) -> None:
    store = _store(tmp_path)
    old = store.remember("Deploy with rsync.", kind="decision")
    store.remember("Deploy with make release.", kind="decision", supersedes=[old.id])
    store.remember("Never say 硅片.", authority="user")

    digest = store.digest(max_chars=500)

    lines = digest.splitlines()
    assert lines[0].startswith("- [user] Never say 硅片.")
    assert "rsync" not in digest
    assert "make release" in digest


def test_a_tight_digest_budget_keeps_the_strongest_note(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("x" * 400, authority="agent")
    store.remember("Always use 芯片.", authority="user")

    digest = store.digest(max_chars=60)

    assert "芯片" in digest
    assert all(len(line) <= 60 for line in digest.splitlines())


def test_render_and_stats_surface_authority_and_supersession(tmp_path) -> None:
    store = _store(tmp_path)
    old = store.remember("old fact")
    new = store.remember("new fact", authority="user", supersedes=[old.id])

    rendered = store.render([old, new])
    assert f"superseded by {new.id}" in rendered
    assert "new fact" in rendered and "<user>" in rendered
    assert f"replaces {old.id}" in rendered

    stats = store.stats()
    assert "authority: user×1, agent×1" in stats
    assert "superseded: 1" in stats


def test_notes_written_before_authority_existed_still_load(tmp_path) -> None:
    import json

    path = tmp_path / "memory.json"
    path.write_text(
        json.dumps(
            {"version": 1, "cwd": str(tmp_path), "entries": [{"id": "m1", "text": "legacy note"}]}
        )
    )

    store = MemoryStore(str(tmp_path), path=str(path))

    assert store.entries[0].authority == "agent"
    assert store.entries[0].superseded is False


def test_the_prompt_index_skips_superseded_notes_and_marks_authority(tmp_path) -> None:
    store = _store(tmp_path)
    old = store.remember("Deploy with rsync.", kind="decision")
    store.remember("Deploy with make release.", kind="decision", supersedes=[old.id])
    store.remember("Always use pytest.", authority="user")

    names = [entry.text for entry in store.index_entries()]
    assert "Deploy with rsync." not in names
    assert names[0] == "Always use pytest."


def test_the_repl_memory_index_uses_the_same_rules(tmp_path) -> None:
    from openlaoke.core.repl import REPL

    store = _store(tmp_path)
    old = store.remember("Deploy with rsync.", kind="decision")
    store.remember("Deploy with make release.", kind="decision", supersedes=[old.id])
    store.remember("Always use pytest.", authority="user")
    state = create_app_state(cwd=str(tmp_path))
    state._memory_store = store

    repl = REPL.__new__(REPL)
    repl.app_state = state
    block = REPL._memory_digest(repl)

    assert "rsync" not in block
    assert "make release" in block
    assert "[user] Always use pytest." in block
    assert block.startswith("<memory-index>")


def test_recent_supersessions_do_not_hide_the_older_current_notes(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("Always use pytest.", authority="user")
    # A long supersession chain: every link except the last is superseded, so
    # the newest window is almost entirely replaced notes.
    previous = store.remember("Port 8080 for the dev server.")
    for step in range(30):
        previous = store.remember(
            f"Port {9000 + step} for the dev server.", supersedes=[previous.id]
        )

    names = [entry.text for entry in store.index_entries(limit=8)]

    assert names[0] == "Always use pytest."
    assert "Port 9029 for the dev server." in names
    assert len(names) >= 2, names


def test_the_prompt_digest_is_not_emptied_by_a_supersession_chain(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember("Always use pytest.", authority="user")
    previous = store.remember("Port 8080 for the dev server.")
    for step in range(20):
        previous = store.remember(
            f"Port {9000 + step} for the dev server.", supersedes=[previous.id]
        )

    block = store.digest()

    assert "Always use pytest." in block
    assert "Port 9019 for the dev server." in block
