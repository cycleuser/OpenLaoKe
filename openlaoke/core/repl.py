"""REPL loop - the main interaction loop.

Improved with:
- Streaming output (character-by-character rendering inspired by Claude Code)
- Rich-themed permission prompts (replacing bare input())
- Real-time token counter during generation
- Theme-aware colors via ThemeManager
- Expandable tool result display
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from openlaoke.commands.registry import get_command, parse_command, register_all
from openlaoke.core.config_wizard import get_proxy_url
from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.core.prompt_input import PromptSessionManager, run_model_picker_async
from openlaoke.core.state import AppState
from openlaoke.core.supervisor import TaskSupervisor
from openlaoke.core.system_prompt import build_system_prompt
from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.tools.register import register_all_tools
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    PermissionResult,
    StreamEventType,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from openlaoke.types.providers import MultiProviderConfig
from openlaoke.utils.theme import ThemeManager


class REPL:
    """Main REPL loop for OpenLaoKe."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.console = Console(force_terminal=True)
        self.registry = ToolRegistry()
        self.api: MultiProviderClient | None = None
        self._running = False
        self._active_tasks: set[asyncio.Task] = set()
        self.multi_provider_config: MultiProviderConfig | None = None
        self.app_config: Any = None
        self._proxy: str | None = None
        self._prompt_manager = PromptSessionManager(multiline=False)
        self.supervisor = TaskSupervisor(app_state)
        self._current_task_id: str | None = None
        self._insomnia_engine: Any = None
        self._theme = ThemeManager(app_state.theme)

        from openlaoke.core.bitter_lesson_tracker import BitterLessonTracker
        from openlaoke.core.file_state import FileStateStore
        from openlaoke.core.gitstore import GitStore
        from openlaoke.core.hook_system import HookRegistry
        from openlaoke.core.memory import get_memory_manager
        from openlaoke.core.small_model_optimizations import (
            ReadLoopTracker,
            TerminalOutputCompressor,
        )

        self._read_loop_tracker = ReadLoopTracker()
        self._output_compressor = TerminalOutputCompressor()
        self._lesson_tracker = BitterLessonTracker()
        self._hook_system = HookRegistry.get()
        self._memory = get_memory_manager()
        self._memory.load()
        self._file_state = FileStateStore()
        self._git_store: GitStore | None = None

        self._register_memory_hooks()

        register_all()
        register_all_tools(self.registry)

    def _c(self, name: str) -> str:
        return self._theme.color(name)

    def _s(self, text: str, style_name: str) -> Text:
        return self._theme.format_text(text, style_name)

    def _register_memory_hooks(self) -> None:
        from openlaoke.core.memory.memory_hooks import (
            session_start_memory_hook,
            tool_execute_after_memory_hook,
            user_prompt_memory_hook,
        )

        self._hook_system.register(
            "tool_execute_after",
            "memory_extractor",
            tool_execute_after_memory_hook,
            priority=10,
            plugin_name="memory",
        )
        self._hook_system.register(
            "session_start",
            "memory_session_start",
            session_start_memory_hook,
            priority=10,
            plugin_name="memory",
        )
        self._hook_system.register(
            "message_transform",
            "memory_user_prompt",
            user_prompt_memory_hook,
            priority=5,
            plugin_name="memory",
        )

    async def run(self) -> None:
        self._running = True
        self._prompt_manager.get_session()
        self._print_banner()
        self._print_welcome()

        config = self.multi_provider_config or self.app_state.multi_provider_config
        if not config:
            self.console.print(f"[bold {self._c('error')}]Error: No provider configured.[/]")
            self.console.print("Run 'openlaoke --config' to set up a provider.")
            return

        if self.app_config:
            self._proxy = get_proxy_url(self.app_config)

        self.api = MultiProviderClient(config, proxy=self._proxy)

        from openlaoke.core.insomnia_engine import InsomniaEngine

        self._insomnia_engine = InsomniaEngine(self.app_state)
        self.app_state._insomnia_engine = self._insomnia_engine

        if self.app_state.insomnia_mode:
            self.console.print(
                f"[bold {self._c('primary')}]Insomnia mode: Resuming background tasks...[/]"
            )
            await self._insomnia_engine.start()
            if self.app_state.insomnia_task_queue:
                task = asyncio.create_task(self._insomnia_engine._process_queue())
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)

        try:
            while self._running:
                await self._handle_input()
        except (KeyboardInterrupt, EOFError):
            self.console.print(f"\n[{self._c('warning')}]Goodbye![/]")
        finally:
            for task in self._active_tasks:
                task.cancel()
            if self._insomnia_engine and self.app_state.insomnia_mode:
                self._insomnia_engine._save_state()
            if self.api:
                await self.api.close()

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

                self.console.print(f"[{self._c('success')}]Skill activated: {skill.name}[/]")
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
        from openlaoke.commands.skill_shortcuts import SkillActivationResult

        command = get_command(name)
        if not command:
            self.console.print(f"[{self._c('error')}]Unknown command: /{name}[/]")
            self.console.print(f"Type [bold {self._c('primary')}]/help[/] for available commands.")
            return

        ctx = CommandContext(app_state=self.app_state, args=args)
        result = await command.execute(ctx)

        if result.message:
            self.console.print(result.message)

        if result.should_exit:
            self._running = False
        if result.should_clear:
            self.console.clear()

        if isinstance(result, SkillActivationResult) and result.should_continue_chat:
            self.console.print()
            await self._handle_chat(args)

    def _handle_model_switch(self, selection: str) -> None:
        if "/" not in selection:
            return
        provider_name, model_name = selection.split("/", 1)

        config = self.app_state.multi_provider_config or self.multi_provider_config
        if not config:
            return

        provider = config.providers.get(provider_name)
        if not provider:
            self.console.print(f"[{self._c('error')}]Provider not found: {provider_name}[/]")
            return

        config.active_provider = provider_name
        config.active_model = model_name
        self.app_state.session_config.model = model_name

        if self.api:
            self.api._builtin_client = None
            self.api.config = config

        from openlaoke.utils.config import load_config, save_config

        app_config = load_config()
        app_config.providers.active_provider = provider_name
        app_config.providers.active_model = model_name
        save_config(app_config)

        self.console.print(f"[{self._c('success')}]Switched to: {provider_name}/{model_name}[/]")

    async def _handle_chat(self, user_input: str) -> None:
        from openlaoke.core.intent_parser import IntentParser, IntentType

        if self.app_state.local_mode:
            parser = IntentParser()
            intent = parser.parse(user_input)

            if intent.intent_type in [
                IntentType.WRITE_PROGRAM,
                IntentType.WRITE_FUNCTION,
                IntentType.WRITE_CLASS,
            ]:
                await self._handle_command("atomic", user_input)
                return

        self.app_state.is_running = True
        self.app_state.set_error(None)

        if self.app_state.local_mode:
            self.supervisor.parse_request(user_input)
            self._current_task_id = (
                list(self.supervisor.tasks.keys())[-1] if self.supervisor.tasks else None
            )
        else:
            self._current_task_id = None

        user_msg = UserMessage(role=MessageRole.USER, content=user_input)
        self.app_state.add_message(user_msg)

        self._memory.on_user_message(
            user_input,
            self.app_state.session_id,
        )

        if self.app_state.insomnia_mode:
            self.app_state.auto_accept = True
            if self._insomnia_engine:
                task_id = await self._insomnia_engine.add_task(user_input)
                self.console.print(
                    f"[bold {self._c('primary')}]Task queued in insomnia mode: {task_id}[/]"
                )
                if not self._insomnia_engine._current_task:
                    task = asyncio.create_task(self._insomnia_engine._process_queue())
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
                self.app_state.is_running = False
                return

        max_retry_attempts = 3
        retry_count = 0

        while retry_count < max_retry_attempts:
            try:
                await self._run_api_loop()

                artifacts = self._collect_artifacts()

                if self._current_task_id:
                    result = await self.supervisor.check_completion(
                        self._current_task_id, artifacts
                    )

                    if result.is_complete:
                        self.console.print(
                            f"\n[{self._c('success')}]Task completed ({result.completion_percentage:.0f}%)[/]"
                        )

                        from openlaoke.core.small_model_optimizations import (
                            estimate_model_size_from_name,
                        )

                        model_size = estimate_model_size_from_name(
                            self.app_state.session_config.model
                        )
                        self._lesson_tracker.record_outcome(
                            strategy_name="supervisor_check",
                            model_size=model_size,
                            success=True,
                            tokens_used=self.app_state.token_usage.total_tokens,
                        )
                        self._lesson_tracker.save()
                        break

                    if result.should_retry:
                        retry_count += 1
                        self.console.print(
                            f"\n[{self._c('warning')}]Task incomplete ({result.completion_percentage:.0f}%)[/]"
                        )

                        if result.feedback:
                            self.console.print(
                                Panel(
                                    result.feedback,
                                    title="Supervisor Feedback",
                                    border_style=self._c("warning"),
                                )
                            )

                        retry_prompt = self.supervisor.get_retry_prompt(
                            self._current_task_id, result
                        )

                        if retry_count < max_retry_attempts:
                            self.console.print(
                                f"\n[{self._c('primary')}]Retrying... (attempt {retry_count}/{max_retry_attempts})[/]"
                            )

                            user_msg = UserMessage(role=MessageRole.USER, content=retry_prompt)
                            self.app_state.add_message(user_msg)
                            continue
                        else:
                            self.console.print(
                                f"\n[{self._c('error')}]Max retries reached. Task incomplete.[/]"
                            )
                            self.console.print(
                                f"[{self._c('muted')}]Missing: {', '.join(result.missing_requirements[:3])}[/]"
                            )

                            from openlaoke.core.small_model_optimizations import (
                                estimate_model_size_from_name,
                            )

                            model_size = estimate_model_size_from_name(
                                self.app_state.session_config.model
                            )
                            self._lesson_tracker.record_outcome(
                                strategy_name="supervisor_check",
                                model_size=model_size,
                                success=False,
                                error_type="max_retries_reached",
                                tokens_used=self.app_state.token_usage.total_tokens,
                            )
                            self._lesson_tracker.save()
                            break
                    else:
                        break
                else:
                    break

            except Exception as e:
                self.console.print(f"\n[bold {self._c('error')}]Error:[/] {e}")
                self.app_state.set_error(str(e))
                retry_count += 1

                if retry_count >= max_retry_attempts:
                    from openlaoke.core.small_model_optimizations import (
                        estimate_model_size_from_name,
                    )

                    model_size = estimate_model_size_from_name(self.app_state.session_config.model)
                    self._lesson_tracker.record_outcome(
                        strategy_name="error_retry",
                        model_size=model_size,
                        success=False,
                        error_type=type(e).__name__,
                        tokens_used=self.app_state.token_usage.total_tokens,
                    )
                    self._lesson_tracker.save()
                    break

                self.console.print(f"\n[{self._c('warning')}]Retrying after error...[/]")
        else:
            self.console.print(
                f"\n[{self._c('error')}]Failed to complete task after {max_retry_attempts} attempts[/]"
            )

        self.app_state.is_running = False

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
            elif msg.role == MessageRole.SYSTEM and hasattr(msg, "tool_use_id") and msg.tool_use_id:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_use_id,
                        "content": msg.content,
                    }
                )

        while iteration < max_iterations and self._running:
            iteration += 1

            from openlaoke.core.compact.fast_pruner import fast_prune
            from openlaoke.core.small_model_optimizations import estimate_model_size_from_name

            model_size = estimate_model_size_from_name(self.app_state.session_config.model)
            max_tokens_map = {
                "tiny": 4096,
                "small": 8192,
                "medium": 16384,
                "large": 32768,
            }
            max_ctx = max_tokens_map.get(model_size, 8192)

            if len(messages) > 10:
                prune_result = fast_prune(messages, max_tokens=max_ctx)
                if prune_result.tokens_after < prune_result.tokens_before:
                    messages = prune_result.messages
                    if self.app_state.verbose:
                        self.console.print(
                            f"[{self._c('muted')}]Context pruned: "
                            f"{prune_result.tokens_before} -> {prune_result.tokens_after} tokens "
                            f"({prune_result.elapsed_ms:.1f}ms)[/]"
                        )

            is_local_builtin = (
                self.app_state.multi_provider_config
                and self.app_state.multi_provider_config.active_provider == "local_builtin"
            )
            if is_local_builtin:
                from openlaoke.core.system_prompt import build_compact_system_prompt

                user_input = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_input = msg.get("content", "")
                        break
                system_prompt = build_compact_system_prompt(self.app_state, user_input)
            else:
                system_prompt = build_system_prompt(
                    self.app_state,
                    self.registry.get_all_for_prompt(),
                )

            tool_list = self._build_tool_list_for_small_model()
            if tool_list:
                system_prompt = system_prompt.rstrip() + tool_list

            memory_prompt = self._memory.inject_into_system_prompt()
            if memory_prompt:
                system_prompt = system_prompt.rstrip() + "\n\n" + memory_prompt

            from openlaoke.core.small_model_optimizations import (
                apply_structured_thinking_prefix,
                estimate_model_size_from_name,
                get_small_model_guidance,
            )

            model_size = estimate_model_size_from_name(self.app_state.session_config.model)
            small_model_guidance = get_small_model_guidance(model_size)
            if small_model_guidance:
                system_prompt = system_prompt.rstrip() + "\n\n" + small_model_guidance

            user_input_for_thinking = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_input_for_thinking = msg.get("content", "")
                    break
            thinking_prefix = apply_structured_thinking_prefix("code")
            if thinking_prefix and user_input_for_thinking:
                system_prompt = thinking_prefix + "\n" + system_prompt

            tools = self.registry.get_all_for_prompt()

            needs_tool_hint = is_local_builtin or self._is_ollama_provider()
            if needs_tool_hint:
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        ti = (
                            "\n\n[Use tools: output <tool_call> <function=FUNC> <parameter=KEY> value "
                            "</tool_call> for each action. Do NOT describe, just DO. "
                            "Available: Write(file_path,content) Read(file_path) Glob(pattern) Bash(command)]"
                        )
                        if ti not in messages[i].get("content", ""):
                            messages[i]["content"] = messages[i].get("content", "") + ti
                        break

            from openlaoke.core.small_model_optimizations import sanitize_tool_schema

            for tool_def in tools:
                if "input_schema" in tool_def:
                    tool_def["input_schema"] = sanitize_tool_schema(tool_def["input_schema"])

            if self.app_state.insomnia_mode:
                self.console.print(f"[{self._c('muted')}]Insomnia iteration {iteration}[/]")

            try:
                if not self.api:
                    return

                if iteration == 1 and self.app_state.verbose:
                    self.console.print(f"[{self._c('muted')}]Messages: {messages}[/]")

                streaming_supported = not is_local_builtin
                response = None
                usage = None
                cost = None
                content_text = ""
                tool_uses: list[ToolUseBlock] = []
                plan_retry_count = 0

                if streaming_supported:
                    token_count = 0
                    stream_error: str | None = None
                    start_time = time.time()
                    status_text = Text(f"  [{self._c('primary')}]0 tokens[/]")

                    try:
                        with Live(status_text, console=self.console, refresh_per_second=4) as live:
                            async for chunk in self.api.stream_message(
                                system_prompt=system_prompt,
                                messages=messages,
                                tools=tools,
                                model=self.app_state.session_config.model,
                            ):
                                if chunk.event_type == StreamEventType.TEXT:
                                    content_text += chunk.text
                                    token_count += 1
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
                                    Text(
                                        f"  [{self._c('primary')}]{token_count} tokens ({tps:.0f} t/s)[/]"
                                    )
                                )
                    except httpx.HTTPStatusError as e:
                        stream_error = f"API {e.response.status_code}"
                    except Exception as e:
                        stream_error = str(e)[:200]

                    elapsed = max(time.time() - start_time, 0.01)
                    tps = token_count / elapsed
                    self.console.print(
                        f"  [{self._c('muted')}]{token_count} tokens · {tps:.0f} t/s · {elapsed:.1f}s[/]"
                    )

                    if stream_error:
                        self.console.print(f"  [bold {self._c('error')}]Error:[/] {stream_error}")
                        break

                    if token_count == 0 and elapsed > 5:
                        self.console.print(
                            f"  [bold {self._c('error')}]Model returned no output[/]"
                            f" (waited {elapsed:.0f}s). Try a different model or check the provider."
                        )
                        break

                    if content_text and not tool_uses and "<tool_call>" in content_text:
                        parsed_tool_uses = self._parse_inline_tool_calls(content_text)
                        if parsed_tool_uses:
                            tool_uses = parsed_tool_uses
                            content_text = self._strip_tool_calls(content_text)

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
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Do NOT describe steps. Use tools NOW. "
                                    "Output <tool_call> format immediately. "
                                    "Start with Read or Glob to explore the project."
                                ),
                            }
                        )
                        continue

                    if content_text:
                        brief = content_text[:200].replace("\n", " ").strip()
                        if brief:
                            self.console.print(f"  [{self._c('muted')}]{brief}...[/]")

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
                        )
                        self.app_state.add_message(msg)
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
                        break

                    for tool_use in tool_uses:
                        if not self._running:
                            break

                        tool_key = f"{tool_use.name}:{json.dumps(tool_use.input, sort_keys=True)}"
                        failed_tool_calls[tool_key] = failed_tool_calls.get(tool_key, 0) + 1

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
                        )
                    finally:
                        spinner.stop()

                    self.app_state.accumulate_tokens(usage)
                    self.app_state.accumulate_cost(cost)

                    if response.thinking:
                        self.console.print(
                            f"[{self._c('muted')} italic]Thinking: {response.thinking}[/]"
                        )

                    if response.content:
                        brief = response.content[:200].replace("\n", " ").strip()
                        if brief:
                            self.console.print(f"  [{self._c('muted')}]{brief}...[/]")

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

                    if not response.tool_uses:
                        break

                    for tool_use in response.tool_uses:
                        if not self._running:
                            break

                        tool_key = f"{tool_use.name}:{json.dumps(tool_use.input, sort_keys=True)}"
                        failed_tool_calls[tool_key] = failed_tool_calls.get(tool_key, 0) + 1

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

                    self.app_state._persist()

            except asyncio.CancelledError:
                self.console.print(f"\n[{self._c('warning')}]Interrupted.[/]")
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

        if perm_result == PermissionResult.DENY:
            self.console.print(f"  [{self._c('error')}]Denied:[/] {tool_use.name}")
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Permission denied for {tool_use.name}",
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
            file_state=self._file_state,
            git_store=self._get_git_store(),
        )

        validation = tool.validate_input(tool_input)
        if not validation.result:
            self.console.print(f"  [{self._c('error')}]Validation: {validation.message}[/]")
            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Validation error: {validation.message}",
                is_error=True,
            )

        result = await tool.call(ctx, **tool_input)

        if tool_use.name in ("Write", "Edit", "NotebookWrite"):
            self._verify_file_written(tool_input, result)

        if result.is_error:
            self._memory.on_tool_error(
                tool_use.name,
                str(result.content)[:200],
                self.app_state.session_id,
            )

        result_content = result.content if isinstance(result.content, str) else str(result.content)

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

    async def _ask_permission(self, tool_name: str, tool_input: dict[str, Any], tool: Tool) -> bool:
        prompt_text = Text()
        prompt_text.append("  Allow ", style=self._theme.style("warning"))
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
        choices.append("]lways", style=self._theme.style("muted"))
        self.console.print(choices)

        try:
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, lambda: input("  > ").strip().lower())
        except (EOFError, OSError):
            answer = "n"

        if answer in ("n", "no"):
            return False
        if answer in ("a", "always"):
            self.app_state.permission_config.approve_tool(tool_name, remember=True)
        return True

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
        if self._git_store is None:
            from openlaoke.core.gitstore import GitStore

            cwd = self.app_state.get_cwd()
            if not os.path.exists(os.path.join(cwd, ".git")):
                return None
            self._git_store = GitStore(cwd)
        return self._git_store

    def _build_tool_list_for_small_model(self) -> str:
        try:
            all_tools = self.registry.get_all()
        except Exception:
            return ""

        if not all_tools:
            return ""

        lines = [
            "\n\n## Available Tools — USE THEM NOW, do NOT describe what you'll do",
            "Output tool calls in this EXACT format on their own line:",
            "<tool_call> <function=ToolName> <parameter=param1> value1 <parameter=param2> value2 </tool_call>",
            "You MUST output real tool calls, not just say you will. Start with Read or Glob to explore.",
            "",
        ]
        max_tools = min(len(all_tools), 8)
        for t in all_tools[:max_tools]:
            name = getattr(t, "name", "?")
            desc = (getattr(t, "description", "") or "")[:50]
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)

    @staticmethod
    def _parse_inline_tool_calls(content: str) -> list[ToolUseBlock]:
        import re
        import uuid

        tool_uses: list[ToolUseBlock] = []
        pattern = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)

        for block in pattern.findall(content):
            tool_name = None
            params: dict[str, Any] = {}

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
            else:
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
        return tool_uses

    @staticmethod
    def _strip_tool_calls(content: str) -> str:
        import re

        return re.sub(
            r"<tool_call>.*?</tool_call>",
            "",
            content,
            flags=re.DOTALL,
        ).strip()

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
        plan_keywords = [
            "实施步骤",
            "实施计划",
            "创建项目结构",
            "代码实现",
            "第一步",
            "第二步",
            "第三步",
            "步骤",
            "step",
            "1.",
            "2.",
            "3.",
            "I will create",
            "I will write",
            "Let me first",
            "First,",
            "接下来",
        ]
        lower = content.lower()
        return "<tool_call>" not in lower and any(kw.lower() in lower for kw in plan_keywords)

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
                f"[{theme.colors.muted}]Open-source AI coding assistant[/]",
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

        self.console.print(f"\n[{c_prim} bold]Provider:[/] {provider_name}")
        self.console.print(f"[{c_prim} bold]Model:[/] {self.app_state.session_config.model}")
        self.console.print(f"[{c_prim} bold]Working directory:[/] {self.app_state.get_cwd()}")
        if self.app_state.local_mode:
            self.console.print(f"[{c_prim} bold]Mode:[/] [{c_warn}]Local (atomic decomposition)[/]")
        else:
            self.console.print(f"[{c_prim} bold]Mode:[/] [{c_succ}]Online[/]")

        self.console.print(
            f"[{c_prim} bold]Tools:[/] {len(self.registry.get_all())} available{proxy_info}"
        )

        if skills:
            self.console.print(
                f"[{c_prim} bold]Skills:[/] {len(skills)} available (Tab to complete)"
            )
            example_skills = sorted(skills)[:5]
            skills_str = ", ".join(f"/{s}" for s in example_skills)
            if len(skills) > 5:
                skills_str += f", ... ({len(skills) - 5} more)"
            self.console.print(f"  [{c.muted}]{skills_str}[/]")

        if self.app_state.insomnia_mode:
            self.console.print(f"[{c_prim} bold]Mode:[/] [bold {c_prim}]Insomnia[/]")

        self.console.print(
            f"\n[{c.muted}]Type [bold {c_prim}]/help[/] for commands, "
            f"[bold {c_prim}]Tab[/] for completion, or just start chatting.[/]"
        )
