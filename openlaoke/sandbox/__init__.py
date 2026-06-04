"""Sandbox module.

Two enforcement layers:

* **Confinement** (always on): in-process symlink/``..``-safe path
  resolution. Any write outside the workspace + allowed list is refused
  before the file is touched.

* **macOS Seatbelt** (when available): wraps ``bash`` in a ``sandbox-exec``
  profile so even shell-executed file writes stay confined.
"""

from __future__ import annotations

from openlaoke.sandbox.confinement import (
    SeatbeltProfile,
    WorkspaceConfinement,
    is_macos,
    macos_sandbox_exec,
)

__all__ = [
    "SeatbeltProfile",
    "WorkspaceConfinement",
    "is_macos",
    "macos_sandbox_exec",
    "wrap_bash_for_sandbox",
]


def wrap_bash_for_sandbox(command: str, workspace_root: str) -> str:
    """Wrap a bash command in a sandbox if available.

    On macOS: wraps in ``sandbox-exec`` with a Seatbelt profile that
    allows reads everywhere but restricts writes to ``workspace_root``
    and standard temp/toolchain directories.

    On Linux: returns the command unchanged (bubblewrap support TBD).

    On Windows: returns the command unchanged.
    """
    import shutil

    if not shutil.which("sandbox-exec"):
        return command
    profile = SeatbeltProfile(
        workspace_root=workspace_root,
        allow_write=["/tmp", "/var/tmp", "/private/tmp"],
        network="restricted",
    )
    return f"sandbox-exec -p '{profile.render()}' bash -c {_shell_quote(command)}"


def _shell_quote(s: str) -> str:
    """Single-quote a shell string, handling embedded quotes."""
    return "'" + s.replace("'", "'\\''") + "'"
