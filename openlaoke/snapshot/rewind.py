"""High-level rewind and fork operations.

`Rewind code+conversation`, `Rewind code only`, `Rewind conversation only`,
`Fork from turn N`, `Branch current tip`, `Summarize from turn N`,
`Summarize up to turn N`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from openlaoke.snapshot.store import SnapshotStore

logger = logging.getLogger(__name__)


@dataclass
class RewindReport:
    files: dict[str, str]
    turns_dropped: int
    scope: str


def rewind_code(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
) -> RewindReport:
    files = store.rewind(session_id, target_turn)
    return RewindReport(
        files=files,
        turns_dropped=0,
        scope="code",
    )


def rewind_conversation(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
) -> RewindReport:
    return RewindReport(
        files={},
        turns_dropped=target_turn,
        scope="conversation",
    )


def rewind_both(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
) -> RewindReport:
    code = rewind_code(store, session_id, target_turn)
    conv = rewind_conversation(store, session_id, target_turn)
    return RewindReport(
        files=code.files,
        turns_dropped=conv.turns_dropped,
        scope="code+conversation",
    )


def fork_from(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
    label: str = "",
) -> dict[str, Any]:
    new_id, meta_path = store.fork_session(session_id, target_turn)
    return {
        "session_id": new_id,
        "meta_path": meta_path,
        "parent": session_id,
        "fork_turn": target_turn,
        "label": label,
    }


def branch_tip(
    store: SnapshotStore,
    session_id: str,
    label: str = "",
) -> dict[str, Any]:
    new_id, meta_path = store.fork_session(session_id, target_turn=-1)
    return {
        "session_id": new_id,
        "meta_path": meta_path,
        "parent": session_id,
        "fork_turn": -1,
        "label": label or "branch",
    }


def summarize_from(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
) -> dict[str, Any]:
    turns = store.all_turns(session_id)
    return {
        "scope": "from",
        "turn": target_turn,
        "compacted": sum(1 for t in turns if t.turn_index >= target_turn),
        "conversation_rewind_available": False,
    }


def summarize_up_to(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
) -> dict[str, Any]:
    turns = store.all_turns(session_id)
    return {
        "scope": "up_to",
        "turn": target_turn,
        "compacted": sum(1 for t in turns if t.turn_index <= target_turn),
        "conversation_rewind_available": False,
    }
