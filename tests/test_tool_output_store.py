"""Tests for externalizing oversized tool output (pointer + artifact on disk)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from openlaoke.core.state import AppState
from openlaoke.core.tool_output_store import (
    ToolOutputStore,
    ToolPointer,
    externalize,
    get_store,
)


def _state(tmp_path, monkeypatch, session_id="sess-1") -> AppState:
    monkeypatch.setenv("OPENLAOKE_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    return AppState(session_id=session_id, cwd=str(tmp_path))


def test_content_within_the_cap_is_returned_untouched(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "s")
    state = AppState(session_id="s", cwd=str(tmp_path))

    assert externalize(state, "Bash", "short", max_bytes=100) == "short"
    assert not (tmp_path / "art").exists()
    assert store.root.name == "s"


def test_an_oversized_body_is_written_out_and_replaced_by_a_pointer(tmp_path, monkeypatch):
    state = _state(tmp_path, monkeypatch)
    body = "line one\n" + ("middle\n" * 400) + "line last\n"

    rendered = externalize(state, "Bash", body, max_bytes=1200)

    assert "externalized" in rendered
    assert len(rendered.encode()) <= 1200
    path = Path(rendered.split("full output: ", 1)[1].splitlines()[0])
    assert path.read_text() == body
    assert hashlib.sha256(body.encode()).hexdigest() in rendered
    assert "line one" in rendered
    assert "line last" in rendered


def test_the_counter_does_not_restart_and_overwrite_an_earlier_artifact(tmp_path):
    """A fresh process must not reuse 0001 and clobber evidence a pointer cites."""
    root = str(tmp_path / "art")
    first = ToolOutputStore(root, "s").store("Bash", "first body")
    second = ToolOutputStore(root, "s").store("Bash", "second body")

    assert first.path != second.path
    assert Path(first.path).read_text() == "first body"
    assert Path(second.path).read_text() == "second body"
    assert Path(second.path).name.startswith("0002-")


def test_the_same_body_twice_reuses_one_artifact(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "s")

    one = store.store("Grep", "identical")
    two = store.store("Grep", "identical")

    assert one.path == two.path
    assert len(list((store.root).iterdir())) == 1


def test_the_filename_carries_the_content_digest(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "s")
    body = "body" * 100
    pointer = store.store("Read", body)

    assert hashlib.sha256(body.encode()).hexdigest()[:12] in Path(pointer.path).name
    assert Path(pointer.path).name.endswith(".txt")
    assert Path(pointer.path).stat().st_mode & 0o777 == 0o600


def test_session_ids_cannot_escape_the_artifact_root(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "../../etc")

    assert ".." not in store.root.parts
    assert str(tmp_path) in str(store.root)


def test_head_and_tail_are_split_within_the_budget(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "s")
    body = "A" * 5000 + "B" * 5000

    pointer = store.store("Bash", body, head_bytes=100, tail_bytes=50)

    assert pointer.head == "A" * 100
    assert pointer.tail == "B" * 50
    assert pointer.total_bytes == len(body)
    assert pointer.omitted_bytes == len(body) - 150
    assert pointer.token_estimate == (len(body) + 3) // 4


def test_a_tiny_cap_falls_back_to_the_compact_pointer(tmp_path, monkeypatch):
    state = _state(tmp_path, monkeypatch)

    rendered = externalize(state, "Bash", "z" * 5000, max_bytes=120)

    assert rendered.startswith("[output 5000B externalized:")
    assert "sha256:" in rendered
    assert Path(rendered.split("externalized: ", 1)[1].split(" sha256")[0]).exists()


def test_an_unwritable_store_falls_back_to_truncation(tmp_path, monkeypatch):
    state = _state(tmp_path, monkeypatch)

    def refuse(*_args, **_kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(ToolOutputStore, "store", refuse)

    rendered = externalize(state, "Bash", "q" * 3000, max_bytes=400)

    assert "tool output compacted" in rendered
    # The header is not counted against the budget by the legacy helper, so
    # the fallback overshoots slightly; what matters is that it is bounded.
    assert len(rendered.encode()) < 600
    assert len(rendered.encode()) < len("q" * 3000)


def test_get_store_is_cached_on_the_state(tmp_path, monkeypatch):
    state = _state(tmp_path, monkeypatch)

    assert get_store(state) is get_store(state)
    assert get_store(state).root.name == "sess-1"


def test_a_pointer_renders_path_digest_and_both_ends():
    pointer = ToolPointer(
        path="/tmp/x.txt",
        digest="a" * 64,
        total_bytes=9000,
        head="head bytes",
        tail="tail bytes",
        omitted_bytes=8000,
    )

    text = pointer.render()

    assert "/tmp/x.txt" in text
    assert "a" * 64 in text
    assert "~2250 tokens" in text
    assert "head bytes" in text
    assert "tail bytes" in text


def test_the_default_artifact_root_lives_under_the_state_dir(monkeypatch):
    from openlaoke.core.tool_output_store import default_artifact_root

    monkeypatch.setenv("HOME", "/home/example")

    assert default_artifact_root() == "/home/example/.openlaoke/artifacts"


def test_a_leftover_file_with_the_same_name_is_not_overwritten(tmp_path, monkeypatch):
    store = ToolOutputStore(str(tmp_path / "art"), "s")
    store.root.mkdir(parents=True)
    body = "body two"
    digest = hashlib.sha256(body.encode()).hexdigest()[:12]
    # A different body already occupies the name this one would pick (a real
    # possibility if a write was interrupted, and the only way O_EXCL fires
    # without a hash collision).
    squatter = store.root / f"0001-bash-{digest}.txt"
    squatter.write_text("truncated")
    # Hold the counter at 1 so the write really meets the squatter.
    monkeypatch.setattr(store, "_next_index", lambda: 1)

    second = store.store("Bash", body)

    assert squatter.read_text() == "truncated"
    assert Path(second.path).read_text() == body
    assert Path(second.path).name.startswith("0002-")


def test_a_zero_length_write_is_an_error_not_a_silent_success(tmp_path, monkeypatch):
    import openlaoke.core.tool_output_store as store_module

    store = ToolOutputStore(str(tmp_path / "art"), "s")
    monkeypatch.setattr(store_module.os, "write", lambda _fd, _view: 0)

    with pytest.raises(OSError, match="short write"):
        store.store("Bash", "body")


def test_the_first_index_is_one_when_the_directory_is_new(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "s")

    assert store._next_index() == 1


def test_the_next_index_follows_whatever_is_on_disk(tmp_path):
    store = ToolOutputStore(str(tmp_path / "art"), "s")
    store.root.mkdir(parents=True)
    (store.root / "0007-whatever.txt").write_text("x")
    (store.root / "notes.txt").write_text("ignored")

    assert store._next_index() == 8


def test_a_racing_writer_with_the_same_body_reuses_the_file(tmp_path, monkeypatch):
    """Two processes storing the same body at once must end up at one file."""
    store = ToolOutputStore(str(tmp_path / "art"), "s")
    store.root.mkdir(parents=True)
    body = "contested body"
    digest = hashlib.sha256(body.encode()).hexdigest()[:12]
    winner = store.root / f"0001-bash-{digest}.txt"
    winner.write_text(body)
    # Preconditions of the race: the scan saw nothing and the counter pointed
    # at the name the other writer then took.
    monkeypatch.setattr(store, "_next_index", lambda: 1)
    monkeypatch.setattr(type(store.root), "glob", lambda *_args, **_kwargs: iter(()))

    pointer = store.store("Bash", body)

    assert pointer.path == str(winner)
    assert len(list(store.root.iterdir())) == 1
