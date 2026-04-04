"""Git tool - Git operations."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class GitInput(BaseModel):
    action: str = Field(
        description="Git action: status, diff, log, add, commit, push, pull, branch, checkout, merge, rebase, stash, reset, fetch, remote"
    )
    args: str | None = Field(default=None, description="Additional arguments for the action")


class GitTool(Tool):
    """Execute Git operations."""

    name = "Git"
    description = (
        "Execute Git operations. Supports common commands: status, diff, log, add, commit, "
        "push, pull, branch, checkout, merge, rebase, stash, reset, fetch, remote. "
        "Use 'args' for additional arguments like commit messages or branch names."
    )
    input_schema = GitInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action", "")
        args = kwargs.get("args", "")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        action = action.lower().strip()

        valid_actions = {
            "status",
            "diff",
            "log",
            "add",
            "commit",
            "push",
            "pull",
            "branch",
            "checkout",
            "merge",
            "rebase",
            "stash",
            "reset",
            "fetch",
            "remote",
            "init",
            "clone",
            "tag",
            "show",
            "blame",
            "cherry-pick",
            "revert",
            "clean",
            "gc",
            "prune",
            "config",
        }

        if action not in valid_actions:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Unknown git action: {action}\n"
                f"Valid actions: {', '.join(sorted(valid_actions))}",
                is_error=True,
            )

        cwd = ctx.app_state.get_cwd()
        if not self._is_git_repo(cwd):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Not a git repository: {cwd}",
                is_error=True,
            )

        try:
            result = await self._run_git(cwd, action, args)
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=result,
                is_error=False,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Git error: {e}",
                is_error=True,
            )

    def _is_git_repo(self, path: str) -> bool:
        git_dir = os.path.join(path, ".git")
        if os.path.isdir(git_dir):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        return self._is_git_repo(parent)

    async def _run_git(self, cwd: str, action: str, args: str | None) -> str:
        cmd = ["git", action]
        if args:
            cmd.extend(args.split())

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            return f"Git exited with code {proc.returncode}\n{output}"

        return output if output.strip() else "(no output)"


def register(registry: ToolRegistry) -> None:
    registry.register(GitTool())
