"""REPL loop - the main interaction loop.

Improved with:
- Streaming output (character-by-character rendering)
- Rich-themed permission prompts (replacing bare input())
- Real-time token counter during generation
- Theme-aware colors via ThemeManager
- Expandable tool result display
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import gc
import json
import os
import re
import signal
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from openlaoke.commands.registry import get_command, parse_command, register_all
from openlaoke.core.cache_guard import CacheGuard
from openlaoke.core.cache_monitor import CacheMonitor
from openlaoke.core.config_wizard import get_proxy_url
from openlaoke.core.engine import assistant_turn, tool_result_message
from openlaoke.core.mcp_runtime import MCPRuntime
from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.core.prompt_input import (
    PromptSessionManager,
    run_lang_picker_async,
    run_model_picker_async,
)
from openlaoke.core.state import AppState
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.tools.register import register_all_tools
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    PermissionResult,
    StreamEventType,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from openlaoke.types.providers import MultiProviderConfig
from openlaoke.utils.theme import ThemeManager

# Hoisted regexes used in the agent loop (avoid re-compiling per iteration).
_CODING_TRIGGERS = re.compile(
    r"(write|code|implement|create|build|fix|debug|edit|modify|change|update|"
    r"add|remove|delete|refactor|test|run|install|deploy|commit|push|pull|merge|"
    r"search|find|check|look|read|show|list|explain|how|make|generate)",
    re.IGNORECASE,
)
_CONVERSATION_ONLY = re.compile(
    r"^(hi|hello|hey|who are you|what can you do|你会做什么|你能做什么|"
    r"你是谁|你好|谢谢|thank|help|what is|what are|天气|时间|日期)$",
    re.IGNORECASE,
)
_KV_PATTERN = re.compile(r"(\w[\w_]*)\s*=\s*")


_BRACE_CALL = re.compile(r"\b(\w+)\s*\{(.+)\}", re.DOTALL)
_BRACE_KV = re.compile(r"(\w+)\s*:\s*<\|[^|]*\|[^>]*>")


@dataclass
class StreamedTurn:
    """What one streamed provider response produced (see _stream_provider_turn)."""

    content: str = ""
    reasoning: str = ""
    tool_uses: list[Any] = field(default_factory=list)
    usage: Any = None
    cost: Any = None
    stream_error: str | None = None
    token_count: int = 0
    reasoning_count: int = 0
    elapsed: float = 0.0


class REPL:
    """Main REPL loop for OpenLaoKe."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.console = Console(force_terminal=True)
        self.registry = ToolRegistry()
        # Tools like Batch resolve their siblings through the session, not a
        # parameter, so the registry has to be reachable from AppState.
        app_state._tool_registry = self.registry
        self.api: MultiProviderClient | None = None
        self._running = False
        self._last_thinking: str = ""
        self._thinking_duration: float = 0.0
        self._turn_start: float = 0.0
        self._artifact_written: set[str] = set()
        self._artifact_verified = False
        self._force_final = False
        self._turn_failures: list[str] = []

        self._reset_terminal()
        self._active_tasks: set[asyncio.Task] = set()
        self.multi_provider_config: MultiProviderConfig | None = None
        self.app_config: Any = None
        self._proxy: str | None = None
        self._prompt_manager = PromptSessionManager(multiline=False)
        self._current_task_id: str | None = None
        self._theme = ThemeManager(app_state.theme)

        from openlaoke.core.hook_system import HookRegistry
        from openlaoke.core.small_model_optimizations import (
            ReadLoopTracker,
            SmallModelGuard,
            TerminalOutputCompressor,
            ToolCallValidator,
        )

        self._read_loop_tracker = ReadLoopTracker()
        self._guard: SmallModelGuard | None = None
        self._budget: Any = None
        from openlaoke.core.result_ledger import ResultLedger

        self._ledger = ResultLedger()
        self._poke_budget = 3
        self._poke_signature = ""
        self._output_compressor = TerminalOutputCompressor()
        self._tool_validator = ToolCallValidator()
        self._hook_system = HookRegistry.get()
        self._world_sensor: Any = None
        self._cache_guard = CacheGuard(app_state)
        app_state._cache_guard = self._cache_guard
        self._cache_monitor = CacheMonitor()
        app_state._cache_monitor = self._cache_monitor
        self._mcp_runtime = MCPRuntime()
        self._scheduler_task: asyncio.Task | None = None
        app_state._mcp_runtime = self._mcp_runtime
        self._last_usage: Any = None

        # Interrupt + queued-input state (B1/B2 harness fixes):
        # - _agent_task: the running agent loop, cancellable via Ctrl+C
        # - _interrupt_requested: set by Ctrl+C, honoured between iterations
        # - _input_queue: messages typed while the agent runs; drained at
        #   safe points (after tool batches) so mid-run corrections land.
        self._agent_task: asyncio.Task | None = None
        self._interrupt_requested = False
        self._input_queue: list[str] = []

        register_all()
        register_all_tools(self.registry)
        self.registry.freeze()  # Byte-stable tool schemas for the session
        self._tool_validator.set_tools(self.registry)

        self._register_cleanup()

    def _register_cleanup(self) -> None:
        """Register cleanup handlers for model unload on exit/crash/signal."""

        def _cleanup() -> None:
            gc.collect()

        atexit.register(_cleanup)

        def _signal_handler(signum: int, frame: Any) -> None:
            if signum == signal.SIGINT and self._agent_task and not self._agent_task.done():
                # First Ctrl+C while an agent runs: interrupt it, keep the REPL.
                self._interrupt_requested = True
                self._agent_task.cancel()
                return
            _cleanup()
            os._exit(0)

        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, _signal_handler)

    @staticmethod
    def _reset_terminal() -> None:
        """Reset terminal state: disable mouse tracking, show cursor, etc."""
        import sys

        # Disable mouse tracking (all modes)
        sys.stdout.write("\x1b[?1000l")  # VT200 tracking
        sys.stdout.write("\x1b[?1002l")  # button-event tracking
        sys.stdout.write("\x1b[?1003l")  # any-event tracking
        sys.stdout.write("\x1b[?1006l")  # SGR extended mode
        # Show cursor
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()

    def _c(self, name: str) -> str:
        return self._theme.color(name)

    def _t(self, key: str) -> str:
        from openlaoke.core.i18n import get_tui_text

        return get_tui_text(key, getattr(self.app_state, "language", "en"))

    async def run(self) -> None:
        self._running = True
        self._prompt_manager.get_session()
        self._print_banner()
        self._print_welcome()
        self._warn_untrusted_project_local()

        if self.app_config:
            self.app_state.language = getattr(self.app_config, "language", "en")

        config = self.multi_provider_config or self.app_state.multi_provider_config
        if not config:
            self.console.print(f"[bold {self._c('error')}]{self._t('no_provider_error')}[/]")
            self.console.print(self._t("run_config_hint"))
            return

        if self.app_config:
            self._proxy = get_proxy_url(self.app_config)

        await self._probe_local_providers(config)
        self.api = MultiProviderClient(config, proxy=self._proxy)

        await self._start_mcp()
        self._start_scheduler()

        try:
            # A resumed session that was working through a queue keeps working:
            # the queue survives on disk precisely so a crash or a reboot does
            # not silently end the shift with half the tasks unrun.
            if (
                getattr(self.app_state, "insomnia_mode", False)
                and self.app_state.insomnia_task_queue
            ):
                self.console.print(
                    f"  [{self._c('muted')}]{self._t('insomnia_resuming')}[/] "
                    f"({len(self.app_state.insomnia_task_queue)} task(s))"
                )
                await self._insomnia_drain()
            while self._running:
                await self._handle_input()
        except (KeyboardInterrupt, EOFError):
            self.console.print(f"\n[{self._c('warning')}]{self._t('goodbye')}[/]")
        finally:
            for task in self._active_tasks:
                task.cancel()
            await self._stop_scheduler()
            await self._stop_mcp()
            if self.api:
                await self.api.close()
            self._reset_terminal()

    def _warn_untrusted_project_local(self) -> None:
        """Say once why a project's own skills are not loading.

        Loading them is fail-closed (see core/trust.py), and silent fail-closed
        looks like a bug to the person who just wrote the skill.
        """
        from openlaoke.core.trust import skipped_project_dirs

        try:
            skipped = skipped_project_dirs(self.app_state.get_cwd())
        except OSError:
            return
        if not skipped:
            return
        self.console.print(
            f"  [{self._c('muted')}]{', '.join(skipped)} in this directory is not loaded "
            "until you trust it ('/trust on').[/]"
        )

    async def _start_mcp(self) -> None:
        """Start the configured MCP servers and add their tools.

        A server that fails is reported once and skipped: the session still
        starts, and the reason is available in `/mcp`.
        """
        config = self.app_config
        if config is None or not getattr(config, "enable_mcp", True):
            return
        servers = getattr(config, "mcp_servers", None) or {}
        if not servers:
            return

        added = await self._mcp_runtime.start(servers, self.registry)
        for name, reason in self._mcp_runtime.failures.items():
            self.console.print(f"  [{self._c('warning')}]MCP '{name}' unavailable: {reason}[/]")
        if not added:
            return
        self.registry.thaw()
        self.registry.freeze()
        self._tool_validator.set_tools(self.registry)
        self.console.print(
            f"  [{self._c('muted')}]MCP: {len(added)} tool(s) from "
            f"{len(self._mcp_runtime.clients)} server(s)[/]"
        )

    async def _probe_local_providers(self, config: Any) -> None:
        """Hide unreachable local providers and tell the user how to remove them."""
        from openlaoke.types.providers import probe_local_providers

        results = await probe_local_providers(config.providers)
        offline = [name for name, reachable in results.items() if not reachable]
        if not offline:
            return
        names = ", ".join(offline)
        self.console.print(f"\n[{self._c('warning')}]Local provider(s) offline:[/] {names}")
        self.console.print(
            f"  [{self._c('muted')}]Remove with /model prune, "
            f"or start the server and run /model probe.[/]"
        )

    def _start_scheduler(self) -> None:
        """Start the local schedule loop when the config enables it."""
        if not self.app_config or not getattr(self.app_config, "enable_scheduler", False):
            return
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def _stop_scheduler(self) -> None:
        task = getattr(self, "_scheduler_task", None)
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        self._scheduler_task = None

    async def _scheduler_loop(self, interval: float = 30.0) -> None:
        from openlaoke.core.scheduler import get_scheduler

        while self._running:
            await asyncio.sleep(interval)
            scheduler = get_scheduler(self.app_state)
            due = scheduler.due()
            for entry in due[:10]:
                started = time.time()
                status, detail = "ok", ""
                if entry.command:
                    try:
                        from openlaoke.core.task import get_task_manager

                        manager = get_task_manager(self.app_state)
                        await manager.run_bash(
                            entry.command,
                            description=f"scheduled: {entry.name}",
                            auto_background_ms=0.0,
                        )
                        notice = f"[scheduled command '{entry.name}' started in the background]"
                    except Exception as exc:  # noqa: BLE001 - one job must not stop the rest
                        # Without this, an exception here ends ``_scheduler_loop``
                        # and every later schedule silently stops firing.
                        status, detail = "error", f"{type(exc).__name__}: {exc}"
                        notice = f"[scheduled command '{entry.name}' failed: {exc}]"
                elif entry.prompt:
                    bot_notice = await self._run_bot_routine(entry)
                    if bot_notice is None:
                        notice = f"[scheduled reminder '{entry.name}': {entry.prompt}]"
                        self._input_queue.append(notice)
                    else:
                        notice = bot_notice
                else:
                    notice = f"[scheduled reminder '{entry.name}': {entry.prompt}]"
                    self._input_queue.append(notice)
                scheduler.mark_run(
                    entry,
                    status=status,
                    detail=detail,
                    started_at=started,
                    duration_ms=int((time.time() - started) * 1000),
                )
                # The notice can carry a bot's own words, brackets included, so
                # it is escaped: unescaped, Rich reads "[...]" as markup and the
                # reply silently disappears from the line.
                from rich.markup import escape

                self.console.print(f"  [{self._c('muted')}]{escape(notice)}[/]")

    async def _stop_mcp(self) -> None:
        with contextlib.suppress(Exception):
            await self._mcp_runtime.stop()

    async def _handle_input(self) -> None:
        self.console.print()
        result = await self._prompt_manager.get_user_input()

        if result.is_exit:
            self._running = False
            return

        if result.is_picker:
            selection = await run_model_picker_async()
            if selection:
                self._handle_model_switch(selection)
            return

        if result.is_lang_picker:
            lang = await run_lang_picker_async(self.app_state.language)
            if lang:
                self._handle_lang_switch(lang)
            return

        if result.is_toggle_thinking:
            self._show_thinking_full()
            return

        user_input = result.text
        if not user_input:
            return

        if user_input.startswith("model_switch:"):
            self._handle_model_switch(user_input[len("model_switch:") :])
            return

        if user_input.startswith("/"):
            from openlaoke.core.skill_system import load_skill

            parts = user_input.split(None, 1)
            potential_name = parts[0][1:] if parts else ""
            skill_args = parts[1] if len(parts) > 1 else ""

            skill = load_skill(potential_name)
            if skill:
                if (
                    hasattr(self.app_state, "active_skills")
                    and potential_name not in self.app_state.active_skills
                ):
                    self.app_state.active_skills.append(potential_name)

                self.console.print(
                    f"[{self._c('success')}]{self._t('skill_activated')} {skill.name}[/]"
                )
                if skill.description:
                    desc = skill.description[:100]
                    if len(skill.description) > 100:
                        desc += "..."
                    self.console.print(f"  [{self._c('muted')}]{desc}[/]")

                if skill_args:
                    self.console.print()
                    await self._handle_chat(skill_args)
                return

        cmd = parse_command(user_input)
        if cmd:
            name, args = cmd
            await self._handle_command(name, args)
            return

        if await self._handle_bot_input(user_input):
            return

        await self._handle_chat(user_input)

    async def _handle_bot_input(self, user_input: str) -> bool:
        """Route plain input to the active bot or room when bot mode is on."""
        from openlaoke.core.bot_mode import get_bot_mode, slug

        mode = get_bot_mode(self.app_state)
        if not mode.enabled:
            return False

        def stream(text: str) -> None:
            self.console.print(text, end="", markup=False)

        try:
            if mode.active_room:
                turns = await mode.room_send(mode.active_room, user_input)
                if not turns:
                    self.console.print(
                        f"[{self._c('muted')}](nobody in #{mode.active_room} had anything to add)[/]"
                    )
                for turn in turns:
                    self.console.print(
                        f"\n[{self._c('accent')}]@{slug(turn.member)}:[/] {turn.text}"
                    )
            else:
                profile = mode.require_bot(mode.active_bot)
                self.console.print(f"[{self._c('muted')}]@{slug(profile.name)} is thinking...[/]")
                reply = await mode.ask(profile.name, user_input, on_text=stream)
                if reply:
                    self.console.print()
                else:
                    self.console.print(
                        f"[{self._c('muted')}](@{slug(profile.name)} stayed silent)[/]"
                    )
        except ValueError as exc:
            self.console.print(f"[{self._c('error')}]{exc}[/]")
            return True

        await self._deliver_bot_inbox(mode)
        return True

    async def _deliver_bot_inbox(self, mode: Any) -> None:
        """Run messages bots left for each other and print the replies."""
        from openlaoke.core.bot_mode import slug

        try:
            delivered = await mode.drain()
        except Exception as exc:  # noqa: BLE001 - delivery must not break the REPL
            self.console.print(f"  [{self._c('warning')}]bot delivery failed: {exc}[/]")
            return
        for item in delivered:
            self.console.print(
                f"  [{self._c('muted')}]🔔 @{slug(item['bot'])} <- @{slug(item['from'])}[/]"
            )
            body = item.get("reply") or "(stayed silent)"
            self.console.print(f"    {body}")

    async def _run_bot_routine(self, entry: Any) -> str | None:
        """Run a schedule entry that belongs to a bot; None if it is a plain reminder."""
        from openlaoke.core.bot_mode import get_bot_mode

        mode = get_bot_mode(self.app_state)
        bot_name = mode.routine_bot(entry.name)
        profile = mode.get_bot(bot_name) if bot_name else None
        if profile is None:
            return None
        reply = await mode.ask(profile.name, f"[routine] {entry.prompt}")
        await self._deliver_bot_inbox(mode)
        return f"[routine for @{bot_name}] " + (reply or "(the bot stayed silent)")

    async def _handle_command(self, name: str, args: str) -> None:
        from openlaoke.commands.base import CommandContext

        command = get_command(name)
        if not command:
            from openlaoke.core.prompt_templates import expand_prompt_template

            expanded = expand_prompt_template(name, args)
            if expanded is not None:
                self.console.print(expanded)
                self.console.print()
                await self._handle_chat(expanded)
                return
            self.console.print(f"[{self._c('error')}]{self._t('unknown_command')} /{name}[/]")
            self.console.print(self._t("type_help"))
            return

        ctx = CommandContext(app_state=self.app_state, args=args)
        result = await command.execute(ctx)

        if result.message:
            self.console.print(result.message)

        if result.should_exit:
            self._running = False
        if result.should_clear:
            self.console.clear()

        submit_text = getattr(result, "submit_text", "")
        if submit_text:
            self.console.print()
            await self._handle_chat(submit_text)

    def _handle_model_switch(self, selection: str) -> None:
        if "/" not in selection:
            return
        provider_name, model_name = selection.split("/", 1)

        config = self.app_state.multi_provider_config or self.multi_provider_config
        if not config:
            return

        provider = config.providers.get(provider_name)
        if not provider:
            self.console.print(
                f"[{self._c('error')}]{self._t('provider_not_found')} {provider_name}[/]"
            )
            return

        config.active_provider = provider_name
        config.active_model = model_name
        self.app_state.session_config.model = model_name

        if self.api:
            self.api.config = config

        from openlaoke.utils.config import load_config, save_config

        app_config = load_config()
        app_config.providers.active_provider = provider_name
        app_config.providers.active_model = model_name
        save_config(app_config)

        self.console.print(
            f"[{self._c('success')}]{self._t('switched_to')} {provider_name}/{model_name}[/]"
        )

    def _handle_lang_switch(self, lang: str) -> None:
        from openlaoke.core.i18n import SUPPORTED_LANGUAGES, get_tui_text
        from openlaoke.utils.config import load_config, save_config

        if lang not in SUPPORTED_LANGUAGES:
            self.console.print(f"[{self._c('error')}]Unsupported language: {lang}[/]")
            return

        self.app_state.language = lang

        app_config = load_config()
        app_config.language = lang
        save_config(app_config)

        if self._cache_guard:
            self._cache_guard.invalidate()

        lang_name = SUPPORTED_LANGUAGES[lang]
        self.console.print(
            f"[{self._c('success')}]{get_tui_text('language_set', lang)} {lang_name} ({lang})[/]"
        )

    async def _handle_chat(self, user_input: str) -> None:
        if self._agent_task and not self._agent_task.done():
            self._input_queue.append(user_input)
            self.console.print(
                f"  [{self._c('muted')}]Queued — will be processed after the current step.[/]"
            )
            return

        self.app_state.is_running = True
        self.app_state.set_error(None)
        self._current_task_id = None
        self._interrupt_requested = False

        user_msg = UserMessage(role=MessageRole.USER, content=user_input)
        self.app_state.add_message(user_msg)
        self.app_state._persist()

        try:
            self._agent_task = asyncio.current_task()
            await self._run_api_loop()
            if self._interrupt_requested:
                self._patch_dangling_tool_calls()
                self.console.print(f"[{self._c('warning')}]Interrupted — context preserved.[/]")
        except Exception as e:
            from rich.markup import escape

            # An exception message is arbitrary text; unescaped brackets either
            # vanish from the display or raise inside the error handler.
            self.console.print(f"\n[bold {self._c('error')}]Error:[/] {escape(str(e))}")
            self.app_state.set_error(str(e))
        finally:
            self._agent_task = None
            self.app_state.is_running = False

        while self._input_queue and not self._interrupt_requested:
            queued = self._input_queue.pop(0)
            self.console.print(f"[{self._c('muted')}]Processing queued message...[/]")
            await self._handle_chat(queued)
            return

        if (
            not self._interrupt_requested
            and getattr(self.app_state, "insomnia_mode", False)
            and not getattr(self, "_insomnia_draining", False)
        ):
            await self._insomnia_drain()

    # -- insomnia mode ------------------------------------------------------

    @property
    def _insomnia_log(self) -> Any:
        from openlaoke.core.insomnia import InsomniaLog, log_path_for

        path = log_path_for(self.app_state)
        existing = getattr(self, "_insomnia_log_obj", None)
        if existing is None or getattr(existing, "path", "") != path:
            existing = InsomniaLog(path)
            self._insomnia_log_obj = existing
        return existing

    async def _insomnia_drain(self) -> int:
        """Work through the queue without asking for input; returns task count.

        Only one drain runs at a time. Each task's turn calls back into
        ``_handle_chat``, which calls back here, so the flag keeps the loop at one
        level instead of one stack frame per task: a queue of a thousand tasks
        would otherwise end in a RecursionError long before it ended in work.
        """
        from openlaoke.core.insomnia import HISTORY_LIMIT, next_task, trim_history

        if getattr(self, "_insomnia_draining", False):
            return 0
        if not getattr(self.app_state, "insomnia_mode", False):
            return 0

        self._insomnia_draining = True
        log = self._insomnia_log
        completed = 0
        started_with = len(self.app_state.insomnia_task_queue or [])
        try:
            if started_with:
                log.append("drain_start", queued=started_with)
            while self._running and not self._interrupt_requested:
                task = next_task(self.app_state)
                if task is None:
                    # The scheduler is the other source of unattended work: a
                    # reminder that fires at 03:00 has to start a turn, not wait
                    # for someone to press enter. Its loop appends the notice to
                    # the input queue, so taking it from there is the same path
                    # a typed message takes.
                    if self._input_queue:
                        notice = str(self._input_queue.pop(0))
                        task = {"prompt": notice, "attempts": 1}
                        log.append("scheduled_wake", prompt=notice[:200])
                    elif self._insomnia_should_idle():
                        await asyncio.sleep(30.0)
                        continue
                    else:
                        break
                head = str(task.get("prompt") or "")[:200]
                log.append(
                    "task_start", index=completed + 1, attempt=task.get("attempts"), prompt=head
                )
                ok, error = await self._insomnia_run_task(task)
                if ok:
                    completed += 1
                    log.append("task_done", index=completed, prompt=head)
                else:
                    log.append("task_failed", index=completed + 1, prompt=head, error=error[:300])
                    self.console.print(
                        f"  [{self._c('error')}]insomnia: task given up after "
                        f"{getattr(self.app_state, 'insomnia_max_retries', 0) or 8} attempt(s): "
                        f"{error[:120]}[/]"
                    )
                dropped = trim_history(self.app_state, HISTORY_LIMIT)
                if dropped:
                    log.append("history_trimmed", dropped=dropped)
        finally:
            self._insomnia_draining = False

        if started_with:
            log.append("drain_end", completed=completed)
        # A drain that had nothing to do is the normal case on every ordinary
        # turn while the mode is on; announcing it would print a line per
        # message for the rest of the session.
        if started_with and self._running and not self._interrupt_requested:
            remaining = len(self.app_state.insomnia_task_queue or [])
            self.console.print(
                f"  [{self._c('muted')}]insomnia: {completed} task(s) done, "
                f"{remaining} still queued. The mode stays on: `/insomnia add <task>` "
                f"or a new message keeps going unattended.[/]"
            )
        return completed

    def _insomnia_should_idle(self) -> bool:
        """True when a running schedule will produce work, so waiting is useful.

        Only when this process actually started the scheduler: idling for a
        schedule nobody is watching would be a sleep with no wake-up.
        """
        if getattr(self, "_scheduler_task", None) is None:
            return False
        try:
            from openlaoke.core.scheduler import get_scheduler

            entries = get_scheduler(self.app_state).entries
        except Exception:
            return False
        return any(entry.enabled and entry.next_run for entry in entries)

    async def _insomnia_run_task(self, task: dict[str, Any]) -> tuple[bool, str]:
        """Run one queued task, retrying a failed turn instead of giving up.

        The turn machinery already reports its own failures; what it does not do
        is try again. A rate limit, a dropped connection or a provider 502 that
        arrives at 03:00 ends the turn, and with nobody at the keyboard that is
        the end of the run. Each retry waits longer than the last.
        """
        from openlaoke.core.insomnia import RETRY_LIMIT, backoff_seconds

        prompt = str(task.get("prompt") or "")
        attempt = int(task.get("attempts") or 1)
        limit = int(getattr(self.app_state, "insomnia_max_retries", 0) or RETRY_LIMIT)
        log = self._insomnia_log

        while True:
            await self._handle_chat(prompt)
            error = str(getattr(self.app_state, "error_message", "") or "")
            if not error or self._interrupt_requested:
                return True, ""
            if attempt > limit:
                return False, error
            delay = backoff_seconds(attempt)
            log.append("retry", attempt=attempt, delay=delay, error=error[:300])
            self.console.print(
                f"  [{self._c('warning')}]insomnia: {error[:100]} (retry "
                f"{attempt}/{limit} in {delay:.0f}s)[/]"
            )
            await asyncio.sleep(delay)
            attempt += 1

    def _collect_artifacts(self) -> dict[str, Any]:
        artifacts: dict[str, Any] = {
            "content": "",
            "output_files": [],
        }

        for msg in reversed(self.app_state.messages):
            if msg.role == MessageRole.ASSISTANT and msg.content:
                artifacts["content"] += msg.content + "\n\n"

        cwd = self.app_state.get_cwd()
        common_outputs = ["Article.md", "article.md", "README.md", "output.md"]
        for filename in common_outputs:
            filepath = f"{cwd}/{filename}"
            if os.path.exists(filepath):
                artifacts["output_files"].append(filepath)

        import glob as glob_mod

        for pattern in ["*.svg", "*.png", "*.pdf"]:
            files = glob_mod.glob(f"{cwd}/{pattern}")
            artifacts["output_files"].extend(files)

        return artifacts

    def _record_tool_result(self, tool_use_id: str, content: str) -> None:
        """Persist tool output so later turns keep its evidence."""
        self.app_state.add_message(
            SystemMessage(
                role=MessageRole.SYSTEM,
                content=content,
                subtype="tool_result",
                tool_use_id=tool_use_id,
            ),
            persist=False,
        )

    def _patch_dangling_tool_calls(self) -> None:
        """After an interrupt, synthesise tool results for any tool_call that
        never received one, so the message history stays provider-valid."""
        from openlaoke.types.core_types import MessageRole

        tool_call_ids: dict[str, bool] = {}
        for msg in self.app_state.messages:
            if msg.role == MessageRole.ASSISTANT:
                for tu in getattr(msg, "tool_uses", None) or []:
                    tool_call_ids[tu.id] = False
            elif isinstance(msg, SystemMessage) and msg.tool_use_id:
                tool_call_ids[msg.tool_use_id] = True

        for tool_use_id, answered in tool_call_ids.items():
            if not answered:
                self._record_tool_result(
                    tool_use_id,
                    "[Interrupted by user before this tool ran. State on disk may "
                    "be mid-change; re-check with Read/Bash before continuing.]",
                )
        self.app_state._persist()

    def _resolve_max_iterations(self) -> int:
        # An unattended run is not a turn with a tool-call budget: it is a shift.
        # The harness mode's 25-80 steps exist to keep a conversation snappy, and
        # stopping a queued task halfway through because of them is the reason
        # insomnia mode never finishes anything. This has to come before the
        # max_steps check: the CLI fills max_steps from the harness mode, so that
        # value is present in every real session. Only a typed --max-steps
        # outranks the mode.
        if getattr(self.app_state, "insomnia_mode", False) and not getattr(
            self.app_state, "max_steps_explicit", False
        ):
            from openlaoke.core.insomnia import MAX_ITERATIONS

            configured = getattr(self.app_state, "insomnia_max_iterations", 0) or 0
            return max(1, int(configured) or MAX_ITERATIONS)
        steps = getattr(self.app_state, "max_steps", 0) or 0
        if steps > 0:
            return steps
        # No explicit override: honour the active harness mode so the
        # interactive loop respects --mode instead of a fixed guess.
        from openlaoke.core.harness_modes import get_mode

        return get_mode(getattr(self.app_state, "harness_mode", None)).max_steps

    def _todo_auto_continue(self, messages: list[Any]) -> bool:
        """Wake the model when it stops with tasks still open.

        The budget is per task-list state, not per session: any change to the
        list refills it, and an unchanged list gets at most three pokes so a
        stuck model cannot burn turns forever.  Blocked tasks never consume it.
        """
        from openlaoke.core.todo_engine import MAX_AUTO_POKES, TodoStore

        store = TodoStore(self.app_state.todo_state)
        open_items = store.open_items()
        if not open_items:
            self._poke_signature = ""
            self._poke_budget = MAX_AUTO_POKES
            return False

        signature = store.signature()
        if signature != self._poke_signature:
            self._poke_signature = signature
            self._poke_budget = MAX_AUTO_POKES
        if self._poke_budget <= 0:
            return False
        if not store.actionable_items() and not any(item.external_blocker for item in open_items):
            return False

        self._poke_budget -= 1
        prompt = store.digest()
        messages.append({"role": "user", "content": prompt, "system_injected": True})
        self.app_state.add_message(
            UserMessage(role=MessageRole.USER, content=prompt), persist=False
        )
        self.console.print(
            f"  [{self._c('muted')}](auto-continue: {len(open_items)} task(s) open, "
            f"{self._poke_budget} reminder(s) left)[/]"
        )
        return True

    def _note_context_usage(self, usage: Any) -> None:
        """Record what the provider says this turn actually occupied."""
        if usage is None:
            return
        total = sum(
            int(getattr(usage, name, 0) or 0)
            for name in ("input_tokens", "output_tokens", "cache_read_input_tokens")
        )
        if total <= 0:
            return
        self.app_state.compact_state["used_tokens"] = total
        self.app_state.compact_state["used_source"] = "provider_usage"
        self._last_usage = usage
        if self._cache_monitor is not None:
            self._cache_monitor.observe(usage, model=self.app_state.session_config.model)

    def _drain_task_notices(self) -> list[str]:
        """Report background tasks that finished since the last turn.

        Without this the model has to remember to poll, which it does not; the
        notice costs one short line and turns a silently finished job into
        something the next turn can act on.
        """
        seen = getattr(self, "_notified_tasks", None)
        if seen is None:
            seen = set()
            self._notified_tasks = seen

        notices: list[str] = []
        for task in self.app_state.get_all_tasks():
            if task.id in seen or not task.end_time:
                continue
            status = task.status.value
            if status in ("running", "pending"):
                continue
            seen.add(task.id)
            code = "" if task.exit_code is None else f", exit code {task.exit_code}"
            notices.append(
                f"[background task {task.id} {status}{code}: {task.description[:80]}. "
                f"Read it with Bg(action='tail', task_id='{task.id}').]"
            )
        return notices

    def _memory_digest(self) -> str:
        """A short index of stored notes, so the model knows what it can ask for.

        Only ids and one-line previews go in the prompt: full notes come back
        through Memory(recall=...), which keeps the fixed cost small however
        much has accumulated.
        """
        from openlaoke.core.memory_store import get_store

        try:
            store = get_store(self.app_state)
        except OSError:
            return ""
        # Same rule as retrieval, or the index contradicts it: a superseded note
        # would keep being named every turn, and a note the user typed would sit
        # below one the agent guessed.
        entries = store.index_entries(limit=8)
        if not entries:
            return ""
        rows = []
        for entry in entries:
            marker = "" if entry.authority == "agent" else f"[{entry.authority}] "
            rows.append(f"- {entry.id} {marker}{entry.text[:90]}")
        return (
            "<memory-index>\n"
            + "\n".join(rows)
            + "\n(call Memory(action='recall', text=...) for the full note)\n"
            + "</memory-index>"
        )

    async def _fire_turn_hook(self, hook_type: str, **fields: Any) -> None:
        """Run a turn-level hook; a hook never gets to break the loop."""
        if not self._hook_system.has_hooks(hook_type):
            return
        from openlaoke.core.hook_system import HookInput

        payload = HookInput(
            session_id=self.app_state.session_id,
            provider_name=self.app_state.multi_provider_config.active_provider
            if self.app_state.multi_provider_config
            else "",
            model_name=self.app_state.session_config.model,
            metadata=dict(fields),
        )
        await self._hook_system.execute_hooks_async(hook_type, payload)

    def _note_artifact_result(self, tool_use: ToolUseBlock, result: Any) -> None:
        """Arm the final-turn gate once a written file has run successfully."""
        from openlaoke.core.engine import artifact_basename, verifies_artifact

        if getattr(result, "is_error", False):
            return
        if tool_use.name in ("Write", "Edit"):
            path = str(tool_use.input.get("file_path") or "")
            if path:
                self._artifact_written.add(artifact_basename(path))
        elif tool_use.name == "Bash" and verifies_artifact(
            str(tool_use.input.get("command") or ""), self._artifact_written
        ):
            self._artifact_verified = True
            self._force_final = True

    def _note_tool_failure(self, tool_name: str, content: str) -> None:
        """Remember a failed call for the end-of-turn report, not the transcript."""
        first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
        if len(first_line) > 120:
            first_line = first_line[:117] + "..."
        # ``getattr`` covers a REPL assembled by tests via ``__new__``, which
        # skips __init__ and therefore has no list yet.
        failures = self._turn_failures = getattr(self, "_turn_failures", [])
        failures.append(f"{tool_name}: {first_line or '(no message)'}")

    def _report_turn_failures(self) -> None:
        """Say which calls failed, in the harness's own words, at turn end.

        The closing message is the model's account of what happened, and a
        cheerful "done" after three failed edits reads as success. This block is
        printed by the harness after that message, so it cannot be edited out.
        """
        failures = getattr(self, "_turn_failures", None)
        if not failures:
            return
        from rich.markup import escape

        unique = list(dict.fromkeys(failures))
        self.console.print()
        self.console.print(f"  [{self._c('error')}]{len(unique)} tool call(s) failed this turn:[/]")
        for line in unique[:5]:
            self.console.print(f"  [{self._c('muted')}]- {escape(line)}[/]")
        if len(unique) > 5:
            self.console.print(f"  [{self._c('muted')}]- ... {len(unique) - 5} more[/]")

    async def _stream_provider_turn(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> StreamedTurn:
        """Stream one provider response, accumulating text/reasoning/tool calls.

        Prints the live status line and the final tokens/tps summary as UI side
        effects, but never raises: a transport error is returned as
        ``stream_error`` for the caller to surface, exactly as the old inline
        code did.
        """
        turn = StreamedTurn()
        if self.api is None:
            turn.stream_error = "No API client configured"
            return turn
        api = self.api
        start_time = time.time()
        self._turn_start = start_time
        status_text = self._build_streaming_display("", 0, 0.0, 0.0)
        last_render = start_time

        try:
            with Live(
                status_text, console=self.console, refresh_per_second=20, transient=True
            ) as live:
                async for chunk in api.stream_message(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                    model=self.app_state.session_config.model,
                    thinking_budget=self.app_state.session_config.thinking_budget,
                    reasoning_effort=self.app_state.session_config.reasoning_effort,
                ):
                    if chunk.event_type == StreamEventType.TEXT:
                        turn.content += chunk.text
                        turn.token_count += 1
                    elif chunk.event_type == StreamEventType.REASONING:
                        turn.reasoning += chunk.text
                        turn.reasoning_count += 1
                    elif chunk.event_type == StreamEventType.TOOL_CALL_START:
                        try:
                            args = (
                                json.loads(chunk.tool_call_arguments)
                                if chunk.tool_call_arguments
                                else {}
                            )
                        except json.JSONDecodeError:
                            args = {}
                        turn.tool_uses.append(
                            ToolUseBlock(
                                id=chunk.tool_call_id,
                                name=chunk.tool_call_name,
                                input=args,
                            )
                        )
                    elif chunk.event_type == StreamEventType.USAGE:
                        if chunk.usage:
                            turn.usage = chunk.usage
                        if chunk.cost:
                            turn.cost = chunk.cost

                    # Rebuild at most ~25 times a second (rich caps redraws anyway).
                    now = time.time()
                    if now - last_render >= 0.04:
                        last_render = now
                        elapsed = max(now - start_time, 0.01)
                        shown = turn.token_count or turn.reasoning_count
                        tps = shown / elapsed
                        live.update(
                            self._build_streaming_display(
                                turn.content,
                                shown,
                                tps,
                                elapsed,
                                reasoning=not turn.content and bool(turn.reasoning),
                            )
                        )
        except httpx.HTTPStatusError as e:
            reason = ""
            with contextlib.suppress(Exception):
                reason = (e.response.text or "").strip()[:300]
            turn.stream_error = f"API {e.response.status_code}"
            if reason:
                turn.stream_error += f": {reason}"
        except Exception as e:  # noqa: BLE001 - surfaced via stream_error
            turn.stream_error = str(e)[:200]

        turn.elapsed = max(time.time() - start_time, 0.01)
        shown_tokens = turn.token_count or turn.reasoning_count
        label = (
            "tokens"
            if turn.token_count
            else ("reasoning tokens" if turn.reasoning_count else "tokens")
        )
        tps = shown_tokens / turn.elapsed
        self.console.print(
            f"  [{self._c('muted')}]{shown_tokens} {label} · {tps:.0f} t/s · {turn.elapsed:.1f}s[/]"
        )
        if self.app_state.verbose:
            self.console.print(
                f"  [{self._c('muted')}]{self._format_context_composition(messages)}[/]"
            )
        return turn

    def _prepare_turn_context(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        context_limit: int | None,
        global_context_cap: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        """Prune/compact history to budget and build the tool list for a turn.

        Returns ``(messages, tools, model_size)``. ``messages`` may be a pruned
        replacement; ``tools`` is empty on the forced-final turn. Also records
        the cacheable-prefix fingerprint (so cache breaks are visible) and
        sanitizes tool schemas for small models.
        """
        from openlaoke.core.compact.fast_pruner import fast_prune, fast_prune_aggressive
        from openlaoke.core.small_model_optimizations import (
            SmallModelGuard,
            estimate_model_size_from_name,
            sanitize_tool_schema,
        )

        model_size = estimate_model_size_from_name(self.app_state.session_config.model)
        # Auto-enable caveman mode for tiny/small models (unless explicitly toggled)
        if model_size in ("tiny", "small"):
            self.app_state.caveman_mode = True
        if self._guard is None or self._guard.model_size != model_size:
            self._guard = SmallModelGuard(model_size=model_size)
        # Prefer the model's real context window from the catalog; fall back to
        # a size-based estimate for providers the catalog does not cover.
        fallback_ctx = {
            "tiny": 4096,
            "small": 8192,
            "medium": 16384,
            "large": 32768,
        }.get(model_size, 8192)
        from openlaoke.core.context_budget import estimate_messages_tokens, resolve_budget

        budget = resolve_budget(
            model_window=context_limit or fallback_ctx,
            session_cap=self.app_state.context_cap,
            global_cap=global_context_cap,
            used_tokens=estimate_messages_tokens(messages),
        )
        self._budget = budget
        self.app_state.compact_state["model_window"] = context_limit or fallback_ctx
        self.app_state.compact_state["used_tokens"] = budget.used_tokens
        self.app_state.compact_state["used_source"] = budget.source
        ctx_budget, keep_tail = budget.prune_targets()

        if len(messages) > 10:
            if model_size in ("tiny", "small"):
                prune_result = fast_prune_aggressive(messages, max_tokens=ctx_budget)
            else:
                prune_result = fast_prune(
                    messages, max_tokens=ctx_budget, keep_tail_tokens=keep_tail
                )
            if prune_result.tokens_after < prune_result.tokens_before:
                messages = prune_result.messages
                self.console.print(
                    f"  [{self._c('muted')}](context compacted: "
                    f"{prune_result.tokens_before} -> {prune_result.tokens_after} tokens)[/]"
                )
                if self.app_state.verbose:
                    self.console.print(
                        f"[{self._c('muted')}]Context pruned in {prune_result.elapsed_ms:.1f}ms[/]"
                    )

        tools = [] if self._force_final else self.registry.get_all_for_prompt()

        # Fingerprint the cacheable prefix every turn: a change here is what
        # makes the next request pay full price, and it is invisible in the UI.
        self._cache_monitor.note_request(
            model=self.app_state.session_config.model,
            system_prompt=system_prompt,
            tool_names=[str(defn.get("name", "")) for defn in tools],
            messages=messages,
        )

        # Apply cache_control markers for Anthropic providers
        if self.api:
            provider = self.api.config.get_active_provider() if self.api.config else None
            if provider and getattr(provider, "provider_type", None):
                from openlaoke.types.providers import ProviderType

                if provider.provider_type == ProviderType.ANTHROPIC:
                    messages = CacheGuard.apply_cache_markers(messages)

        for tool_def in tools:
            if "input_schema" in tool_def:
                tool_def["input_schema"] = sanitize_tool_schema(tool_def["input_schema"])

        return messages, tools, model_size

    async def _dispatch_tools(
        self,
        tool_uses: list[ToolUseBlock],
        messages: list[dict[str, Any]],
        failed_tool_calls: dict[str, int],
        max_repeat_calls: int,
    ) -> None:
        """Run this turn's tool calls: repair names, break repeat loops, dispatch.

        Read-only batches run concurrently; everything else runs in order. Each
        result is appended to ``messages`` and recorded, and a successful write
        feeds the artifact gate. Mutates ``messages`` and ``failed_tool_calls``
        in place, then persists once.
        """
        _all_readonly = all(self.registry.is_readonly(tu.name) for tu in tool_uses)
        if _all_readonly and len(tool_uses) > 1:
            results = await asyncio.gather(
                *[self._execute_tool(tu) for tu in tool_uses],
                return_exceptions=True,
            )
            for tool_use, result in zip(tool_uses, results, strict=True):
                if isinstance(result, BaseException):
                    result_content = f"Error: {result}"
                    self._note_tool_failure(tool_use.name, result_content)
                else:
                    result_content = (
                        result.content if isinstance(result.content, str) else str(result.content)
                    )
                    if getattr(result, "is_error", False):
                        self._note_tool_failure(tool_use.name, result_content)
                messages.append(tool_result_message(tool_use.id, result_content))
                self._record_tool_result(tool_use.id, result_content)
                if not isinstance(result, BaseException):
                    self._note_artifact_result(tool_use, result)
        else:
            for tool_use in tool_uses:
                if not self._running:
                    break

                corrected_name, corrected_params, val_hint = self._tool_validator.validate(
                    tool_use.name, tool_use.input
                )
                if corrected_name != tool_use.name or corrected_params != tool_use.input:
                    tool_use.name = corrected_name
                    tool_use.input = corrected_params
                    if val_hint:
                        messages.append({"role": "user", "content": val_hint})

                tool_key = f"{tool_use.name}:{json.dumps(tool_use.input, sort_keys=True)}"
                failed_tool_calls[tool_key] = failed_tool_calls.get(tool_key, 0) + 1

                if self._guard:
                    loop_msg = self._guard.notify_tool_call(tool_use.name)
                    if loop_msg:
                        messages.append({"role": "user", "content": loop_msg})

                if failed_tool_calls[tool_key] > max_repeat_calls:
                    self.console.print(
                        f"\n[{self._c('error')}]Tool '{tool_use.name}' called too many times with same parameters.[/]"
                    )
                    messages.append(
                        tool_result_message(
                            tool_use.id,
                            f"ERROR: Tool '{tool_use.name}' has been called "
                            f"{failed_tool_calls[tool_key]} times with the same parameters.",
                        )
                    )
                    continue

                result = await self._execute_tool(tool_use)

                result_content = (
                    result.content if isinstance(result.content, str) else str(result.content)
                )
                if getattr(result, "is_error", False):
                    self._note_tool_failure(tool_use.name, result_content)
                messages.append(tool_result_message(tool_use.id, result_content))
                self._record_tool_result(tool_use.id, result_content)
                self._note_artifact_result(tool_use, result)

        self.app_state._persist()

    def _history_to_messages(self) -> list[dict[str, Any]]:
        """Convert the stored session messages into provider message dicts."""
        messages: list[Any] = []
        for msg in self.app_state.messages:
            if msg.role == MessageRole.USER:
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if hasattr(msg, "tool_uses") and msg.tool_uses:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tu.id,
                            "type": "function",
                            "function": {"name": tu.name, "arguments": json.dumps(tu.input)},
                        }
                        for tu in msg.tool_uses
                    ]
                messages.append(assistant_msg)
            elif (
                msg.role == MessageRole.SYSTEM
                and isinstance(msg, SystemMessage)
                and msg.tool_use_id
            ):
                messages.append(tool_result_message(msg.tool_use_id, msg.content))
        return messages

    async def _inject_runtime_context(
        self, messages: list[dict[str, Any]]
    ) -> tuple[int | None, str]:
        """Append the runtime context block; return (context_limit, model_size).

        Bundles session context, world sensor, memory digest, small-model
        guidance and thinking prefix into one system-injected user message, and
        adds an Ollama tool-format hint when the provider needs it.
        """
        runtime_blocks: list[str] = []
        session_ctx = self._cache_guard.ensure_session_context(
            model=self.app_state.session_config.model,
        )
        if session_ctx:
            runtime_blocks.append(session_ctx)
        if self._world_sensor:
            world_ctx = self._world_sensor.to_context_block()
            if world_ctx:
                runtime_blocks.append(f"<sc:context>{world_ctx}</sc:context>")
        memory_block = self._memory_digest()
        if memory_block:
            runtime_blocks.append(memory_block)

        from openlaoke.core.small_model_optimizations import (
            apply_structured_thinking_prefix,
            estimate_model_size_from_name,
            get_small_model_guidance,
        )

        model_size = estimate_model_size_from_name(self.app_state.session_config.model)
        from openlaoke.core.model_discovery import get_effective_context_limit

        _active_provider = (
            self.api.config.get_active_provider() if self.api and self.api.config else None
        )
        context_limit = (
            await get_effective_context_limit(_active_provider, self.app_state.session_config.model)
            if _active_provider
            else None
        )
        for part in (
            get_small_model_guidance(model_size),
            apply_structured_thinking_prefix("code"),
        ):
            if part:
                runtime_blocks.append(part)
        if runtime_blocks:
            messages.append(
                {
                    "role": "user",
                    "content": "\n\n".join(runtime_blocks),
                    "system_injected": True,
                }
            )

        if self._is_ollama_provider():
            latest_user = next(
                (
                    msg.get("content", "")
                    for msg in reversed(messages)
                    if msg.get("role") == "user" and not msg.get("system_injected")
                ),
                "",
            ).strip()
            if not _CONVERSATION_ONLY.match(latest_user) and (
                len(latest_user) >= 30 or _CODING_TRIGGERS.search(latest_user)
            ):
                if model_size == "tiny":
                    tool_hint = (
                        "[Use ONE tool now. Simple format: "
                        "Write file_path=name content=code  OR  "
                        "Bash command=cmd  OR  Read file_path=name  OR  "
                        "Glob pattern=*.py. Do NOT describe, just OUTPUT the tool line.]"
                    )
                else:
                    lt = chr(60)
                    gt = chr(62)
                    tool_hint = (
                        f"[Use tools: output {lt}tool_call{gt} {lt}function=FUNC{gt} "
                        f"{lt}parameter=KEY{gt} value {lt}/parameter{gt} "
                        f"{lt}/function{gt} {lt}/tool_call{gt} for each action. "
                        "Do NOT describe, just DO. Available: "
                        "Write(file_path,content) Read(file_path) "
                        "Glob(pattern) Bash(command)]"
                    )
                messages.append({"role": "user", "content": tool_hint, "system_injected": True})

        return context_limit, model_size

    async def _run_api_loop(self) -> None:
        from openlaoke.core.harness_modes import get_mode

        _mode = get_mode(getattr(self.app_state, "harness_mode", None))
        max_iterations = self._resolve_max_iterations()
        # Identical-call loop breaker threshold comes from the harness mode,
        # so a "thorough" mode tolerates more retries than a "fast" one.
        max_repeat_calls = _mode.max_repeat_calls
        iteration = 0
        failed_tool_calls: dict[str, int] = {}
        self._artifact_written = set()
        self._artifact_verified = False
        self._force_final = False
        self._turn_failures = []

        messages = self._history_to_messages()
        # Resolve the window before the prompt is built: the frozen prompt is
        # assembled once, and an optional block (retrieved knowledge) can be
        # longer than a small model's whole window. Building first meant the
        # budget arrived too late to apply and the extras were never bounded.
        context_limit, model_size = await self._inject_runtime_context(messages)
        from openlaoke.core.prompt_budget import budget_for_window

        self._cache_guard.set_prompt_budget(budget_for_window(context_limit))
        system_prompt = self._cache_guard.system_prompt

        # Config on disk does not change mid-turn; read it once instead of
        # hitting the filesystem on every iteration.
        from openlaoke.utils.config import load_config as _load_config

        _global_context_cap = _load_config().context_cap_tokens

        while iteration < max_iterations and self._running:
            iteration += 1

            # Mid-run queued input (B2): flush user corrections between
            # iterations so the model sees them on the next call.
            while self._input_queue:
                queued = self._input_queue.pop(0)
                self.console.print(f"  [{self._c('muted')}]Injecting queued message...[/]")
                self.app_state.add_message(
                    UserMessage(role=MessageRole.USER, content=queued), persist=False
                )
                messages.append({"role": "user", "content": queued})

            for notice in self._drain_task_notices():
                messages.append({"role": "user", "content": notice, "system_injected": True})

            turn_start_index = len(messages)
            await self._fire_turn_hook(
                "turn_start",
                turn=iteration,
                messages=len(messages),
                context_cap=self.app_state.context_cap,
            )

            messages, tools, model_size = self._prepare_turn_context(
                messages, system_prompt, context_limit, _global_context_cap
            )

            if self.app_state.insomnia_mode:
                self.console.print(f"[{self._c('muted')}]Insomnia iteration {iteration}[/]")

            try:
                if self._guard:
                    limit_msg = self._guard.check_before_api_call()
                    if limit_msg:
                        messages.append({"role": "user", "content": limit_msg})
                        if self._guard.task_tool_calls >= self._guard.max_task_tool_calls:
                            break

                if not self.api:
                    return

                if iteration == 1 and self.app_state.verbose:
                    self.console.print(f"[{self._c('muted')}]Messages: {messages}[/]")

                # Streaming is the only provider path (the old non-streaming
                # send_message fallback was dead code and has been removed).
                streaming_supported = True
                usage = None
                cost = None
                content_text = ""
                reasoning_text = ""
                tool_uses: list[ToolUseBlock] = []
                plan_retry_count = 0
                retry_after_parse_failure = False

                if streaming_supported:
                    turn = await self._stream_provider_turn(
                        system_prompt=system_prompt, messages=messages, tools=tools
                    )
                    content_text = turn.content
                    reasoning_text = turn.reasoning
                    tool_uses = turn.tool_uses
                    usage = turn.usage
                    cost = turn.cost

                    if turn.stream_error:
                        from rich.markup import escape

                        self.console.print(
                            f"  [bold {self._c('error')}]Error:[/] {escape(str(turn.stream_error))}"
                        )
                        # Machine-readable copy: the insomnia retry loop reads
                        # app_state.error_message to decide whether the task
                        # actually finished, and a printed line is not readable.
                        self.app_state.set_error(str(turn.stream_error))
                        break

                    if (
                        turn.token_count == 0
                        and turn.reasoning_count == 0
                        and not tool_uses
                        and not content_text.strip()
                        and turn.elapsed > 5
                    ):
                        self.console.print(
                            f"  [bold {self._c('error')}]Model returned no output[/]"
                            f" (waited {turn.elapsed:.0f}s). Try a different model or check the provider."
                        )
                        self.app_state.set_error("Model returned no output")
                        break

                    if self._guard:
                        quality_msg = self._guard.check_after_api_call(content_text, len(tool_uses))
                        if quality_msg:
                            messages.append({"role": "user", "content": quality_msg})

                    if content_text and not tool_uses and "<tool_call>" in content_text:
                        parsed_tool_uses = self._parse_inline_tool_calls(content_text)
                        if parsed_tool_uses:
                            if self._guard:
                                self._guard.notify_parse_success()
                            tool_uses = parsed_tool_uses
                            content_text = self._strip_tool_calls(content_text)
                        elif self._guard:
                            parse_msg = self._guard.notify_parse_failure(content_text)
                            messages.append({"role": "user", "content": parse_msg})
                            # The correction only helps if the model gets another
                            # turn to act on it; once it has failed too often the
                            # guard asks it to stop using tools instead, and that
                            # reply is the one to keep.
                            retry_after_parse_failure = (
                                self._guard.consecutive_parse_failures
                                < self._guard.max_parse_failures
                            )

                    if reasoning_text:
                        self._last_thinking = reasoning_text
                        self.app_state.last_thinking = reasoning_text
                        self._thinking_duration = (
                            (time.time() - self._turn_start) * 1000 if self._turn_start else 0
                        )
                        self._display_thinking_inline(reasoning_text)

                    if content_text:
                        self._render_response(content_text)

                    if self._force_final:
                        tool_uses = []

                    is_plan_only = (
                        content_text
                        and not tool_uses
                        and plan_retry_count < 2
                        and self._is_plan_response(content_text)
                    )
                    if is_plan_only:
                        self.console.print(
                            f"[{self._c('muted')}](auto-retry: requesting tool calls...)[/]"
                        )
                        plan_retry_count += 1
                        if model_size == "tiny":
                            retry_content = (
                                "Do NOT list steps. Output ONE tool line NOW. "
                                "Format: Write file_path=x content=code  OR  Bash command=cmd  OR  Read file_path=x"
                            )
                        else:
                            retry_content = (
                                "Do NOT describe steps. Use tools NOW. "
                                "Output <tool_call> format immediately. "
                                "Start with Read or Glob to explore the project."
                            )
                        messages.append({"role": "user", "content": retry_content})
                        continue

                    for tu in tool_uses:
                        self.console.print(self._tool_action_line(tu))

                    if usage and cost:
                        self.app_state.accumulate_tokens(usage)
                        self.app_state.accumulate_cost(cost)
                    self._note_context_usage(usage)

                    if content_text or tool_uses or usage:
                        msg = AssistantMessage(
                            role=MessageRole.ASSISTANT,
                            content=content_text,
                            tool_uses=tool_uses if tool_uses else [],
                            thinking=reasoning_text,
                        )
                        # Defer persistence to the explicit _persist() call at
                        # turn end — avoids a blocking disk write per iteration.
                        self.app_state.add_message(msg, persist=False)
                        messages.append(assistant_turn(content_text, tool_uses))

                    if not tool_uses:
                        if retry_after_parse_failure:
                            self.console.print(
                                f"  [{self._c('muted')}]"
                                "(auto-retry: that tool call could not be parsed)[/]"
                            )
                            continue
                        if (
                            content_text.strip().upper().startswith("DONE")
                            or "\nDONE" in content_text.upper()
                            or content_text.strip().upper() == "DONE"
                        ):
                            self.console.print(f"  [{self._c('success')}]Task complete (DONE)[/]")
                            break
                        if self._todo_auto_continue(messages):
                            continue
                        break

                    await self._dispatch_tools(
                        tool_uses, messages, failed_tool_calls, max_repeat_calls
                    )

            except asyncio.CancelledError:
                self._interrupt_requested = True
                self._patch_dangling_tool_calls()
                self.console.print(f"\n[{self._c('warning')}]Interrupted — context preserved.[/]")
                break
            except httpx.HTTPStatusError as e:
                # Provider error bodies routinely contain bracketed text; markup
                # would either swallow it or raise inside the error handler.
                from rich.markup import escape

                self.console.print(
                    f"\n[bold {self._c('error')}]API Error:[/] {e.response.status_code}"
                )
                self.app_state.set_error(f"API {e.response.status_code}")
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                    self.console.print(f"[{self._c('error')}]{escape(str(error_msg))}[/]")
                except Exception:
                    self.console.print(f"[{self._c('error')}]{escape(e.response.text[:500])}[/]")
                break
            except Exception as e:
                from rich.markup import escape

                self.console.print(f"\n[bold {self._c('error')}]Error:[/] {escape(str(e))}")
                self.app_state.set_error(str(e))
                break
            finally:
                # turn_end fires however the iteration leaves, including the
                # break paths above, so a counter that listens for it can never
                # drift out of sync with turn_start.
                usage = self._last_usage
                await self._fire_turn_hook(
                    "turn_end",
                    turn=iteration,
                    tool_calls=sum(
                        1
                        for msg in messages[turn_start_index:]
                        if msg.get("role") == "assistant" and msg.get("tool_calls")
                    ),
                    input_tokens=int(getattr(usage, "input_tokens", 0) or 0) if usage else 0,
                    output_tokens=int(getattr(usage, "output_tokens", 0) or 0) if usage else 0,
                    cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0)
                    if usage
                    else 0,
                )

        # After the model's own closing message, so a turn that failed loudly and
        # then reported success still ends with the harness's account.
        self._report_turn_failures()

    async def _execute_tool(self, tool_use: ToolUseBlock) -> ToolResultBlock:
        tool = self.registry.get(tool_use.name)
        self.app_state.tool_call_counts[tool_use.name] = (
            self.app_state.tool_call_counts.get(tool_use.name, 0) + 1
        )
        if not tool:
            self.console.print(f"  [{self._c('muted')}]Unknown tool: {tool_use.name}[/]")
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Unknown tool: {tool_use.name}",
                is_error=True,
            )

        from openlaoke.core.small_model_optimizations import (
            coerce_tool_args,
            sanitize_tool_schema,
        )

        tool_input = tool_use.input
        tool_schema = tool.get_input_schema()
        sanitized_schema = sanitize_tool_schema(tool_schema)
        tool_input = coerce_tool_args(tool_input, sanitized_schema)

        from openlaoke.core.hook_system import HookInput, HookOutput

        hook_input = HookInput(
            tool_name=tool_use.name,
            tool_args=dict(tool_input),
            session_id=self.app_state.session_id,
            provider_name=self.app_state.multi_provider_config.active_provider
            if self.app_state.multi_provider_config
            else "",
            model_name=self.app_state.session_config.model,
        )
        hook_output = HookOutput()

        if self._hook_system.has_hooks("tool_execute_before"):
            self._hook_system.execute_hooks("tool_execute_before", hook_input, hook_output)
            if hook_output.skip_execution:
                return ToolResultBlock(
                    tool_use_id=tool_use.id,
                    content=hook_output.tool_result or "Tool execution skipped by hook",
                    is_error=False,
                )
            if hook_output.tool_args is not None:
                tool_input = hook_output.tool_args

        # The veto point sits after argument rewriting and before the
        # permission check, so a gate sees the final arguments and the user is
        # never asked to approve a call a plugin already refused.
        if self._hook_system.has_hooks("tool_gate"):
            gate_input = HookInput(
                tool_name=tool_use.name,
                tool_args=dict(tool_input),
                session_id=hook_input.session_id,
                provider_name=hook_input.provider_name,
                model_name=hook_input.model_name,
            )
            gate_output = self._hook_system.gate(gate_input)
            if gate_output.tool_args is not None:
                tool_input = gate_output.tool_args
                hook_input.tool_args = dict(tool_input)
            if gate_output.handled:
                reason = (
                    gate_output.tool_result
                    or gate_output.metadata.get("reason")
                    or "Blocked by a tool_gate hook."
                )
                self.console.print(f"  [{self._c('warning')}]Blocked:[/] {tool_use.name}")
                return ToolResultBlock(tool_use_id=tool_use.id, content=str(reason), is_error=True)

        self._read_loop_tracker.notify_tool_call(tool_use.name)

        if self._read_loop_tracker.should_warn():
            self.console.print(
                f"  [{self._c('warning')}]{self._read_loop_tracker.get_warning_message()}[/]"
            )

        perm_result = tool.check_permissions(
            tool_input,
            self.app_state.permission_config,
        )

        if perm_result != PermissionResult.DENY:
            subject = self._approval_subject(tool_use.name, tool_input)
            subject_result = self.app_state.permission_config.check_tool_subject(
                tool_use.name, subject
            )
            if subject_result == PermissionResult.DENY:
                perm_result = PermissionResult.DENY
            elif subject_result == PermissionResult.ALLOW:
                perm_result = PermissionResult.ALLOW

        if perm_result == PermissionResult.DENY:
            self.console.print(f"  [{self._c('error')}]Denied:[/] {tool_use.name}")
            from openlaoke.core import audit

            audit.record(
                self.app_state,
                "tool.denied",
                tool=tool_use.name,
                call_id=tool_use.id,
                reason="config",
                args=audit.summarize_args(tool_input),
            )
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Permission denied for {tool_use.name}",
                is_error=True,
            )

        if perm_result == PermissionResult.ASK and not self.app_state.auto_accept:
            approved = await self._ask_permission(tool_use.name, tool_input, tool)
            if not approved:
                self.console.print(f"  [{self._c('error')}]Denied: {tool_use.name}[/]")
                from openlaoke.core import audit

                audit.record(
                    self.app_state,
                    "tool.denied",
                    tool=tool_use.name,
                    call_id=tool_use.id,
                    reason="user",
                    args=audit.summarize_args(tool_input),
                )
                return ToolResultBlock(
                    tool_use_id=tool_use.id,
                    content=f"User denied {tool_use.name}",
                    is_error=True,
                )

        tool_icon = "\u2219" if not self.app_state.insomnia_mode else "\u2615"
        intent_label = str(tool_input.get("intent") or "").strip()
        if len(intent_label) > 60:
            intent_label = intent_label[:57] + "..."
        suffix = f" [dim]{intent_label}[/]" if intent_label else ""
        self.console.print(f"  [{self._c('secondary')}]{tool_icon}{tool_use.name}[/]{suffix}")

        ctx = ToolContext(
            app_state=self.app_state,
            tool_use_id=tool_use.id,
            file_state=self.app_state.get_file_state(),
        )

        validation = tool.validate_input(tool_input)
        if not validation.result:
            self.console.print(f"  [{self._c('error')}]Validation: {validation.message}[/]")
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Validation error: {validation.message}",
                is_error=True,
            )

        from openlaoke.core import audit

        audit.record_tool_request(self.app_state, tool_use.name, tool_input, tool_use.id)
        result = await tool.safe_call(ctx, **tool_input)
        audit.record_tool_result(self.app_state, tool_use.name, result, tool_use.id)

        if tool_use.name in ("Write", "Edit"):
            self._verify_file_written(tool_input, result)

        result_content = result.content if isinstance(result.content, str) else str(result.content)

        # The ledger runs before the fixed cap: a body the model has already seen
        # collapses to a pointer, and an oversized one is withheld until the model
        # explicitly accepts its cost.
        accepts_large = bool(tool_input.get("accept_large_output"))
        if not result.is_error:
            guarded = self._ledger.guard(tool_use.name, tool_input, result_content)
            if guarded != result_content:
                result_content = guarded
                result = ToolResultBlock(
                    tool_use_id=result.tool_use_id, content=guarded, is_error=False
                )

        # Oversized output is kept on disk and replaced in history by a
        # pointer (path + digest + head/tail), so the middle of a long log is
        # still reachable instead of being dropped. An explicitly accepted
        # result keeps 4x the normal cap, still bounded.
        _max_tool_out = self.app_state.max_tool_history * (4 if accepts_large else 1)
        if len(result_content.encode("utf-8")) > _max_tool_out:
            from openlaoke.core.tool_output_store import externalize

            result_content = externalize(
                self.app_state, tool_use.name, result_content, max_bytes=_max_tool_out
            )
            # Rebuild the block: it is ``result.content`` that goes into the
            # history, so replacing the local copy alone capped nothing.
            result = ToolResultBlock(
                tool_use_id=result.tool_use_id,
                content=result_content,
                is_error=result.is_error,
            )

        if tool_use.name == "Bash":
            compressed = self._output_compressor.compress(result_content)
            if compressed != result_content:
                result = ToolResultBlock(
                    tool_use_id=result.tool_use_id,
                    content=compressed,
                    is_error=result.is_error,
                )
                result_content = compressed

        if self._hook_system.has_hooks("tool_execute_after"):
            hook_input.tool_result = result_content
            hook_input.tool_error = result_content if result.is_error else ""
            hook_output_after = HookOutput()
            self._hook_system.execute_hooks("tool_execute_after", hook_input, hook_output_after)
            if hook_output_after.tool_result is not None:
                result = ToolResultBlock(
                    tool_use_id=result.tool_use_id,
                    content=hook_output_after.tool_result,
                    is_error=result.is_error,
                )

        # A plugin's feedback is queued as a user-role remark rather than
        # injected into the tool result, so it survives into the next turn
        # without pretending the tool said it.
        if self._hook_system.has_hooks("tool_feedback"):
            feedback_input = HookInput(
                tool_name=tool_use.name,
                tool_args=dict(tool_input),
                tool_result=result.content if isinstance(result.content, str) else "",
                tool_error=(result.content if isinstance(result.content, str) else "")
                if result.is_error
                else "",
                session_id=hook_input.session_id,
                provider_name=hook_input.provider_name,
                model_name=hook_input.model_name,
            )
            feedback_output = self._hook_system.execute_hooks("tool_feedback", feedback_input)
            if feedback_output.feedback:
                note = f"[hook feedback on {tool_use.name}] {feedback_output.feedback}"
                self._input_queue.append(note)
                self.console.print(
                    f"  [{self._c('muted')}]hook feedback queued ({len(feedback_output.feedback)} chars)[/]"
                )

        rendered = tool.render_result(result)
        if rendered:
            self._print_tool_result(rendered, tool_use.name, result.is_error)

        return result

    def _build_streaming_display(
        self, content: str, tokens: int, tps: float, elapsed: float, reasoning: bool = False
    ) -> Any:
        # A single line of plain styled text: rich Live clears it cleanly, and
        # model output is never parsed as markup.
        from rich.text import Text

        meta = f"  {elapsed:.0f}s"
        if tokens:
            meta += f" · {tokens} tok"
        if tps > 0:
            meta += f" · {tps:.0f} t/s"

        width = getattr(getattr(self, "console", None), "width", 80)
        room = max(20, width - len(meta) - 6)
        # Only the tail is ever shown. Slice a bounded window first so this
        # stays O(room) instead of O(len(content)) on every streamed chunk
        # (the old `content.split()` made long streams quadratic).
        window = content[-max(200, room * 2) :] if content else ""
        tail = " ".join(window.split())
        if len(tail) > room:
            tail = "…" + tail[-room:]
        if not tail:
            tail = "thinking…" if reasoning else "streaming…"

        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        spin = frames[int(elapsed * 12) % len(frames)]

        status = Text()
        status.append(f"  {spin} ", style=self._c("primary"))
        status.append(tail, style=self._c("muted"))
        status.append(meta, style=self._c("muted"))
        return status

    def _display_thinking_inline(self, thinking: str) -> None:
        enabled = self.app_state.thinking_enabled
        if not enabled:
            self.console.print(
                f"  [{self._c('muted')} dim]Thought: {self._thinking_duration:.0f}ms (Ctrl+G to view)[/]"
            )
            return
        lines = thinking.strip().split("\n")
        from rich.text import Text

        max_show = 5
        for line in lines[:max_show]:
            self.console.print(Text("  " + line, style=self._c("muted")))
        if len(lines) > max_show:
            self.console.print(
                Text(
                    f"  ... ({len(lines) - max_show} more lines, Ctrl+G to see all)",
                    style=self._c("muted"),
                )
            )

    def _show_thinking_full(self) -> None:
        if not self._last_thinking:
            self.console.print(f"  [{self._c('muted')}]No thinking content.[/]")
            return
        lines = self._last_thinking.strip().split("\n")
        self.console.print()
        self.console.print(
            f"  [{self._c('muted')}]── Thought ({len(lines)} lines, {self._thinking_duration:.0f}ms) ──[/]"
        )
        for line in lines:
            self.console.print(f"  [{self._c('muted')}]{line}[/]")
        self.console.print(f"  [{self._c('muted')}]── end ──[/]")

    def _render_response(self, content: str) -> None:
        """Render assistant response with proper terminal formatting."""
        if not content.strip():
            return
        try:
            from rich.markdown import Markdown

            md = Markdown(content, code_theme="monokai")
            self.console.print(md)
        except Exception:
            self.console.print(content)

    async def _ask_permission(self, tool_name: str, tool_input: dict[str, Any], tool: Tool) -> bool:
        # Show a preview of what the tool would do before asking (diff for
        # editors/writers, command summary for bash).
        try:
            preview = tool.preview(**tool_input)
            if preview and preview.summary:
                self.console.print(f"  [{self._c('muted')}]Preview:[/] {preview.summary}")
        except Exception:
            pass

        prompt_text = Text()
        prompt_text.append(f"  {self._t('allow_tool')} ", style=self._theme.style("warning"))
        prompt_text.append(f"{tool_name}", style=self._theme.style("assistant_message"))
        prompt_text.append("?", style=self._theme.style("warning"))
        self.console.print(prompt_text)

        choices = Text()
        choices.append("  [", style=self._theme.style("muted"))
        choices.append("y", style=self._theme.style("success"))
        choices.append("]es  ", style=self._theme.style("muted"))
        choices.append("[", style=self._theme.style("muted"))
        choices.append("n", style=self._theme.style("error"))
        choices.append("]o  ", style=self._theme.style("muted"))
        choices.append("[", style=self._theme.style("muted"))
        choices.append("a", style=self._theme.style("primary"))
        choices.append("]lways  ", style=self._theme.style("muted"))
        choices.append("[", style=self._theme.style("muted"))
        choices.append("v", style=self._theme.style("error"))
        choices.append("]never", style=self._theme.style("muted"))
        self.console.print(choices)

        try:
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, lambda: input("  > ").strip().lower())
        except (EOFError, OSError):
            answer = "n"

        if answer in ("n", "no"):
            return False
        if answer in ("v", "never"):
            self.app_state.permission_config.deny_subject(
                tool_name, self._approval_subject(tool_name, tool_input)
            )
            self.console.print(
                f"  [{self._c('muted')}]Saved permanent deny for {tool_name}. "
                "Remove it via /permission rules to re-enable.[/]"
            )
            return False
        if answer in ("a", "always"):
            self.app_state.permission_config.approve_subject(
                tool_name, self._approval_subject(tool_name, tool_input), remember=True
            )
        return True

    @staticmethod
    def _approval_subject(tool_name: str, tool_input: dict[str, Any]) -> str:
        """Narrow approval key for 'Always allow': base command for Bash,
        target path for file writers, tool-wide when no narrower subject."""
        if tool_name == "Bash":
            return str(tool_input.get("command", ""))[:200]
        if tool_name in ("Write", "Edit"):
            path = str(tool_input.get("file_path", ""))
            return path[:200]
        return ""

    def _tool_action_line(self, tu: ToolUseBlock) -> str:
        """One compact, informative line for a tool call about to run.

        The old line only showed the tool name plus ``file_path``, so ``Bash``
        printed as a bare word and you could not tell what was about to run.
        This picks the most telling argument per tool and trims it.
        """
        name = tu.name
        data = tu.input or {}

        def _short(value: Any, limit: int = 72) -> str:
            text = " ".join(str(value).split())
            return text if len(text) <= limit else text[: limit - 1] + "…"

        subject = ""
        if name == "Bash":
            subject = _short(data.get("command", ""))
        elif name in ("Grep", "Glob"):
            subject = _short(data.get("pattern", ""))
            path = data.get("path")
            if path:
                subject += f"  {_short(path, 32)}"
        elif name in ("Write", "Edit", "Read", "apply_patch"):
            subject = _short(data.get("file_path") or data.get("path") or "")
        elif name in ("WebFetch",):
            subject = _short(data.get("url", ""))
        elif name in ("WebSearch",):
            subject = _short(data.get("query") or data.get("pattern") or "")
        elif name == "TodoWrite":
            todos = data.get("todos")
            if isinstance(todos, list):
                subject = f"{len(todos)} items"
        else:
            subject = _short(data.get("file_path") or data.get("path") or data.get("command") or "")

        line = f"  [{self._c('secondary')}]{name}[/]"
        if subject:
            line += f" [{self._c('muted')}]{subject}[/]"
        return line

    def _print_tool_result(self, rendered: str, tool_name: str, is_error: bool) -> None:
        # Tool output is arbitrary text: a traceback ("[Errno 2] ..."), a markdown
        # link or a log line with "[WARN]" is not markup. Printed unescaped, a
        # bracket is either swallowed from the display or, for "[/]", raises
        # MarkupError inside the print and aborts the whole turn.
        from rich.markup import escape

        if is_error:
            style = self._c("error")
            prefix = "!"
        else:
            style = self._c("muted")
            prefix = " "

        max_inline = 300
        if len(rendered) <= max_inline:
            self.console.print(f"  [{style}]{prefix} {escape(rendered)}[/]")
        else:
            self.console.print(f"  [{style}]{prefix} {escape(rendered[:max_inline])}...[/]")
            self.console.print(f"  [{self._c('muted')}]{prefix}   ({len(rendered)} chars total)[/]")

    def _get_git_store(self) -> Any | None:
        return None

    @staticmethod
    def _parse_inline_tool_calls(content: str) -> list[ToolUseBlock]:
        """Recover tool calls that a model emitted as text.

        The dialects (JSON, ``<function=>``, ``<arg_key>/<arg_value>``) live in
        :mod:`openlaoke.core.text_tool_calls` so this path and the headless
        engine cannot drift apart. The brace form below is the one syntax that
        module does not cover.
        """
        from openlaoke.core.text_tool_calls import parse_text_tool_calls

        _clean, calls = parse_text_tool_calls(content)
        if calls:
            return calls
        return REPL._parse_brace_tool_calls(content)

    @staticmethod
    def _parse_brace_tool_calls(content: str) -> list[ToolUseBlock]:
        """Parse ``Write{file_path:<|arg|>a.py<|arg|>}`` style calls."""
        calls: list[ToolUseBlock] = []
        for match in _BRACE_CALL.finditer(content):
            name, inner = match.group(1), match.group(2)
            marks = list(_BRACE_KV.finditer(inner))
            if not marks:
                continue
            params: dict[str, str] = {}
            for i, mark in enumerate(marks):
                stop = marks[i + 1].start() if i + 1 < len(marks) else len(inner)
                value = inner[mark.end() : stop].rstrip("}").strip()
                value = re.sub(r"(?:\s*<\|[^|]*\|>)+\s*$", "", value).strip()
                if value:
                    params[mark.group(1)] = value
            if params:
                calls.append(
                    ToolUseBlock(
                        id=f"call_{uuid.uuid4().hex[:12]}",
                        name=name,
                        input=params,
                    )
                )
        return calls

    @staticmethod
    def _strip_tool_calls(content: str) -> str:
        import re

        content = re.sub(
            r"<tool_call>.*?</tool_call>",
            "",
            content,
            flags=re.DOTALL,
        )
        for tool_name in [
            "Write",
            "Read",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "ListDirectory",
            "write",
            "read",
            "edit",
            "bash",
            "glob",
            "grep",
            "ls",
        ]:
            content = re.sub(
                rf"^{tool_name}\s+\w[\w_]*\s*=.*$",
                "",
                content,
                flags=re.MULTILINE,
            )
        return content.strip()

    def _is_ollama_provider(self) -> bool:
        cfg = self.app_state.multi_provider_config
        if not cfg:
            return False
        provider = cfg.get_active_provider()
        if not provider:
            return False
        return provider.provider_type in ("ollama", "openai_compatible", "lm_studio")

    @staticmethod
    def _is_plan_response(content: str) -> bool:
        """True only when the model clearly promises to act but sends no tool
        call. A final answer often contains numbered points, so a numbered list
        alone must never be treated as a plan."""
        lower = content.lower()
        if "<tool_call>" in lower:
            return False
        # A completed answer reads like a summary, not a promise.
        if any(k in lower for k in ("总结", "以下是", "完成", "结论", "summary", "done")):
            return False
        # Promises are short; a long reply is an answer.
        if len(content) > 600:
            return False
        intents = (
            "i will now",
            "i will use",
            "i will create",
            "i will write",
            "i will run",
            "let me first",
            "let me start",
            "i'll start",
            "i'll now",
            "接下来我将",
            "接下来我会",
            "我将创建",
            "我将执行",
            "让我先",
        )
        return any(k in lower for k in intents)

    def _verify_file_written(self, tool_input: dict[str, Any], result: ToolResultBlock) -> None:
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        import os

        abs_path = file_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(self.app_state.get_cwd(), abs_path)

        if os.path.exists(abs_path):
            size = os.path.getsize(abs_path)
            lines = 0
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    lines = sum(1 for _ in f)
            except Exception:
                pass
            self.console.print(
                f"  [{self._c('success')}]✓ Verified: {abs_path} ({lines} lines, {size} bytes)[/]"
            )
        else:
            self.console.print(f"  [{self._c('error')}]✗ Missing: {abs_path} was NOT created[/]")

    def _print_banner(self) -> None:
        from openlaoke import __version__

        theme = self._theme.current_theme
        color = theme.colors.primary
        self.console.print(
            Panel.fit(
                f"[bold {color}]OpenLaoKe[/] v{__version__}\n"
                f"[{theme.colors.muted}]{self._t('app_subtitle')}[/]",
                border_style=color,
            )
        )

    def _print_welcome(self) -> None:
        theme = self._theme.current_theme
        c = theme.colors

        provider_name = "unknown"
        if self.multi_provider_config:
            provider_name = self.multi_provider_config.active_provider
        elif self.app_state.multi_provider_config:
            provider_name = self.app_state.multi_provider_config.active_provider

        proxy_info = ""
        if self._proxy:
            proxy_info = f"\n[{self._c('primary')} bold]Proxy:[/] {self._proxy}"

        from openlaoke.core.skill_system import list_available_skills

        skills = list_available_skills()
        c_prim = self._c("primary")
        c_succ = self._c("success")
        c_warn = self._c("warning")

        self.console.print(f"\n[{c_prim} bold]{self._t('provider_label')}[/] {provider_name}")
        self.console.print(
            f"[{c_prim} bold]{self._t('model_label')}[/] {self.app_state.session_config.model}"
        )
        self.console.print(
            f"[{c_prim} bold]{self._t('working_dir_label')}[/] {self.app_state.get_cwd()}"
        )
        if self.app_state.local_mode:
            self.console.print(
                f"[{c_prim} bold]{self._t('mode_label')}[/] [{c_warn}]{self._t('mode_local')}[/]"
            )
        else:
            self.console.print(
                f"[{c_prim} bold]{self._t('mode_label')}[/] [{c_succ}]{self._t('mode_online')}[/]"
            )

        self.console.print(
            f"[{c_prim} bold]{self._t('tools_label')}[/] "
            f"{len(self.registry.get_all())} {self._t('tools_available')}{proxy_info}"
        )

        if skills:
            self.console.print(
                f"[{c_prim} bold]{self._t('skills_label')}[/] "
                f"{len(skills)} {self._t('skills_available')}"
            )
            example_skills = sorted(skills)[:5]
            skills_str = ", ".join(f"/{s}" for s in example_skills)
            if len(skills) > 5:
                skills_str += f", ... ({len(skills) - 5} more)"
            self.console.print(f"  [{c.muted}]{skills_str}[/]")

        if self.app_state.insomnia_mode:
            self.console.print(f"[{c_prim} bold]Mode:[/] [bold {c_prim}]Insomnia[/]")

        self.console.print(f"\n[{c.muted}]{self._t('welcome_hint')}[/]")

    @staticmethod
    def _format_context_composition(messages: list[dict]) -> str:
        """Estimate context window composition by role (verbose mode).

        Like sekrun's ``formatContextComposition`` — shows what % of the
        context is system prompt, user messages, assistant replies, and tool
        results.
        """
        import json as _json

        sections: dict[str, int] = {"system": 0, "user": 0, "assistant": 0, "tool": 0}
        total = 0
        for msg in messages:
            role = msg.get("role", "other")
            text = str(msg.get("content", ""))
            tokens = max(1, len(text) // 4)
            if role in sections:
                sections[role] += tokens
            elif role != "other":
                sections[role] = sections.get(role, 0) + tokens
            if msg.get("tool_calls"):
                calls_str = _json.dumps(msg["tool_calls"])
                sections["assistant"] += max(1, len(calls_str) // 4)
            total += tokens

        if total == 0:
            return "(empty context)"

        parts: list[str] = []
        labels = {"system": "sys", "user": "usr", "assistant": "ast", "tool": "tool"}
        for role, label in labels.items():
            t = sections.get(role, 0)
            if t:
                pct = t * 100.0 / total
                parts.append(f"{label} {t}t ({pct:.0f}%)")
        return "ctx: " + " | ".join(parts) + f" | total ~{total}t"
