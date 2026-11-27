"""Tests for session and conversation search (P10)."""

from __future__ import annotations

import asyncio
import json
import time

from openlaoke.core.session_index import search_conversation, search_sessions
from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.session_search_tool import ConversationSearchTool, SessionSearchTool
from openlaoke.types.core_types import AssistantMessage, MessageRole, UserMessage


def _write_session(directory, session_id: str, cwd: str, messages: list[dict]) -> None:
    payload = {"session_id": session_id, "cwd": cwd, "messages": messages}
    with open(directory / f"{session_id}.json", "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def _msg(role: str, content: str, timestamp: float | None = None) -> dict:
    return {"role": role, "content": content, "timestamp": timestamp or time.time()}


def test_search_finds_a_message_across_sessions(tmp_path) -> None:
    _write_session(
        tmp_path,
        "s1",
        str(tmp_path),
        [
            _msg("user", "we should cache the token budget per session"),
            _msg("assistant", "agreed, the budget is min(window, cap)"),
        ],
    )
    _write_session(tmp_path, "s2", str(tmp_path), [_msg("user", "unrelated talk about fonts")])

    hits = search_sessions("token budget", sessions_dir=str(tmp_path))
    assert hits
    assert hits[0].session_id == "s1"
    assert "cache the token budget" in hits[0].text
    assert all(hit.score > 0 for hit in hits)


def test_search_ranks_the_better_match_first(tmp_path) -> None:
    _write_session(tmp_path, "weak", "", [_msg("user", "budget mentioned once, budget")])
    _write_session(
        tmp_path,
        "strong",
        "",
        [_msg("user", "cache monitor reads cache_read_input_tokens and cache creation")],
    )
    hits = search_sessions("cache monitor cache_read_input_tokens", sessions_dir=str(tmp_path))
    assert hits[0].session_id == "strong"


def test_search_filters_by_role_and_cwd(tmp_path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _write_session(tmp_path, "s1", str(tmp_path), [_msg("user", "alpha decision")])
    _write_session(tmp_path, "s2", str(other), [_msg("user", "alpha elsewhere")])
    _write_session(tmp_path, "s3", str(tmp_path), [_msg("assistant", "alpha reply")])

    by_cwd = search_sessions("alpha", sessions_dir=str(tmp_path), cwd=str(tmp_path))
    assert {hit.session_id for hit in by_cwd} == {"s1", "s3"}

    by_role = search_sessions("alpha", sessions_dir=str(tmp_path), role="assistant")
    assert [hit.session_id for hit in by_role] == ["s3"]


def test_search_respects_the_day_window(tmp_path) -> None:
    _write_session(tmp_path, "old", "", [_msg("user", "ancient wisdom about queues")])
    old_path = tmp_path / "old.json"
    past = time.time() - 10 * 86400
    import os

    os.utime(old_path, (past, past))
    _write_session(tmp_path, "new", "", [_msg("user", "fresh wisdom about queues")])

    hits = search_sessions("wisdom", sessions_dir=str(tmp_path), days=2)
    assert [hit.session_id for hit in hits] == ["new"]


def test_chinese_query_matches_by_bigram(tmp_path) -> None:
    _write_session(tmp_path, "zh", "", [_msg("user", "上下文预算要按模型的窗口来算")])
    hits = search_sessions("上下文", sessions_dir=str(tmp_path))
    assert hits and "上下文" in hits[0].text


def test_search_handles_a_missing_or_broken_directory(tmp_path) -> None:
    assert search_sessions("anything", sessions_dir=str(tmp_path / "nope")) == []
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    assert search_sessions("anything", sessions_dir=str(tmp_path)) == []


def test_conversation_search_finds_an_old_message(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    state.messages.extend(
        [
            UserMessage(role=MessageRole.USER, content="the timeout should be 3000ms"),
            AssistantMessage(role=MessageRole.ASSISTANT, content="noted the timeout"),
            UserMessage(role=MessageRole.USER, content="something else entirely"),
        ]
    )
    hits = search_conversation("timeout 3000", state.messages)
    assert hits
    assert "3000ms" in hits[0].text
    assert hits[0].role == "user"


def test_session_search_tool_reports_hits(tmp_path, monkeypatch) -> None:
    _write_session(tmp_path, "s1", "", [_msg("user", "the release gate is pytest ruff mypy")])
    monkeypatch.setattr("openlaoke.core.session_index.SESSIONS_DIR", str(tmp_path))
    ctx = ToolContext(app_state=create_app_state(cwd=str(tmp_path)), tool_use_id="s1")
    result = asyncio.run(SessionSearchTool().call(ctx, query="release gate"))
    assert "1 hit" in result.content
    assert "pytest ruff mypy" in result.content


def test_session_search_tool_requires_a_query(tmp_path) -> None:
    ctx = ToolContext(app_state=create_app_state(cwd=str(tmp_path)), tool_use_id="s1")
    assert asyncio.run(SessionSearchTool().call(ctx, query="  ")).is_error


def test_conversation_search_tool_uses_the_live_history(tmp_path) -> None:
    state = create_app_state(cwd=str(tmp_path))
    state.messages.append(UserMessage(role=MessageRole.USER, content="remember the walrus"))
    ctx = ToolContext(app_state=state, tool_use_id="c1")
    result = asyncio.run(ConversationSearchTool().call(ctx, query="walrus"))
    assert "walrus" in result.content
    missing = asyncio.run(ConversationSearchTool().call(ctx, query="zebra"))
    assert "matches" in missing.content


def test_search_command_formats_hits(tmp_path, monkeypatch) -> None:
    from openlaoke.commands.base import SearchCommand

    _write_session(tmp_path, "s1", "", [_msg("user", "we chose BM25 over embeddings")])
    monkeypatch.setattr("openlaoke.core.session_index.SESSIONS_DIR", str(tmp_path))

    class Ctx:
        def __init__(self, state, args: str) -> None:
            self.app_state = state
            self.args = args

    state = create_app_state(cwd=str(tmp_path))
    result = asyncio.run(SearchCommand().execute(Ctx(state, "BM25")))
    assert "BM25" in result.message
    assert not asyncio.run(SearchCommand().execute(Ctx(state, ""))).success


def _write_journal(directory, session_id: str, cwd: str, lines: list[str]) -> None:
    from openlaoke.core.state import create_app_state
    from openlaoke.core.transcript import Transcript

    state = create_app_state(cwd=cwd, persist_path=str(directory / f"{session_id}.json"))
    state.session_id = session_id
    state.set_persist_path(str(directory / f"{session_id}.json"))
    transcript = Transcript(
        str(directory / f"{session_id}.jsonl"), session_id=session_id, cwd=cwd, model="m"
    )
    for line in lines:
        transcript.append_message(UserMessage(role=MessageRole.USER, content=line))


def test_a_journal_only_session_is_searchable(tmp_path) -> None:
    _write_journal(tmp_path, "recovered", str(tmp_path), ["the migration order was users first"])
    # No .json beside it: this session exists only as a journal.
    assert not (tmp_path / "recovered.json").exists()

    hits = search_sessions("migration order", sessions_dir=str(tmp_path))

    assert hits
    assert hits[0].session_id == "recovered"
    assert "users first" in hits[0].text


def test_a_corrupt_snapshot_is_searched_through_its_journal(tmp_path) -> None:
    _write_journal(tmp_path, "broken", str(tmp_path), ["the timeout is 30 seconds"])
    (tmp_path / "broken.json").write_text("{ not json")

    hits = search_sessions("timeout", sessions_dir=str(tmp_path))

    assert [hit.session_id for hit in hits] == ["broken"]


def test_a_journal_without_messages_is_skipped_by_search(tmp_path) -> None:
    (tmp_path / "empty.jsonl").write_text("")

    assert search_sessions("anything", sessions_dir=str(tmp_path)) == []


def test_search_does_not_list_a_session_twice(tmp_path) -> None:
    _write_session(tmp_path, "both", str(tmp_path), [_msg("user", "the flag is enabled")])
    _write_journal(tmp_path, "both", str(tmp_path), ["duplicate journal line"])

    hits = search_sessions("enabled", sessions_dir=str(tmp_path))

    assert len({hit.session_id for hit in hits}) == 1


def test_search_of_a_missing_directory_is_empty(tmp_path) -> None:
    assert search_sessions("anything", sessions_dir=str(tmp_path / "nope")) == []


def test_score_documents_scores_plain_texts(tmp_path) -> None:
    from openlaoke.core.session_index import score_documents

    scores = score_documents("migration order", ["the migration order", "nothing here"])

    assert len(scores) == 2
    assert scores[0] > 0
    assert scores[1] == 0


def test_the_limit_stops_the_result_list(tmp_path) -> None:
    for index in range(6):
        _write_session(tmp_path, f"s{index}", str(tmp_path), [_msg("user", "the same flag")])

    hits = search_sessions("flag", sessions_dir=str(tmp_path), limit=3)

    assert len(hits) == 3


def test_an_unreadable_mtime_skips_the_session(tmp_path, monkeypatch) -> None:
    import os.path as os_path

    _write_session(tmp_path, "s1", str(tmp_path), [_msg("user", "a searchable line")])
    real_getmtime = os_path.getmtime

    def fake_getmtime(path):
        if str(path).endswith("s1.json"):
            raise OSError("gone")
        return real_getmtime(path)

    monkeypatch.setattr("openlaoke.core.session_index.os.path.getmtime", fake_getmtime)

    assert search_sessions("searchable", sessions_dir=str(tmp_path), days=1) == []


def test_an_unlistable_directory_is_treated_as_empty(tmp_path, monkeypatch) -> None:
    import openlaoke.core.session_index as index_module

    def refuse(_path):
        raise OSError("permission denied")

    monkeypatch.setattr(index_module.os, "listdir", refuse)

    assert index_module._payloads(str(tmp_path)) == []


def test_the_conversation_search_limit_stops_the_list() -> None:
    messages = [UserMessage(role=MessageRole.USER, content=f"repeated flag {i}") for i in range(5)]

    hits = search_conversation("flag", messages, limit=2)

    assert len(hits) == 2


def test_an_empty_conversation_search_returns_nothing() -> None:
    assert search_conversation("flag", []) == []
    assert search_conversation("", [UserMessage(role=MessageRole.USER, content="x")]) == []


def test_a_message_with_no_text_is_not_indexed() -> None:
    messages = [
        UserMessage(role=MessageRole.USER, content=""),
        UserMessage(role=MessageRole.USER, content="   "),
        UserMessage(role=MessageRole.USER, content="a real line"),
    ]

    hits = search_conversation("real", messages)

    assert [hit.index for hit in hits] == [2]
