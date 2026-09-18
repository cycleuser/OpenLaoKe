"""Command registry."""

from __future__ import annotations

from openlaoke.commands.base import (
    ClearCommand,
    CompactCommand,
    ExitCommand,
    ExportCommand,
    HelpCommand,
    ModelCommand,
    ResumeCommand,
    SettingsCommand,
    SlashCommand,
    ThemeCommand,
    ThinkingCommand,
)
from openlaoke.commands.pi_commands import (
    ChangelogCommand,
    CloneCommand,
    CopyCommand,
    ForkCommand,
    HotkeysCommand,
    ImportCommand,
    LoginCommand,
    LogoutCommand,
    NameCommand,
    NewCommand,
    PromptCommand,
    ReloadCommand,
    ScopedModelsCommand,
    SessionCommand,
    ShareCommand,
    TreeCommand,
    TrustCommand,
)
from openlaoke.commands.skill_commands import SkillCommand

_commands: dict[str, SlashCommand] = {}


def register_all() -> None:
    """Register all built-in slash commands."""
    commands = [
        ClearCommand(),
        CompactCommand(),
        ExitCommand(),
        ExportCommand(),
        HelpCommand(),
        ModelCommand(),
        ResumeCommand(),
        SettingsCommand(),
        ThemeCommand(),
        ThinkingCommand(),
        ChangelogCommand(),
        CloneCommand(),
        CopyCommand(),
        ForkCommand(),
        HotkeysCommand(),
        ImportCommand(),
        LoginCommand(),
        LogoutCommand(),
        NameCommand(),
        NewCommand(),
        PromptCommand(),
        ReloadCommand(),
        ScopedModelsCommand(),
        SessionCommand(),
        ShareCommand(),
        TreeCommand(),
        TrustCommand(),
        SkillCommand(),
    ]
    for cmd in commands:
        _commands[cmd.name] = cmd
        for alias in cmd.aliases:
            _commands[alias] = cmd


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
