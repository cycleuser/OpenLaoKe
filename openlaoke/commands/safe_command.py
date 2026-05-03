"""/safe command — workspace checkpoint, undo, diff, and safety status.

Inspired by nanobot's /dream and /dream-restore commands.
Provides user-facing control over commit-rollback for workspace files.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from openlaoke.core.gitstore import GitStore


@dataclass
class SafeCommandResult:
    message: str = ""
    should_exit: bool = False
    should_clear: bool = False


class SafeCommand:
    name = "safe"
    description = "Workspace safety: checkpoint, undo, diff, and rollback"
    aliases = ["undo", "checkpoint", "rollback", "gitlog", "safe"]
    hidden = False

    async def execute(self, ctx: SafeCommandContext) -> SafeCommandResult:
        args = ctx.args.strip() if hasattr(ctx, "args") else ""
        cwd = ctx.app_state.get_cwd() if hasattr(ctx, "app_state") else "."
        git = GitStore(cwd)

        if not args or args == "status":
            return self._show_status(git)

        if args == "checkpoint" or args == "snapshot":
            return self._do_checkpoint(git, ctx)

        if args == "undo":
            return self._do_undo(git)

        if args == "log":
            return self._show_log(git)

        if args.startswith("diff"):
            return self._show_diff(git, args)

        if args.startswith("revert "):
            sha = args[7:].strip()
            return self._do_revert(git, sha)

        if args == "help":
            return SafeCommandResult(message=self._help_text())

        return SafeCommandResult(message=self._help_text())

    def _show_status(self, git: GitStore) -> SafeCommandResult:
        if not git.initialized:
            return SafeCommandResult(
                message="[dim]No git safety store initialized. Use /safe checkpoint to start.[/]"
            )

        has = git.has_changes()
        log = git.log(max_count=5)
        lines = [
            f"[bold]Git Safety Store[/] at {git.workspace}",
            f"Status: {'[yellow]uncommitted changes[/]' if has else '[green]clean[/]'}",
            f"Commits: {len(log)} total",
        ]
        if log:
            lines.append("\n[bold]Recent:[/]")
            for c in log[:5]:
                lines.append(f"  {c.short_sha} {c.message}")
        return SafeCommandResult(message="\n".join(lines))

    def _do_checkpoint(self, git: GitStore, ctx: SafeCommandContext) -> SafeCommandResult:
        if not git.init():
            return SafeCommandResult(message="[red]Git init failed.[/]")

        info = git.auto_commit("user checkpoint")
        if info:
            return SafeCommandResult(
                message=f"[green]Checkpoint created:[/] {info.short_sha}"
            )
        return SafeCommandResult(
            message="[dim]No changes to checkpoint.[/]"
        )

    def _do_undo(self, git: GitStore) -> SafeCommandResult:
        if not git.initialized:
            return SafeCommandResult(message="[red]No commits to undo.[/]")

        log = git.log(max_count=1)
        if not log:
            return SafeCommandResult(message="[dim]No commits to undo.[/]")

        last = log[0]
        result = git.revert(last.sha)
        if result:
            return SafeCommandResult(
                message=(
                    f"[green]Undone:[/] {last.short_sha} {last.message}\n"
                    f"[green]Revert commit:[/] {result.short_sha}"
                )
            )
        return SafeCommandResult(message="[red]Undo failed.[/]")

    def _show_log(self, git: GitStore) -> SafeCommandResult:
        if not git.initialized:
            return SafeCommandResult(message="[dim]No git log available.[/]")

        log = git.log(max_count=30)
        if not log:
            return SafeCommandResult(message="[dim]No commits yet.[/]")

        lines = ["[bold]Git History:[/]"]
        for c in log:
            ts = time.strftime("%H:%M", time.localtime(c.timestamp)) if c.timestamp else ""
            lines.append(f"  [{c.short_sha}] {ts} {c.message}")
        return SafeCommandResult(message="\n".join(lines))

    def _show_diff(self, git: GitStore, args: str) -> SafeCommandResult:
        parts = args.split()
        commit = parts[1] if len(parts) > 1 else None
        diff = git.diff(commit_a=commit)
        if diff:
            return SafeCommandResult(message=f"```diff\n{diff[:5000]}\n```")
        return SafeCommandResult(message="[dim]No diff available.[/]")

    def _do_revert(self, git: GitStore, sha: str) -> SafeCommandResult:
        info = git.revert(sha)
        if info:
            return SafeCommandResult(
                message=f"[green]Reverted to before {sha[:12]}. New commit:[/] {info.short_sha}"
            )
        return SafeCommandResult(message=f"[red]Revert failed for {sha[:12]}.[/]")

    def _help_text(self) -> str:
        return (
            "[bold]/safe[/] — Workspace Safety Commands\n"
            "  /safe status         — Show git store status\n"
            "  /safe checkpoint     — Create a safety checkpoint\n"
            "  /safe undo           — Undo last commit\n"
            "  /safe log            — Show commit history\n"
            "  /safe diff [sha]     — Show diff\n"
            "  /safe revert <sha>   — Revert to before a commit\n"
            "  /safe help           — Show this help"
        )


@dataclass
class SafeCommandContext:
    app_state: Any = None
    args: str = ""


def register_command() -> None:
    from openlaoke.commands.registry import register_command as reg

    reg(SafeCommand())
