"""In-process workspace sandbox.

Two enforcement layers:

* **Confinement** (always on): in-process symlink/``..``-safe path
  resolution. Any write outside the workspace + allowed list is refused
  before the file is touched.

* **macOS Seatbelt** (when available): wraps ``bash`` in a ``sandbox-exec``
  profile so even shell-executed file writes stay confined.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field


@dataclass
class WorkspaceConfinement:
    """Refuses writes outside the workspace and the allowed list.

    Resolves symlinks and ``..`` components *before* checking, so a
    malicious ``/workspace/../etc/passwd`` target is blocked.
    """

    workspace_root: str
    allow_write: list[str] = field(default_factory=list)
    network: str = "restricted"
    bash_mode: str = "enforce"

    def allowed_roots(self) -> list[str]:
        roots: list[str] = []
        ws = os.path.realpath(self.workspace_root)
        if ws:
            roots.append(ws)
        for entry in self.allow_write:
            abs_path = os.path.abspath(os.path.expanduser(entry))
            roots.append(os.path.realpath(abs_path))
        return [r for r in roots if r]

    def is_under_allowed(self, abs_path: str) -> bool:
        real = os.path.realpath(abs_path)
        return any(real == root or real.startswith(root + os.sep) for root in self.allowed_roots())

    def assert_write(self, target: str) -> None:
        """Raise :class:`PermissionError` if ``target`` is outside allowed roots."""
        abs_path = os.path.abspath(target)
        if not self.is_under_allowed(abs_path):
            raise PermissionError(
                f"Path '{target}' is outside the workspace "
                f"({self.workspace_root}) and not in allow_write"
            )

    def assert_read(self, target: str) -> None:
        abs_path = os.path.abspath(target)
        if not self.is_under_allowed(abs_path):
            raise PermissionError(f"Read of '{target}' is not allowed")


@dataclass
class SeatbeltProfile:
    """macOS sandbox-exec profile generator.

    On non-macOS platforms, this produces a profile that is silently
    ignored by the OS, but the tool layer still respects in-process
    confinement.
    """

    workspace_root: str
    allow_write: list[str] = field(default_factory=list)
    network: str = "restricted"

    def render(self) -> str:
        ws = self.workspace_root
        allow_writes = "\n".join(
            f'(allow file-write* (subpath "{p}"))' for p in [ws, *self.allow_write]
        )
        network_block = "(deny network*)" if self.network == "restricted" else "(allow network*)"
        return f"""(version 1)
(deny default)
(allow process-exec)
(allow file-read*)
{allow_writes}
{network_block}
"""


def macos_sandbox_exec(command: list[str], profile: SeatbeltProfile) -> list[str]:
    """Wrap ``command`` in ``sandbox-exec`` with the given profile.

    On non-macOS platforms, returns ``command`` unchanged. The in-process
    confinement layer must still be consulted by the tool.
    """
    if not shutil.which("sandbox-exec"):
        return command
    return ["sandbox-exec", "-p", profile.render(), *command]


def is_macos() -> bool:
    import platform

    return platform.system() == "Darwin"
