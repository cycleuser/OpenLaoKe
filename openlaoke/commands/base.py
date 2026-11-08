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
    description = "List saved sessions"
    aliases = ["ls-sessions"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.sessions import SessionManager

        manager = SessionManager()
        sessions = manager.list_sessions()
        if not sessions:
            return CommandResult(message="No saved sessions yet.")
        rows = []
        for info in sessions[:25]:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(info.created_at))
            current = " *" if info.session_id == ctx.app_state.session_id else "  "
            rows.append(
                f"{current}{info.session_id}  {stamp}  {info.message_count:>3} msg  "
                f"{info.model}  {info.cwd or '-'}"
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
    description = "Show, search or clear this project's stored notes"
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
        entries = store.recall(arg, limit=8)
        return CommandResult(message=store.render(entries) if entries else "No matching notes.")


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
    description = "Show the local schedule"
    aliases = ["cron"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.scheduler import get_scheduler

        scheduler = get_scheduler(ctx.app_state)
        enabled = bool(getattr(getattr(ctx, "app_config", None), "enable_scheduler", False))
        note = (
            "" if enabled else "\n(scheduler loop is off: set enable_scheduler=true in the config)"
        )
        return CommandResult(message=scheduler.render() + note)


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
