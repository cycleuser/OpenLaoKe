"""Slash command system."""

from __future__ import annotations

import asyncio
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class CommandContext:
    """Context passed to command handlers."""
    app_state: AppState
    args: str = ""
    reply: callable | None = None


@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool = True
    message: str = ""
    should_exit: bool = False
    should_clear: bool = False


class SlashCommand(ABC):
    """Base class for slash commands."""

    name: str = ""
    description: str = ""
    aliases: list[str] = []
    hidden: bool = False

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> CommandResult:
        ...


class HelpCommand(SlashCommand):
    name = "help"
    description = "Show available commands"
    aliases = ["?"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.commands.registry import get_all_commands
        commands = get_all_commands()
        lines = ["Available commands:"]
        for cmd in sorted(commands, key=lambda c: c.name):
            if cmd.hidden:
                continue
            aliases_str = f" ({', '.join('/' + a for a in cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"  /{cmd.name}{aliases_str} - {cmd.description}")
        lines.append("")
        lines.append("Type a message to chat with the AI. Use /exit to quit.")
        return CommandResult(message="\n".join(lines))


class ExitCommand(SlashCommand):
    name = "exit"
    description = "Exit OpenLaoKe"
    aliases = ["quit", "q"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(should_exit=True)


class ClearCommand(SlashCommand):
    name = "clear"
    description = "Clear the screen and conversation"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        return CommandResult(should_clear=True, message="Screen cleared.")


class ModelCommand(SlashCommand):
    name = "model"
    description = "Show or change the current model"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            current = ctx.app_state.session_config.model
            return CommandResult(message=f"Current model: {current}")

        ctx.app_state.session_config.model = args
        return CommandResult(message=f"Model set to: {args}")


class PermissionCommand(SlashCommand):
    name = "permission"
    description = "Change permission mode (default/auto/bypass)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.types.core_types import PermissionMode
        args = ctx.args.strip().lower()

        if not args:
            current = ctx.app_state.permission_config.mode.value
            return CommandResult(message=f"Current permission mode: {current}")

        try:
            mode = PermissionMode(args)
            ctx.app_state.permission_config.mode = mode
            return CommandResult(message=f"Permission mode set to: {mode.value}")
        except ValueError:
            return CommandResult(
                success=False,
                message=f"Invalid mode: {args}. Use: default, auto, bypass",
            )


class CompactCommand(SlashCommand):
    name = "compact"
    description = "Compact the conversation to save context"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        messages = ctx.app_state.get_messages()
        if len(messages) < 4:
            return CommandResult(message="Conversation is too short to compact.")

        ctx.app_state.messages = messages[:2]
        ctx.app_state.messages.append(type(messages[-1])(
            role=messages[-1].role,
            content="[Conversation compacted - earlier messages summarized]",
        ))
        return CommandResult(message="Conversation compacted.")


class CostCommand(SlashCommand):
    name = "cost"
    description = "Show current session cost and token usage"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        usage = ctx.app_state.token_usage
        cost = ctx.app_state.cost_info
        lines = [
            "Session usage:",
            f"  Input tokens:  {usage.input_tokens:,}",
            f"  Output tokens: {usage.output_tokens:,}",
            f"  Cache read:    {usage.cache_read_tokens:,}",
            f"  Cache created: {usage.cache_creation_tokens:,}",
            f"  Total tokens:  {usage.total_tokens:,}",
            "",
            "Session cost:",
            f"  Input:         ${cost.input_cost:.4f}",
            f"  Output:        ${cost.output_cost:.4f}",
            f"  Cache read:    ${cost.cache_read_cost:.4f}",
            f"  Cache created: ${cost.cache_creation_cost:.4f}",
            f"  Total:         ${cost.total_cost:.4f}",
        ]
        return CommandResult(message="\n".join(lines))


class CwdCommand(SlashCommand):
    name = "cwd"
    description = "Show or change the current working directory"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            return CommandResult(message=f"Working directory: {ctx.app_state.get_cwd()}")

        new_cwd = os.path.expanduser(args)
        if os.path.isdir(new_cwd):
            ctx.app_state.set_cwd(new_cwd)
            os.chdir(new_cwd)
            return CommandResult(message=f"Working directory: {new_cwd}")
        return CommandResult(success=False, message=f"Not a directory: {new_cwd}")


class ResumeCommand(SlashCommand):
    name = "resume"
    description = "Resume the last session"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        persist_dir = os.path.expanduser("~/.openlaoke/sessions")
        if not os.path.exists(persist_dir):
            return CommandResult(message="No sessions found to resume.")

        sessions = sorted(os.listdir(persist_dir), reverse=True)
        if not sessions:
            return CommandResult(message="No sessions found to resume.")

        latest = sessions[0]
        session_path = os.path.join(persist_dir, latest)
        ctx.app_state.set_persist_path(session_path)
        ctx.app_state.resume_session = True
        return CommandResult(message=f"Session {latest} will be resumed.")


class CommandsCommand(SlashCommand):
    name = "commands"
    description = "Show example commands to try"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        examples = [
            "Examples:",
            '  "Write a Python script that reads a CSV and prints summary stats"',
            '  "Find all TODO comments in the src/ directory"',
            '  "Explain how the authentication system works"',
            '  "Refactor the database queries to use async"',
            '  "Add unit tests for the user service"',
            '  "Create a REST API for managing tasks"',
            "",
            "You can also use tools directly:",
            '  /Bash ls -la',
            '  /Read src/main.py',
        ]
        return CommandResult(message="\n".join(examples))


class SettingsCommand(SlashCommand):
    name = "settings"
    description = "Show current settings"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        config = ctx.app_state.session_config
        perm = ctx.app_state.permission_config
        lines = [
            "Settings:",
            f"  Model:       {config.model}",
            f"  Max tokens:  {config.max_tokens}",
            f"  Temperature: {config.temperature}",
            f"  Thinking:    {config.thinking_budget} tokens",
            f"  Permissions: {perm.mode.value}",
            f"  Working dir: {ctx.app_state.get_cwd()}",
        ]
        return CommandResult(message="\n".join(lines))