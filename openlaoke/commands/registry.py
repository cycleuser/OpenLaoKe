"""Command registry."""

from __future__ import annotations

from openlaoke.commands.base import (
    ClearCommand,
    CommandsCommand,
    CompactCommand,
    CostCommand,
    CwdCommand,
    ExitCommand,
    HelpCommand,
    ModelCommand,
    PermissionCommand,
    ResumeCommand,
    SettingsCommand,
    SlashCommand,
)
from openlaoke.commands.skill_commands import SkillCommand, UseSkillCommand
from openlaoke.commands.skill_shortcuts import register_skill_shortcuts

_commands: dict[str, SlashCommand] = {}


def register_all() -> None:
    """Register all built-in slash commands."""
    commands = [
        HelpCommand(),
        ExitCommand(),
        ClearCommand(),
        ModelCommand(),
        PermissionCommand(),
        CompactCommand(),
        CostCommand(),
        CwdCommand(),
        ResumeCommand(),
        CommandsCommand(),
        SettingsCommand(),
        SkillCommand(),
        UseSkillCommand(),
    ]
    for cmd in commands:
        _commands[cmd.name] = cmd
        for alias in cmd.aliases:
            _commands[alias] = cmd
    
    # Register skill shortcuts like /browse, /qa, etc.
    register_skill_shortcuts(_commands)


def get_command(name: str) -> SlashCommand | None:
    return _commands.get(name)


def get_all_commands() -> list[SlashCommand]:
    seen = set()
    result = []
    for cmd in _commands.values():
        if cmd.name not in seen:
            seen.add(cmd.name)
            result.append(cmd)
    return result


def parse_command(text: str) -> tuple[str, str] | None:
    """Parse a slash command from user input. Returns (name, args) or None."""
    text = text.strip()
    if not text.startswith("/"):
        return None
    parts = text[1:].split(" ", 1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return name, args
