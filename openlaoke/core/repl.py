"""REPL loop - the main interaction loop."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from openlaoke.commands.registry import get_command, parse_command, register_all
from openlaoke.core.config_wizard import get_proxy_url
from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.core.prompt_input import create_prompt_session, get_user_input
from openlaoke.core.state import AppState
from openlaoke.core.supervisor import TaskSupervisor
from openlaoke.core.system_prompt import build_system_prompt
from openlaoke.core.tool import ToolContext, ToolRegistry
from openlaoke.tools.register import register_all_tools
from openlaoke.types.core_types import (
    MessageRole,
    PermissionResult,
    UserMessage,
)
from openlaoke.types.providers import MultiProviderConfig


class REPL:
    """Main REPL loop for OpenLaoKe."""

    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.console = Console(force_terminal=True)
        self.registry = ToolRegistry()
        self.api: MultiProviderClient | None = None
        self._running = False
        self.multi_provider_config: MultiProviderConfig | None = None
        self.app_config: Any = None
        self._proxy: str | None = None
        self._prompt_session = None
        self.supervisor = TaskSupervisor(app_state)
        self._current_task_id: str | None = None

        register_all()
        register_all_tools(self.registry)

    async def run(self) -> None:
        """Start the REPL loop."""
        self._running = True

        self._prompt_session = create_prompt_session()

        self._print_banner()
        self._print_welcome()

        config = self.multi_provider_config or self.app_state.multi_provider_config
        if not config:
            self.console.print("[bold red]Error: No provider configured.[/bold red]")
            self.console.print("Run 'openlaoke --config' to set up a provider.")
            return

        if self.app_config:
            self._proxy = get_proxy_url(self.app_config)

        self.api = MultiProviderClient(config, proxy=self._proxy)

        try:
            while self._running:
                await self._handle_input()
        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[yellow]Goodbye![/yellow]")
        finally:
            if self.api:
                await self.api.close()

    async def _handle_input(self) -> None:
        """Get input from user and process it."""
        self.console.print()

        user_input = await get_user_input(self._prompt_session)

        if user_input is None:
            self._running = False
            return

        user_input = user_input.strip()
        if not user_input:
            return

        if user_input.startswith("/"):
            from openlaoke.core.skill_system import load_skill

            parts = user_input.split(None, 1)
            potential_name = parts[0][1:] if parts else ""
            skill_args = parts[1] if len(parts) > 1 else ""

            skill = load_skill(potential_name)
            if skill:
                if hasattr(self.app_state, "active_skills"):
                    if potential_name not in self.app_state.active_skills:
                        self.app_state.active_skills.append(potential_name)

                self.console.print(f"[green]✓ Skill activated: {skill.name}[/green]")
                if skill.description:
                    desc = skill.description[:100]
                    if len(skill.description) > 100:
                        desc += "..."
                    self.console.print(f"  [dim]{desc}[/dim]")

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
        """Execute a slash command."""
        from openlaoke.commands.base import CommandContext
        from openlaoke.commands.skill_shortcuts import SkillActivationResult

        command = get_command(name)
        if not command:
            self.console.print(f"[red]Unknown command: /{name}[/red]")
            self.console.print("Type [bold]/help[/bold] for available commands.")
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

    async def _handle_chat(self, user_input: str) -> None:
        """Process a chat message through the AI model."""
        from openlaoke.core.intent_parser import IntentParser, IntentType
        from openlaoke.core.translation import TranslationPipeline, Language

        translation = TranslationPipeline()
        english_input, original_lang = translation.prepare_for_processing(user_input)

        if original_lang != Language.ENGLISH:
            self.console.print(f"[dim]Original: {user_input[:50]}...[/dim]")
            self.console.print(f"[dim]Translated: {english_input[:50]}...[/dim]")
            combined_input = f"[Original ({original_lang.value}): {user_input}]\n\n[English translation: {english_input}]"
        else:
            combined_input = user_input

        if self.app_state.local_mode:
            parser = IntentParser()
            intent = parser.parse(english_input)

            if original_lang == Language.ENGLISH and intent.intent_type in [
                IntentType.WRITE_PROGRAM,
                IntentType.WRITE_FUNCTION,
                IntentType.WRITE_CLASS,
            ]:
                await self._handle_command("atomic", combined_input)
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

        user_msg = UserMessage(role=MessageRole.USER, content=combined_input)
        self.app_state.add_message(user_msg)

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
                            f"\n[green]✓ Task completed ({result.completion_percentage:.0f}%)[/green]"
                        )
                        break

                    if result.should_retry:
                        retry_count += 1
                        self.console.print(
                            f"\n[yellow]⚠ Task incomplete ({result.completion_percentage:.0f}%)[/yellow]"
                        )

                        if result.feedback:
                            self.console.print(
                                Panel(
                                    result.feedback,
                                    title="Supervisor Feedback",
                                    border_style="yellow",
                                )
                            )

                        retry_prompt = self.supervisor.get_retry_prompt(
                            self._current_task_id, result
                        )

                        if retry_count < max_retry_attempts:
                            self.console.print(
                                f"\n[cyan]Retrying... (attempt {retry_count}/{max_retry_attempts})[/cyan]"
                            )

                            user_msg = UserMessage(role=MessageRole.USER, content=retry_prompt)
                            self.app_state.add_message(user_msg)
                            continue
                        else:
                            self.console.print("\n[red]Max retries reached. Task incomplete.[/red]")
                            self.console.print(
                                f"[dim]Missing: {', '.join(result.missing_requirements[:3])}[/dim]"
                            )
                            break
                    else:
                        break
                else:
                    break

            except Exception as e:
                self.console.print(f"\n[bold red]Error:[/bold red] {e}")
                self.app_state.set_error(str(e))
                retry_count += 1

                if retry_count >= max_retry_attempts:
                    break

                self.console.print("\n[yellow]Retrying after error...[/yellow]")
        else:
            self.console.print(
                f"\n[red]Failed to complete task after {max_retry_attempts} attempts[/red]"
            )

        self.app_state.is_running = False

    def _collect_artifacts(self) -> dict[str, Any]:
        """Collect artifacts from the conversation for supervision check."""
        artifacts = {
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

        import glob

        for pattern in ["*.svg", "*.png", "*.pdf"]:
            files = glob.glob(f"{cwd}/{pattern}")
            artifacts["output_files"].extend(files)

        return artifacts

    async def _run_api_loop(self) -> None:
        """Main API interaction loop."""
        max_iterations = 100
        iteration = 0

        messages: list[dict[str, Any]] = []
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
                            "function": {
                                "name": tu.name,
                                "arguments": json.dumps(tu.input),
                            },
                        }
                        for tu in msg.tool_uses
                    ]
                messages.append(assistant_msg)
            elif msg.role == MessageRole.TOOL:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_use_id,
                        "content": msg.content,
                    }
                )

        while iteration < max_iterations and self._running:
            iteration += 1

            system_prompt = build_system_prompt(
                self.app_state,
                self.registry.get_all_for_prompt(),
            )

            tools = self.registry.get_all_for_prompt()

            self.console.print()
            spinner = self.console.status("[bold blue]Thinking...[/bold blue]", spinner="dots")
            spinner.start()

            try:
                if not self.api:
                    spinner.stop()
                    return

                if iteration == 1 and self.app_state.verbose:
                    self.console.print(f"[dim]Messages: {messages}[/dim]")
                response, usage, cost = await self.api.send_message(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                    model=self.app_state.session_config.model,
                )

                spinner.stop()

                self.app_state.accumulate_tokens(usage)
                self.app_state.accumulate_cost(cost)

                if response.content:
                    self.console.print(Markdown(response.content))

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if response.content:
                    assistant_msg["content"] = response.content
                if response.tool_uses:
                    assistant_msg["tool_calls"] = [
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
                messages.append(assistant_msg)

                if not response.tool_uses:
                    break

                for tool_use in response.tool_uses:
                    if not self._running:
                        break

                    result = await self._execute_tool(tool_use)

                    result_content = (
                        result.content if isinstance(result.content, str) else str(result.content)
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_use.id,
                            "content": result_content,
                        }
                    )

            except asyncio.CancelledError:
                spinner.stop()
                self.console.print("\n[yellow]Interrupted.[/yellow]")
                break
            except httpx.HTTPStatusError as e:
                spinner.stop()
                self.console.print(f"\n[bold red]API Error:[/bold red] {e.response.status_code}")
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                    self.console.print(f"[red]{error_msg}[/red]")
                except Exception:
                    self.console.print(f"[red]{e.response.text[:500]}[/red]")
                break
            except Exception as e:
                spinner.stop()
                self.console.print(f"\n[bold red]Error:[/bold red] {e}")
                break

    async def _execute_tool(self, tool_use) -> Any:
        """Execute a single tool call with permission checking."""
        tool = self.registry.get(tool_use.name)
        if not tool:
            self.console.print(f"  [dim]Unknown tool: {tool_use.name}[/dim]")
            from openlaoke.types.core_types import ToolResultBlock

            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Unknown tool: {tool_use.name}",
                is_error=True,
            )

        perm_result = tool.check_permissions(
            tool_use.input,
            self.app_state.permission_config,
        )

        if perm_result == PermissionResult.DENY:
            self.console.print(
                f"  [red]Denied:[/red] {tool_use.name} - {tool.get_deny_message(tool_use.input)}"
            )
            from openlaoke.types.core_types import ToolResultBlock

            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Permission denied for {tool_use.name}",
                is_error=True,
            )

        if perm_result == PermissionResult.ASK and not self.app_state.auto_accept:
            self.console.print(
                f"  [yellow]Allow {tool_use.name}?[/yellow] "
                f"[green](y)es[/green] / [red](n)o[/red] / [blue](a)lways[/blue]"
            )
            try:
                answer = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("  > ").strip().lower()
                )
            except (EOFError, OSError):
                answer = "n"

            if answer in ("n", "no"):
                self.console.print(f"  [red]Denied: {tool_use.name}[/red]")
                from openlaoke.types.core_types import ToolResultBlock

                return ToolResultBlock(
                    tool_use_id=tool_use.id,
                    content=f"User denied {tool_use.name}",
                    is_error=True,
                )
            elif answer in ("a", "always"):
                self.app_state.permission_config.approve_tool(tool_use.name, remember=True)

        self.console.print(f"  [dim]{tool_use.name}[/dim]")

        ctx = ToolContext(
            app_state=self.app_state,
            tool_use_id=tool_use.id,
        )

        validation = tool.validate_input(tool_use.input)
        if not validation.result:
            self.console.print(f"  [red]Validation failed: {validation.message}[/red]")
            from openlaoke.types.core_types import ToolResultBlock

            return ToolResultBlock(
                tool_use_id=tool_use.id,
                content=f"Validation error: {validation.message}",
                is_error=True,
            )

        result = await tool.call(ctx, **tool_use.input)

        rendered = tool.render_result(result)
        if rendered and len(rendered) > 200:
            self.console.print(f"  [dim]{rendered[:200]}...[/dim]")
        elif rendered:
            self.console.print(f"  [dim]{rendered}[/dim]")

        return result

    def _print_banner(self) -> None:
        from openlaoke import __version__

        self.console.print(
            Panel.fit(
                f"[bold cyan]OpenLaoKe[/bold cyan] v{__version__}\n"
                "[dim]Open-source AI coding assistant[/dim]",
                border_style="cyan",
            )
        )

    def _print_welcome(self) -> None:
        provider_name = "unknown"
        if self.multi_provider_config:
            provider_name = self.multi_provider_config.active_provider
        elif self.app_state.multi_provider_config:
            provider_name = self.app_state.multi_provider_config.active_provider

        proxy_info = ""
        if self._proxy:
            proxy_info = f"\n[bold]Proxy:[/bold] {self._proxy}"

        # Get available skills
        from openlaoke.core.skill_system import list_available_skills

        skills = list_available_skills()

        self.console.print(f"\n[bold]Provider:[/bold] {provider_name}")
        self.console.print(f"[bold]Model:[/bold] {self.app_state.session_config.model}")
        self.console.print(f"[bold]Working directory:[/bold] {self.app_state.get_cwd()}")
        if self.app_state.local_mode:
            self.console.print(
                "[bold]Mode:[/bold] [yellow]Local (atomic decomposition enabled)[/yellow]"
            )
        else:
            self.console.print("[bold]Mode:[/bold] [green]Online (direct API calls)[/green]")
        self.console.print(
            f"[bold]Tools:[/bold] {len(self.registry.get_all())} available{proxy_info}"
        )

        if skills:
            self.console.print(
                f"[bold]Skills:[/bold] {len(skills)} available (use Tab to complete)"
            )
            # Show first few skills as examples
            example_skills = sorted(skills)[:5]
            skills_str = ", ".join(f"/{s}" for s in example_skills)
            if len(skills) > 5:
                skills_str += f", ... ({len(skills) - 5} more)"
            self.console.print(f"[dim]  Examples: {skills_str}[/dim]")

        self.console.print(
            "\n[dim]Type [bold]/help[/bold] for commands, [bold]Tab[/bold] for skill completion, or just start chatting.[/dim]"
        )
