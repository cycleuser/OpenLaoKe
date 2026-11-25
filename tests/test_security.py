"""Tests for security helpers: credential redaction, ANSI stripping, path sanitize."""

from __future__ import annotations

import os

import pytest

from openlaoke.utils.security import (
    redact_credentials,
    sanitize_path,
    sanitize_tool_args,
    strip_ansi,
)


def test_redact_bearer_and_headers():
    out = redact_credentials("Authorization: Bearer abcdef123\nok")
    assert "abcdef123" not in out
    assert "[redacted]" in out


def test_redact_common_keys():
    for text in ("api_key=SECRET123", "password: hunter2", "token=abc.def"):
        out = redact_credentials(text)
        assert "[redacted]" in out
        assert "SECRET123" not in out and "hunter2" not in out


def test_redact_known_token_shapes():
    assert "sk-" not in redact_credentials("sk-" + "a" * 30)
    assert "[redacted-token]" in redact_credentials("ghp_" + "b" * 30)
    assert "[redacted-key]" in redact_credentials("AIza" + "c" * 30)
    assert "[redacted-slack]" in redact_credentials("xoxb-" + "d" * 20)


def test_strip_ansi():
    assert strip_ansi("\x1b[31mred\x1b[0m") == "red"
    assert strip_ansi("plain") == "plain"


def test_sanitize_tool_args_strips_strings_only():
    out = sanitize_tool_args({"cmd": "\x1b[1mls\x1b[0m", "n": 3})
    assert out["cmd"] == "ls"
    assert out["n"] == 3


def test_sanitize_path_inside_cwd(tmp_path):
    cwd = str(tmp_path)
    assert sanitize_path("a.txt", cwd) == os.path.realpath(os.path.join(cwd, "a.txt"))


def test_sanitize_path_allows_home(tmp_path):
    home_file = os.path.join(os.path.expanduser("~"), ".openlaoke", "cfg.json")
    assert sanitize_path(home_file, str(tmp_path)) == os.path.realpath(
        os.path.expanduser(home_file)
    )


def test_sanitize_path_rejects_outside(tmp_path):
    with pytest.raises(ValueError):
        sanitize_path("/etc/hostname", str(tmp_path))
