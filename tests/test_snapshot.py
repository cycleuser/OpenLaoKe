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

    def test_fork_session(self, store: SnapshotStore) -> None:
        new_id, meta_path = store.fork_session("s1", 3)
        assert new_id.startswith("s1_fork_")
        assert os.path.exists(meta_path)
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["parent"] == "s1"
        assert meta["fork_turn"] == 3

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

    def test_rewind_conversation_report(self, store: SnapshotStore) -> None:
        report = rewind_conversation(store, "s1", 5)
        assert report.scope == "conversation"
        assert report.turns_dropped == 5

    def test_rewind_both(self, store: SnapshotStore, workspace: str) -> None:
        report = rewind_both(store, "s1", 5)
        assert report.scope == "code+conversation"

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
