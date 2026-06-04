"""Permission and sandboxing system.

Two cooperating layers:

* :class:`Policy` is a *declarative* rule list. The same policy is used
  for chat, run, and sub-agent contexts. ``deny > ask > allow`` ordering.

* :class:`Gate` is the *enforcement* point. It consults the policy and,
  if the result is ``ask``, waits on an :class:`Approver`.

* :class:`Sandbox` is the *kernel-level* enforcement for file writers and
  bash. In-process symlink/``..``-safe resolution is the universal layer;
  on macOS, ``sandbox-exec`` (Seatbelt) is added for bash.
"""

from __future__ import annotations
