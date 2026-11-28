"""Tests for the file-history / checkpoint system.

Snapshots go under a HISTORY_DIR redirected into tmp_path, so nothing touches
~/.openlaoke. The important guarantees are: a snapshot is captured *before* an
edit (so it can be restored), versions are sequential, the ring keeps only the
last MAX_SNAPSHOTS entries, and a corrupt history file degrades to "no history"
rather than raising.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from openlaoke.utils import file_history as fh
from openlaoke.utils.file_history import (
    FileHistory,
    FileHistoryState,
    FileSnapshot,
    clear_all_histories,
    clear_history,
    compute_checksum,
    file_history_enabled,
    format_history_list,
    format_timestamp,
    get_history,
    get_history_dir,
    get_history_path,
    get_latest_snapshot,
    get_snapshot_by_version,
    restore_snapshot,
    save_snapshot,
    track_file_edit,
)


@pytest.fixture(autouse=True)
def history_dir(tmp_path, monkeypatch):
    target = tmp_path / "history"
    monkeypatch.setattr(fh, "HISTORY_DIR", str(target))
    return target


@pytest.fixture()
def work_file(tmp_path):
    path = tmp_path / "src" / "app.py"
    path.parent.mkdir()
    path.write_text("original content\n", encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------- #
# Dataclass round trips
# --------------------------------------------------------------------------- #


def test_snapshot_round_trip() -> None:
    snap = FileSnapshot(
        path="/a.py", content="x", timestamp=1.0, checksum="abc", version=2, message_id="m1"
    )
    restored = FileSnapshot.from_dict(snap.to_dict())
    assert restored == snap


def test_snapshot_from_dict_defaults() -> None:
    snap = FileSnapshot.from_dict(
        {"path": "/a.py", "content": "", "timestamp": 0.0, "checksum": "c"}
    )
    assert snap.version == 1
    assert snap.message_id is None


def test_history_round_trip() -> None:
    history = FileHistory(
        path="/a.py",
        snapshots=[FileSnapshot(path="/a.py", content="1", timestamp=1.0, checksum="c")],
    )
    assert FileHistory.from_dict(history.to_dict()) == history


def test_history_state_round_trip_keeps_the_tracked_set() -> None:
    state = FileHistoryState(histories={"a": FileHistory(path="a")}, tracked_files={"a", "b"})
    restored = FileHistoryState.from_dict(state.to_dict())
    assert restored.tracked_files == {"a", "b"}
    assert "a" in restored.histories


def test_history_state_from_empty_dict() -> None:
    state = FileHistoryState.from_dict({})
    assert state.histories == {}
    assert state.tracked_files == set()


# --------------------------------------------------------------------------- #
# Paths and checksums
# --------------------------------------------------------------------------- #


def test_history_dir_is_expanded(history_dir) -> None:
    assert get_history_dir() == str(history_dir)


def test_history_path_is_stable_and_per_file(history_dir, tmp_path) -> None:
    first = get_history_path("/some/file.py")
    assert first == get_history_path("/some/file.py")
    assert first != get_history_path("/other/file.py")
    assert Path(first).parent == history_dir
    assert Path(first).suffix == ".json"


def test_checksum_is_short_deterministic_and_content_sensitive() -> None:
    assert compute_checksum("abc") == compute_checksum("abc")
    assert compute_checksum("abc") != compute_checksum("abd")
    assert len(compute_checksum("abc")) == 16


# --------------------------------------------------------------------------- #
# save_snapshot
# --------------------------------------------------------------------------- #


def test_save_snapshot_creates_the_store_and_assigns_versions(work_file, history_dir) -> None:
    first = save_snapshot(work_file, "v1")
    second = save_snapshot(work_file, "v2", message_id="m1")

    assert first.version == 1
    assert second.version == 2
    assert second.message_id == "m1"
    assert first.path == os.path.abspath(work_file)
    assert history_dir.is_dir()

    stored = get_history(work_file)
    assert stored is not None
    assert [s.content for s in stored.snapshots] == ["v1", "v2"]


def test_save_snapshot_keeps_only_the_last_hundred(work_file) -> None:
    for i in range(fh.MAX_SNAPSHOTS + 5):
        save_snapshot(work_file, f"content-{i}")

    stored = get_history(work_file)
    assert len(stored.snapshots) == fh.MAX_SNAPSHOTS
    assert stored.snapshots[-1].content == f"content-{fh.MAX_SNAPSHOTS + 4}"
    # Versions stay unique and monotonic even though older entries are dropped:
    # a length-based counter would repeat 101 forever after the ring wraps.
    assert stored.snapshots[-1].version == fh.MAX_SNAPSHOTS + 5
    versions = [s.version for s in stored.snapshots]
    assert versions == list(range(6, fh.MAX_SNAPSHOTS + 6))
    # The newest version therefore restores the newest content.
    assert (
        get_snapshot_by_version(work_file, fh.MAX_SNAPSHOTS + 5).content
        == f"content-{fh.MAX_SNAPSHOTS + 4}"
    )


def test_save_snapshot_survives_a_corrupt_history_file(work_file) -> None:
    path = Path(get_history_path(os.path.abspath(work_file)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    snapshot = save_snapshot(work_file, "fresh")

    # The unreadable file is replaced by a fresh history starting at v1.
    assert snapshot.version == 1
    assert get_history(work_file).snapshots[0].content == "fresh"


def test_save_snapshot_reports_failure_when_the_store_is_unwritable(work_file, history_dir) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(history_dir, 0o500)
    try:
        # An unrecorded snapshot must not be handed back: /restore would search
        # for a version that was never written. The edit itself still goes on.
        assert save_snapshot(work_file, "x") is None
    finally:
        os.chmod(history_dir, 0o700)


def test_a_failed_write_keeps_the_versions_already_recorded(work_file) -> None:
    save_snapshot(work_file, "v1 content")
    store = Path(get_history_path(os.path.abspath(work_file)))

    def half_then_fail(payload, handle, **kwargs):
        handle.write('{"path": "half')
        raise OSError(28, "No space left on device")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fh.json, "dump", half_then_fail)
        assert save_snapshot(work_file, "v2 content") is None

    # The half-written temporary file is gone and the earlier version survived.
    assert [item.name for item in store.parent.iterdir()] == [store.name]
    history = get_history(work_file)
    assert [snapshot.content for snapshot in history.snapshots] == ["v1 content"]


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #


def test_get_history_without_a_store_returns_none(tmp_path) -> None:
    assert get_history(str(tmp_path / "never-touched.py")) is None


def test_get_history_returns_none_for_corrupt_json(work_file) -> None:
    path = Path(get_history_path(os.path.abspath(work_file)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")
    assert get_history(work_file) is None


def test_get_latest_snapshot(work_file) -> None:
    assert get_latest_snapshot(work_file) is None
    save_snapshot(work_file, "one")
    save_snapshot(work_file, "two")
    latest = get_latest_snapshot(work_file)
    assert latest is not None
    assert latest.content == "two"


def test_get_snapshot_by_version(work_file) -> None:
    save_snapshot(work_file, "one")
    save_snapshot(work_file, "two")

    assert get_snapshot_by_version(work_file, 1).content == "one"
    assert get_snapshot_by_version(work_file, 2).content == "two"
    assert get_snapshot_by_version(work_file, 99) is None
    assert get_snapshot_by_version("/never/snapshotted.py", 1) is None


# --------------------------------------------------------------------------- #
# restore_snapshot
# --------------------------------------------------------------------------- #


def test_restore_latest_snapshot(work_file) -> None:
    save_snapshot(work_file, "first version\n")
    Path(work_file).write_text("edited badly\n", encoding="utf-8")

    assert restore_snapshot(work_file) is True
    assert Path(work_file).read_text(encoding="utf-8") == "first version\n"


def test_restore_a_specific_version(work_file) -> None:
    save_snapshot(work_file, "v1\n")
    save_snapshot(work_file, "v2\n")

    assert restore_snapshot(work_file, version=1) is True
    assert Path(work_file).read_text(encoding="utf-8") == "v1\n"


def test_restore_recreates_a_deleted_file(tmp_path) -> None:
    path = str(tmp_path / "gone" / "file.txt")
    save_snapshot(path, "content\n")
    assert not os.path.exists(path)
    assert restore_snapshot(path) is True
    assert Path(path).read_text(encoding="utf-8") == "content\n"


def test_restore_without_history_fails(work_file) -> None:
    assert restore_snapshot(work_file) is False
    assert restore_snapshot(work_file, version=3) is False


def test_restore_reports_write_failures(work_file, monkeypatch) -> None:
    save_snapshot(work_file, "content")

    def boom(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("builtins.open", boom)
    assert restore_snapshot(work_file) is False


# --------------------------------------------------------------------------- #
# Display helpers
# --------------------------------------------------------------------------- #


def test_format_timestamp_is_second_precision() -> None:
    formatted = format_timestamp(0.0)
    assert len(formatted) == len("1970-01-01 00:00:00")
    assert formatted.count(":") == 2


def test_format_history_list_without_history(work_file) -> None:
    assert format_history_list(work_file) == f"No history found for {work_file}"


def test_format_history_list_shows_each_version(work_file) -> None:
    save_snapshot(work_file, "abc")
    save_snapshot(work_file, "abcdef")

    listing = format_history_list(work_file)

    assert listing.startswith(f"History for {work_file}:")
    assert "v1:" in listing
    assert "v2:" in listing
    assert "size: 3 bytes" in listing
    assert "size: 6 bytes" in listing
    checksum = get_latest_snapshot(work_file).checksum[:8]
    assert checksum in listing


# --------------------------------------------------------------------------- #
# Clearing
# --------------------------------------------------------------------------- #


def test_clear_history(work_file) -> None:
    save_snapshot(work_file, "x")
    assert clear_history(work_file) is True
    assert get_history(work_file) is None
    # Clearing something with no history is still a success.
    assert clear_history(work_file) is True


def test_clear_history_reports_removal_failures(work_file, monkeypatch) -> None:
    save_snapshot(work_file, "x")

    def boom(_path):
        raise OSError("busy")

    monkeypatch.setattr(fh.os, "remove", boom)
    assert clear_history(work_file) is False


def test_clear_all_histories(work_file, tmp_path) -> None:
    save_snapshot(work_file, "x")
    save_snapshot(str(tmp_path / "other.py"), "y")
    # A non-JSON file in the store must survive.
    (Path(get_history_dir()) / "notes.txt").write_text("keep me", encoding="utf-8")

    assert clear_all_histories() is True
    assert get_history(work_file) is None
    assert (Path(get_history_dir()) / "notes.txt").exists()


def test_clear_all_histories_without_a_directory(history_dir) -> None:
    assert not history_dir.exists()
    assert clear_all_histories() is True


def test_clear_all_histories_reports_failures(work_file, monkeypatch) -> None:
    save_snapshot(work_file, "x")

    def boom(_path):
        raise OSError("busy")

    monkeypatch.setattr(fh.os, "remove", boom)
    assert clear_all_histories() is False


def test_file_history_is_always_enabled() -> None:
    assert file_history_enabled() is True


# --------------------------------------------------------------------------- #
# track_file_edit
# --------------------------------------------------------------------------- #


def test_track_file_edit_snapshots_the_current_content(work_file) -> None:
    snapshot = track_file_edit(work_file, message_id="m7")
    assert snapshot is not None
    assert snapshot.content == "original content\n"
    assert snapshot.message_id == "m7"


def test_track_file_edit_of_a_new_file_records_an_empty_snapshot(tmp_path) -> None:
    path = str(tmp_path / "brand-new.py")
    snapshot = track_file_edit(path)
    assert snapshot is not None
    assert snapshot.content == ""
    # Restoring it recreates the file as empty, matching "did not exist".
    assert restore_snapshot(path) is True
    assert Path(path).read_text(encoding="utf-8") == ""


def test_track_file_edit_returns_none_when_the_read_fails(work_file, monkeypatch) -> None:
    real_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("app.py"):
            raise OSError("permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    assert track_file_edit(work_file) is None


# --------------------------------------------------------------------------- #
# The stored JSON shape
# --------------------------------------------------------------------------- #


def test_stored_history_is_human_readable_json(work_file) -> None:
    save_snapshot(work_file, "hello", message_id="m1")
    payload = json.loads(
        Path(get_history_path(os.path.abspath(work_file))).read_text(encoding="utf-8")
    )
    assert payload["path"] == os.path.abspath(work_file)
    assert payload["snapshots"][0]["content"] == "hello"
    assert payload["snapshots"][0]["message_id"] == "m1"


# --------------------------------------------------------------------------- #
# Repeated identical content is not re-snapshotted
# --------------------------------------------------------------------------- #


def test_identical_content_is_not_stored_twice(work_file) -> None:
    first = save_snapshot(work_file, "same")
    second = save_snapshot(work_file, "same")

    # Same entry comes back: no new version, no ring slot consumed.
    assert second.version == first.version == 1
    assert len(get_history(work_file).snapshots) == 1


def test_identical_content_after_a_different_one_is_still_stored(work_file) -> None:
    save_snapshot(work_file, "a")
    save_snapshot(work_file, "b")
    third = save_snapshot(work_file, "a")
    assert third.version == 3
    assert len(get_history(work_file).snapshots) == 3


def test_track_twice_without_an_edit_keeps_one_snapshot(work_file) -> None:
    track_file_edit(work_file)
    track_file_edit(work_file)
    assert len(get_history(work_file).snapshots) == 1


# --------------------------------------------------------------------------- #
# list_histories
# --------------------------------------------------------------------------- #


def test_list_histories_is_empty_without_a_store(history_dir) -> None:
    assert fh.list_histories() == []


def test_list_histories_returns_newest_activity_first(work_file, tmp_path) -> None:
    older = str(tmp_path / "older.py")
    Path(older).write_text("old", encoding="utf-8")
    track_file_edit(older)
    # Force a distinguishable timestamp ordering.
    history = get_history(older)
    history.snapshots[-1].timestamp = 1000.0
    Path(get_history_path(os.path.abspath(older))).write_text(
        json.dumps(history.to_dict()), encoding="utf-8"
    )

    track_file_edit(work_file)

    listed = fh.list_histories()
    assert [h.path for h in listed] == [os.path.abspath(work_file), os.path.abspath(older)]


def test_list_histories_skips_corrupt_and_empty_entries(work_file, history_dir) -> None:
    track_file_edit(work_file)
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "broken.json").write_text("{not json", encoding="utf-8")
    (history_dir / "empty.json").write_text(
        json.dumps({"path": "/x", "snapshots": []}), encoding="utf-8"
    )
    (history_dir / "ignored.txt").write_text("noise", encoding="utf-8")

    listed = fh.list_histories()
    assert len(listed) == 1
    assert listed[0].path == os.path.abspath(work_file)
