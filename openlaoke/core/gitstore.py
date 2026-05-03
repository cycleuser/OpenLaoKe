"""GitStore — Git-backed workspace file versioning with commit-rollback.

Inspired by nanobot's dulwich-based GitStore. Uses system git CLI for
commit/snapshot/revert of workspace files. Every tool operation that
modifies files is protected by pre-commit snapshots.

Key features:
- auto_commit(): snapshot all tracked changes
- revert(): restore files from any commit's tree
- diff(): inspect changes between commits
- pre_commit(): atomic snapshot before destructive ops
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    sha: str = ""
    short_sha: str = ""
    message: str = ""
    author: str = ""
    timestamp: float = 0.0


class GitStore:
    def __init__(self, workspace: str | Path) -> None:
        self._workspace = Path(workspace).resolve()
        self._initialized = False

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def initialized(self) -> bool:
        if not self._initialized:
            self._initialized = (self._workspace / ".git").exists()
        return self._initialized

    def init(self) -> bool:
        if self.initialized:
            return True
        try:
            subprocess.run(
                ["git", "init", "-q", "--initial-branch=main"],
                cwd=str(self._workspace),
                check=True,
                capture_output=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "config", "user.name", "OpenLaoKe"],
                cwd=str(self._workspace),
                check=True,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "config", "user.email", "openlaoke@local"],
                cwd=str(self._workspace),
                check=True,
                capture_output=True,
                timeout=10,
            )
            self._initialized = True
            return True
        except subprocess.CalledProcessError as e:
            logger.warning("Git init failed: %s", e)
            return False

    def has_changes(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def auto_commit(self, message: str = "") -> CommitInfo | None:
        if not self.init():
            return None
        if not self.has_changes():
            return None

        msg = message or f"checkpoint {time.strftime('%H:%M:%S')}"
        try:
            subprocess.run(
                ["git", "add", "-A", "."],
                cwd=str(self._workspace),
                check=True,
                capture_output=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "commit", "-q", "-m", msg],
                cwd=str(self._workspace),
                check=True,
                capture_output=True,
                timeout=30,
            )

            sha = self._get_head_sha()
            if sha:
                return CommitInfo(
                    sha=sha,
                    short_sha=sha[:12],
                    message=msg,
                    timestamp=time.time(),
                )
            return None
        except subprocess.CalledProcessError:
            return None

    def revert(self, commit_sha: str) -> CommitInfo | None:
        if not self.init():
            return None

        try:
            parent_sha = self._get_parent(commit_sha)
            if not parent_sha:
                return None

            all_files = subprocess.run(
                ["git", "diff", "--name-only", parent_sha, commit_sha],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            files = [f for f in all_files.stdout.strip().split("\n") if f]

            if files:
                subprocess.run(
                    ["git", "checkout", parent_sha, "--"] + files,
                    cwd=str(self._workspace),
                    check=True,
                    capture_output=True,
                    timeout=60,
                )

            return self.auto_commit(f"revert: undo {commit_sha[:12]}")
        except subprocess.CalledProcessError as e:
            logger.warning("Revert failed: %s", e)
            return None

    def diff(
        self,
        commit_a: str | None = None,
        commit_b: str | None = None,
        path: str | None = None,
    ) -> str:
        if not self.init():
            return ""
        try:
            cmd = ["git", "diff"]
            if commit_a:
                cmd.append(commit_a)
            if commit_b:
                cmd.append(commit_b)
            if path:
                cmd += ["--", path]

            result = subprocess.run(
                cmd,
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout[:10000]
        except Exception:
            return ""

    def log(self, max_count: int = 20) -> list[CommitInfo]:
        if not self.init():
            return []
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    "--oneline",
                    f"-n{max_count}",
                    "--format=%H|%s|%at",
                ],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=30,
            )
            commits: list[CommitInfo] = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 2)
                if len(parts) >= 3:
                    commits.append(
                        CommitInfo(
                            sha=parts[0],
                            short_sha=parts[0][:12],
                            message=parts[1],
                            timestamp=float(parts[2]),
                        )
                    )
            return commits
        except Exception:
            return []

    def pre_commit(self, label: str = "") -> CommitInfo | None:
        return self.auto_commit(f"pre: {label}" if label else "pre-operation snapshot")

    def post_commit(self, label: str = "") -> CommitInfo | None:
        return self.auto_commit(f"post: {label}" if label else "post-operation snapshot")

    def _get_head_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _get_parent(self, sha: str) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", f"{sha}~1"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            return result.stdout.strip()
        except Exception:
            return ""
