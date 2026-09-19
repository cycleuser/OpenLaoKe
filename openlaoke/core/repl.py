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
from typing import Any

import httpx
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from openlaoke.commands.registry import get_command, parse_command, register_all
from openlaoke.core.cache_guard import CacheGuard
from openlaoke.core.config_wizard import get_proxy_url
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


class REPL:
    """Main REPL loop for OpenLaoKe."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.console = Console(force_terminal=True)
        self.registry = ToolRegistry()
        self.api: MultiProviderClient | None = None
        self._running = False
        self._last_thinking: str = ""
        self._thinking_duration: float = 0.0
        self._turn_start: float = 0.0

        self._reset_terminal()
        self._active_tasks: set[asyncio.Task] = set()
        self.multi_provider_config: MultiProviderConfig | None = None
        self.app_config: Any = None
        self._proxy: str | None = None
        self._prompt_manager = PromptSessionManager(multiline=False)
        self._current_task_id: str | None = None
        self._theme = ThemeManager(app_state.theme)

        from openlaoke.core.hook_system import HookRegistry
        from openlaoke.core.prompt_cache_split import PromptCacheSplit
        from openlaoke.core.small_model_optimizations import (
            ReadLoopTracker,
            SmallModelGuard,
            TerminalOutputCompressor,
            ToolCallValidator,
        )

        self._read_loop_tracker = ReadLoopTracker()
        self._guard: SmallModelGuard | None = None
        self._output_compressor = TerminalOutputCompressor()
        self._tool_validator = ToolCallValidator()
        self._hook_system = HookRegistry.get()
        self._world_sensor: Any = None
        self._cache_guard = CacheGuard(app_state)
        app_state._cache_guard = self._cache_guard
        self._cache_split = PromptCacheSplit()

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

    def _s(self, text: str, style_name: str) -> Text:
        return self._theme.format_text(text, style_name)

    def _t(self, key: str) -> str:
        from openlaoke.core.i18n import get_tui_text

        return get_tui_text(key, getattr(self.app_state, "language", "en"))

    def _register_memory_hooks(self) -> None:
        return None

    def _sense_world(self) -> None:
        return None

    async def run(self) -> None:
        self._running = True
        self._prompt_manager.get_session()
        self._print_banner()
        self._print_welcome()

        if self.app_config:
            self.app_state.language = getattr(self.app_config, "language", "en")

        config = self.multi_provider_config or self.app_state.multi_provider_config
        if not config:
            self.console.print(f"[bold {self._c('error')}]{self._t('no_provider_error')}[/]")
            self.console.print(self._t("run_config_hint"))
            return

        if self.app_config:
            self._proxy = get_proxy_url(self.app_config)

        self.api = MultiProviderClient(config, proxy=self._proxy)

        try:
            while self._running:
                await self._handle_input()
        except (KeyboardInterrupt, EOFError):
            self.console.print(f"\n[{self._c('warning')}]{self._t('goodbye')}[/]")
        finally:
            for task in self._active_tasks:
                task.cancel()
            if self.api:
                await self.api.close()
            self._reset_terminal()

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

        await self._handle_chat(user_input)

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
            self.console.print(f"\n[bold {self._c('error')}]Error:[/] {e}")
            self.app_state.set_error(str(e))
        finally:
            self._agent_task = None
            self.app_state.is_running = False

        while self._input_queue and not self._interrupt_requested:
            queued = self._input_queue.pop(0)
            self.console.print(f"[{self._c('muted')}]Processing queued message...[/]")
            await self._handle_chat(queued)
            return

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

    async def _run_api_loop(self) -> None:
        max_iterations = 100
        iteration = 0
        failed_tool_calls: dict[str, int] = {}

        messages: list[Any] = []
        for msg in self.app_state.messages:
            if msg.role == MessageRole.USER:
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": msg.content,
                }
                if hasattr(msg, "tool_uses") and msg.tool_uses:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tu.id,
                            "type": "function",
                            "function": {
                                "name": tu.name,
                                "arguments": json.dumps(tu.input),
                            },
                        }
                        for tu in msg.tool_uses
                    ]
                messages.append(assistant_msg)
            elif (
                msg.role == MessageRole.SYSTEM
                and isinstance(msg, SystemMessage)
                and msg.tool_use_id
            ):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_use_id,
                        "content": msg.content,
                    }
                )

        runtime_blocks: list[str] = []
        system_prompt = self._cache_guard.system_prompt
        session_ctx = self._cache_guard.ensure_session_context(
            model=self.app_state.session_config.model,
        )
        if session_ctx:
            runtime_blocks.append(session_ctx)
        if self._world_sensor:
            world_ctx = self._world_sensor.to_context_block()
            if world_ctx:
                runtime_blocks.append(f"<sc:context>{world_ctx}</sc:context>")

        from openlaoke.core.small_model_optimizations import (
            apply_structured_thinking_prefix,
            estimate_model_size_from_name,
            get_small_model_guidance,
        )

        model_size = estimate_model_size_from_name(self.app_state.session_config.model)
        from openlaoke.core.model_discovery import get_context_limit

        _active_provider = (
            self.api.config.get_active_provider() if self.api and self.api.config else None
        )
        context_limit = (
            await get_context_limit(_active_provider, self.app_state.session_config.model)
            if _active_provider
            else None
        )
        small_model_guidance = get_small_model_guidance(model_size)
        memory_prompt = ""
        thinking_prefix = apply_structured_thinking_prefix("code")
        runtime_parts: list[str] = []
        if small_model_guidance:
            runtime_parts.append(small_model_guidance)
        if memory_prompt:
            runtime_parts.append(memory_prompt)
        if thinking_prefix:
            runtime_parts.append(thinking_prefix)
        runtime_blocks.extend(runtime_parts)
        if runtime_blocks:
            messages.append(
                {
                    "role": "user",
                    "content": "\n\n".join(runtime_blocks),
                    "system_injected": True,
                }
            )

        needs_tool_hint = self._is_ollama_provider()
        if needs_tool_hint:
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

            from openlaoke.core.compact.fast_pruner import fast_prune, fast_prune_aggressive
            from openlaoke.core.small_model_optimizations import estimate_model_size_from_name

            model_size = estimate_model_size_from_name(self.app_state.session_config.model)
            # Auto-enable caveman mode for tiny/small models (unless explicitly toggled)
            if model_size in ("tiny", "small"):
                self.app_state.caveman_mode = True
            if self._guard is None or self._guard.model_size != model_size:
                from openlaoke.core.small_model_optimizations import SmallModelGuard

                self._guard = SmallModelGuard(model_size=model_size)
            # Prefer the model's real context window from the catalog; fall back
            # to a size-based estimate for providers the catalog does not cover.
            fallback_ctx = {
                "tiny": 4096,
                "small": 8192,
                "medium": 16384,
                "large": 32768,
            }.get(model_size, 8192)
            max_ctx = context_limit or fallback_ctx
            # Reserve room for the model's reply and keep a proportional tail
            # verbatim instead of the small 8k default.
            ctx_budget = max(2048, int(max_ctx * 0.8))
            keep_tail = max(2048, ctx_budget // 3)

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
                            f"[{self._c('muted')}]Context pruned in "
                            f"{prune_result.elapsed_ms:.1f}ms[/]"
                        )

            tools = self.registry.get_all_for_prompt()

            # Apply cache_control markers for Anthropic providers
            if self.api:
                provider = self.api.config.get_active_provider() if self.api.config else None
                if provider and getattr(provider, "provider_type", None):
                    from openlaoke.types.providers import ProviderType

                    if provider.provider_type == ProviderType.ANTHROPIC:
                        messages = CacheGuard.apply_cache_markers(messages)

            from openlaoke.core.small_model_optimizations import sanitize_tool_schema

            for tool_def in tools:
                if "input_schema" in tool_def:
                    tool_def["input_schema"] = sanitize_tool_schema(tool_def["input_schema"])

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

                streaming_supported = True
                response = None
                usage = None
                cost = None
                content_text = ""
                reasoning_text = ""
                tool_uses: list[ToolUseBlock] = []
                plan_retry_count = 0

                if streaming_supported:
                    token_count = 0
                    reasoning_count = 0
                    stream_error: str | None = None
                    start_time = time.time()
                    self._turn_start = start_time
                    status_text = self._build_streaming_display("", 0, 0.0, 0.0)

                    try:
                        with Live(
                            status_text, console=self.console, refresh_per_second=10, transient=True
                        ) as live:
                            async for chunk in self.api.stream_message(
                                system_prompt=system_prompt,
                                messages=messages,
                                tools=tools,
                                model=self.app_state.session_config.model,
                                thinking_budget=self.app_state.session_config.thinking_budget,
                            ):
                                if chunk.event_type == StreamEventType.TEXT:
                                    content_text += chunk.text
                                    token_count += 1
                                elif chunk.event_type == StreamEventType.REASONING:
                                    reasoning_text += chunk.text
                                    reasoning_count += 1
                                elif chunk.event_type == StreamEventType.TOOL_CALL_START:
                                    try:
                                        args = (
                                            json.loads(chunk.tool_call_arguments)
                                            if chunk.tool_call_arguments
                                            else {}
                                        )
                                    except json.JSONDecodeError:
                                        args = {}
                                    tool_uses.append(
                                        ToolUseBlock(
                                            id=chunk.tool_call_id,
                                            name=chunk.tool_call_name,
                                            input=args,
                                        )
                                    )
                                elif chunk.event_type == StreamEventType.USAGE:
                                    if chunk.usage:
                                        usage = chunk.usage
                                    if chunk.cost:
                                        cost = chunk.cost

                                elapsed = max(time.time() - start_time, 0.01)
                                tps = token_count / elapsed
                                live.update(
                                    self._build_streaming_display(
                                        content_text, token_count, tps, elapsed
                                    )
                                )
                    except httpx.HTTPStatusError as e:
                        reason = ""
                        with contextlib.suppress(Exception):
                            reason = (e.response.text or "").strip()[:300]
                        stream_error = f"API {e.response.status_code}"
                        if reason:
                            stream_error += f": {reason}"
                    except Exception as e:
                        stream_error = str(e)[:200]

                    elapsed = max(time.time() - start_time, 0.01)
                    shown_tokens = token_count or reasoning_count
                    label = (
                        "tokens"
                        if token_count
                        else ("reasoning tokens" if reasoning_count else "tokens")
                    )
                    tps = shown_tokens / elapsed
                    self.console.print(
                        f"  [{self._c('muted')}]{shown_tokens} {label} · {tps:.0f} t/s · {elapsed:.1f}s[/]"
                    )
                    if self.app_state.verbose:
                        self.console.print(
                            f"  [{self._c('muted')}]{self._format_context_composition(messages)}[/]"
                        )

                    if stream_error:
                        self.console.print(f"  [bold {self._c('error')}]Error:[/] {stream_error}")
                        break

                    if (
                        token_count == 0
                        and reasoning_count == 0
                        and not tool_uses
                        and not content_text.strip()
                        and elapsed > 5
                    ):
                        self.console.print(
                            f"  [bold {self._c('error')}]Model returned no output[/]"
                            f" (waited {elapsed:.0f}s). Try a different model or check the provider."
                        )
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

                    if reasoning_text:
                        self._last_thinking = reasoning_text
                        self.app_state.last_thinking = reasoning_text
                        self._thinking_duration = (
                            (time.time() - self._turn_start) * 1000 if self._turn_start else 0
                        )
                        self._display_thinking_inline(reasoning_text)

                    if content_text:
                        self._render_response(content_text)

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
                        file_path = tu.input.get("file_path", "")
                        action = (
                            f"  [{self._c('secondary')}]{tu.name}[/] {file_path}"
                            if file_path
                            else f"  [{self._c('secondary')}]{tu.name}[/]"
                        )
                        self.console.print(action)

                    if usage and cost:
                        self.app_state.accumulate_tokens(usage)
                        self.app_state.accumulate_cost(cost)

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
                        assistant_msg_dict: dict[str, Any] = {"role": "assistant"}
                        if content_text:
                            assistant_msg_dict["content"] = content_text
                        if tool_uses:
                            assistant_msg_dict["tool_calls"] = [
                                {
                                    "id": tu.id,
                                    "type": "function",
                                    "function": {
                                        "name": tu.name,
                                        "arguments": json.dumps(tu.input),
                                    },
                                }
                                for tu in tool_uses
                            ]
                        messages.append(assistant_msg_dict)

                    if not tool_uses:
                        if (
                            content_text.strip().upper().startswith("DONE")
                            or "\nDONE" in content_text.upper()
                            or content_text.strip().upper() == "DONE"
                        ):
                            self.console.print(f"  [{self._c('success')}]Task complete (DONE)[/]")
                            break
                        break

                    # Parallel dispatch for read-only tool batches
                    _all_readonly = all(self.registry.is_readonly(tu.name) for tu in tool_uses)
                    if _all_readonly and len(tool_uses) > 1:
                        results = await asyncio.gather(
                            *[self._execute_tool(tu) for tu in tool_uses],
                            return_exceptions=True,
                        )
                        for tool_use, result in zip(tool_uses, results, strict=True):
                            if isinstance(result, BaseException):
                                result_content = f"Error: {result}"
                            else:
                                result_content = (
                                    result.content
                                    if isinstance(result.content, str)
                                    else str(result.content)
                                )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_use.id,
                                    "content": result_content,
                                }
                            )
                            self._record_tool_result(tool_use.id, result_content)
                    else:
                        for tool_use in tool_uses:
                            if not self._running:
                                break

                            corrected_name, corrected_params, val_hint = (
                                self._tool_validator.validate(tool_use.name, tool_use.input)
                            )
                            if (
                                corrected_name != tool_use.name
                                or corrected_params != tool_use.input
                            ):
                                tool_use.name = corrected_name
                                tool_use.input = corrected_params
                                if val_hint:
                                    messages.append({"role": "user", "content": val_hint})

                            tool_key = (
                                f"{tool_use.name}:{json.dumps(tool_use.input, sort_keys=True)}"
                            )
                            failed_tool_calls[tool_key] = failed_tool_calls.get(tool_key, 0) + 1

                            if self._guard:
                                loop_msg = self._guard.notify_tool_call(tool_use.name)
                                if loop_msg:
                                    messages.append({"role": "user", "content": loop_msg})

                            if failed_tool_calls[tool_key] > 3:
                                self.console.print(
                                    f"\n[{self._c('error')}]Tool '{tool_use.name}' called too many times with same parameters.[/]"
                                )
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_use.id,
                                        "content": f"ERROR: Tool '{tool_use.name}' has been called {failed_tool_calls[tool_key]} times with the same parameters.",
                                    }
                                )
                                continue

                            result = await self._execute_tool(tool_use)

                            result_content = (
                                result.content
                                if isinstance(result.content, str)
                                else str(result.content)
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_use.id,
                                    "content": result_content,
                                }
                            )
                            self._record_tool_result(tool_use.id, result_content)

                    self.app_state._persist()

                else:
                    spinner = self.console.status(
                        f"[bold {self._c('primary')}]Thinking...[/]",
                        spinner="dots",
                    )
                    spinner.start()

                    try:
                        response, usage, cost = await self.api.send_message(
                            system_prompt=system_prompt,
                            messages=messages,
                            tools=tools,
                            model=self.app_state.session_config.model,
                            thinking_budget=self.app_state.session_config.thinking_budget,
                        )
                    finally:
                        spinner.stop()

                    if self._guard:
                        content_for_check = response.content or ""
                        quality_msg = self._guard.check_after_api_call(
                            content_for_check, len(response.tool_uses)
                        )
                        if quality_msg:
                            messages.append({"role": "user", "content": quality_msg})

                    self.app_state.accumulate_tokens(usage)
                    self.app_state.accumulate_cost(cost)

                    if response.thinking:
                        self._last_thinking = response.thinking
                        self.app_state.last_thinking = response.thinking
                        self._thinking_duration = (
                            (time.time() - self._turn_start) * 1000 if self._turn_start else 0
                        )
                        self._display_thinking_inline(response.thinking)

                    if response.content:
                        self._render_response(response.content)

                    if self._hook_system.has_hooks("message_transform"):
                        from openlaoke.core.hook_system import HookInput, HookOutput

                        msg_hook_input = HookInput(
                            messages=[{"role": "assistant", "content": response.content or ""}],
                            model_name=self.app_state.session_config.model,
                        )
                        msg_hook_output = HookOutput()
                        self._hook_system.execute_hooks(
                            "message_transform", msg_hook_input, msg_hook_output
                        )
                        if msg_hook_output.messages:
                            response.content = msg_hook_output.messages[0].get(
                                "content", response.content
                            )

                    response_dict: dict[str, Any] = {"role": "assistant"}
                    if response.content:
                        response_dict["content"] = response.content
                    if response.tool_uses:
                        response_dict["tool_calls"] = [
                            {
                                "id": tu.id,
                                "type": "function",
                                "function": {
                                    "name": tu.name,
                                    "arguments": json.dumps(tu.input),
                                },
                            }
                            for tu in response.tool_uses
                        ]
                    messages.append(response_dict)
                    self.app_state.add_message(
                        AssistantMessage(
                            role=MessageRole.ASSISTANT,
                            content=response.content or "",
                            tool_uses=response.tool_uses,
                            thinking=response.thinking or "",
                        ),
                        persist=False,
                    )

                    if not response.tool_uses:
                        rc = (response.content or "").strip().upper()
                        if rc.startswith("DONE") or "\nDONE" in rc:
                            self.console.print(f"  [{self._c('success')}]Task complete (DONE)[/]")
                            break
                        break

                    for tool_use in response.tool_uses:
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

                        if failed_tool_calls[tool_key] > 3:
                            self.console.print(
                                f"\n[{self._c('error')}]Tool '{tool_use.name}' called too many times with same parameters.[/]"
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_use.id,
                                    "content": f"ERROR: Tool '{tool_use.name}' has been called {failed_tool_calls[tool_key]} times with the same parameters.",
                                }
                            )
                            continue

                        result = await self._execute_tool(tool_use)

                        result_content = (
                            result.content
                            if isinstance(result.content, str)
                            else str(result.content)
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_use.id,
                                "content": result_content,
                            }
                        )
                        self._record_tool_result(tool_use.id, result_content)

                    self.app_state._persist()

            except asyncio.CancelledError:
                self._interrupt_requested = True
                self._patch_dangling_tool_calls()
                self.console.print(f"\n[{self._c('warning')}]Interrupted — context preserved.[/]")
                break
            except httpx.HTTPStatusError as e:
                self.console.print(
                    f"\n[bold {self._c('error')}]API Error:[/] {e.response.status_code}"
                )
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                    self.console.print(f"[{self._c('error')}]{error_msg}[/]")
                except Exception:
                    self.console.print(f"[{self._c('error')}]{e.response.text[:500]}[/]")
                break
            except Exception as e:
                self.console.print(f"\n[bold {self._c('error')}]Error:[/] {e}")
                break

    async def _execute_tool(self, tool_use: ToolUseBlock) -> ToolResultBlock:
        tool = self.registry.get(tool_use.name)
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
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Permission denied for {tool_use.name}",
                is_error=True,
            )

        if perm_result == PermissionResult.ASK and self._is_denied_subject(
            tool_use.name, tool_input
        ):
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Permission denied for {tool_use.name} (subject deny rule)",
                is_error=True,
            )

        if perm_result == PermissionResult.ASK and not self.app_state.auto_accept:
            approved = await self._ask_permission(tool_use.name, tool_input, tool)
            if not approved:
                self.console.print(f"  [{self._c('error')}]Denied: {tool_use.name}[/]")
                return ToolResultBlock(
                    tool_use_id=tool_use.id,
                    content=f"User denied {tool_use.name}",
                    is_error=True,
                )

        tool_icon = "\u2219" if not self.app_state.insomnia_mode else "\u2615"
        self.console.print(f"  [{self._c('secondary')}]{tool_icon}{tool_use.name}[/]")

        ctx = ToolContext(
            app_state=self.app_state,
            tool_use_id=tool_use.id,
        )

        validation = tool.validate_input(tool_input)
        if not validation.result:
            self.console.print(f"  [{self._c('error')}]Validation: {validation.message}[/]")
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Validation error: {validation.message}",
                is_error=True,
            )

        result = await tool.safe_call(ctx, **tool_input)

        if tool_use.name in ("Write", "Edit"):
            self._verify_file_written(tool_input, result)

        result_content = result.content if isinstance(result.content, str) else str(result.content)

        # Truncate tool output for history: keep head 70% + tail 30%
        # to preserve both beginning and end of long outputs.
        _max_tool_out = self.app_state.max_tool_history
        if len(result_content.encode("utf-8")) > _max_tool_out:
            from openlaoke.core.tool import truncate_tool_history

            result_content = truncate_tool_history(result_content, _max_tool_out)

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

        rendered = tool.render_result(result)
        if rendered:
            self._print_tool_result(rendered, tool_use.name, result.is_error)

        return result

    def _build_streaming_display(
        self, content: str, tokens: int, tps: float, elapsed: float
    ) -> Any:
        from rich.box import ROUNDED
        from rich.console import Group
        from rich.panel import Panel
        from rich.text import Text

        visible_lines = 8

        if content:
            lines = content.split("\n")
            if len(lines) > visible_lines:
                shown = lines[-visible_lines:]
                body = "\n".join(shown)
                hidden = len(lines) - visible_lines
                body += f"\n[{self._c('muted')}]+ {hidden} more lines[/]"
            else:
                body = content
        else:
            body = f"[{self._c('muted')}]...[/]"

        panel = Panel(
            Text.from_markup(body, justify="left"),
            title=f"[{self._c('muted')}]Streaming[/]",
            border_style=self._c("muted"),
            box=ROUNDED,
            padding=(0, 1),
        )

        counter = Text()
        counter.append(f"  [{self._c('primary')}]{tokens} tokens[/]")
        if tps > 0:
            counter.append(f" [{self._c('muted')}]· {tps:.0f} t/s · {elapsed:.1f}s[/]")

        return Group(panel, counter)

    def _display_thinking_inline(self, thinking: str) -> None:
        enabled = self.app_state.thinking_enabled
        if not enabled:
            self.console.print(
                f"  [{self._c('muted')} dim]Thought: {self._thinking_duration:.0f}ms (Ctrl+G to view)[/]"
            )
            return
        lines = thinking.strip().split("\n")
        max_show = 5
        if len(lines) <= max_show:
            for line in lines:
                self.console.print(f"  [{self._c('muted')}]{line}[/]")
        else:
            for line in lines[:max_show]:
                self.console.print(f"  [{self._c('muted')}]{line}[/]")
            self.console.print(
                f"  [{self._c('muted')} dim]... ({len(lines) - max_show} more lines, Ctrl+G to see all)[/]"
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

    def _is_denied_subject(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        """True when a deny_subject rule stored via 'never' matches this call."""
        subject = self._approval_subject(tool_name, tool_input)
        if not subject:
            return False
        from openlaoke.types.core_types import PermissionResult

        return (
            self.app_state.permission_config.check_tool_subject(tool_name, subject)
            == PermissionResult.DENY
        )

    def _print_tool_result(self, rendered: str, tool_name: str, is_error: bool) -> None:
        if is_error:
            style = self._c("error")
            prefix = "!"
        else:
            style = self._c("muted")
            prefix = " "

        max_inline = 300
        if len(rendered) <= max_inline:
            self.console.print(f"  [{style}]{prefix} {rendered}[/]")
        else:
            self.console.print(f"  [{style}]{prefix} {rendered[:max_inline]}...[/]")
            self.console.print(f"  [{self._c('muted')}]{prefix}   ({len(rendered)} chars total)[/]")

    def _get_git_store(self) -> Any | None:
        return None

    @staticmethod
    def _parse_inline_tool_calls(content: str) -> list[ToolUseBlock]:
        tool_uses: list[ToolUseBlock] = []

        _tool_aliases: dict[str, str] = {
            "write": "Write",
            "read": "Read",
            "edit": "Edit",
            "bash": "Bash",
            "glob": "Glob",
            "grep": "Grep",
            "ls": "ListDirectory",
            "list": "ListDirectory",
            "dir": "ListDirectory",
        }

        def _clean(val: str) -> str:
            val = val.strip().rstrip(",").rstrip(";")
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            return val

        def _parse_simple_line(line: str) -> tuple[str, dict[str, str]] | None:
            parts = line.strip().split()
            if not parts:
                return None
            raw_name = parts[0]
            name = _tool_aliases.get(raw_name, raw_name)
            name = name[0].upper() + name[1:] if name[0].islower() else name

            params: dict[str, str] = {}
            remaining = " ".join(parts[1:])
            pos = 0
            last_key = None
            for km in _KV_PATTERN.finditer(remaining):
                if last_key:
                    params[last_key] = _clean(remaining[pos : km.start()])
                last_key = km.group(1)
                pos = km.end()
            if last_key:
                params[last_key] = _clean(remaining[pos:])
            return (name, params) if name and params else None

        has_xml_format = "<tool_call>" in content
        pattern = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)
        for block in pattern.findall(content):
            tool_name = None
            params = {}

            fn_match = re.search(r"<function=(\w+)>", block)
            if fn_match:
                tool_name = fn_match.group(1)
                param_parts = re.split(r"<parameter=(\w+)>", block)
                if len(param_parts) > 1:
                    i = 1
                    while i < len(param_parts) - 1:
                        key = param_parts[i]
                        val = param_parts[i + 1]
                        val = re.sub(r"\s*</?\w+>\s*", "", val)
                        val = val.strip()
                        if val:
                            params[key] = val
                        i += 2
            elif not tool_uses:
                alt_match = re.match(r"(\w+)\{(.+)\}", block.strip(), re.DOTALL)
                if alt_match:
                    tool_name = alt_match.group(1)
                    body = alt_match.group(2)
                    kv_pattern = re.compile(
                        r"(\w+)\s*:\s*<\|\W+\|\W*\s*>(.*?)(?=<\|\W+\|)", re.DOTALL
                    )
                    for km in kv_pattern.finditer(body):
                        params[km.group(1)] = km.group(2).strip()
                    last_kv = re.search(r"(\w+)\s*:\s*<\|\W+\|\W*\s*>(.*?)}\s*$", body, re.DOTALL)
                    if last_kv:
                        key = last_kv.group(1)
                        val = last_kv.group(2).rstrip("}").strip()
                        if key not in params and val:
                            params[key] = val

            if tool_name and params:
                tool_uses.append(
                    ToolUseBlock(
                        id=f"call_{uuid.uuid4().hex[:12]}",
                        name=tool_name,
                        input=params,
                    )
                )

        if not tool_uses and not has_xml_format:
            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parsed = _parse_simple_line(line)
                if parsed:
                    raw_name = parsed[0]
                    if raw_name and (raw_name[0].isupper() or raw_name in _tool_aliases):
                        tool_uses.append(
                            ToolUseBlock(
                                id=f"call_{uuid.uuid4().hex[:12]}",
                                name=raw_name,
                                input=parsed[1],
                            )
                        )

        return tool_uses

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
