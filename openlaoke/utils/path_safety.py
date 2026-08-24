"""Shared path resolution and validation for file-operating tools.

All tools that touch the filesystem should use these helpers to ensure
consistent workspace-containment checks. Previously each tool copy-pasted
its own version of this logic, leading to inconsistencies (e.g. Glob/Grep
skipped validation entirely).
"""

from __future__ import annotations

import os


def resolve_path(path: str, cwd: str) -> str:
    """Resolve a path relative to cwd, normalising it."""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(cwd, path))


def validate_path(resolved: str, cwd: str) -> str | None:
    """Return an error message if *resolved* is outside the workspace or
    user home directory, else ``None``.

    Allows paths under the current working directory or the user's home
    directory. This matches Claude Code / opencode containment semantics.
    """
    real_resolved = os.path.realpath(resolved)
    real_cwd = os.path.realpath(cwd)
    home = os.path.realpath(os.path.expanduser("~"))

    if _contains(real_cwd, real_resolved) or _contains(home, real_resolved):
        return None
    if _is_user_home_path(resolved):
        return None
    return f"Path '{resolved}' is outside workspace and home directory"


def _contains(parent: str, child: str) -> bool:
    """Check if *child* path is inside *parent*."""
    try:
        rel = os.path.relpath(child, parent)
        return not rel.startswith("..")
    except ValueError:
        return False


def _is_user_home_path(path: str) -> bool:
    """Check if path is under user home directory, allowing truncated usernames."""
    home = os.path.realpath(os.path.expanduser("~"))
    home_parent = os.path.dirname(home)
    if path.startswith(home_parent + "/"):
        parts = path[len(home_parent) + 1 :].split("/", 1)
        if parts and os.path.basename(home).startswith(parts[0]):
            return True
    return False
