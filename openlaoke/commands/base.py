"""Slash command system."""

from __future__ import annotations

import contextlib
import json
import os
import time
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
    description = "Show, switch, add, remove, or prune provider/model"
    aliases = ["m", "models"]

    async def _refresh(self, config, provider_name: str) -> list[str]:
        from openlaoke.core.model_discovery import discover_model_details

        provider = config.providers.providers[provider_name]
        live, labels = await discover_model_details(provider)
        if live:
            provider.models = live
            provider.model_labels = {
                model: label for model, label in labels.items() if model in live
            }
        return live or provider.models

    @staticmethod
    def _listing(
        provider_name: str,
        models: list[str],
        current: str,
        current_provider: str,
        labels: dict[str, str] | None = None,
    ) -> str:
        lines = [f"{provider_name} models ({len(models)}):"]
        for i, name in enumerate(models, 1):
            star = "*" if provider_name == current_provider and name == current else " "
            label = f"  ·  {labels[name]}" if labels and name in labels else ""
            lines.append(f" {star} {i:>2}. {name}{label}")
        return "\n".join(lines)

    @staticmethod
    def _mask(key: str) -> str:
        if not key:
            return "(no key)"
        if len(key) <= 12:
            return "***"
        return f"{key[:6]}...{key[-4:]}"

    @staticmethod
    def _provider_ready(provider) -> bool:
        ready = getattr(provider, "is_ready", None)
        if callable(ready):
            return bool(ready())
        try:
            return bool(provider.is_configured())
        except Exception:
            return False

    def _ready_listing(self, providers, cur_provider: str, cur_model: str) -> list[str]:
        ready = [(k, p) for k, p in providers.items() if self._provider_ready(p)]
        base_to_names: dict[str, list[str]] = {}
        for key, provider in ready:
            base = (getattr(provider, "base_url", "") or "").rstrip("/").lower()
            if base:
                base_to_names.setdefault(base, []).append(key)
        duplicate_generic = {
            "openai_compatible"
            for names in base_to_names.values()
            if "openai_compatible" in names and any(name != "openai_compatible" for name in names)
        }
        ready = [
            (key, provider)
            for key, provider in ready
            if key not in duplicate_generic or key == cur_provider
        ]
        lines = [f"Current: {cur_provider or '-'} / {cur_model or '-'}"]
        if not ready:
            lines.append("No providers configured yet.")
        else:
            lines.append("Configured providers:")
            for key, provider in ready:
                marker = "*" if key == cur_provider else " "
                shown = (
                    cur_model
                    if key == cur_provider and cur_model
                    else (provider.get_default_model() or "-")
                )
                count = len(provider.models)
                label = f"{shown} ({count})" if count else shown
                key_state = "local" if provider.is_local else self._mask(provider.api_key)
                lines.append(f" {marker} {key:<18} {label:<30} {key_state}")
        offline_local = [
            (key, provider)
            for key, provider in providers.items()
            if provider.enabled and provider.is_local and not self._provider_ready(provider)
        ]
        if offline_local:
            lines.append("")
            lines.append("Unreachable local providers:")
            for key, provider in offline_local:
                lines.append(f"   {key:<18} {provider.base_url or '-'}  (offline)")
        if (
            cur_provider
            and cur_provider in providers
            and not self._provider_ready(providers[cur_provider])
        ):
            lines.append(
                f"[warning] {cur_provider} has no API key. "
                f"Use /model add or /login {cur_provider} <key>."
            )
        lines += [
            "",
            "Switch:   /model <provider>/<model>",
            "Add:      /model add",
            "Discover: /model list <provider>",
            "Probe:    /model probe",
            "Remove:   /model rm <provider>",
            "Prune:    /model prune",
        ]
        return lines

    async def _add(self, ctx: CommandContext, config, providers, args: str) -> CommandResult:
        from openlaoke.core.provider_presets import (
            PRESETS_BY_KEY,
            custom_preset,
            wizard_presets,
        )
        from openlaoke.utils.config import save_config

        tokens = args.split()
        preset_key = tokens[0] if tokens and tokens[0] in PRESETS_BY_KEY else None

        if not tokens:
            from rich.prompt import Prompt

            presets = wizard_presets()
            lines = ["Add a provider:"]
            for i, preset in enumerate(presets, 1):
                env_mark = " [env]" if preset.env_var and os.environ.get(preset.env_var) else ""
                lines.append(f"  [{i:>2}] {preset.label} ({preset.key}){env_mark}")
            lines.append(f"  [{len(presets) + 1:>2}] Custom OpenAI-compatible (URL + key)")
            print("\n".join(lines))
            choice = Prompt.ask(
                "Select provider",
                choices=[str(i) for i in range(1, len(presets) + 2)],
                default=str(len(presets) + 1),
            )
            if choice == str(len(presets) + 1):
                return await self._add_custom(providers, config)
            preset_key = presets[int(choice) - 1].key

        if preset_key is not None:
            preset = PRESETS_BY_KEY[preset_key]
            provider = preset.build()
            if not provider.api_key and not provider.is_local:
                from rich.prompt import Prompt

                provider.api_key = Prompt.ask(
                    f"API key for {preset.label} ({preset.env_var or 'required'})",
                    password=True,
                    default="",
                )
            providers[preset.key] = provider
            if not config.providers.active_provider:
                config.providers.active_provider = preset.key
                config.providers.active_model = provider.get_default_model()
            save_config(config)
            models = ", ".join(provider.models) or f"(run /model list {preset.key})"
            return CommandResult(message=f"Added {preset.key} ({preset.label}).\nModels: {models}")

        # Custom: /model add <name> <base-url> [api-key] [model-id]
        if len(tokens) < 2:
            return CommandResult(
                success=False,
                message="Usage: /model add <name> <base-url> [api-key] [model-id]",
            )
        name, base_url = tokens[0], tokens[1]
        api_key = tokens[2] if len(tokens) > 2 else ""
        model_id = tokens[3] if len(tokens) > 3 else ""
        provider = custom_preset(name, base_url, model_id).build(api_key)
        providers[name] = provider
        if not config.providers.active_provider:
            config.providers.active_provider = name
            config.providers.active_model = provider.get_default_model()
        save_config(config)
        return CommandResult(message=f"Added {name} -> {base_url}.")

    async def _add_custom(self, providers, config) -> CommandResult:
        from rich.prompt import Prompt

        from openlaoke.core.provider_presets import custom_preset
        from openlaoke.utils.config import save_config

        name = Prompt.ask("Provider name", default="custom").strip()
        base_url = Prompt.ask("Base URL (OpenAI-compatible, e.g. https://host/v1)").strip()
        api_key = Prompt.ask("API key", password=True, default="").strip()
        model_id = Prompt.ask("Default model id (optional)", default="").strip()
        if not name or not base_url:
            return CommandResult(success=False, message="Name and base URL are required.")
        provider = custom_preset(name, base_url, model_id).build(api_key)
        providers[name] = provider
        if not config.providers.active_provider:
            config.providers.active_provider = name
            config.providers.active_model = provider.get_default_model()
        save_config(config)
        return CommandResult(message=f"Added {name} -> {base_url}.")

    async def _remove(self, config, providers, name: str) -> CommandResult:
        from openlaoke.utils.config import save_config

        if not name:
            return CommandResult(success=False, message="Usage: /model rm <provider>")
        if name not in providers:
            return CommandResult(success=False, message=f"Unknown provider: {name}")
        del providers[name]
        if config.providers.active_provider == name:
            config.providers.active_provider = ""
            config.providers.active_model = ""
        save_config(config)
        return CommandResult(message=f"Removed provider {name}.")

    async def _probe(self, providers) -> CommandResult:
        from openlaoke.types.providers import probe_local_providers

        results = await probe_local_providers(providers)
        if not results:
            return CommandResult(message="No local providers configured.")
        lines = ["Local providers:"]
        for name, reachable in sorted(results.items()):
            provider = providers[name]
            state = "online" if reachable else "offline"
            lines.append(f"   {name:<18} {state:<8} {provider.base_url or '-'}")
        lines += ["", "Remove offline: /model prune"]
        return CommandResult(message="\n".join(lines))

    async def _prune(self, ctx: CommandContext, config, providers) -> CommandResult:
        from openlaoke.types.providers import probe_local_providers
        from openlaoke.utils.config import save_config

        results = await probe_local_providers(providers)
        offline = [name for name, reachable in results.items() if not reachable]
        if not offline:
            return CommandResult(message="No unreachable local providers.")
        for name in offline:
            providers.pop(name, None)
        state = ctx.app_state.multi_provider_config or config.providers
        if getattr(state, "active_provider", "") in offline:
            remaining = [
                name for name, provider in providers.items() if self._provider_ready(provider)
            ]
            if remaining:
                state.active_provider = remaining[0]
                state.active_model = providers[remaining[0]].get_default_model()
            else:
                state.active_provider = ""
                state.active_model = ""
            config.providers.active_provider = state.active_provider
            config.providers.active_model = state.active_model
        save_config(config)
        return CommandResult(
            message=f"Removed {len(offline)} unreachable local provider(s): {', '.join(offline)}"
        )

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.config import load_config, save_config

        config = load_config()
        providers = config.providers.providers
        state = ctx.app_state.multi_provider_config or config.providers
        cur_provider = getattr(state, "active_provider", "") or ""
        cur_model = getattr(state, "active_model", "") or ctx.app_state.session_config.model
        args = ctx.args.strip()

        if not args:
            from openlaoke.types.providers import probe_local_providers

            await probe_local_providers(providers)
            return CommandResult(
                message="\n".join(self._ready_listing(providers, cur_provider, cur_model))
            )

        tokens = args.split()

        if tokens[0] in ("add", "+"):
            return await self._add(ctx, config, providers, " ".join(tokens[1:]))

        if tokens[0] in ("rm", "remove", "delete", "-"):
            return await self._remove(config, providers, tokens[1] if len(tokens) > 1 else "")

        if tokens[0] in ("probe", "check"):
            return await self._probe(providers)

        if tokens[0] in ("prune", "clean"):
            return await self._prune(ctx, config, providers)

        if tokens[0] in ("list", "ls", "models"):
            target = tokens[1] if len(tokens) > 1 else cur_provider
            if target not in providers:
                return CommandResult(
                    success=False, message=f"Unknown provider: {target or '(none)'}"
                )
            models = await self._refresh(config, target)
            save_config(config)
            if not models:
                return CommandResult(message=f"{target}: no models found.")
            return CommandResult(
                message=self._listing(
                    target,
                    models,
                    cur_model,
                    cur_provider,
                    getattr(providers[target], "model_labels", {}),
                )
            )

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
                success=False,
                message=(
                    f"No provider selected for '{args}'. "
                    "Use /model add or /model <provider>/<model>."
                ),
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
        if not self._provider_ready(providers[provider_name]):
            note = f"  (no key — /login {provider_name} <api-key>)"
        result = f"Switched to {provider_name} / {model_name or '-'}{note}"
        if len(models) > 1:
            result += "\n\n" + self._listing(
                provider_name,
                models,
                model_name,
                provider_name,
                getattr(providers[provider_name], "model_labels", {}),
            )
        return CommandResult(message=result)


