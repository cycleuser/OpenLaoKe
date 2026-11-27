"""Tests for externalizing oversized tool output (pointer + artifact on disk)."""

from __future__ import annotations

import hashlib
from pathlib import Path

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
