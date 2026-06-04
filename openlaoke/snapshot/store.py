"""Per-turn file snapshot and rewind store."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FileSnapshot:
    """First-touch content of a file in a turn.

    ``content is None`` means the file did not exist at the start of
    the turn. On rewind, ``None`` triggers deletion of the file.
    """

    path: str
    content: str | None
    existed: bool
    captured_at_turn: int
    captured_at: float = field(default_factory=time.time)


@dataclass
class TurnSnapshot:
    turn_index: int
    files: dict[str, FileSnapshot] = field(default_factory=dict)
    conversation: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class SnapshotStore:
    """Persists per-turn file snapshots for rewind and fork."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = base_dir or os.path.expanduser("~/.openlaoke/snapshots")
        os.makedirs(self.base_dir, exist_ok=True)
        self._cache: dict[tuple[str, int], TurnSnapshot] = {}

    def path_for(self, session_id: str) -> str:
        return os.path.join(self.base_dir, f"{session_id}.jsonl")

    def capture_file(self, session_id: str, turn_index: int, file_path: str) -> FileSnapshot:
        """Snapshot a file's pre-edit content. Deduplicated per turn."""
        key = (session_id, turn_index)
        if key not in self._cache:
            self._cache[key] = self.load_turn(session_id, turn_index)
        snap = self._cache[key]
        if file_path in snap.files:
            return snap.files[file_path]

        content: str | None = None
        existed = False
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            existed = True
        except FileNotFoundError:
            content = None
            existed = False
        except OSError as exc:
            logger.warning("Could not read %s for snapshot: %s", file_path, exc)
            content = None
            existed = False

        snap.files[file_path] = FileSnapshot(
            path=file_path,
            content=content,
            existed=existed,
            captured_at_turn=turn_index,
        )
        self.save_turn(session_id, snap)
        return snap.files[file_path]

    def load_turn(self, session_id: str, turn_index: int) -> TurnSnapshot:
        path = self.path_for(session_id)
        if not os.path.exists(path):
            return TurnSnapshot(turn_index=turn_index)
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("turn_index") == turn_index:
                    return self._deserialize_turn(data)
        return TurnSnapshot(turn_index=turn_index)

    def save_turn(self, session_id: str, turn: TurnSnapshot) -> None:
        path = self.path_for(session_id)
        existing = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("turn_index") != turn.turn_index:
                        existing.append(line.rstrip())
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=os.path.dirname(path) or ".",
            prefix=".snap_",
            suffix=".tmp",
        ) as tmp:
            for line in existing:
                tmp.write(line + "\n")
            tmp.write(self._serialize_turn(turn))
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)

    def all_turns(self, session_id: str) -> list[TurnSnapshot]:
        path = self.path_for(session_id)
        if not os.path.exists(path):
            return []
        turns: list[TurnSnapshot] = []
        seen: set[int] = set()
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                idx = data.get("turn_index", -1)
                if idx in seen:
                    continue
                seen.add(idx)
                turns.append(self._deserialize_turn(data))
        return sorted(turns, key=lambda t: t.turn_index)

    def rewind(self, session_id: str, target_turn: int) -> dict[str, str]:
        """Restore file content captured at ``target_turn`` for every
        file touched after that turn.

        Returns a dict ``{path: "restored" | "deleted"}`` for reporting.
        """
        all_turns = self.all_turns(session_id)
        if target_turn not in {t.turn_index for t in all_turns}:
            return {}
        touched_after: dict[str, FileSnapshot] = {}
        for turn in all_turns:
            if turn.turn_index >= target_turn:
                for path, snap in turn.files.items():
                    if path not in touched_after:
                        touched_after[path] = snap
        report: dict[str, str] = {}
        for path, snap in touched_after.items():
            if snap.content is None:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        report[path] = "deleted"
                    except OSError as exc:
                        logger.warning("Could not delete %s: %s", path, exc)
                        report[path] = f"error:{exc}"
            else:
                try:
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(snap.content)
                    report[path] = "restored"
                except OSError as exc:
                    logger.warning("Could not restore %s: %s", path, exc)
                    report[path] = f"error:{exc}"
        return report

    def fork_session(self, session_id: str, target_turn: int) -> tuple[str, str]:
        """Create a new session that contains the state up to ``target_turn``.

        Returns ``(new_session_id, sidecar_meta_path)``.
        """
        new_id = f"{session_id}_fork_{uuid.uuid4().hex[:6]}"
        meta_path = os.path.join(self.base_dir, f"{new_id}.meta")
        meta = {
            "id": new_id,
            "parent": session_id,
            "fork_turn": target_turn,
            "created_at": time.time(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return new_id, meta_path

    def _serialize_turn(self, turn: TurnSnapshot) -> str:
        return json.dumps(
            {
                "turn_index": turn.turn_index,
                "created_at": turn.created_at,
                "files": {
                    p: {
                        "path": snap.path,
                        "content": snap.content,
                        "existed": snap.existed,
                        "captured_at_turn": snap.captured_at_turn,
                        "captured_at": snap.captured_at,
                    }
                    for p, snap in turn.files.items()
                },
                "conversation": turn.conversation,
            }
        )

    def _deserialize_turn(self, data: dict[str, Any]) -> TurnSnapshot:
        files = {
            p: FileSnapshot(
                path=s["path"],
                content=s["content"],
                existed=s["existed"],
                captured_at_turn=s["captured_at_turn"],
                captured_at=s.get("captured_at", 0.0),
            )
            for p, s in data.get("files", {}).items()
        }
        return TurnSnapshot(
            turn_index=data["turn_index"],
            files=files,
            conversation=data.get("conversation", []),
            created_at=data.get("created_at", 0.0),
        )


def snapshot_dir() -> Path:
    return Path(os.path.expanduser("~/.openlaoke/snapshots"))
