"""Tests for the snapshot (rewind, fork, branch) system."""

from __future__ import annotations

import json
import os

import pytest

from openlaoke.snapshot.rewind import (
    branch_tip,
    fork_from,
    rewind_both,
    rewind_code,
    rewind_conversation,
    summarize_from,
    summarize_up_to,
)
from openlaoke.snapshot.store import SnapshotStore, TurnSnapshot


@pytest.fixture
def store(tmp_path) -> SnapshotStore:
    return SnapshotStore(base_dir=str(tmp_path / "snap"))


@pytest.fixture
def workspace(tmp_path) -> str:
    work = tmp_path / "work"
    work.mkdir()
    return str(work)


class TestSnapshotStore:
    def test_capture_new_file(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        snap = store.capture_file("s1", 0, target)
        assert snap.content is None
        assert not snap.existed

    def test_capture_existing_file(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("hello")
        snap = store.capture_file("s1", 0, target)
        assert snap.existed
        assert snap.content == "hello"

    def test_dedup_within_turn(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("v1")
        store.capture_file("s1", 0, target)
        with open(target, "w", encoding="utf-8") as f:
            f.write("v2")
        snap = store.capture_file("s1", 0, target)
        assert snap.content == "v1"

    def test_rewind_restores_content(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("original")
        store.capture_file("s1", 0, target)
        with open(target, "w", encoding="utf-8") as f:
            f.write("modified")
        report = store.rewind("s1", 0)
        assert target in report
        assert report[target] == "restored"
        with open(target, encoding="utf-8") as f:
            assert f.read() == "original"

    def test_rewind_deletes_new_file(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "new.txt")
        store.capture_file("s1", 0, target)
        with open(target, "w", encoding="utf-8") as f:
            f.write("data")
        report = store.rewind("s1", 0)
        assert report[target] == "deleted"
        assert not os.path.exists(target)

    def test_capture_conversation_persists(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 0, [{"role": "user", "content": "hello"}])
        turn = store.load_turn("s1", 0)
        assert turn.conversation == [{"role": "user", "content": "hello"}]

    def test_capture_conversation_serializes_message_objects(self, store: SnapshotStore) -> None:
        from openlaoke.types.core_types import MessageRole, UserMessage

        store.capture_conversation("s1", 0, [UserMessage(role=MessageRole.USER, content="hi")])
        turn = store.load_turn("s1", 0)
        assert turn.conversation[0]["type"] == "user"
        assert turn.conversation[0]["content"] == "hi"

    def test_conversation_before(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 0, [{"role": "user", "content": "turn0"}])
        store.capture_conversation("s1", 1, [{"role": "user", "content": "turn1"}])
        assert store.conversation_before("s1", 1) == [{"role": "user", "content": "turn0"}]
        assert store.conversation_before("s1", 0) is None
        assert store.conversation_before("s1", 99) == [{"role": "user", "content": "turn1"}]

    def test_fork_session(self, store: SnapshotStore) -> None:
        new_id, meta_path = store.fork_session("s1", 3)
        assert new_id.startswith("s1_fork_")
        assert os.path.exists(meta_path)
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["parent"] == "s1"
        assert meta["fork_turn"] == 3

    def test_fork_inherits_conversation_and_files(
        self, store: SnapshotStore, workspace: str
    ) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("v0")
        store.capture_file("s1", 0, target)
        store.capture_conversation("s1", 0, [{"role": "user", "content": "msg0"}])
        store.capture_conversation("s1", 1, [{"role": "user", "content": "msg1"}])

        new_id, _ = store.fork_session("s1", 1)
        turns = store.all_turns(new_id)
        assert [t.turn_index for t in turns] == [0, 1]
        assert turns[0].conversation == [{"role": "user", "content": "msg0"}]
        assert turns[1].conversation == [{"role": "user", "content": "msg1"}]
        assert target in turns[0].files

    def test_fork_at_tip_inherits_all(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 0, [{"role": "user", "content": "a"}])
        store.capture_conversation("s1", 2, [{"role": "user", "content": "c"}])
        new_id, meta_path = store.fork_session("s1", -1)
        assert store.all_turns(new_id)[-1].conversation == [{"role": "user", "content": "c"}]
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["fork_turn"] == 2

    def test_save_and_load_turn(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("hi")
        turn = TurnSnapshot(turn_index=7)
        turn.files[target] = store.capture_file("s1", 7, target)
        store.save_turn("s1", turn)
        loaded = store.load_turn("s1", 7)
        assert loaded.turn_index == 7
        assert target in loaded.files

    def test_all_turns_sorted(self, store: SnapshotStore, workspace: str) -> None:
        for i in (3, 1, 2):
            store.save_turn("s1", TurnSnapshot(turn_index=i))
        turns = store.all_turns("s1")
        assert [t.turn_index for t in turns] == [1, 2, 3]


class TestRewindOps:
    def test_rewind_code_report(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("v0")
        store.capture_file("s1", 0, target)
        with open(target, "w", encoding="utf-8") as f:
            f.write("v1")
        report = rewind_code(store, "s1", 0)
        assert report.scope == "code"
        assert target in report.files

    def test_rewind_conversation_truncates_messages(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 0, [{"role": "user", "content": "early"}])
        store.capture_conversation("s1", 1, [{"role": "user", "content": "late"}])
        live: list[dict] = [
            {"role": "user", "content": "early"},
            {"role": "user", "content": "late"},
            {"role": "assistant", "content": "answer"},
        ]
        report = rewind_conversation(store, "s1", 1, messages=live)
        assert report.scope == "conversation"
        assert report.turns_dropped == 1
        assert len(live) == 1
        assert live[0].content == "early"

    def test_rewind_conversation_no_recorded_keeps_live(self, store: SnapshotStore) -> None:
        live: list[dict] = [{"role": "user", "content": "x"}]
        report = rewind_conversation(store, "s1", 5, messages=live)
        assert report.turns_dropped == 0
        assert live == [{"role": "user", "content": "x"}]

    def test_rewind_to_turn_zero_clears_messages(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 0, [{"role": "user", "content": "first"}])
        store.capture_conversation("s1", 1, [{"role": "user", "content": "second"}])
        live: list[dict] = [
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
        ]
        report = rewind_conversation(store, "s1", 0, messages=live)
        assert report.turns_dropped == 2
        assert live == []

    def test_rewind_before_first_turn_clears_messages(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 2, [{"role": "user", "content": "c"}])
        live: list[dict] = [{"role": "user", "content": "c"}]
        report = rewind_conversation(store, "s1", 1, messages=live)
        assert report.turns_dropped == 1
        assert live == []

    def test_rewind_both(self, store: SnapshotStore, workspace: str) -> None:
        target = os.path.join(workspace, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("v0")
        store.capture_file("s1", 0, target)
        store.capture_conversation("s1", 0, [{"role": "user", "content": "early"}])
        store.capture_file("s1", 1, target)
        store.capture_conversation("s1", 1, [{"role": "user", "content": "late"}])
        with open(target, "w", encoding="utf-8") as f:
            f.write("v1")
        live: list[dict] = [
            {"role": "user", "content": "early"},
            {"role": "user", "content": "late"},
        ]
        report = rewind_both(store, "s1", 1, messages=live)
        assert report.scope == "code+conversation"
        assert target in report.files
        assert len(live) == 1
        assert live[0].content == "early"

    def test_fork_from(self, store: SnapshotStore) -> None:
        info = fork_from(store, "s1", 3, label="test")
        assert info["fork_turn"] == 3
        assert info["label"] == "test"

    def test_branch_tip(self, store: SnapshotStore) -> None:
        info = branch_tip(store, "s1", label="alt")
        assert info["label"] == "alt"

    def test_summarize_from(self, store: SnapshotStore) -> None:
        store.save_turn("s1", TurnSnapshot(turn_index=1))
        store.save_turn("s1", TurnSnapshot(turn_index=2))
        info = summarize_from(store, "s1", 1)
        assert info["scope"] == "from"

    def test_summarize_up_to(self, store: SnapshotStore) -> None:
        store.save_turn("s1", TurnSnapshot(turn_index=1))
        info = summarize_up_to(store, "s1", 1)
        assert info["scope"] == "up_to"

    def test_summarize_conversation_rewind_available(self, store: SnapshotStore) -> None:
        store.capture_conversation("s1", 0, [{"role": "user", "content": "x"}])
        assert summarize_from(store, "s1", 0)["conversation_rewind_available"] is True
        assert summarize_up_to(store, "s1", 0)["conversation_rewind_available"] is True

    def test_summarize_conversation_rewind_unavailable(self, store: SnapshotStore) -> None:
        store.save_turn("s1", TurnSnapshot(turn_index=0))
        assert summarize_from(store, "s1", 0)["conversation_rewind_available"] is False
