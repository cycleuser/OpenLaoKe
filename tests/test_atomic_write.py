"""The shared atomic writer, and the callers that depend on it."""

from __future__ import annotations

import json
import os

import pytest

from openlaoke.utils.atomic_write import write_json_atomic, write_text_atomic


def test_a_write_leaves_no_temporary_behind(tmp_path) -> None:
    target = tmp_path / "state.json"

    write_json_atomic(str(target), {"a": 1})

    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert [path.name for path in tmp_path.iterdir()] == ["state.json"]


def test_a_failed_swap_leaves_the_old_file_intact(tmp_path, monkeypatch) -> None:
    """The point of writing beside the target: the old bytes survive."""
    target = tmp_path / "state.json"
    target.write_text('{"name": "before"}', encoding="utf-8")

    def explode(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError):
        write_json_atomic(str(target), {"name": "after"})

    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "before"
    assert not list(tmp_path.glob("*.tmp")), "a failed write must not litter"


def test_an_unserialisable_payload_touches_nothing(tmp_path) -> None:
    target = tmp_path / "state.json"
    write_json_atomic(str(target), {"name": "before"})

    with pytest.raises(TypeError):
        write_json_atomic(str(target), {"bad": object()})

    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "before"


def test_the_directory_is_created(tmp_path) -> None:
    target = tmp_path / "deep" / "nested" / "state.json"

    write_text_atomic(str(target), "hello")

    assert target.read_text(encoding="utf-8") == "hello"


def test_session_metadata_is_written_atomically(tmp_path, monkeypatch) -> None:
    """A truncated ``.meta.json`` reads back as the default: the name is gone."""
    from openlaoke.commands import pi_commands

    path = tmp_path / "sessions" / "abc.meta.json"
    pi_commands._write_json(path, {"name": "before", "session_id": "abc"})

    def explode(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError):
        pi_commands._write_json(path, {"name": "after", "session_id": "abc"})

    assert pi_commands._read_json(path, {})["name"] == "before"
