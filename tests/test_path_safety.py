"""Tests for the filesystem containment helpers.

These are a security boundary: every file tool routes through them, and the
apply_patch escape bug is exactly what a missing case here looks like. Cover the
allow/deny edges for each variant (workspace / home / strict / read-system).
"""

from __future__ import annotations

import os

from openlaoke.utils.path_safety import (
    resolve_path,
    validate_path,
    validate_path_strict,
    validate_read_path,
)


def test_resolve_path_relative_and_absolute(tmp_path):
    cwd = str(tmp_path)
    assert resolve_path("a/b.txt", cwd) == os.path.join(cwd, "a", "b.txt")
    assert resolve_path("a/../b.txt", cwd) == os.path.join(cwd, "b.txt")
    assert resolve_path("/abs/x", cwd) == "/abs/x"


def test_validate_path_allows_inside_cwd(tmp_path):
    cwd = str(tmp_path)
    assert validate_path(resolve_path("a.txt", cwd), cwd) is None


def test_validate_path_allows_home(tmp_path):
    # A path under $HOME but outside cwd is allowed by the lenient variant.
    home_child = os.path.join(os.path.expanduser("~"), ".openlaoke", "x.json")
    assert validate_path(home_child, str(tmp_path)) is None


def test_validate_path_rejects_outside_home(tmp_path):
    # /etc is outside both cwd and $HOME.
    assert validate_path("/etc/hostname", str(tmp_path)) is not None


def test_validate_path_strict_rejects_parent_escape(tmp_path):
    cwd = str(tmp_path)
    escaped = resolve_path("../escape.txt", cwd)
    # The lenient variant may allow it (it can land under $HOME); strict must not.
    assert validate_path_strict(escaped, cwd) is not None


def test_validate_path_strict_allows_inside(tmp_path):
    cwd = str(tmp_path)
    assert validate_path_strict(resolve_path("ok.txt", cwd), cwd) is None


def test_validate_path_strict_rejects_absolute_outside(tmp_path):
    assert validate_path_strict("/tmp/definitely_outside_xyz", str(tmp_path)) is not None


def test_validate_read_path_allows_system_paths(tmp_path):
    cwd = str(tmp_path)
    for p in ("/etc/hostname", "/usr/bin/env", "/private/etc/hosts"):
        assert validate_read_path(p, cwd) is None, p


def test_validate_read_path_still_rejects_random(tmp_path):
    # A path outside home and outside the system-read prefixes stays rejected.
    assert validate_read_path("/root/secret", str(tmp_path)) is not None
