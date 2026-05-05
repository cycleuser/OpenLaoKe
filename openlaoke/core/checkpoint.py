"""Checkpoint system for auto-snapshot and restore on failure.

Adapted from kwcode's checkpoint.py - creates file snapshots before
execution and can restore them if the task fails.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class FileSnapshot:
    """Snapshot of a single file."""

    path: str
    content: str | None = None
    exists: bool = True
    modified_time: float = 0.0


@dataclass
class Checkpoint:
    """A checkpoint containing file snapshots."""

    id: str
    timestamp: float
    cwd: str
    files: dict[str, FileSnapshot] = field(default_factory=dict)
    git_stash_ref: str | None = None


@dataclass
class CheckpointResult:
    """Result of a checkpoint operation."""

    success: bool
    checkpoint_id: str = ""
    files_snapshotted: int = 0
    files_restored: int = 0
    error: str = ""


CHECKPOINT_DIR = Path(tempfile.gettempdir()) / "openlaoke" / "checkpoints"


def _get_changed_files(cwd: str, extensions: Sequence[str] | None = None) -> list[str]:
    """Get list of files that may be affected by the task."""
    extensions = extensions or (
        ".py",
        ".js",
        ".ts",
        ".go",
        ".rs",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".css",
        ".html",
    )

    changed: list[str] = []
    cwd_path = Path(cwd)

    for ext in extensions:
        for f in cwd_path.rglob(f"*{ext}"):
            if _should_include(f):
                changed.append(str(f))

    return changed[:500]


def _should_include(path: Path) -> bool:
    """Check if file should be included in checkpoint."""
    skip_dirs = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
    }
    for part in path.parts:
        if part in skip_dirs:
            return False
    if path.name.startswith("."):
        return False
    return path.is_file() and path.stat().st_size < 10 * 1024 * 1024


def create_checkpoint(
    cwd: str,
    files: Sequence[str] | None = None,
    extensions: Sequence[str] | None = None,
) -> CheckpointResult:
    """Create a checkpoint snapshot of current file state."""
    checkpoint_id = f"ckpt_{int(time.time() * 1000)}"
    checkpoint_dir = CHECKPOINT_DIR / checkpoint_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if files is None:
        files = _get_changed_files(cwd, extensions)

    snapshot: dict[str, FileSnapshot] = {}

    for file_path in files:
        try:
            path = Path(file_path)
            if not path.exists():
                snapshot[file_path] = FileSnapshot(path=file_path, exists=False)
                continue

            content = path.read_text(encoding="utf-8", errors="replace")
            rel_path = str(Path(file_path).relative_to(cwd))

            snap_dir = checkpoint_dir / Path(rel_path).parent
            snap_dir.mkdir(parents=True, exist_ok=True)
            (checkpoint_dir / rel_path).write_text(content, encoding="utf-8")

            snapshot[file_path] = FileSnapshot(
                path=file_path,
                content=content[:10000],
                exists=True,
                modified_time=path.stat().st_mtime,
            )
        except (OSError, ValueError):
            continue

    meta_path = checkpoint_dir / ".meta"
    meta_path.write_text(
        f"id={checkpoint_id}\ntimestamp={time.time()}\ncwd={cwd}\nfiles={len(snapshot)}\n",
        encoding="utf-8",
    )

    return CheckpointResult(
        success=True,
        checkpoint_id=checkpoint_id,
        files_snapshotted=len(snapshot),
    )


def restore_checkpoint(checkpoint_id: str, cwd: str) -> CheckpointResult:
    """Restore files from a checkpoint."""
    checkpoint_dir = CHECKPOINT_DIR / checkpoint_id
    if not checkpoint_dir.exists():
        return CheckpointResult(
            success=False,
            error=f"Checkpoint {checkpoint_id} not found",
        )

    meta_path = checkpoint_dir / ".meta"
    if not meta_path.exists():
        return CheckpointResult(
            success=False,
            error="Checkpoint metadata missing",
        )

    restored = 0
    for snapshot_file in checkpoint_dir.rglob("*"):
        if snapshot_file.name == ".meta":
            continue
        if not snapshot_file.is_file():
            continue

        rel_path = snapshot_file.relative_to(checkpoint_dir)
        target_path = Path(cwd) / rel_path

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = snapshot_file.read_text(encoding="utf-8")
            target_path.write_text(content, encoding="utf-8")
            restored += 1
        except (OSError, ValueError):
            continue

    return CheckpointResult(
        success=True,
        checkpoint_id=checkpoint_id,
        files_restored=restored,
    )


def list_checkpoints(cwd: str | None = None) -> list[dict[str, str]]:
    """List available checkpoints."""
    if not CHECKPOINT_DIR.exists():
        return []

    checkpoints = []
    for ckpt_dir in sorted(CHECKPOINT_DIR.iterdir(), reverse=True):
        if not ckpt_dir.is_dir():
            continue
        meta_path = ckpt_dir / ".meta"
        if not meta_path.exists():
            continue

        meta = {}
        for line in meta_path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                meta[key.strip()] = value.strip()

        if cwd and meta.get("cwd") != cwd:
            continue

        checkpoints.append(
            {
                "id": ckpt_dir.name,
                "timestamp": meta.get("timestamp", "unknown"),
                "cwd": meta.get("cwd", "unknown"),
                "files": meta.get("files", "0"),
            }
        )

    return checkpoints


def cleanup_old_checkpoints(keep: int = 10, max_age_hours: float = 24.0) -> int:
    """Remove old checkpoints."""
    if not CHECKPOINT_DIR.exists():
        return 0

    checkpoints = sorted(CHECKPOINT_DIR.iterdir(), key=lambda d: d.name, reverse=True)
    removed = 0
    cutoff = time.time() - (max_age_hours * 3600)

    for i, ckpt_dir in enumerate(checkpoints):
        if i < keep:
            continue
        meta_path = ckpt_dir / ".meta"
        if meta_path.exists():
            content = meta_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("timestamp="):
                    try:
                        ts = float(line.split("=", 1)[1])
                        if ts < cutoff:
                            shutil.rmtree(ckpt_dir, ignore_errors=True)
                            removed += 1
                    except ValueError:
                        pass
        else:
            shutil.rmtree(ckpt_dir, ignore_errors=True)
            removed += 1

    return removed
