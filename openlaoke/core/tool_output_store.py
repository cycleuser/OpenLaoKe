"""Externalize oversized tool output instead of dropping its middle.

``truncate_tool_history`` keeps the first 70% and the last 30% of a long result
and throws the rest away. That is fine until the model needs line 3000 of a
test log: the bytes are gone, and the only remedy is to re-run the command,
which may not be reproducible.

This keeps the full body on disk and puts a *pointer* in history instead: the
path, the digest, the size, and the head and tail of the output. The model can
then ``Read`` the file (or ``Grep`` it) at any offset, so nothing is lost and
the context window still stays small.

Two things the naive version gets wrong and this one does not:

* the artifact counter must not restart at 001 in every process, or the next
  run silently overwrites the evidence an earlier pointer refers to;
* the filename must include a content digest, so a pointer can be checked
  against the file it claims to describe.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_SLUG = 24


def default_artifact_root() -> str:
    return os.path.expanduser(os.path.join("~", ".openlaoke", "artifacts"))


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = _SAFE_SEGMENT.sub("_", value.strip()).strip("._")
    return (cleaned[:_MAX_SLUG] or fallback)


@dataclass(frozen=True)
class ToolPointer:
    """What replaces an oversized result in conversation history."""

    path: str
    digest: str
    total_bytes: int
    head: str
    tail: str
    omitted_bytes: int

    @property
    def token_estimate(self) -> int:
        """Rough token count of the stored body (4 bytes per token)."""
        return (self.total_bytes + 3) // 4

    def render(self) -> str:
        lines = [
            f"[tool output externalized: {self.total_bytes} bytes, "
            f"~{self.token_estimate} tokens, {self.omitted_bytes} bytes not shown here]",
            f"full output: {self.path}",
            f"sha256: {self.digest}",
            "Read that path (with offset/limit) or Grep it to see any omitted part.",
        ]
        if self.head:
            lines.append("--- head ---")
            lines.append(self.head)
        if self.tail:
            lines.append("--- tail ---")
            lines.append(self.tail)
        return "\n".join(lines)

    def render_compact(self) -> str:
        """One-line form for caps too small to hold the full pointer.

        The pointer is the floor: below this size there is no way to name the
        stored body and still stay under the cap, so the cap wins only as far
        as it can. Callers with a tiny ``max_tool_history`` get a pointer that
        is a little over budget instead of an unrecoverable truncation.
        """
        return (
            f"[output {self.total_bytes}B externalized: {self.path} "
            f"sha256:{self.digest[:12]}]"
        )


class ToolOutputStore:
    """Writes oversized results under ``<root>/<session>/`` and returns pointers."""

    def __init__(self, root: str | None = None, session_id: str = "") -> None:
        self.root = Path(root or default_artifact_root()) / _safe_segment(
            session_id, "unscoped"
        )

    def store(
        self,
        tool_name: str,
        content: str,
        *,
        head_bytes: int = 3072,
        tail_bytes: int = 1024,
    ) -> ToolPointer:
        encoded = content.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        path = self._write(tool_name, encoded, digest)
        head, tail = _split(encoded, head_bytes, tail_bytes)
        return ToolPointer(
            path=str(path),
            digest=digest,
            total_bytes=len(encoded),
            head=head,
            tail=tail,
            omitted_bytes=max(0, len(encoded) - len(head.encode()) - len(tail.encode())),
        )

    def _write(self, tool_name: str, encoded: bytes, digest: str) -> Path:
        directory = self.root
        directory.mkdir(parents=True, exist_ok=True)
        slug = _safe_segment(tool_name.lower(), "tool")
        stem = f"{slug}-{digest[:12]}"
        # The digest in the name makes the common case idempotent: the same
        # body produced twice reuses one file. The counter only breaks ties
        # between different bodies, and O_EXCL guarantees no overwrite.
        for existing in directory.glob(f"*-{stem}.txt"):
            if existing.stat().st_size == len(encoded):
                return existing
        index = self._next_index()
        while True:
            path = directory / f"{index:04d}-{stem}.txt"
            try:
                fd = os.open(
                    path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
            except FileExistsError:
                if path.stat().st_size == len(encoded):
                    return path
                index += 1
                continue
            try:
                view = memoryview(encoded)
                while view:
                    written = os.write(fd, view)
                    if written == 0:
                        raise OSError("short write while storing tool output")
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            return path

    def _next_index(self) -> int:
        highest = 0
        try:
            names = os.listdir(self.root)
        except FileNotFoundError:
            return 1
        for name in names:
            prefix = name.split("-", 1)[0]
            if prefix.isdigit():
                highest = max(highest, int(prefix))
        return highest + 1


def _split(encoded: bytes, head_bytes: int, tail_bytes: int) -> tuple[str, str]:
    if head_bytes + tail_bytes >= len(encoded):
        return encoded.decode("utf-8", errors="replace"), ""
    head = encoded[:head_bytes].decode("utf-8", errors="replace")
    tail = encoded[-tail_bytes:].decode("utf-8", errors="replace")
    return head, tail


def get_store(app_state: Any) -> ToolOutputStore:
    store = getattr(app_state, "_tool_output_store", None)
    if store is None:
        root = os.environ.get("OPENLAOKE_ARTIFACT_DIR") or default_artifact_root()
        store = ToolOutputStore(root, getattr(app_state, "session_id", ""))
        app_state._tool_output_store = store
    return store


def externalize(
    app_state: Any,
    tool_name: str,
    content: str,
    *,
    max_bytes: int,
    head_bytes: int = 3072,
    tail_bytes: int = 1024,
) -> str:
    """Return ``content`` when it fits, else a pointer block that still fits.

    Falls back to plain truncation when the store cannot be written (read-only
    home, full disk): losing the tail of a log is bad, losing the turn is worse.
    """
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    budget = max(0, max_bytes - 512)
    if head_bytes + tail_bytes > budget:
        head_bytes = int(budget * 0.75)
        tail_bytes = budget - head_bytes
    try:
        pointer = get_store(app_state).store(
            tool_name, content, head_bytes=head_bytes, tail_bytes=tail_bytes
        )
    except OSError as exc:
        logger.warning("Could not externalize tool output: %s", exc)
        from openlaoke.core.tool import truncate_tool_history

        return truncate_tool_history(content, max_bytes)
    rendered = pointer.render()
    if len(rendered.encode("utf-8")) > max_bytes:
        rendered = pointer.render_compact()
    return rendered