class ModeCommand(SlashCommand):
    name = "mode"
    description = "Switch harness mode (balanced, pi, jcode, opencode)"
    aliases = ["harness"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.harness_modes import (
            get_mode,
            is_valid_mode,
            list_modes,
            normalize_mode,
        )
        from openlaoke.utils.config import load_config, save_config

        config = load_config()
        args = ctx.args.strip().lower()
        current = normalize_mode(getattr(ctx.app_state, "harness_mode", None) or config.mode)

        if not args or args in ("list", "ls", "show"):
            lines = [f"Harness mode: {current}", ""]
            for mode in list_modes():
                marker = "*" if mode.key == current else " "
                effort = mode.reasoning_effort or "auto"
                lines.append(f" {marker} {mode.key:<9} {mode.summary}")
                lines.append(f"   effort={effort}  steps={mode.max_steps}  tools={mode.tools}")
            lines.append("")
            lines.append("Switch: /mode <name>    aliases: fast, robust, thorough, max")
            return CommandResult(message="\n".join(lines))

        if not is_valid_mode(args):
            valid = ", ".join(mode.key for mode in list_modes())
            return CommandResult(
                success=False,
                message=f"Unknown mode: {args}\nValid modes: {valid}",
            )

        mode = get_mode(args)
        config.mode = mode.key
        config.reasoning_effort = mode.reasoning_effort
        save_config(config)

        ctx.app_state.harness_mode = mode.key
        ctx.app_state.max_steps = mode.max_steps
        session_config = getattr(ctx.app_state, "session_config", None)
        if session_config is not None:
            session_config.reasoning_effort = mode.reasoning_effort

        guard = getattr(ctx.app_state, "_cache_guard", None)
        if guard is not None and hasattr(guard, "invalidate"):
            guard.invalidate()

        effort = mode.reasoning_effort or "auto"
        return CommandResult(
            message=(
                f"Harness mode: {mode.key}\n"
                f"{mode.summary}\n"
                f"effort={effort}  steps={mode.max_steps}  tools={mode.tools}  "
                f"verify={mode.verify}"
            )
        )


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
            # Copy first: when nothing needed pruning the pruner returns the
            # live history list itself, and clear()-then-extend() on that same
            # object would leave the conversation empty.
            replacement = list(pruned)
            ctx.app_state.messages.clear()
            ctx.app_state.messages.extend(replacement)
        after = len(ctx.app_state.messages)
        return CommandResult(message=f"Compacted context: {before} -> {after} message(s).")


class ContextCommand(SlashCommand):
    name = "context"
    description = "Show or set the context budget for this session"
    aliases = ["ctx"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.context_budget import resolve_budget
        from openlaoke.utils.config import load_config

        state = ctx.app_state
        arg = ctx.args.strip().lower()

        if arg:
            if arg in ("clear", "reset", "none", "0"):
                state.set_context_cap(None)
                return CommandResult(message="Session context cap cleared; global default applies.")
            try:
                tokens = _parse_amount(arg)
            except ValueError as exc:
                return CommandResult(success=False, message=str(exc))
            if tokens < 1024:
                return CommandResult(
                    success=False, message="Session cap must be at least 1024 tokens."
                )
            state.set_context_cap(tokens)
            return CommandResult(message=f"Session context cap set to {tokens:,} tokens.")

        config = load_config()
        window = state.compact_state.get("model_window")
        if not isinstance(window, int) or window <= 0:
            window = None
            provider = config.providers.get_active_provider()
            if provider is not None:
                with contextlib.suppress(Exception):
                    from openlaoke.core.model_discovery import get_effective_context_limit

                    window = await get_effective_context_limit(provider, state.session_config.model)

        used = state.compact_state.get("used_tokens") or 0
        source = state.compact_state.get("used_source") or "estimate"
        budget = resolve_budget(
            model_window=window,
            session_cap=state.context_cap,
            global_cap=config.context_cap_tokens,
            used_tokens=int(used),
            source=source,
        )
        return CommandResult(message=budget.render())


def _parse_amount(raw: str) -> int:
    multipliers = {"k": 1024, "m": 1024 * 1024}
    tail = raw[-1].lower()
    try:
        if tail in multipliers:
            return int(float(raw[:-1]) * multipliers[tail])
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(f"Not a token amount: {raw}") from exc


class SessionsCommand(SlashCommand):
    name = "sessions"
    description = "List saved sessions, or '/sessions prune [days]' to delete old ones"
    aliases = ["ls-sessions"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import shlex

        from openlaoke.core.sessions import SessionManager

        manager = SessionManager()
        args = shlex.split(ctx.args or "")
        if args:
            if args[0].lower() not in ("prune", "clean"):
                return CommandResult(
                    success=False, message="Usage: /sessions  |  /sessions prune [days]"
                )
            days = 30
            if len(args) > 1:
                try:
                    days = max(1, int(args[1]))
                except ValueError:
                    return CommandResult(success=False, message="Usage: /sessions prune [days]")
            # Deleting sessions is destructive, so it only happens when asked for
            # by name. cleanup_old_sessions() existed but nothing ever called it.
            removed = manager.cleanup_old_sessions(max_age_days=days)
            return CommandResult(
                message=(
                    f"Removed {removed} session(s) older than {days} day(s), "
                    "with their journals and stored tool output."
                )
            )
        sessions = manager.list_sessions()
        if not sessions:
            return CommandResult(message="No saved sessions yet.")
        rows = []
        for info in sessions[:25]:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(info.created_at))
            current = " *" if info.session_id == ctx.app_state.session_id else "  "
            # Say when the snapshot is gone: that row is listed from its journal
            # and will be replayed rather than loaded.
            note = "  (journal only)" if getattr(info, "recovered", False) else ""
            rows.append(
                f"{current}{info.session_id}  {stamp}  {info.message_count:>3} msg  "
                f"{info.model}  {info.cwd or '-'}{note}"
            )
        header = f"{len(sessions)} session(s); * marks this one"
        return CommandResult(message=header + "\n" + "\n".join(rows))


class SearchCommand(SlashCommand):
    name = "search"
    description = "Search saved sessions for a phrase"
    aliases = ["find-session"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.session_index import search_sessions

        query = ctx.args.strip()
        if not query:
            return CommandResult(success=False, message="Use '/search <query>'.")
        hits = search_sessions(query, limit=10)
        if not hits:
            return CommandResult(message=f"No session messages match '{query}'.")
        return CommandResult(message="\n\n".join(hit.line() for hit in hits))


class MemoryCommand(SlashCommand):
    name = "memory"
    description = "Show, search, add or clear this project's stored notes"
    aliases = ["mem"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.memory_store import get_store

        store = get_store(ctx.app_state)
        arg = ctx.args.strip()
        if not arg:
            return CommandResult(
                message=store.stats() + "\n" + store.render(store.recent(limit=10))
            )
        if arg.lower() in ("clear", "wipe"):
            count = store.clear()
            return CommandResult(message=f"Cleared {count} note(s) from {store.path}.")
        # Typing "/memory remember ..." is the one way to write a note the model
        # cannot outrank. Everything the Memory tool writes is "agent".
        lowered = arg.lower()
        for verb in ("remember ", "add "):
            if lowered.startswith(verb):
                text = arg[len(verb) :].strip()
                if not text:
                    return CommandResult(
                        success=False, message=f"Usage: /memory {verb.strip()} <text>"
                    )
                entry = store.remember(text, authority="user")
                return CommandResult(message=f"Remembered as {entry.id} (user): {entry.text}")
        entries = store.recall(arg, limit=8)
        if not entries:
            return CommandResult(
                message="No matching notes. '/memory remember <text>' saves one as a user note."
            )
        return CommandResult(message=store.render(entries))


class BatchCommand(SlashCommand):
    name = "batch"
    description = "Turn the Batch tool (parallel tool calls) on or off"
    aliases = []

    async def execute(self, ctx: CommandContext) -> CommandResult:
        registry = getattr(ctx.app_state, "_tool_registry", None)
        if registry is None:
            return CommandResult(
                success=False, message="No tool registry on this session; Batch cannot be toggled."
            )
        arg = ctx.args.strip().lower()
        enabled = registry.get("Batch") is not None
        if not arg:
            state = "on" if enabled else "off"
            return CommandResult(
                message=(
                    f"Batch is {state}. '/batch on' enables parallel tool calls "
                    "(1-10 read-only calls per turn); '/batch off' disables it."
                )
            )
        if arg in ("on", "enable", "true", "1"):
            from openlaoke.tools.batch_tool import BatchTool

            registry.register(BatchTool())
            registry.thaw()
            return CommandResult(
                message="Batch enabled for this session. Read-only calls only; writes still go "
                "through the permission prompt one at a time."
            )
        if arg in ("off", "disable", "false", "0"):
            registry.unregister("Batch")
            registry.thaw()
            return CommandResult(message="Batch disabled for this session.")
        return CommandResult(success=False, message="Use '/batch on' or '/batch off'.")


class EditsCommand(SlashCommand):
    name = "edits"
    description = "Show what this session changed on disk"
    aliases = ["diffstat"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.edit_stats import EditStats

        stats = EditStats.from_dict(ctx.app_state.edit_stats)
        return CommandResult(message=stats.render())


class HistoryCommand(SlashCommand):
    """Reader for the persistent per-file snapshot store.

    Every ``edit``/``write`` records the pre-edit content of the file it is
    about to touch, so a bad change can be rolled back after the session (and
    the process) is long gone. ``/tree`` covers undo within a session; this
    covers undo across sessions.
    """

    name = "history"
    description = "List files with saved snapshots, or show one file's versions"
    aliases = ["versions"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.file_history import (
            format_history_list,
            format_timestamp,
            list_histories,
        )

        target = ctx.args.strip()
        if target:
            return CommandResult(message=format_history_list(target))

        histories = list_histories()
        if not histories:
            return CommandResult(
                message="No file snapshots yet. They are recorded automatically when "
                "the edit or write tool modifies a file."
            )

        lines = [f"{len(histories)} file(s) with snapshots:", ""]
        for history in histories:
            latest = history.snapshots[-1]
            lines.append(
                f"  {history.path}  ({len(history.snapshots)} versions, "
                f"last {format_timestamp(latest.timestamp)}, "
                f"latest v{latest.version})"
            )
        lines.append("")
        lines.append("Use /history <path> to see versions, or /restore <path> [version].")
        return CommandResult(message="\n".join(lines))


class RestoreCommand(SlashCommand):
    name = "restore"
    description = "Restore a file from a saved snapshot: /restore <path> [version]"
    aliases = ["rollback"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.file_history import (
            get_latest_snapshot,
            get_snapshot_by_version,
            restore_snapshot,
        )

        parts = ctx.args.split()
        if not parts:
            return CommandResult(success=False, message="Usage: /restore <path> [version]")

        path = parts[0]
        version: int | None = None
        if len(parts) > 1:
            try:
                version = int(parts[1].lstrip("vV"))
            except ValueError:
                return CommandResult(
                    success=False,
                    message=f"Not a version number: {parts[1]}. Use /history {path} to list versions.",
                )

        # Look the snapshot up before touching the file so the message can name
        # exactly what was written back.
        snapshot = (
            get_latest_snapshot(path) if version is None else get_snapshot_by_version(path, version)
        )
        if snapshot is None:
            wanted = "a saved snapshot" if version is None else f"saved version {version}"
            return CommandResult(
                success=False,
                message=f"No {wanted} for {path}. Run /history without arguments to see what is saved.",
            )

        if not restore_snapshot(path, version):
            return CommandResult(success=False, message=f"Could not write {path}.")

        return CommandResult(
            message=f"Restored {path} to v{snapshot.version} ({len(snapshot.content)} bytes)."
        )


class StatsCommand(SlashCommand):
    name = "stats"
    description = "Session dashboard: tokens, tools, edits, tasks, memory"
    aliases = ["dashboard"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.edit_stats import EditStats
        from openlaoke.core.todo_engine import TodoStore

        state = ctx.app_state
        lines: list[str] = []

        usage = state.token_usage
        total_in = int(getattr(usage, "input_tokens", 0) or 0)
        total_out = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_tokens", 0) or 0) or int(
            getattr(usage, "cache_read_input_tokens", 0) or 0
        )
        cache_write = int(getattr(usage, "cache_creation_tokens", 0) or 0)
        hit = f"{cache_read / total_in:.0%}" if total_in else "n/a"
        lines.append(
            f"Tokens: {total_in:,} in / {total_out:,} out; cache read {cache_read:,} "
            f"({hit}), written {cache_write:,}"
        )

        cost = state.cost_info
        input_cost = float(getattr(cost, "input_cost", 0) or 0)
        output_cost = float(getattr(cost, "output_cost", 0) or 0)
        if input_cost or output_cost:
            lines.append(f"Estimated cost: ${input_cost + output_cost:.4f}")

        counts = state.tool_call_counts or {}
        if counts:
            ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]
            lines.append(
                f"Tool calls: {sum(counts.values())} "
                + ", ".join(f"{name}×{count}" for name, count in ordered)
            )
        else:
            lines.append("Tool calls: none yet")

        edits = EditStats.from_dict(state.edit_stats)
        lines.append(
            f"Edits: {edits.files_created} created, {edits.files_modified} modified, "
            f"+{edits.lines_added}/-{edits.lines_removed}"
        )

        todos = TodoStore(state.todo_state)
        lines.append(
            f"Tasks: {len(todos.open_items())} open, {len(todos.items)} total, "
            f"{len(todos.blocked_items())} blocked"
        )

        running = [
            task for task in state.get_all_tasks() if task.id and task.status.value == "running"
        ]
        lines.append(f"Background jobs: {len(running)} running, {len(state.tasks)} total")

        memory = getattr(state, "_memory_store", None)
        if memory is not None:
            lines.append(f"Memory notes: {len(memory.entries)}")

        monitor = getattr(state, "_cache_monitor", None)
        if monitor is not None and getattr(monitor, "readings", None):
            lines.append(f"Cache hit rate (recent): {monitor.avg_hit_rate():.0%}")

        lines.append(f"Session: {state.session_id} ({len(state.messages)} messages)")
        return CommandResult(message="\n".join(lines))


class SleepCommand(SlashCommand):
    name = "sleep"
    description = "Release derived caches without ending the session"
    aliases = ["hibernate"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import gc

        state = ctx.app_state
        released: list[str] = []

        swarm = getattr(state, "_swarm", None)
        if swarm is not None and swarm.running():
            return CommandResult(
                success=False,
                message="Refusing to hibernate while swarm workers are running; cancel them first.",
            )

        if getattr(state, "_memory_store", None) is not None:
            state._memory_store = None
            released.append("memory index")
        monitor = getattr(state, "_cache_monitor", None)
        if monitor is not None and getattr(monitor, "readings", None):
            count = len(monitor.readings)
            monitor.readings.clear()
            released.append(f"cache readings ({count})")
        if getattr(state, "_swarm", None) is not None:
            state._swarm = None
            state._swarm_board = None
            released.append("swarm board")
        if getattr(state, "_task_manager", None) is not None:
            manager = state._task_manager
            manager._procs.clear()
            manager._handles.clear()
            released.append("task handles")

        collected = gc.collect()
        body = ", ".join(released) if released else "nothing to release"
        return CommandResult(
            message=f"Released {body}. Collected {collected} object(s). "
            "Stores reload from disk on next use."
        )


class ScheduleCommand(SlashCommand):
    name = "schedule"
    description = "Show the local schedule, or its run history with '/schedule log'"
    aliases = ["cron"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import shlex

        from openlaoke.core.scheduler import get_scheduler

        scheduler = get_scheduler(ctx.app_state)
        args = shlex.split(ctx.args or "")
        if args and args[0].lower() in ("log", "history", "runs"):
            # "runs: 12" with nothing else says a job fired twelve times and
            # tells you nothing about whether any of them worked.
            identifier = args[1] if len(args) > 1 else ""
            limit = 20
            if len(args) > 2:
                try:
                    limit = max(1, min(200, int(args[2])))
                except ValueError:
                    return CommandResult(success=False, message="Usage: /schedule log [id] [count]")
            return CommandResult(message=scheduler.render_history(identifier, limit))
        if args:
            return CommandResult(
                success=False,
                message="Usage: /schedule  (list)  |  /schedule log [id] [count]",
            )
        enabled = bool(getattr(getattr(ctx, "app_config", None), "enable_scheduler", False))
        note = (
            "" if enabled else "\n(scheduler loop is off: set enable_scheduler=true in the config)"
        )
        return CommandResult(
            message=scheduler.render() + note + "\n('/schedule log' shows what actually ran)"
        )


class McpCommand(SlashCommand):
    name = "mcp"
    description = "Show MCP servers and the tools they contributed"
    aliases = []

    async def execute(self, ctx: CommandContext) -> CommandResult:
        runtime = getattr(ctx.app_state, "_mcp_runtime", None)
        if runtime is None:
            return CommandResult(
                message="MCP runtime is not attached to this session (it starts with the REPL)."
            )
        tools = (
            sorted(
                tool.name
                for tool in ctx.app_state._tool_registry.get_all()
                if tool.name.startswith("mcp__")
            )
            if getattr(ctx.app_state, "_tool_registry", None)
            else []
        )
        lines = [runtime.summary()]
        if tools:
            lines.append("tools: " + ", ".join(tools))
        return CommandResult(message="\n".join(lines))


class CacheCommand(SlashCommand):
    name = "cache"
    description = "Show prompt-cache hit rate and prefix stability"
    aliases = ["kv"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        monitor = getattr(ctx.app_state, "_cache_monitor", None)
        if monitor is None:
            return CommandResult(
                message="Cache monitor is not attached to this session (it starts with the REPL)."
            )
        return CommandResult(message=monitor.render())


class TodosCommand(SlashCommand):
    name = "todos"
    description = "Show the session task list"
    aliases = ["todo"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.todo_engine import TodoStore

        store = TodoStore(ctx.app_state.todo_state)
        return CommandResult(message=store.render(detail=True))


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
        note = (
            " Its snapshot is gone, so the messages will be replayed from the journal."
            if getattr(latest, "recovered", False)
            else ""
        )
        return CommandResult(
            message=f"Session {latest.session_id} will be resumed on next start.{note}"
        )


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


class AuditCommand(SlashCommand):
    """Show the tool-execution audit chain and whether it still verifies.

    The log is written by ``core.audit``: one hash-chained line per tool
    request, result, or refusal. ``verify`` re-walks the chain and compares its
    tip against the out-of-band anchor, so a hand-edited or truncated log is
    reported rather than silently trusted.
    """

    name = "audit"
    description = "Show the tool audit chain (and verify it)"
    aliases = ["trail"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import shlex

        from openlaoke.core import audit

        if not audit.audit_enabled():
            return CommandResult(
                success=False,
                message="Audit logging is disabled (OPENLAOKE_NO_AUDIT=1).",
            )
        args = shlex.split(ctx.args or "")
        limit = 10
        if args:
            try:
                limit = max(1, min(500, int(args[0])))
            except ValueError:
                return CommandResult(success=False, message="Usage: /audit [count]")
        log = audit.get_audit(ctx.app_state)
        if log is None:  # pragma: no cover - guarded by audit_enabled above
            return CommandResult(success=False, message="Audit logging is disabled.")
        text = log.status_text(limit=limit)
        others = [name for name, _size in audit.list_logs(str(log.directory)) if name != log.name]
        if others:
            text += (
                f"\n({len(others)} other session chain(s) in {log.directory}; "
                "each session writes its own)"
            )
        return CommandResult(success=log.verify(), message=text)


class TranscriptCommand(SlashCommand):
    """Show the append-only journal that backs this session's messages.

    The snapshot (``<id>.json``) is rewritten on every save and is what the
    runtime loads; the journal costs one line per message and is what recovers
    the conversation when the snapshot is unreadable. This command is how you
    check that both exist and agree on how much happened.
    """

    name = "transcript"
    description = "Show the append-only session journal and its integrity"
    aliases = ["journal"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import shlex

        transcript = getattr(ctx.app_state, "_transcript", None)
        if transcript is None:
            return CommandResult(message="This session has no journal: it was never saved to disk.")
        args = shlex.split(ctx.args or "")
        limit = 10
        if args:
            try:
                limit = max(1, min(200, int(args[0])))
            except ValueError:
                return CommandResult(success=False, message="Usage: /transcript [count]")

        health = transcript.health()
        header, records = transcript.replay()
        lines = [
            f"Journal: {transcript.path}",
            f"  {health.render()}",
        ]
        if header:
            started = float(header.get("at") or 0.0)
            stamp = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(started)) if started else "unknown"
            )
            lines.append(
                f"  session {header.get('session_id') or '?'}  cwd {header.get('cwd') or '-'}  "
                f"model {header.get('model') or '-'}  started {stamp}"
            )
        for record in records[-limit:]:
            message = record.get("message", {})
            role = str(message.get("role", "?"))
            content = message.get("content")
            text = content if isinstance(content, str) else str(content or "")
            preview = " ".join(text.split())[:80]
            lines.append(f"  #{record.get('seq', '?'):<4} {role:<10} {preview}")
        return CommandResult(success=health.ok, message="\n".join(lines))


class ArtifactsCommand(SlashCommand):
    """Externalized tool output: what is stored, and how to reclaim it.

    Every oversized result writes a file here, and nothing else prunes them, so
    a long-lived checkout accumulates them without bound. Listing is read-only;
    pruning is explicit because the pointers in old sessions stop resolving.
    """

    name = "artifacts"
    description = "List stored tool-output files, or prune old ones"
    aliases = ["outputs"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import shlex

        from openlaoke.core.tool_output_store import (
            artifact_inventory,
            prune_artifacts,
            resolve_artifact_root,
        )

        args = shlex.split(ctx.args or "")
        base = resolve_artifact_root(ctx.app_state)

        if args and args[0].lower() in ("prune", "clean", "clear"):
            days = 30
            if len(args) > 1:
                try:
                    days = max(1, int(args[1]))
                except ValueError:
                    return CommandResult(success=False, message="Usage: /artifacts prune [days]")
            files, freed = prune_artifacts(
                root=base,
                max_age_days=days,
                # The running session's pointers must keep resolving even if its
                # first artifacts are older than the cutoff.
                keep_sessions={ctx.app_state.session_id},
            )
            return CommandResult(
                message=(
                    f"Removed {files} artifact file(s), {freed / 1024:.1f} KB, "
                    f"older than {days} day(s)."
                )
            )
        if args:
            return CommandResult(
                success=False, message="Usage: /artifacts  |  /artifacts prune [days]"
            )

        inventory = artifact_inventory(root=base)
        if not inventory:
            return CommandResult(message=f"No stored tool output in {base}.")
        total_files = sum(count for _name, count, _size in inventory)
        total_bytes = sum(size for _name, _count, size in inventory)
        lines = [
            f"{total_files} file(s), {total_bytes / 1024:.1f} KB in {base}",
        ]
        for name, count, size in inventory[:20]:
            lines.append(f"  {name:<24} {count:>4} file(s)  {size / 1024:>8.1f} KB")
        lines.append("('/artifacts prune 30' removes files older than 30 days)")
        return CommandResult(message="\n".join(lines))
