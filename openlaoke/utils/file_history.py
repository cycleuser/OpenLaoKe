"""File history and checkpoint system for tracking file modifications."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

MAX_SNAPSHOTS = 100
HISTORY_DIR = "~/.openlaoke/file_history"


@dataclass
class FileSnapshot:
    """Snapshot of a file at a specific point in time."""

    path: str
    content: str
    timestamp: float
    checksum: str
    version: int = 1
    message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "timestamp": self.timestamp,
            "checksum": self.checksum,
            "version": self.version,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileSnapshot:
        return cls(
            path=data["path"],
            content=data["content"],
            timestamp=data["timestamp"],
            checksum=data["checksum"],
            version=data.get("version", 1),
            message_id=data.get("message_id"),
        )


@dataclass
class FileHistory:
    """History of snapshots for a single file."""

    path: str
    snapshots: list[FileSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "snapshots": [s.to_dict() for s in self.snapshots],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileHistory:
        return cls(
            path=data["path"],
            snapshots=[FileSnapshot.from_dict(s) for s in data.get("snapshots", [])],
        )


@dataclass
class FileHistoryState:
    """Global file history state tracking all files."""

    histories: dict[str, FileHistory] = field(default_factory=dict)
    tracked_files: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "histories": {k: v.to_dict() for k, v in self.histories.items()},
            "tracked_files": list(self.tracked_files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileHistoryState:
        return cls(
            histories={k: FileHistory.from_dict(v) for k, v in data.get("histories", {}).items()},
            tracked_files=set(data.get("tracked_files", [])),
        )


def get_history_dir() -> str:
    """Get the file history storage directory."""
    return os.path.expanduser(HISTORY_DIR)


def get_history_path(file_path: str) -> str:
    """Get the JSON path for storing a file's history."""
    history_dir = get_history_dir()
    file_hash = hashlib.sha256(file_path.encode()).hexdigest()[:16]
    return os.path.join(history_dir, f"{file_hash}.json")


def compute_checksum(content: str) -> str:
    """Compute SHA256 checksum for content."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def save_snapshot(
    file_path: str,
    content: str,
    message_id: str | None = None,
) -> FileSnapshot:
    """Save a snapshot of the file before modification."""
    abs_path = os.path.abspath(file_path)
    history_dir = get_history_dir()
    os.makedirs(history_dir, exist_ok=True)

    history_path = get_history_path(abs_path)

    history = FileHistory(path=abs_path)
    if os.path.exists(history_path):
        try:
            with open(history_path, encoding="utf-8") as f:
                data = json.load(f)
            history = FileHistory.from_dict(data)
        except Exception:
            pass

    version = len(history.snapshots) + 1
    timestamp = time.time()
    checksum = compute_checksum(content)

    snapshot = FileSnapshot(
        path=abs_path,
        content=content,
        timestamp=timestamp,
        checksum=checksum,
        version=version,
        message_id=message_id,
    )

    history.snapshots.append(snapshot)

    if len(history.snapshots) > MAX_SNAPSHOTS:
        history.snapshots = history.snapshots[-MAX_SNAPSHOTS:]

    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history.to_dict(), f, indent=2)
    except Exception:
        pass

    return snapshot


def get_history(file_path: str) -> FileHistory | None:
    """Get the history for a file."""
    abs_path = os.path.abspath(file_path)
    history_path = get_history_path(abs_path)

    if not os.path.exists(history_path):
        return None

    try:
        with open(history_path, encoding="utf-8") as f:
            data = json.load(f)
        return FileHistory.from_dict(data)
    except Exception:
        return None


def get_latest_snapshot(file_path: str) -> FileSnapshot | None:
    """Get the most recent snapshot for a file."""
    history = get_history(file_path)
    if not history or not history.snapshots:
        return None
    return history.snapshots[-1]


def get_snapshot_by_version(file_path: str, version: int) -> FileSnapshot | None:
    """Get a specific version snapshot for a file."""
    history = get_history(file_path)
    if not history:
        return None
    for snapshot in history.snapshots:
        if snapshot.version == version:
            return snapshot
    return None


def restore_snapshot(file_path: str, version: int | None = None) -> bool:
    """Restore a file to a specific version (or latest if version is None)."""
    abs_path = os.path.abspath(file_path)

    if version is None:
        snapshot = get_latest_snapshot(abs_path)
    else:
        snapshot = get_snapshot_by_version(abs_path, version)

    if not snapshot:
        return False

    try:
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(snapshot.content)
        return True
    except Exception:
        return False


def format_timestamp(timestamp: float) -> str:
    """Format timestamp for display."""
    import datetime

    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_history_list(file_path: str) -> str:
    """Format history list for display."""
    history = get_history(file_path)
    if not history or not history.snapshots:
        return f"No history found for {file_path}"

    lines = [f"History for {file_path}:", ""]
    for snapshot in history.snapshots:
        ts = format_timestamp(snapshot.timestamp)
        checksum = snapshot.checksum[:8]
        size = len(snapshot.content)
        lines.append(f"  v{snapshot.version}: {ts} (checksum: {checksum}, size: {size} bytes)")

    return "\n".join(lines)


def clear_history(file_path: str) -> bool:
    """Clear history for a file."""
    abs_path = os.path.abspath(file_path)
    history_path = get_history_path(abs_path)

    if os.path.exists(history_path):
        try:
            os.remove(history_path)
            return True
        except Exception:
            return False
    return True


def clear_all_histories() -> bool:
    """Clear all file histories."""
    history_dir = get_history_dir()
    if not os.path.exists(history_dir):
        return True

    try:
        for filename in os.listdir(history_dir):
            if filename.endswith(".json"):
                os.remove(os.path.join(history_dir, filename))
        return True
    except Exception:
        return False


def file_history_enabled() -> bool:
    """Check if file history is enabled."""
    return True


def track_file_edit(
    file_path: str,
    message_id: str | None = None,
) -> FileSnapshot | None:
    """Track a file before editing - save current state as snapshot."""
    abs_path = os.path.abspath(file_path)

    if not os.path.exists(abs_path):
        return save_snapshot(abs_path, "", message_id)

    try:
        with open(abs_path, encoding="utf-8") as f:
            content = f.read()
        return save_snapshot(abs_path, content, message_id)
    except Exception:
        return None
