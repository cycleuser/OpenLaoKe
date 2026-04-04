"""Session management and persistence."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from openlaoke.core.state import AppState, create_app_state
from openlaoke.types.core_types import MessageRole, TaskStatus, TaskType, UserMessage


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
        for filename in os.listdir(self.session_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.session_dir, filename)
            try:
                with open(path) as f:
                    data = json.load(f)
                sessions.append(
                    SessionInfo(
                        session_id=data.get("session_id", filename.replace(".json", "")),
                        path=path,
                        created_at=os.path.getmtime(path),
                        message_count=len(data.get("messages", [])),
                        task_count=len(data.get("tasks", {})),
                        model=data.get("model", "unknown"),
                        cwd=data.get("cwd", ""),
                    )
                )
            except Exception:
                continue
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        path = os.path.join(self.session_dir, f"{session_id}.json")
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

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

            app_state = create_app_state(
                cwd=data.get("cwd", os.getcwd()),
                persist_path=path,
            )
            app_state.session_id = data.get("session_id", "")

            for msg_data in data.get("messages", []):
                role = msg_data.get("role", "user")
                content = msg_data.get("content", "")
                if role == "user":
                    app_state.messages.append(
                        UserMessage(
                            role=MessageRole.USER,
                            content=content,
                        )
                    )

            for task_id, task_data in data.get("tasks", {}).items():
                from openlaoke.types.core_types import TaskState

                app_state.tasks[task_id] = TaskState(
                    id=task_id,
                    type=TaskType(task_data.get("type", "local_bash")),
                    status=TaskStatus(task_data.get("status", "pending")),
                    description=task_data.get("description", ""),
                    start_time=task_data.get("start_time", 0),
                    end_time=task_data.get("end_time"),
                    output_file=task_data.get("output_file", ""),
                )

            return app_state

        except Exception:
            return None
