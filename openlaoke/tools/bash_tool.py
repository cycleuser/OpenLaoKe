"""Bash tool - execute shell commands."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import PermissionMode, ToolResultBlock
from openlaoke.utils.permissions.bash_classifier import (
    CommandSafetyLevel,
    ConfidenceLevel,
    classify_bash_command,
)


class BashInput(BaseModel):
    command: str = Field(description="The bash command to execute")
    description: str = Field(default="", description="Brief description of what this command does")
    timeout: float | None = Field(
        default=None,
        description=(
            "Hard deadline in seconds. When it passes the command is killed. "
            "Leave unset to let a slow command move to the background instead."
        ),
    )
    auto_background_timeout_ms: float = Field(
        default=3000,
        description=(
            "After this many milliseconds a still-running command is moved to the background "
            "and its task id is returned, so it does not block the turn. 0 disables."
        ),
    )
    background: bool = Field(
        default=False, description="Start in the background immediately and return the task id"
    )
    justification: str = Field(
        default="",
        description=(
            "Required when the result says the command needs one: name the target and how the "
            "change can be undone. Ignored for commands that do not ask for it."
        ),
    )


class BashTool(Tool):
    """Execute bash commands in the terminal."""

    name = "Bash"
    description = (
        "Execute a bash command in the current working directory. "
        "Use this for running scripts, installing packages, git operations, etc. "
        "A command still running after auto_background_timeout_ms (default 3000) is moved to "
        "the background and its task id is returned; read it with Bg. Pass timeout only when "
        "you want the command killed at a deadline."
    )
    input_schema = BashInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    @staticmethod
    def _record_risk(ctx: ToolContext, command: str, reason: str, justification: str) -> None:
        """Keep a bounded trail of low-risk but destructive commands."""
        events = getattr(ctx.app_state, "risk_events", None)
        if not isinstance(events, list):
            return
        import time as _time

        events.append(
            {
                "tier": "low",
                "command": command[:400],
                "reason": reason,
                "justification": justification[:400],
                "at": _time.time(),
            }
        )
        del events[:-200]

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        command = kwargs.get("command", "")
        description = kwargs.get("description", "")
        timeout = kwargs.get("timeout")

        if not command.strip():
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: Empty command",
                is_error=True,
            )

        classification = classify_bash_command(command)

        # Four-tier blast radius on top of the pattern classifier: a catastrophic
        # command is refused outright, and a command whose target cannot be read
        # off the text has to come back with a justification.
        from openlaoke.utils.permissions.command_risk import CATASTROPHIC, CONFIRM, assess

        risk = assess(command, ctx.app_state.get_cwd())
        justification = str(kwargs.get("justification") or "").strip()
        if risk.tier == CATASTROPHIC:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Refused: {risk.reason}. No justification unlocks this class of command.",
                is_error=True,
            )
        if risk.tier == CONFIRM and not justification:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=(
                    f"Needs justification: {risk.reason}\n"
                    'Re-send the same command with justification="what this targets and how to '
                    'undo it" if you still mean it.'
                ),
                is_error=True,
            )
        if risk.records:
            self._record_risk(ctx, command, risk.reason, justification)

        # The four-tier reading is more precise than the pattern classifier, so a
        # command it places in safe or low skips the older dangerous branches.
        suppress_legacy_dangerous = risk.tier in ("safe", "low")

        if classification.safety_level == CommandSafetyLevel.DESTRUCTIVE:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Command blocked for safety: {classification.reason}\n"
                f"This command is classified as destructive and cannot be executed.",
                is_error=True,
            )

        perm_mode = ctx.app_state.permission_config.mode

        if (
            not suppress_legacy_dangerous
            and perm_mode == PermissionMode.DEFAULT
            and classification.safety_level == CommandSafetyLevel.DANGEROUS
        ):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Command requires approval: {classification.reason}\n"
                f"Confidence: {classification.confidence.value}\n"
                f"Use 'approve' to allow this command, or run with --permission-mode auto.",
                is_error=True,
            )

        if (
            not suppress_legacy_dangerous
            and perm_mode == PermissionMode.AUTO
            and (
                classification.safety_level == CommandSafetyLevel.DANGEROUS
                and classification.confidence == ConfidenceLevel.HIGH
            )
        ):
            # AUTO auto-approves anything except high-confidence dangerous
            # matches (rm -rf, curl|sh, interpreter inline code, file-writing
            # redirects). Unknown commands (low confidence) run normally.
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Command needs confirmation in auto mode: {classification.reason}\n"
                f"Safety level: {classification.safety_level.value}\n"
                f"Confidence: {classification.confidence.value}\n"
                "Ask the user to approve or adjust the permission mode.",
                is_error=True,
            )

        from openlaoke.core.task import DEFAULT_AUTO_BACKGROUND_MS, get_task_manager

        auto_bg = kwargs.get("auto_background_timeout_ms", DEFAULT_AUTO_BACKGROUND_MS)
        try:
            auto_bg_ms = float(auto_bg) if auto_bg is not None else None
        except (TypeError, ValueError):
            auto_bg_ms = DEFAULT_AUTO_BACKGROUND_MS

        force_background = bool(kwargs.get("background"))
        effective_bg_ms = 0.0 if force_background else auto_bg_ms

        task_mgr = get_task_manager(ctx.app_state)
        try:
            outcome = await task_mgr.run_bash(
                command=command,
                description=description or command[:100],
                timeout=timeout,
                tool_use_id=ctx.tool_use_id,
                working_dir=ctx.app_state.get_cwd(),
                auto_background_ms=effective_bg_ms,
            )

            max_output = 30000
            output = outcome.output
            original_len = len(output)
            truncated = False
            if original_len > max_output:
                output = f"{output[:max_output]}\n\n... (output truncated, {original_len - max_output} chars omitted)"
                truncated = True

            if outcome.backgrounded:
                why = (
                    "started in the background"
                    if force_background
                    else f"still running after {effective_bg_ms:.0f}ms; moved to the background"
                )
                head = (
                    f"Command {why} as task {outcome.task_id}.\n"
                    f"Read it with Bg(action='tail', task_id='{outcome.task_id}'), "
                    f"wait with Bg(action='wait', ...), cancel with Bg(action='cancel', ...)."
                )
                body = f"\n\nOutput so far:\n{output}" if output.strip() else ""
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id, content=head + body, is_error=False
                )

            if outcome.timed_out:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=(
                        f"Command timed out after {timeout}s and was killed (task {outcome.task_id}).\n\n"
                        f"Output before the timeout:\n{output or '(none)'}\n\n"
                        "Pass a larger timeout, or leave timeout unset so a slow command is "
                        "moved to the background instead of killed."
                    ),
                    is_error=True,
                )

            exit_code = outcome.exit_code or 0
            if exit_code != 0:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Command exited with code {exit_code}\n\n{output}",
                    is_error=True,
                )

            content = output if output else "(command completed successfully with no output)"
            if truncated:
                content += "\n(note: output was truncated)"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=content,
                is_error=False,
            )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error executing command: {e}",
                is_error=True,
            )


def register(registry: ToolRegistry) -> None:
    registry.register(BashTool())
