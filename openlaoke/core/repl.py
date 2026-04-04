"""REPL loop - the main interaction loop."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import readline
from typing import Any

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from openlaoke.commands.registry import get_command, parse_command, register_all
from openlaoke.core.config_wizard import get_proxy_url
from openlaoke.core.multi_provider_api import MultiProviderClient
from openlaoke.core.state import AppState
from openlaoke.core.system_prompt import build_system_prompt
from openlaoke.core.tool import ToolContext, ToolRegistry
from openlaoke.core.autocomplete import get_autocomplete_manager
from openlaoke.tools.register import register_all_tools
from openlaoke.types.core_types import (
    AssistantMessage,
    MessageRole,
    PermissionResult,
    SystemMessage,
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

        register_all()
        register_all_tools(self.registry)
        
        self._setup_completion()

    def _setup_completion(self):
        """Setup tab completion following OpenCode's behavior."""
        manager = get_autocomplete_manager()
        manager._cwd = self.app_state.get_cwd()
        
        def complete(text: str, state: int):
            """自定义补全函数"""
            if state == 0:
                # 首次调用
                manager.state.reset()
                
                # 检查是否以 / 开头（命令/技能补全）
                if text.startswith("/"):
                    manager.start_completion("/", len(text), text)
                    return
            
            # 返回补全选项
            if manager.state.visible and manager.state.options:
                if state < len(manager.state.options):
                    opt = manager.state.options[state]
                    return opt.display
            
            return None
        
        readline.set_completer(complete)
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(" \t\n")
        
        # 保存 manager 供后续使用
        self._autocomplete_manager = manager

    async def run(self) -> None:
        """Start the REPL loop."""
        self._running = True

        self._print_banner()
        self._print_welcome()

        config = self.multi_provider_config or self.app_state.multi_provider_config
        if not config:
            self.console.print(
                "[bold red]Error: No provider configured.[/bold red]"
            )
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
        try:
            # 使用 readline 进行输入，支持 Tab 补全
            self.console.print()
            try:
                user_input = input("\033[1;32mOpenLaoKe\033[0m: ")
            except EOFError:
                self._running = False
                return
        except KeyboardInterrupt:
            self._running = False
            return

        user_input = user_input.strip()
        if not user_input:
            return
        
        # 如果输入以 / 开头但没有空格，可能是想使用技能
        if user_input.startswith("/") and " " not in user_input:
            # 检查是否是有效的技能或命令
            from openlaoke.core.skill_system import load_skill
            
            potential_name = user_input[1:]
            
            # 检查是否是技能
            skill = load_skill(potential_name)
            if skill:
                # 激活技能
                if hasattr(self.app_state, 'active_skills'):
                    if potential_name not in self.app_state.active_skills:
                        self.app_state.active_skills.append(potential_name)
                
                self.console.print(f"[green]✓ Skill activated: {skill.name}[/green]")
                if skill.description:
                    desc = skill.description[:100]
                    if len(skill.description) > 100:
                        desc += "..."
                    self.console.print(f"  [dim]{desc}[/dim]")
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

        command = get_command(name)
        if not command:
            self.console.print(f"[red]Unknown command: /{name}[/red]")
            self.console.print('Type [bold]/help[/bold] for available commands.')
            return

        ctx = CommandContext(app_state=self.app_state, args=args)
        result = await command.execute(ctx)

        if result.message:
            self.console.print(result.message)

        if result.should_exit:
            self._running = False
        if result.should_clear:
            self.console.clear()

    async def _handle_chat(self, user_input: str) -> None:
        """Process a chat message through the AI model."""
        self.app_state.is_running = True
        self.app_state.set_error(None)

        user_msg = UserMessage(role=MessageRole.USER, content=user_input)
        self.app_state.add_message(user_msg)

        try:
            await self._run_api_loop()
        except Exception as e:
            self.console.print(f"\n[bold red]Error:[/bold red] {e}")
            self.app_state.set_error(str(e))
        finally:
            self.app_state.is_running = False

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
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_use_id,
                    "content": msg.content,
                })

        while iteration < max_iterations and self._running:
            iteration += 1

            system_prompt = build_system_prompt(
                self.app_state,
                self.registry.get_all_for_prompt(),
            )

            tools = self.registry.get_all_for_prompt()

            self.console.print()
            spinner = self.console.status(
                "[bold blue]Thinking...[/bold blue]", spinner="dots"
            )
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

                    result_content = result.content if isinstance(result.content, str) else str(result.content)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_use.id,
                        "content": result_content,
                    })

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
        self.console.print(f"[bold]Tools:[/bold] {len(self.registry.get_all())} available{proxy_info}")
        
        if skills:
            self.console.print(f"[bold]Skills:[/bold] {len(skills)} available (use Tab to complete)")
            # Show first few skills as examples
            example_skills = sorted(skills)[:5]
            skills_str = ", ".join(f"/{s}" for s in example_skills)
            if len(skills) > 5:
                skills_str += f", ... ({len(skills) - 5} more)"
            self.console.print(f"[dim]  Examples: {skills_str}[/dim]")
        
        self.console.print(f"\n[dim]Type [bold]/help[/bold] for commands, [bold]Tab[/bold] for skill completion, or just start chatting.[/dim]")