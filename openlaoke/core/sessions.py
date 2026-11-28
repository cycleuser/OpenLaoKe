"""Session management and persistence."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

from openlaoke.core.state import AppState, create_app_state
from openlaoke.types.core_types import (
    AssistantMessage,
    AttachmentMessage,
    MessageRole,
    ProgressMessage,
    SystemMessage,
    TaskState,
    TaskStatus,
    TaskType,
    UserMessage,
    message_from_dict,
)

logger = logging.getLogger(__name__)

_SESSION_VERSION = 2


@dataclass
class SessionInfo:
    """Summary information about a saved session."""

    session_id: str
    path: str
    created_at: float
    message_count: int
    task_count: int
    model: str
    cwd: str
    # True when only the append-only journal survived: the snapshot is missing or
    # unreadable, and loading this session means replaying the journal.
    recovered: bool = False


def _message_from_dict(
    msg_data: dict,
) -> UserMessage | AssistantMessage | SystemMessage | ProgressMessage | AttachmentMessage | None:
    msg = message_from_dict(msg_data)
    if msg is not None:
        return msg
    return SystemMessage(
        role=MessageRole.SYSTEM,
        content=msg_data.get("content", ""),
        subtype=msg_data.get("subtype", "info"),
        tool_use_id=msg_data.get("tool_use_id", ""),
    )


class SessionManager:
    """Manages session persistence and recovery."""

    def __init__(self, session_dir: str | None = None) -> None:
        self.session_dir = session_dir or os.path.expanduser("~/.openlaoke/sessions")
        os.makedirs(self.session_dir, exist_ok=True)

    def save_session(self, app_state: AppState) -> str:
        path = os.path.join(self.session_dir, f"{app_state.session_id}.json")
        app_state.set_persist_path(path)
        app_state._persist()
        return path

    def load_session(self, session_id: str) -> AppState | None:
        path = os.path.join(self.session_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        return self._load_from_path(path)

    def load_latest(self) -> AppState | None:
        sessions = self.list_sessions()
        if not sessions:
            return None
        latest = max(sessions, key=lambda s: s.created_at)
        return self._load_from_path(latest.path)

    def list_sessions(self) -> list[SessionInfo]:
        sessions = []
        seen: set[str] = set()
        for filename in os.listdir(self.session_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.session_dir, filename)
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, dict) and "exported_at" in data:
                    # /export used to write its JSON into this directory. Such a
                    # file carries the same session_id as the snapshot it came
                    # from, so listing it showed the session twice and gave
                    # /resume a second, wrong candidate.
                    continue
                seen.add(filename[: -len(".json")])
                sessions.append(
                    SessionInfo(
                        session_id=data.get("session_id", filename.replace(".json", "")),
                        path=path,
                        created_at=data.get("created_at", os.path.getmtime(path)),
                        message_count=len(data.get("messages", [])),
                        task_count=len(data.get("tasks", {})),
                        model=data.get("session_config", {}).get("model", "unknown"),
                        cwd=data.get("cwd", ""),
                    )
                )
            except Exception:
                # An unreadable snapshot is still a session if its journal is
                # there; listing it is how you find out it can be recovered.
                logger.warning("Failed to load session from %s", path, exc_info=True)
                session_id = filename[: -len(".json")]
                recovered = self._journal_entry(session_id)
                if recovered is not None:
                    # Claim the id, so the journal scan below does not add the
                    # same session a second time.
                    seen.add(session_id)
                    sessions.append(recovered)
                continue
        sessions.extend(self._journal_only_sessions(seen))
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def _journal_entry(self, session_id: str) -> SessionInfo | None:
        """Describe a session that only exists as a journal, or ``None``."""
        from openlaoke.core.transcript import Transcript, transcript_path_for

        snapshot = os.path.join(self.session_dir, f"{session_id}.json")
        journal = transcript_path_for(snapshot)
        if not os.path.exists(journal):
            return None
        transcript = Transcript(journal)
        header, records = transcript.replay()
        if not records:
            return None
        return SessionInfo(
            session_id=header.get("session_id") or session_id,
            path=snapshot,
            created_at=header.get("at") or os.path.getmtime(journal),
            message_count=len(records),
            task_count=0,
            model=header.get("model") or "unknown",
            cwd=header.get("cwd") or "",
            recovered=True,
        )

    def _journal_only_sessions(self, seen: set[str]) -> list[SessionInfo]:
        found: list[SessionInfo] = []
        for filename in os.listdir(self.session_dir):
            if not filename.endswith(".jsonl"):
                continue
            session_id = filename[: -len(".jsonl")]
            if session_id in seen:
                continue
            entry = self._journal_entry(session_id)
            if entry is not None:
                found.append(entry)
        return found

    def delete_session(self, session_id: str) -> bool:
        path = os.path.join(self.session_dir, f"{session_id}.json")
        from openlaoke.core.transcript import transcript_path_for

        journal = transcript_path_for(path)
        removed = False
        # The journal is part of the session. Leaving it behind means the
        # conversation keeps living on disk after the user asked to delete it,
        # and /sessions would still list it.
        for candidate in (path, journal):
            if os.path.exists(candidate):
                os.remove(candidate)
                removed = True
        # Same argument for the externalized tool output: it is the body of that
        # session's own results. Audit chains are left alone on purpose: they are
        # the record of what ran, and evidence should outlive the working file.
        from openlaoke.core.tool_output_store import remove_session_artifacts

        if remove_session_artifacts(session_id) > 0:
            removed = True
        return removed

    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        cutoff = time.time() - (max_age_days * 86400)
        count = 0
        for session in self.list_sessions():
            if session.created_at < cutoff:
                self.delete_session(session.session_id)
                count += 1
        return count

    def _load_from_path(self, path: str) -> AppState | None:
        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # A truncated snapshot used to mean a lost conversation. The
            # append-only transcript beside it still holds every message, so
            # recover from that instead of returning nothing.
            recovered = self._recover_from_transcript(path)
            if recovered is not None:
                logger.warning("Recovered session from the transcript at %s", path)
            return recovered
        except OSError:
            return None

        try:
            session_config = data.get("session_config", {})
            model = session_config.get("model", data.get("model", "claude-sonnet-4-20250514"))

            app_state = create_app_state(
                cwd=data.get("cwd", os.getcwd()),
                model=model,
                persist_path=path,
            )
            app_state.session_id = (
                data.get("session_id") or os.path.splitext(os.path.basename(path))[0]
            )

            for msg_data in data.get("messages", []):
                msg = _message_from_dict(msg_data)
                if msg is not None:
                    app_state.messages.append(msg)

            for task_id, task_data in data.get("tasks", {}).items():
                try:
                    task_type = TaskType(task_data.get("type", "local_bash"))
                except ValueError:
                    task_type = TaskType.LOCAL_BASH
                try:
                    task_status = TaskStatus(task_data.get("status", "pending"))
                except ValueError:
                    task_status = TaskStatus.PENDING
                app_state.tasks[task_id] = TaskState(
                    id=task_id,
                    type=task_type,
                    status=task_status,
                    description=task_data.get("description", ""),
                    start_time=task_data.get("start_time", 0),
                    end_time=task_data.get("end_time"),
                    output_file=task_data.get("output_file", ""),
                )

            token_data = data.get("token_usage", {})
            if token_data:
                from openlaoke.types.core_types import TokenUsage

                app_state.token_usage = TokenUsage(
                    input_tokens=token_data.get("input_tokens", 0),
                    output_tokens=token_data.get("output_tokens", 0),
                    cache_read_tokens=token_data.get("cache_read_tokens", 0),
                    cache_creation_tokens=token_data.get("cache_creation_tokens", 0),
                )

            if data.get("guard_state"):
                app_state.guard_state = data["guard_state"]
            if data.get("compact_state"):
                app_state.compact_state = data["compact_state"]
            if data.get("todo"):
                app_state.todo_state = data["todo"]
            if isinstance(data.get("risk_events"), list):
                app_state.risk_events = data["risk_events"]
            if isinstance(data.get("edit_stats"), dict):
                app_state.edit_stats = data["edit_stats"]
            if isinstance(data.get("tool_call_counts"), dict):
                app_state.tool_call_counts = {
                    str(key): int(value) for key, value in data["tool_call_counts"].items()
                }

            cost_data = data.get("cost_info", {})
            if cost_data:
                from openlaoke.types.core_types import CostInfo

                app_state.cost_info = CostInfo(
                    input_cost=cost_data.get("input_cost", 0.0),
                    output_cost=cost_data.get("output_cost", 0.0),
                    cache_read_cost=cost_data.get("cache_read_cost", 0.0),
                    cache_creation_cost=cost_data.get("cache_creation_cost", 0.0),
                )

            # The fallbacks are the AppState defaults, not zero-ish values: a
            # snapshot written before a field existed must restore into the same
            # behaviour a new session has, or a resumed unattended run starts
            # with a 10-step budget and no auto-accept.
            from openlaoke.core.insomnia import (
                ARTIFACT_HOURS,
                COST_LIMIT_USD,
                MAX_ITERATIONS,
                RETRY_LIMIT,
            )

            app_state.insomnia_mode = data.get("insomnia_mode", False)
            app_state.insomnia_task_queue = data.get("insomnia_task_queue", [])
            app_state.insomnia_max_iterations = data.get("insomnia_max_iterations", MAX_ITERATIONS)
            app_state.insomnia_max_retries = data.get("insomnia_max_retries", RETRY_LIMIT)
            app_state.insomnia_max_cost = data.get("insomnia_max_cost", COST_LIMIT_USD)
            app_state.insomnia_artifact_hours = data.get("insomnia_artifact_hours", ARTIFACT_HOURS)
            app_state.insomnia_auto_accept = data.get("insomnia_auto_accept", True)
            app_state.insomnia_log_path = data.get("insomnia_log_path", None)

            return app_state

        except Exception:
            logger.warning("Failed to load session from %s", path, exc_info=True)
            return None

    def _recover_from_transcript(self, path: str) -> AppState | None:
        """Rebuild a session from its append-only journal.

        Only the messages come back, because that is all the journal records:
        costs, tasks and the todo list live in the snapshot. Half a session with
        its conversation beats no session at all, and the next save rewrites the
        snapshot from what was recovered.
        """
        from openlaoke.core.transcript import Transcript, transcript_path_for

        transcript = Transcript(transcript_path_for(path))
        header, records = transcript.replay()
        if not records:
            return None

        app_state = create_app_state(
            cwd=header.get("cwd") or os.getcwd(),
            model=header.get("model") or "claude-sonnet-4-20250514",
            persist_path=path,
        )
        app_state.session_id = (
            header.get("session_id") or os.path.splitext(os.path.basename(path))[0]
        )
        for record in records:
            message = _message_from_dict(record["message"])
            if message is not None:
                app_state.messages.append(message)
        return app_state
