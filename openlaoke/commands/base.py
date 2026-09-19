"""Slash command system."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


@dataclass
class CommandContext:
    """Context passed to command handlers."""

    app_state: AppState
    args: str = ""
    reply: Callable | None = None


@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool = True
    message: str = ""
    should_exit: bool = False
    should_clear: bool = False
    submit_text: str = ""


class SlashCommand(ABC):
    """Base class for slash commands."""

    name: str = ""
    description: str = ""
    aliases: list[str] = []
    hidden: bool = False

    @abstractmethod
    async def execute(self, ctx: CommandContext) -> CommandResult: ...


class HelpCommand(SlashCommand):
    name = "help"
    description = "Show available commands"
    aliases = ["?"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.commands.registry import get_all_commands

        lines = ["Available commands:"]
        for cmd in sorted(get_all_commands(), key=lambda c: c.name):
            if cmd.hidden:
                continue
            aliases = f" ({', '.join('/' + a for a in cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"  /{cmd.name}{aliases} - {cmd.description}")
        lines.append("")
        lines.append("Type a message to chat. Use /quit to exit.")
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
        ctx.app_state.messages.clear()
        return CommandResult(should_clear=True, message="Screen cleared.")


class ModelCommand(SlashCommand):
    name = "model"
    description = "Show or switch provider/model"
    aliases = ["m"]

    async def _refresh(self, config, provider_name: str) -> list[str]:
        from openlaoke.core.model_discovery import discover_models

        provider = config.providers.providers[provider_name]
        live = await discover_models(provider)
        if live:
            provider.models = live
        return live or provider.models

    @staticmethod
    def _listing(provider_name: str, models: list[str], current: str, current_provider: str) -> str:
        lines = [f"{provider_name} models ({len(models)}):"]
        for i, name in enumerate(models, 1):
            star = "*" if provider_name == current_provider and name == current else " "
            lines.append(f" {star} {i:>2}. {name}")
        return "\n".join(lines)

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.config import load_config, save_config

        config = load_config()
        providers = config.providers.providers
        state = ctx.app_state.multi_provider_config or config.providers
        cur_provider = getattr(state, "active_provider", "") or ""
        cur_model = getattr(state, "active_model", "") or ctx.app_state.session_config.model
        args = ctx.args.strip()

        if not args:
            lines = [f"Current: {cur_provider or '-'} / {cur_model or '-'}", "", "Providers:"]
            for key, provider in providers.items():
                status = "ready" if provider.is_configured() else "no key"
                marker = "*" if key == cur_provider else " "
                default = provider.get_default_model() or "-"
                lines.append(f" {marker} {key:<20} {status:<7} {default}  [{len(provider.models)}]")
            lines += [
                "",
                "Usage: /model <provider> | /model <provider>/<model> | /model <provider> <n> | /model list <provider>",
            ]
            return CommandResult(message="\n".join(lines))

        tokens = args.split()

        if tokens and tokens[0] in ("list", "ls", "models"):
            target = tokens[1] if len(tokens) > 1 else cur_provider
            if target not in providers:
                return CommandResult(
                    success=False, message=f"Unknown provider: {target or '(none)'}"
                )
            models = await self._refresh(config, target)
            save_config(config)
            if not models:
                return CommandResult(message=f"{target}: no models found.")
            return CommandResult(message=self._listing(target, models, cur_model, cur_provider))

        # Split on the first whitespace only, so model ids that contain "/"
        # (e.g. "LiquidAI-dev/lfm2.5-2.6b:latest", "anthropic/claude-3.5-sonnet")
        # survive intact.
        head, _, tail = args.partition(" ")
        head = head.strip()
        tail = tail.strip()

        provider_name: str | None = None
        model_name: str | None = None
        if not tail:
            if head in providers:
                provider_name = head
            elif "/" in head and head.split("/", 1)[0] in providers:
                provider_name, model_name = head.split("/", 1)
            else:
                model_name = head
                for key, provider in providers.items():
                    if model_name in provider.models:
                        provider_name = key
                        break
        else:
            provider_name, model_name = head, tail

        if provider_name is not None and provider_name not in providers:
            return CommandResult(success=False, message=f"Unknown provider: {provider_name}")
        if provider_name is None:
            provider_name = cur_provider
        if not provider_name:
            return CommandResult(
                success=False, message="No provider selected. Use /model <provider>."
            )

        models = await self._refresh(config, provider_name)
        if model_name and model_name.isdigit():
            idx = int(model_name)
            if not 1 <= idx <= len(models):
                return CommandResult(
                    success=False, message=f"Index {idx} out of range (1-{len(models)})."
                )
            model_name = models[idx - 1]
        if not model_name:
            model_name = providers[provider_name].get_default_model() or (
                models[0] if models else ""
            )

        state.active_provider = provider_name
        config.providers.active_provider = provider_name
        if model_name:
            state.active_model = model_name
            config.providers.active_model = model_name
            ctx.app_state.session_config.model = model_name
        save_config(config)

        note = ""
        if not providers[provider_name].is_configured():
            note = f"  (no key — /login {provider_name} <api-key>)"
        result = f"Switched to {provider_name} / {model_name or '-'}{note}"
        if len(models) > 1:
            result += "\n\n" + self._listing(provider_name, models, model_name, provider_name)
        return CommandResult(message=result)


class ThinkingCommand(SlashCommand):
    name = "thinking"
    description = "Toggle or show thinking display"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()
        if args in ("on", "off"):
            ctx.app_state.thinking_enabled = args == "on"
            return CommandResult(message=f"Thinking display: {args}")
        if args in ("show", "last"):
            text = ctx.app_state.last_thinking or "(no thinking recorded)"
            return CommandResult(message=text)
        state = "on" if ctx.app_state.thinking_enabled else "off"
        return CommandResult(message=f"Thinking display: {state}. Use /thinking on|off|show.")


class SettingsCommand(SlashCommand):
    name = "settings"
    description = "Show or change settings"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.config import load_config, save_config

        args = ctx.args.strip()
        config = load_config()
        if not args:
            lines = ["Settings:"]
            for key, value in vars(config).items():
                if key.startswith("_"):
                    continue
                if isinstance(value, (str, int, float, bool)) or value is None:
                    lines.append(f"  {key} = {value!r}")
            lines.append("")
            lines.append("Usage: /settings <key> <value>")
            return CommandResult(message="\n".join(lines))

        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            value = getattr(config, parts[0], None)
            return CommandResult(message=f"{parts[0]} = {value!r}")
        key, raw = parts
        if not hasattr(config, key):
            return CommandResult(success=False, message=f"Unknown setting: {key}")
        current = getattr(config, key)
        try:
            if isinstance(current, bool):
                parsed: object = raw.lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                parsed = int(raw)
            elif isinstance(current, float):
                parsed = float(raw)
            else:
                parsed = raw
        except ValueError:
            parsed = raw
        setattr(config, key, parsed)
        save_config(config)
        return CommandResult(message=f"{key} = {parsed!r}")


class CompactCommand(SlashCommand):
    name = "compact"
    description = "Compact the conversation context"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.compact.fast_pruner import fast_prune

        before = len(ctx.app_state.messages)
        result = fast_prune(ctx.app_state.messages)
        pruned = getattr(result, "messages", None)
        if pruned is not None:
            ctx.app_state.messages.clear()
            ctx.app_state.messages.extend(pruned)
        after = len(ctx.app_state.messages)
        return CommandResult(message=f"Compacted context: {before} -> {after} message(s).")


class ResumeCommand(SlashCommand):
    name = "resume"
    description = "Resume the most recent session"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.sessions import SessionManager

        manager = SessionManager()
        sessions = manager.list_sessions()
        if not sessions:
            return CommandResult(message="No sessions found to resume.")
        latest = sessions[0]
        ctx.app_state.set_persist_path(latest.path)
        ctx.app_state.resume_session = True
        return CommandResult(message=f"Session {latest.session_id} will be resumed on next start.")


class ExportCommand(SlashCommand):
    name = "export"
    description = "Export the session to JSON or Markdown"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        parts = ctx.args.split(maxsplit=1)
        fmt = parts[0].lower() if parts else "markdown"
        filename = parts[1] if len(parts) > 1 else None
        state = ctx.app_state
        sessions_dir = os.path.expanduser("~/.openlaoke/sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        if filename:
            path = os.path.expanduser(filename)
        elif fmt == "json":
            path = os.path.join(sessions_dir, f"session_{state.session_id}.json")
        else:
            path = os.path.join(sessions_dir, f"session_{state.session_id}.md")

        try:
            if fmt == "json":
                data = {
                    "session_id": state.session_id,
                    "exported_at": datetime.now().isoformat(),
                    "model": state.session_config.model,
                    "messages": [m.to_dict() for m in state.messages],
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
            elif fmt in ("markdown", "md"):
                lines = [f"# Session {state.session_id}", ""]
                for message in state.messages:
                    lines.append(f"## {getattr(message, 'role', 'message')}")
                    lines.append(str(getattr(message, "content", "")))
                    lines.append("")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            else:
                return CommandResult(
                    success=False, message=f"Unknown format: {fmt}. Use json|markdown."
                )
        except OSError as exc:
            return CommandResult(success=False, message=f"Export failed: {exc}")
        return CommandResult(message=f"Session exported to {path}")


class ThemeCommand(SlashCommand):
    name = "theme"
    description = "Set or show the terminal theme"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()
        themes = ["dark", "light"]
        if not args:
            current = getattr(ctx.app_state, "theme", "dark")
            return CommandResult(
                message=f"Current theme: {current}\nAvailable: {', '.join(themes)}"
            )
        if args not in themes:
            return CommandResult(
                success=False, message=f"Unknown theme: {args}. Use: {', '.join(themes)}"
            )
        ctx.app_state.theme = args
        return CommandResult(message=f"Theme set to: {args}")
