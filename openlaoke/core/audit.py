"""Append-only audit trail: a hash chain with an out-of-band anchor.

Every high-risk action (a tool request, its result, a refused call) gets one
line in ``audit.jsonl``. Each line commits to the previous line's hash, so
editing or removing an entry breaks every hash after it.

A hash chain alone cannot detect **truncation**: any prefix of a valid chain is
itself a valid chain, so deleting the last three entries leaves a log that
verifies clean. ``audit.head`` therefore records the chain tip out of band
(``{"count": n, "head": <hash>}``), and the two are cross-checked.

The log is fail-closed: if the chain cannot be read or does not match its
anchor, ``append()`` refuses to extend it rather than forking the evidence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
ENTRY_PERMISSIONS = 0o600
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

if os.name == "nt":  # pragma: no cover - Windows only
    import msvcrt
else:
    import fcntl

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class AuditCorruptionError(RuntimeError):
    """The existing chain cannot be extended safely."""


@dataclass(frozen=True)
class AuditEntry:
    index: int
    timestamp: int
    action: str
    data: dict[str, Any]
    prev_hash: str
    hash: str

    @property
    def summary(self) -> str:
        args = self.data.get("args")
        arguments = args if isinstance(args, dict) else {}
        tool = str(self.data.get("tool") or arguments.get("tool") or "")
        detail = ""
        for key in ("command", "file_path", "path", "pattern", "query"):
            value = arguments.get(key) or self.data.get(key)
            if isinstance(value, str) and value:
                detail = value[:80]
                break
        verdict = "error" if self.data.get("error") else ""
        return " ".join(
            part for part in (f"#{self.index}", self.action, tool, detail, verdict) if part
        )


def default_audit_dir() -> str:
    return os.path.expanduser(os.path.join("~", ".openlaoke", "audit"))


def _process_lock(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


class AuditLog:
    """One hash chain under ``directory``, safe for threads and processes."""

    def __init__(self, directory: str | None = None) -> None:
        self.directory = Path(directory or default_audit_dir())
        self.path = self.directory / "audit.jsonl"
        self.head_path = self.directory / "audit.head"
        self.lock_path = self.directory / "audit.lock"
        self._lock = _process_lock(str(self.lock_path.resolve()))
        # (inode, size, mtime_ns, count, tip) from the last successful append.
        # Revalidating a 100k-entry chain on every tool call would be wasteful,
        # so the tip is reused while the file is provably untouched; anything
        # else falls back to a full pass, which also checks the anchor.
        self._tip_cache: tuple[int, int, int, int, str] | None = None

    # ── public API ───────────────────────────────────────────────────────

    def append(self, action: str, data: dict[str, Any] | None = None) -> AuditEntry:
        """Validate the current chain and add one entry to it."""
        payload = dict(data or {})
        with self._exclusive_lock():
            count, prev_hash = self._tip_with_count_locked()
            entry = AuditEntry(
                index=count + 1,
                timestamp=int(time.time() * 1000),
                action=action,
                data=payload,
                prev_hash=prev_hash,
                hash="",
            )
            entry = replace(
                entry,
                hash=_digest(entry.index, entry.timestamp, entry.action, entry.data, prev_hash),
            )
            self._append_line_locked(entry)
            self._write_head_locked(entry.index, entry.hash)
            self._tip_cache = (*self._stat_tuple_locked(), entry.index, entry.hash)
            return entry

    def verify(self) -> bool:
        try:
            with self._exclusive_lock():
                self._tip_locked(self._read_locked())
            return True
        except (AuditCorruptionError, OSError, ValueError, TypeError):
            return False

    def read(self) -> list[AuditEntry]:
        with self._exclusive_lock():
            return self._read_locked()

    def head(self) -> tuple[int, str] | None:
        with self._exclusive_lock():
            return self._read_head_locked()

    def tail(self, limit: int = 10) -> list[AuditEntry]:
        rows = self.read()
        return rows[-max(1, limit) :]

    def status_text(self, limit: int = 10) -> str:
        try:
            entries = self.read()
        except (AuditCorruptionError, OSError, ValueError) as exc:
            return f"Audit log is unreadable: {exc}"
        if not entries:
            return f"Audit log is empty ({self.path})."
        verdict = "verified" if self.verify() else "CORRUPT"
        lines = [
            f"Audit chain: {len(entries)} entries, {verdict}",
            f"  log:  {self.path}",
        ]
        head = self.head()
        if head is not None:
            lines.append(f"  anchor: count={head[0]} head={head[1][:16]}…")
        for entry in entries[-max(1, limit) :]:
            lines.append(f"  {entry.summary}")
        return "\n".join(lines)

    # ── chain internals ──────────────────────────────────────────────────

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._lock:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | _NOFOLLOW, 0o600)
            try:
                _require_regular(fd, self.lock_path)
                _lock_fd(fd)
                try:
                    yield
                finally:
                    _unlock_fd(fd)
            finally:
                os.close(fd)

    def _read_locked(self) -> list[AuditEntry]:
        if not self.path.exists():
            return []
        text = self._read_text_locked(self.path).replace("\r\n", "\n").replace("\r", "\n")
        entries: list[AuditEntry] = []
        for number, line in enumerate(text.split("\n"), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuditCorruptionError(
                    f"{self.path.name}:{number}: invalid JSON record"
                ) from exc
            if not isinstance(payload, dict):
                raise AuditCorruptionError(f"{self.path.name}:{number}: record is not an object")
            try:
                entries.append(AuditEntry(**payload))
            except TypeError as exc:
                raise AuditCorruptionError(
                    f"{self.path.name}:{number}: record has the wrong shape"
                ) from exc
        return entries

    def _stat_tuple_locked(self) -> tuple[int, int, int]:
        info = os.stat(self.path)
        return info.st_ino, info.st_size, info.st_mtime_ns

    def _tip_with_count_locked(self) -> tuple[int, str]:
        """Current (entry count, tip hash), validating unless the cache holds."""
        cached = self._tip_cache
        try:
            current_stat: tuple[int, int, int] | None = self._stat_tuple_locked()
        except FileNotFoundError:
            current_stat = None
        if cached is not None and current_stat is not None and current_stat == cached[:3]:
            return cached[3], cached[4]
        entries = self._read_locked()
        tip = self._tip_locked(entries)
        if current_stat is not None:
            self._tip_cache = (*current_stat, len(entries), tip)
        return len(entries), tip

    def _tip_locked(self, entries: list[AuditEntry]) -> str:
        """Validate the whole chain and the anchor, return the tip hash."""
        prev_hash = GENESIS_HASH
        for expected, entry in enumerate(entries, start=1):
            if entry.index != expected or entry.prev_hash != prev_hash:
                raise AuditCorruptionError(f"audit chain linkage is broken at entry {expected}")
            digest = _digest(
                entry.index, entry.timestamp, entry.action, entry.data, entry.prev_hash
            )
            if digest != entry.hash:
                raise AuditCorruptionError(f"audit entry hash is wrong at entry {expected}")
            prev_hash = entry.hash
        anchor = self._read_head_locked()
        if anchor is None:
            # A log written before anchoring existed is readable; the next
            # append creates the anchor.
            return prev_hash
        count, head = anchor
        if count != len(entries) or head != prev_hash:
            raise AuditCorruptionError(
                "audit head anchor does not match the chain tip (truncated or rewritten)"
            )
        return prev_hash

    def _read_head_locked(self) -> tuple[int, str] | None:
        if not self.head_path.exists():
            return None
        try:
            payload = json.loads(self._read_text_locked(self.head_path))
        except json.JSONDecodeError as exc:
            raise AuditCorruptionError("audit head anchor is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise AuditCorruptionError("audit head anchor is not an object")
        count = payload.get("count")
        head = payload.get("head")
        if type(count) is not int or count < 0:
            raise AuditCorruptionError("audit head count is invalid")
        if (
            not isinstance(head, str)
            or len(head) != len(GENESIS_HASH)
            or any(character not in "0123456789abcdef" for character in head)
        ):
            raise AuditCorruptionError("audit head hash is invalid")
        return count, head

    def _append_line_locked(self, entry: AuditEntry) -> None:
        line = json.dumps(
            {
                "index": entry.index,
                "timestamp": entry.timestamp,
                "action": entry.action,
                "data": entry.data,
                "prev_hash": entry.prev_hash,
                "hash": entry.hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        fd = _open_regular(
            self.path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY | _NOFOLLOW,
            ENTRY_PERMISSIONS,
        )
        try:
            _require_regular(fd, self.path)
            _write_all(fd, (line + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def _write_head_locked(self, count: int, head: str) -> None:
        payload = json.dumps({"count": count, "head": head}, sort_keys=True) + "\n"
        temporary = self.head_path.with_name(
            f".{self.head_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        fd = _open_regular(
            temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _NOFOLLOW, ENTRY_PERMISSIONS
        )
        try:
            _require_regular(fd, temporary)
            _write_all(fd, payload.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.replace(temporary, self.head_path)
            _fsync_directory(self.directory)
        finally:
            with suppress(FileNotFoundError):
                temporary.unlink()

    def _read_text_locked(self, path: Path) -> str:
        fd = _open_regular(path, os.O_RDONLY | _NOFOLLOW)
        try:
            _require_regular(fd, path)
            chunks: list[bytes] = []
            while chunk := os.read(fd, 64 * 1024):
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8")
        finally:
            os.close(fd)


def _digest(
    index: int,
    timestamp: int,
    action: str,
    data: dict[str, Any],
    prev_hash: str,
) -> str:
    return hashlib.sha256(
        _canonical(
            {
                "index": index,
                "timestamp": timestamp,
                "action": action,
                "data": data,
                "prev_hash": prev_hash,
            }
        )
    ).hexdigest()


def _require_regular(fd: int, path: Path) -> None:
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        raise AuditCorruptionError(f"audit path is not a regular file: {path}")


def _open_regular(path: Path, flags: int, mode: int = 0o600) -> int:
    """Open without following symlinks, reporting refusals as corruption."""
    try:
        return os.open(path, flags, mode)
    except OSError as exc:
        raise AuditCorruptionError(f"cannot open {path}: {exc}") from exc


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("short write while persisting the audit log")
        view = view[written:]


def _lock_fd(fd: int) -> None:
    if os.name == "nt":  # pragma: no cover - Windows only
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
    else:
        fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock_fd(fd: int) -> None:
    if os.name == "nt":  # pragma: no cover - Windows only
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":  # pragma: no cover - not supported
        return
    with suppress(OSError):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


# ── per-session access ──────────────────────────────────────────────────


def audit_enabled() -> bool:
    return os.environ.get("OPENLAOKE_NO_AUDIT") != "1"


def get_audit(app_state: Any) -> AuditLog | None:
    """Return the audit log for a session, or ``None`` when disabled."""
    if not audit_enabled():
        return None
    log = getattr(app_state, "_audit_log", None)
    if log is None:
        directory = os.environ.get("OPENLAOKE_AUDIT_DIR") or default_audit_dir()
        log = AuditLog(directory)
        app_state._audit_log = log
    return log


def record(app_state: Any, action: str, **data: Any) -> None:
    """Append one entry, swallowing storage failures.

    An audit write must never take down the turn: a tool that ran correctly
    should not be reported as failed because the log directory is read-only.
    The failure is logged instead, which is what ``/audit`` shows.
    """
    log = get_audit(app_state)
    if log is None:
        return
    try:
        log.append(action, data)
    except (AuditCorruptionError, OSError) as exc:
        logger.warning("Could not append to the audit log: %s", exc)


REDACTED = "[redacted]"
SENSITIVE_ARG_HINTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
)
MAX_ARG_CHARS = 400


def summarize_args(data: dict[str, Any] | None) -> dict[str, Any]:
    """Keep a forensic trace of a tool call without copying file bodies in.

    Long values are truncated and credential-looking keys are replaced: the
    audit log is meant to answer "what ran here", not to become a second copy
    of every file the agent has read (or a place where a token leaks).
    """
    if not isinstance(data, dict):
        return {}
    summary: dict[str, Any] = {}
    for key, value in data.items():
        lowered = str(key).lower()
        if any(hint in lowered for hint in SENSITIVE_ARG_HINTS):
            summary[str(key)] = REDACTED
        elif isinstance(value, str):
            summary[str(key)] = (
                value
                if len(value) <= MAX_ARG_CHARS
                else f"{value[:MAX_ARG_CHARS]}…({len(value)} chars)"
            )
        elif isinstance(value, (int, float, bool)) or value is None:
            summary[str(key)] = value
        else:
            summary[str(key)] = f"<{type(value).__name__}>"
    return summary


def record_tool_request(
    app_state: Any, tool_name: str, tool_input: dict[str, Any] | None, call_id: str = ""
) -> None:
    record(
        app_state,
        "tool.request",
        tool=tool_name,
        call_id=call_id,
        args=summarize_args(tool_input),
    )


def record_tool_result(
    app_state: Any,
    tool_name: str,
    result: Any,
    call_id: str = "",
) -> None:
    content = getattr(result, "content", "")
    size = len(content.encode("utf-8")) if isinstance(content, str) else 0
    is_error = bool(getattr(result, "is_error", False))
    payload: dict[str, Any] = {
        "tool": tool_name,
        "call_id": call_id,
        "bytes": size,
        "is_error": is_error,
    }
    if is_error and isinstance(content, str):
        payload["error"] = content[:MAX_ARG_CHARS]
    record(app_state, "tool.result", **payload)
