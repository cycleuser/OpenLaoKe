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
from openlaoke.types.core_types import message_from_dict

logger = logging.getLogger(__name__)


@dataclass
class RewindReport:
    files: dict[str, str]
    turns_dropped: int
    scope: str


def _deserialize_messages(records: list[dict[str, Any]]) -> list[Any]:
    msgs: list[Any] = []
    for rec in records:
        msg = message_from_dict(rec)
        if msg is not None:
            msgs.append(msg)
    return msgs


def _conversation_recorded(store: SnapshotStore, session_id: str) -> bool:
    return any(t.conversation for t in store.all_turns(session_id))


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
    messages: list[Any] | None = None,
) -> RewindReport:
    """Truncate the live conversation to the state before ``target_turn``.

    When ``messages`` (the live message list) is provided, it is
    replaced with the conversation recorded at the last turn strictly
    before ``target_turn``. If ``target_turn`` is at or before the
    earliest recorded turn the conversation is cleared (rewind to
    before the first recorded turn). When the store holds no recorded
    turns at all the live list is left untouched (conservative).
    """
    turns = store.all_turns(session_id)
    recorded = store.conversation_before(session_id, target_turn)
    if messages is not None:
        if recorded is not None:
            messages.clear()
            messages.extend(_deserialize_messages(recorded))
        elif turns:
            messages.clear()
    turns_dropped = sum(1 for t in turns if t.turn_index >= target_turn)
    return RewindReport(
        files={},
        turns_dropped=turns_dropped,
        scope="conversation",
    )


def rewind_both(
    store: SnapshotStore,
    session_id: str,
    target_turn: int,
    messages: list[Any] | None = None,
) -> RewindReport:
    code = rewind_code(store, session_id, target_turn)
    conv = rewind_conversation(store, session_id, target_turn, messages=messages)
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
        "conversation_rewind_available": _conversation_recorded(store, session_id),
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
        "conversation_rewind_available": _conversation_recorded(store, session_id),
    }
