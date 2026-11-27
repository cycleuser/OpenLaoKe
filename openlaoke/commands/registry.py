"""Command registry."""

from __future__ import annotations

from openlaoke.commands.base import (
    AuditCommand,
    BatchCommand,
    CacheCommand,
    ClearCommand,
    CompactCommand,
    ContextCommand,
    EditsCommand,
    ExitCommand,
    ExportCommand,
    HelpCommand,
    HistoryCommand,
    McpCommand,
    MemoryCommand,
    ModeCommand,
    ModelCommand,
    RestoreCommand,
    ResumeCommand,
    ScheduleCommand,
    SearchCommand,
    SessionsCommand,
    SettingsCommand,
    SlashCommand,
    SleepCommand,
    StatsCommand,
    ThemeCommand,
    ThinkingCommand,
    TodosCommand,
    TranscriptCommand,
)
from openlaoke.commands.bot_commands import BotCommand
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
        AuditCommand(),
        ClearCommand(),
        CompactCommand(),
        BatchCommand(),
        CacheCommand(),
        ContextCommand(),
        EditsCommand(),
        ExitCommand(),
        HistoryCommand(),
        RestoreCommand(),
        ExportCommand(),
        HelpCommand(),
        McpCommand(),
        MemoryCommand(),
        ModeCommand(),
        ModelCommand(),
        ResumeCommand(),
        ScheduleCommand(),
        SearchCommand(),
        SessionsCommand(),
        SettingsCommand(),
        SleepCommand(),
        StatsCommand(),
        ThemeCommand(),
        ThinkingCommand(),
        TranscriptCommand(),
        TodosCommand(),
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
        BotCommand(),
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
