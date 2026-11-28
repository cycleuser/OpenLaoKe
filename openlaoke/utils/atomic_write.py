"""Write a small file in one step, so a crash cannot leave half of it.

Every state file in this project is rewritten whole: session metadata, rooms,
bots, queues, file histories. Truncating one in place and then dying means the
next read sees a half-written document and falls back to its default, which
silently turns "one bad moment" into "all of it is gone". Writing beside the
target, forcing the bytes out, and renaming over it means a reader either sees
the old file or the new one, never a mixture.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from typing import Any


def write_text_atomic(path: str, text: str, *, fsync: bool = True) -> None:
    """Replace ``path`` with ``text`` atomically.

    The rename is what makes it atomic; the fsync is what makes it survive a
    power cut rather than just a process crash (a rename can otherwise be
    committed before the data it points at). It costs a few milliseconds on a
    small file, and these files are written once per turn, not per token.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(text)
            if fsync:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        # A leftover temp file would be read as garbage by nobody, but it would
        # pile up; the failure path is exactly when the disk is unhappy.
        if os.path.exists(temporary):
            with suppress(OSError):
                os.remove(temporary)


def write_json_atomic(
    path: str,
    payload: Any,
    *,
    indent: int = 2,
    fsync: bool = True,
    default: Any = None,
) -> None:
    """Serialise ``payload`` first, so a serialisation error touches nothing."""
    kwargs: dict[str, Any] = {"ensure_ascii": False, "indent": indent}
    if default is not None:
        kwargs["default"] = default
    text = json.dumps(payload, **kwargs)
    write_text_atomic(path, text, fsync=fsync)
