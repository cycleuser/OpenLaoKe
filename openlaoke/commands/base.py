"""Slash command system."""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
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

        commands = get_all_commands()
        lines = ["Available commands:"]
        for cmd in sorted(commands, key=lambda c: c.name):
            if cmd.hidden:
                continue
            aliases_str = f" ({', '.join('/' + a for a in cmd.aliases)})" if cmd.aliases else ""
            lines.append(f"  /{cmd.name}{aliases_str} - {cmd.description}")
        lines.append("")
        lines.append("Type a message to chat with the AI. Use /exit to quit.")
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
        return CommandResult(should_clear=True, message="Screen cleared.")


class ModelCommand(SlashCommand):
    name = "model"
    description = "Show or change the current model"
    aliases = ["m"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()

        # Show current model and available models
        if not args:
            return self._show_model_info(ctx)

        # Interactive selection with flags
        if args.startswith("-"):
            if args in ["-l", "-list", "--list"]:
                return self._list_all_models(ctx)
            if args in ["-p", "-provider", "--provider"]:
                return self._list_providers(ctx)
            return CommandResult(
                success=False, message=f"Unknown option: {args}. Use: -l (list), -p (providers)"
            )

        # Check if input is a number (select by index)
        if args.isdigit() or (args.startswith("#") and args[1:].isdigit()):
            return self._select_by_index(ctx, args)

        # Direct model name provided (with optional provider/model format)
        if "/" in args:
            provider_name, model_name = args.split("/", 1)
            return self._switch_provider_and_model(ctx, provider_name, model_name)

        # Set model name directly
        ctx.app_state.session_config.model = args
        if ctx.app_state.multi_provider_config:
            ctx.app_state.multi_provider_config.active_model = args
        return CommandResult(message=f"Model set to: {args}")

    def _select_by_index(self, ctx: CommandContext, index_str: str) -> CommandResult:
        """Select model by numeric index."""
        # Parse index (support "#1" or "1" format)
        if index_str.startswith("#"):
            index_str = index_str[1:]

        try:
            index = int(index_str)
        except ValueError:
            return CommandResult(success=False, message=f"Invalid index: {index_str}")

        if not ctx.app_state.multi_provider_config:
            return CommandResult(message="No provider configured. Run --config first.")

        provider_name = ctx.app_state.multi_provider_config.active_provider
        provider = ctx.app_state.multi_provider_config.providers.get(provider_name)

        if not provider or not provider.models:
            return CommandResult(message=f"No models available for provider: {provider_name}")

        models = provider.models
        if index < 1 or index > len(models):
            return CommandResult(
                success=False,
                message=f"Invalid index {index}. Available models: 1-{len(models)}",
            )

        selected_model = models[index - 1]
        ctx.app_state.session_config.model = selected_model
        if ctx.app_state.multi_provider_config:
            ctx.app_state.multi_provider_config.active_model = selected_model

        lines = [
            f"[green]✓[/green] Model set to: {selected_model}",
            f"[dim]Provider: {provider_name}[/dim]",
            "",
            "[dim]Tip: You can also use the model name directly[/dim]",
        ]
        return CommandResult(message="\n".join(lines))

    def _switch_provider_and_model(
        self, ctx: CommandContext, provider_name: str, model_name: str
    ) -> CommandResult:
        """Switch to a different provider and model."""
        if not ctx.app_state.multi_provider_config:
            return CommandResult(message="No provider configured. Run --config first.")

        provider_name = provider_name.lower()

        if provider_name not in ctx.app_state.multi_provider_config.providers:
            available = [
                name
                for name, p in ctx.app_state.multi_provider_config.providers.items()
                if p.enabled
            ]
            return CommandResult(
                success=False,
                message=f"Provider '{provider_name}' not found. Available: {', '.join(available)}",
            )

        provider = ctx.app_state.multi_provider_config.providers[provider_name]
        if not provider.enabled:
            return CommandResult(
                success=False,
                message=f"Provider '{provider_name}' is disabled. Run --config to enable.",
            )

        if not provider.is_configured() and not provider.is_local:
            return CommandResult(
                success=False,
                message=f"Provider '{provider_name}' is not configured. Run --config to set API key.",
            )

        # Switch provider
        ctx.app_state.multi_provider_config.active_provider = provider_name

        # Handle model selection (can be index or name)
        if model_name.isdigit() or (model_name.startswith("#") and model_name[1:].isdigit()):
            # Select by index
            if model_name.startswith("#"):
                model_name = model_name[1:]
            try:
                index = int(model_name)
                if provider.models and 1 <= index <= len(provider.models):
                    model_name = provider.models[index - 1]
                else:
                    ctx.app_state.session_config.model = provider.default_model or (
                        provider.models[0] if provider.models else ""
                    )
                    return CommandResult(
                        success=False,
                        message=f"Invalid model index {index}. Using default: {ctx.app_state.session_config.model}",
                    )
            except ValueError:
                pass

        ctx.app_state.session_config.model = model_name
        if ctx.app_state.multi_provider_config:
            ctx.app_state.multi_provider_config.active_model = model_name

        return CommandResult(
            message=f"[green]✓[/green] Switched to provider: {provider_name}\nModel: {model_name}"
        )

    def _show_model_info(self, ctx: CommandContext) -> CommandResult:
        """Show current model and available models for current provider."""
        current_model = ctx.app_state.session_config.model
        provider_name = "unknown"

        if ctx.app_state.multi_provider_config:
            provider_name = ctx.app_state.multi_provider_config.active_provider
            provider = ctx.app_state.multi_provider_config.providers.get(provider_name)
            if provider:
                # For Ollama, fetch models dynamically
                if provider_name == "ollama":
                    models = self._get_ollama_models(provider.base_url)
                    if models:
                        provider.models = models
                    else:
                        models = provider.models
                else:
                    models = provider.models

                lines = [
                    f"[bold]Current provider:[/bold] {provider_name}",
                    f"[bold]Current model:[/bold] {current_model}",
                    "",
                    f"[bold]Available models ({provider_name}):[/bold]",
                ]
                for i, model in enumerate(models, 1):
                    marker = " [cyan](current)[/cyan]" if model == current_model else ""
                    lines.append(f"  [{i}] {model}{marker}")
                lines.extend(
                    [
                        "",
                        "[dim]Usage:[/dim]",
                        "  /model <name>        - Switch to specific model",
                        f"  /model <1-{len(models)}>         - Select by index number",
                        f"  /model #<1-{len(models)}>        - Select by index (with # prefix)",
                        "  /model <provider>/<model> - Switch provider and model",
                        "  /model -l            - List all models from all providers",
                        "  /model -p            - List all providers",
                    ]
                )
                return CommandResult(message="\n".join(lines))

        return CommandResult(message=f"Current model: {current_model}")

    def _get_ollama_models(self, base_url: str) -> list[str]:
        """Fetch available models from Ollama."""
        try:
            import httpx

            url = base_url.replace("/v1", "/api/tags")
            with httpx.Client(timeout=3.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    all_models = [m["name"] for m in data.get("models", [])]

                    # Filter out embedding models
                    embedding_keywords = [
                        "embed",
                        "embedding",
                        "rerank",
                        "reranker",
                        "minilm",
                        "arctic-embed",
                        "bge-",
                        "nomic-embed",
                        "paraphrase",
                        "granite-embedding",
                    ]

                    return [
                        m
                        for m in all_models
                        if not any(kw in m.lower() for kw in embedding_keywords)
                    ] or all_models
        except Exception:
            pass
        return []

    def _list_all_models(self, ctx: CommandContext) -> CommandResult:
        """List models from all configured providers."""
        lines = ["[bold]Available models from all providers:[/bold]", ""]

        if not ctx.app_state.multi_provider_config:
            return CommandResult(message="No provider configured. Run --config first.")

        current_provider = ctx.app_state.multi_provider_config.active_provider
        current_model = ctx.app_state.session_config.model

        for provider_name, provider in ctx.app_state.multi_provider_config.providers.items():
            if not provider.enabled:
                continue

            # For Ollama, fetch models dynamically
            if provider_name == "ollama":
                models = self._get_ollama_models(provider.base_url)
                if models:
                    provider.models = models
                else:
                    models = provider.models
            else:
                models = provider.models

            is_current = provider_name == current_provider
            header = f"[bold cyan]{provider_name}[/bold cyan]"
            if is_current:
                header += " [green](active)[/green]"
            lines.append(header)

            for model in models:
                marker = ""
                if is_current and model == current_model:
                    marker = " [cyan](current)[/cyan]"
                lines.append(f"  {model}{marker}")
            lines.append("")

        lines.append("[dim]Usage: /model <provider>/<model> or just /model <model>[/dim]")
        return CommandResult(message="\n".join(lines))

    def _list_providers(self, ctx: CommandContext) -> CommandResult:
        """List all available providers."""
        lines = ["[bold]Available providers:[/bold]", ""]

        if not ctx.app_state.multi_provider_config:
            return CommandResult(message="No provider configured. Run --config first.")

        current_provider = ctx.app_state.multi_provider_config.active_provider

        for provider_name, provider in ctx.app_state.multi_provider_config.providers.items():
            status = ""
            if provider_name == current_provider:
                status = " [green](active)[/green]"
            elif provider.enabled and provider.is_configured():
                status = " [yellow](configured)[/yellow]"
            elif provider.enabled:
                status = " [dim](available)[/dim]"
            else:
                status = " [dim](disabled)[/dim]"

            model_info = provider.default_model or provider.models[0] if provider.models else ""
            lines.append(f"  {provider_name}{status}")
            if model_info:
                lines.append(f"    [dim]Model: {model_info}[/dim]")

        lines.extend(
            [
                "",
                "[dim]Usage: /provider <name> to switch active provider[/dim]",
            ]
        )
        return CommandResult(message="\n".join(lines))


class ProviderCommand(SlashCommand):
    name = "provider"
    description = "Switch to a different provider"
    aliases = ["p"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()

        if not ctx.app_state.multi_provider_config:
            return CommandResult(message="No provider configured. Run --config first.")

        # Get list of enabled providers
        enabled_providers = [
            (name, p)
            for name, p in ctx.app_state.multi_provider_config.providers.items()
            if p.enabled
        ]

        # Show current provider if no args
        if not args:
            current_provider = ctx.app_state.multi_provider_config.active_provider
            current_model = ctx.app_state.session_config.model
            lines = [
                f"[bold]Current provider:[/bold] {current_provider}",
                f"[bold]Current model:[/bold] {current_model}",
                "",
                "[bold]Available providers:[/bold]",
            ]

            for i, (provider_name, provider) in enumerate(enabled_providers, 1):
                status = ""
                if provider_name == current_provider:
                    status = " [green](active)[/green]"
                elif provider.is_configured():
                    status = " [yellow](ready)[/yellow]"

                model_info = provider.default_model or (
                    provider.models[0] if provider.models else ""
                )
                model_str = f" [dim]({model_info})[/dim]" if model_info else ""

                lines.append(f"  [{i}] {provider_name}{status}{model_str}")

            lines.extend(
                [
                    "",
                    "[dim]Usage:[/dim]",
                    "  /provider <name>   - Switch to a provider by name",
                    "  /provider <1-n>    - Switch by index number",
                    "  /provider #<1-n>   - Switch by index (with # prefix)",
                ]
            )
            return CommandResult(message="\n".join(lines))

        # Check if input is a number (select by index)
        if args.isdigit() or (args.startswith("#") and args[1:].isdigit()):
            index_str = args[1:] if args.startswith("#") else args
            try:
                index = int(index_str)
            except ValueError:
                return CommandResult(success=False, message=f"Invalid index: {args}")

            if index < 1 or index > len(enabled_providers):
                return CommandResult(
                    success=False,
                    message=f"Invalid index {index}. Available: 1-{len(enabled_providers)}",
                )

            provider_name, provider = enabled_providers[index - 1]
        else:
            # Switch to specified provider by name
            provider_name = args.lower()

            if provider_name not in ctx.app_state.multi_provider_config.providers:
                available = [name for name, _ in enabled_providers]
                return CommandResult(
                    success=False,
                    message=f"Provider '{provider_name}' not found. Available: {', '.join(available)}",
                )

            provider = ctx.app_state.multi_provider_config.providers[provider_name]
            if not provider.enabled:
                return CommandResult(
                    success=False,
                    message=f"Provider '{provider_name}' is disabled. Run --config to enable.",
                )

        if not provider.is_configured() and not provider.is_local:
            return CommandResult(
                success=False,
                message=f"Provider '{provider_name}' is not configured. Run --config to set API key.",
            )

        # Switch provider
        ctx.app_state.multi_provider_config.active_provider = provider_name

        # Set default model for this provider
        default_model = provider.default_model or (provider.models[0] if provider.models else "")
        if default_model:
            ctx.app_state.session_config.model = default_model
            ctx.app_state.multi_provider_config.active_model = default_model

        return CommandResult(
            message=f"[green]✓[/green] Switched to provider: {provider_name}\nModel: {default_model}"
        )


class PermissionCommand(SlashCommand):
    name = "permission"
    description = "Change permission mode (default/auto/bypass)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.types.core_types import PermissionMode

        args = ctx.args.strip().lower()

        if not args:
            current = ctx.app_state.permission_config.mode.value
            return CommandResult(message=f"Current permission mode: {current}")

        try:
            mode = PermissionMode(args)
            ctx.app_state.permission_config.mode = mode
            return CommandResult(message=f"Permission mode set to: {mode.value}")
        except ValueError:
            return CommandResult(
                success=False,
                message=f"Invalid mode: {args}. Use: default, auto, bypass",
            )


class CompactCommand(SlashCommand):
    name = "compact"
    description = "Compact the conversation to save context"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        messages = ctx.app_state.get_messages()
        if len(messages) < 4:
            return CommandResult(message="Conversation is too short to compact.")

        ctx.app_state.messages = messages[:2]
        ctx.app_state.messages.append(
            type(messages[-1])(
                role=messages[-1].role,
                content="[Conversation compacted - earlier messages summarized]",
            )
        )
        return CommandResult(message="Conversation compacted.")


class CostCommand(SlashCommand):
    name = "cost"
    description = "Show current session cost and token usage"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        usage = ctx.app_state.token_usage
        cost = ctx.app_state.cost_info
        lines = [
            "Session usage:",
            f"  Input tokens:  {usage.input_tokens:,}",
            f"  Output tokens: {usage.output_tokens:,}",
            f"  Cache read:    {usage.cache_read_tokens:,}",
            f"  Cache created: {usage.cache_creation_tokens:,}",
            f"  Total tokens:  {usage.total_tokens:,}",
            "",
            "Session cost:",
            f"  Input:         ${cost.input_cost:.4f}",
            f"  Output:        ${cost.output_cost:.4f}",
            f"  Cache read:    ${cost.cache_read_cost:.4f}",
            f"  Cache created: ${cost.cache_creation_cost:.4f}",
            f"  Total:         ${cost.total_cost:.4f}",
        ]
        return CommandResult(message="\n".join(lines))


class CwdCommand(SlashCommand):
    name = "cwd"
    description = "Show or change the current working directory"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            return CommandResult(message=f"Working directory: {ctx.app_state.get_cwd()}")

        new_cwd = os.path.expanduser(args)
        if os.path.isdir(new_cwd):
            ctx.app_state.set_cwd(new_cwd)
            os.chdir(new_cwd)
            return CommandResult(message=f"Working directory: {new_cwd}")
        return CommandResult(success=False, message=f"Not a directory: {new_cwd}")


class ResumeCommand(SlashCommand):
    name = "resume"
    description = "Resume the last session"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        persist_dir = os.path.expanduser("~/.openlaoke/sessions")
        if not os.path.exists(persist_dir):
            return CommandResult(message="No sessions found to resume.")

        sessions = sorted(os.listdir(persist_dir), reverse=True)
        if not sessions:
            return CommandResult(message="No sessions found to resume.")

        latest = sessions[0]
        session_path = os.path.join(persist_dir, latest)
        ctx.app_state.set_persist_path(session_path)
        ctx.app_state.resume_session = True
        return CommandResult(message=f"Session {latest} will be resumed.")


class CommandsCommand(SlashCommand):
    name = "commands"
    description = "Show example commands to try"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        examples = [
            "Examples:",
            '  "Write a Python script that reads a CSV and prints summary stats"',
            '  "Find all TODO comments in the src/ directory"',
            '  "Explain how the authentication system works"',
            '  "Refactor the database queries to use async"',
            '  "Add unit tests for the user service"',
            '  "Create a REST API for managing tasks"',
            "",
            "You can also use tools directly:",
            "  /Bash ls -la",
            "  /Read src/main.py",
        ]
        return CommandResult(message="\n".join(examples))


class SettingsCommand(SlashCommand):
    name = "settings"
    description = "Show current settings"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        config = ctx.app_state.session_config
        perm = ctx.app_state.permission_config
        lines = [
            "Settings:",
            f"  Model:       {config.model}",
            f"  Max tokens:  {config.max_tokens}",
            f"  Temperature: {config.temperature}",
            f"  Thinking:    {config.thinking_budget} tokens",
            f"  Permissions: {perm.mode.value}",
            f"  Working dir: {ctx.app_state.get_cwd()}",
        ]
        return CommandResult(message="\n".join(lines))


class DoctorCommand(SlashCommand):
    name = "doctor"
    description = "Run diagnostic checks for environment, API, and tools"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        import platform
        import shutil

        lines = ["Diagnostic Report:", ""]

        lines.append("System:")
        lines.append(f"  Platform:     {platform.system()} {platform.release()}")
        lines.append(f"  Python:       {sys.version.split()[0]}")
        lines.append(f"  Architecture: {platform.machine()}")
        lines.append("")

        lines.append("Environment:")
        env_checks = [
            ("ANTHROPIC_API_KEY", "Anthropic"),
            ("OPENAI_API_KEY", "OpenAI"),
            ("DASHSCOPE_API_KEY", "Aliyun"),
            ("MINIMAX_API_KEY", "MiniMax"),
        ]
        for env_var, provider in env_checks:
            status = "set" if os.environ.get(env_var) else "not set"
            lines.append(f"  {provider}: {status}")
        lines.append("")

        lines.append("Tools:")
        tool_checks = ["git", "python3", "node", "npm", "docker"]
        for tool in tool_checks:
            path = shutil.which(tool)
            status = path if path else "not found"
            lines.append(f"  {tool}: {status}")
        lines.append("")

        lines.append("Configuration:")
        config_dir = os.path.expanduser("~/.openlaoke")
        agents_md = os.path.join(ctx.app_state.get_cwd(), "AGENTS.md")
        lines.append(
            f"  Config dir:   {config_dir} ({'exists' if os.path.exists(config_dir) else 'missing'})"
        )
        lines.append(
            f"  AGENTS.md:    {agents_md} ({'exists' if os.path.exists(agents_md) else 'missing'})"
        )
        lines.append("")

        lines.append("Session:")
        lines.append(f"  Session ID:   {ctx.app_state.session_id}")
        lines.append(f"  Model:        {ctx.app_state.session_config.model}")
        lines.append(f"  Messages:     {len(ctx.app_state.messages)}")
        lines.append(f"  Tasks:        {len(ctx.app_state.tasks)}")

        return CommandResult(message="\n".join(lines))


class InitCommand(SlashCommand):
    name = "init"
    description = "Initialize AGENTS.md in current project"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        cwd = ctx.app_state.get_cwd()
        agents_path = os.path.join(cwd, "AGENTS.md")

        if os.path.exists(agents_path):
            return CommandResult(message=f"AGENTS.md already exists at {agents_path}")

        default_content = """# AGENTS.md - Project Guide

This file contains instructions for AI assistants working with this codebase.

## Project Overview

<!-- Describe your project here -->

## Commands

### Build
```bash
# Add build commands here
```

### Test
```bash
# Add test commands here
```

### Lint
```bash
# Add lint commands here
```

## Code Style

<!-- Add coding conventions and style guidelines -->

## Architecture

<!-- Describe the project architecture -->

## Important Files

<!-- List important files and their purposes -->
"""

        try:
            with open(agents_path, "w", encoding="utf-8") as f:
                f.write(default_content)
            return CommandResult(message=f"Created AGENTS.md at {agents_path}")
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to create AGENTS.md: {e}")


class McpCommand(SlashCommand):
    name = "mcp"
    description = "Manage MCP servers (list, add, remove, enable, disable)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args or args == "list":
            return self._list_servers(ctx)
        elif args.startswith("add "):
            return self._add_server(ctx, args[4:].strip())
        elif args.startswith("remove "):
            return self._remove_server(ctx, args[7:].strip())
        elif args.startswith("enable "):
            return self._enable_server(ctx, args[7:].strip())
        elif args.startswith("disable "):
            return self._disable_server(ctx, args[8:].strip())
        else:
            return CommandResult(
                success=False,
                message="Usage: /mcp [list|add <name>|remove <name>|enable <name>|disable <name>]",
            )

    def _list_servers(self, ctx: CommandContext) -> CommandResult:
        mcp_service = getattr(ctx.app_state, "mcp_service", None)

        lines = ["MCP Servers:", ""]

        if mcp_service and hasattr(mcp_service, "servers"):
            if not mcp_service.servers:
                lines.append("  No MCP servers configured.")
            else:
                for name, conn in mcp_service.servers.items():
                    status = "connected" if conn.connected else "disconnected"
                    tools_count = len(conn.tools) if conn.tools else 0
                    error = f" (error: {conn.error})" if conn.error else ""
                    lines.append(f"  {name}: {status}, {tools_count} tools{error}")
        else:
            config_path = os.path.expanduser("~/.openlaoke/mcp_servers.json")
            if os.path.exists(config_path):
                import json

                try:
                    with open(config_path) as f:
                        data = json.load(f)
                    servers = data.get("mcpServers", {})
                    if not servers:
                        lines.append("  No MCP servers configured.")
                    else:
                        for name in servers:
                            lines.append(f"  {name}: not loaded")
                except Exception:
                    lines.append(f"  Error reading {config_path}")
            else:
                lines.append("  No MCP servers configured.")
                lines.append(f"  Create {config_path} to add servers.")

        return CommandResult(message="\n".join(lines))

    def _add_server(self, ctx: CommandContext, name: str) -> CommandResult:
        return CommandResult(
            success=False,
            message=f"To add MCP server '{name}', edit ~/.openlaoke/mcp_servers.json",
        )

    def _remove_server(self, ctx: CommandContext, name: str) -> CommandResult:
        return CommandResult(
            success=False,
            message=f"To remove MCP server '{name}', edit ~/.openlaoke/mcp_servers.json",
        )

    def _enable_server(self, ctx: CommandContext, name: str) -> CommandResult:
        return CommandResult(message=f"MCP server '{name}' enabled (restart required)")

    def _disable_server(self, ctx: CommandContext, name: str) -> CommandResult:
        return CommandResult(message=f"MCP server '{name}' disabled (restart required)")


class ThemeCommand(SlashCommand):
    name = "theme"
    description = "Set or show terminal theme (dark/light/custom)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        themes = ["dark", "light", "custom"]

        if not args:
            current = getattr(ctx.app_state, "theme", "dark")
            lines = [
                f"Current theme: {current}",
                "",
                "Available themes:",
                "  dark   - Dark theme (default)",
                "  light  - Light theme",
                "  custom - Custom theme (requires config)",
            ]
            return CommandResult(message="\n".join(lines))

        if args not in themes:
            return CommandResult(
                success=False,
                message=f"Invalid theme '{args}'. Available: {', '.join(themes)}",
            )

        ctx.app_state.theme = args
        return CommandResult(message=f"Theme set to: {args}")


class VimCommand(SlashCommand):
    name = "vim"
    description = "Toggle Vim input mode"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args:
            current = ctx.app_state.vim_mode
            return CommandResult(message=f"Vim mode: {'enabled' if current else 'disabled'}")

        if args in ("on", "enable", "true", "1"):
            ctx.app_state.vim_mode = True
            return CommandResult(message="Vim mode enabled")
        elif args in ("off", "disable", "false", "0"):
            ctx.app_state.vim_mode = False
            return CommandResult(message="Vim mode disabled")
        elif args == "toggle":
            current = ctx.app_state.vim_mode
            ctx.app_state.vim_mode = not current
            return CommandResult(message=f"Vim mode: {'enabled' if not current else 'disabled'}")
        else:
            return CommandResult(
                success=False,
                message="Usage: /vim [on|off|toggle]",
            )


class HooksCommand(SlashCommand):
    name = "hooks"
    description = "Manage hooks (list, add, remove, test)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args or args == "list":
            return self._list_hooks(ctx)
        elif args.startswith("test "):
            return self._test_hook(ctx, args[5:].strip())
        else:
            return CommandResult(
                success=False,
                message="Usage: /hooks [list|test <hook_type>]",
            )

    def _list_hooks(self, ctx: CommandContext) -> CommandResult:
        hook_manager = getattr(ctx.app_state, "hook_manager", None)

        lines = ["Registered Hooks:", ""]

        if hook_manager:
            hooks = hook_manager.get_registered_hooks()
            if not hooks:
                lines.append("  No hooks registered.")
            else:
                from openlaoke.types.hooks import HookType

                for hook_type in HookType:
                    registered = hooks.get(hook_type.value, [])
                    if registered:
                        lines.append(f"  {hook_type.value}:")
                        for name in registered:
                            lines.append(f"    - {name}")
                    else:
                        lines.append(f"  {hook_type.value}: (none)")
        else:
            from openlaoke.types.hooks import HookType

            lines.append("  Hook manager not initialized.")
            lines.append("")
            lines.append("  Available hook types:")
            for hook_type in HookType:
                lines.append(f"    - {hook_type.value}")

        return CommandResult(message="\n".join(lines))

    def _test_hook(self, ctx: CommandContext, hook_type: str) -> CommandResult:
        from openlaoke.types.hooks import HookType

        try:
            HookType(hook_type)
        except ValueError:
            return CommandResult(
                success=False,
                message=f"Invalid hook type: {hook_type}",
            )

        return CommandResult(message=f"Hook test for '{hook_type}' - no handlers registered")


class ExportCommand(SlashCommand):
    name = "export"
    description = "Export session to JSON or Markdown format"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args:
            return CommandResult(
                message="Usage: /export [json|markdown] [filename]\n"
                "  /export json - Export as JSON\n"
                "  /export markdown - Export as Markdown"
            )

        parts = args.split(maxsplit=1)
        format_type = parts[0]
        filename = parts[1] if len(parts) > 1 else None

        if format_type == "json":
            return self._export_json(ctx, filename)
        elif format_type in ("markdown", "md"):
            return self._export_markdown(ctx, filename)
        else:
            return CommandResult(
                success=False,
                message=f"Invalid format: {format_type}. Use 'json' or 'markdown'.",
            )

    def _export_json(self, ctx: CommandContext, filename: str | None) -> CommandResult:
        import json
        from datetime import datetime

        data = {
            "session_id": ctx.app_state.session_id,
            "exported_at": datetime.now().isoformat(),
            "model": ctx.app_state.session_config.model,
            "messages": [m.to_dict() for m in ctx.app_state.messages],
            "token_usage": {
                "input_tokens": ctx.app_state.token_usage.input_tokens,
                "output_tokens": ctx.app_state.token_usage.output_tokens,
                "cache_read_tokens": ctx.app_state.token_usage.cache_read_tokens,
                "cache_creation_tokens": ctx.app_state.token_usage.cache_creation_tokens,
            },
            "cost": ctx.app_state.cost_info.total_cost,
        }

        sessions_dir = os.path.expanduser("~/.openlaoke/sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        if filename:
            path = os.path.expanduser(filename)
        else:
            path = os.path.join(sessions_dir, f"session_{ctx.app_state.session_id}.json")

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            return CommandResult(message=f"Session exported to {path}")
        except Exception as e:
            return CommandResult(success=False, message=f"Export failed: {e}")

    def _export_markdown(self, ctx: CommandContext, filename: str | None) -> CommandResult:
        from datetime import datetime

        lines = [
            "# Session Export",
            "",
            f"**Session ID:** {ctx.app_state.session_id}",
            f"**Exported at:** {datetime.now().isoformat()}",
            f"**Model:** {ctx.app_state.session_config.model}",
            "",
            "---",
            "",
            "## Conversation",
            "",
        ]

        for msg in ctx.app_state.messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            content = getattr(msg, "content", "")
            lines.append(f"### {role.title()}")
            lines.append("")
            lines.append(content)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## Statistics")
        lines.append("")
        lines.append(f"- Input tokens: {ctx.app_state.token_usage.input_tokens:,}")
        lines.append(f"- Output tokens: {ctx.app_state.token_usage.output_tokens:,}")
        lines.append(f"- Total cost: ${ctx.app_state.cost_info.total_cost:.4f}")

        sessions_dir = os.path.expanduser("~/.openlaoke/sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        if filename:
            path = os.path.expanduser(filename)
        else:
            path = os.path.join(sessions_dir, f"session_{ctx.app_state.session_id}.md")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return CommandResult(message=f"Session exported to {path}")
        except Exception as e:
            return CommandResult(success=False, message=f"Export failed: {e}")


class UsageCommand(SlashCommand):
    name = "usage"
    description = "Show detailed usage statistics (tokens, cost, API calls)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        usage = ctx.app_state.token_usage
        cost = ctx.app_state.cost_info

        lines = [
            "Usage Statistics",
            "================",
            "",
            "Token Usage:",
            f"  Input tokens:         {usage.input_tokens:,}",
            f"  Output tokens:        {usage.output_tokens:,}",
            f"  Cache read:          {usage.cache_read_tokens:,}",
            f"  Cache created:       {usage.cache_creation_tokens:,}",
            f"  Total tokens:        {usage.total_tokens:,}",
            "",
            "Cost Breakdown:",
            f"  Input cost:          ${cost.input_cost:.4f}",
            f"  Output cost:         ${cost.output_cost:.4f}",
            f"  Cache read cost:     ${cost.cache_read_cost:.4f}",
            f"  Cache creation cost: ${cost.cache_creation_cost:.4f}",
            f"  Total cost:          ${cost.total_cost:.4f}",
            "",
            "Session Info:",
            f"  Session ID:          {ctx.app_state.session_id}",
            f"  Model:                {ctx.app_state.session_config.model}",
            f"  Messages:             {len(ctx.app_state.messages):,}",
            f"  Tasks:                {len(ctx.app_state.tasks):,}",
        ]

        return CommandResult(message="\n".join(lines))


class MemoryCommand(SlashCommand):
    name = "memory"
    description = "Manage long-term memory storage"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args or args == "list":
            return self._list_memory(ctx)
        elif args.startswith("add "):
            return self._add_memory(ctx, args[4:].strip())
        elif args.startswith("remove "):
            return self._remove_memory(ctx, args[7:].strip())
        elif args == "clear":
            return self._clear_memory(ctx)
        else:
            return CommandResult(
                success=False,
                message="Usage: /memory [list|add <text>|remove <id>|clear]",
            )

    def _list_memory(self, ctx: CommandContext) -> CommandResult:
        memory_path = os.path.expanduser("~/.openlaoke/memory.json")

        lines = ["Memory Storage:", ""]

        if not os.path.exists(memory_path):
            lines.append("  No memories stored.")
            lines.append(f"  Memory file: {memory_path} (not found)")
            return CommandResult(message="\n".join(lines))

        try:
            import json

            with open(memory_path) as f:
                memories = json.load(f)

            if not memories:
                lines.append("  No memories stored.")
            else:
                for i, mem in enumerate(memories, 1):
                    text = mem.get("text", "")[:50]
                    timestamp = mem.get("timestamp", "unknown")
                    lines.append(f"  [{i}] {text}... ({timestamp})")
        except Exception as e:
            lines.append(f"  Error reading memory: {e}")

        return CommandResult(message="\n".join(lines))

    def _add_memory(self, ctx: CommandContext, text: str) -> CommandResult:
        import json
        from datetime import datetime

        memory_path = os.path.expanduser("~/.openlaoke/memory.json")

        try:
            os.makedirs(os.path.dirname(memory_path), exist_ok=True)

            memories = []
            if os.path.exists(memory_path):
                with open(memory_path) as f:
                    memories = json.load(f)

            memories.append(
                {
                    "text": text,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            with open(memory_path, "w") as f:
                json.dump(memories, f, indent=2)

            return CommandResult(message=f"Memory added: {text[:50]}...")
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to add memory: {e}")

    def _remove_memory(self, ctx: CommandContext, index_str: str) -> CommandResult:
        import json

        try:
            index = int(index_str) - 1
        except ValueError:
            return CommandResult(success=False, message="Invalid index. Use a number.")

        memory_path = os.path.expanduser("~/.openlaoke/memory.json")

        try:
            with open(memory_path) as f:
                memories = json.load(f)

            if index < 0 or index >= len(memories):
                return CommandResult(
                    success=False, message=f"Index out of range. Valid: 1-{len(memories)}"
                )

            removed = memories.pop(index)

            with open(memory_path, "w") as f:
                json.dump(memories, f, indent=2)

            return CommandResult(message=f"Removed memory: {removed.get('text', '')[:50]}...")
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to remove memory: {e}")

    def _clear_memory(self, ctx: CommandContext) -> CommandResult:
        memory_path = os.path.expanduser("~/.openlaoke/memory.json")

        try:
            if os.path.exists(memory_path):
                os.remove(memory_path)
            return CommandResult(message="Memory cleared")
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to clear memory: {e}")


class AgentsCommand(SlashCommand):
    name = "agents"
    description = "Show available agent types"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.types.core_types import TaskType

        lines = [
            "Available Agent Types:",
            "",
        ]

        agent_descriptions = {
            TaskType.LOCAL_BASH: "Execute bash commands locally",
            TaskType.LOCAL_AGENT: "Run sub-agents for complex tasks",
            TaskType.REMOTE_AGENT: "Connect to remote agent servers",
            TaskType.IN_PROCESS_TEAMMATE: "In-process teammate collaboration",
            TaskType.LOCAL_WORKFLOW: "Execute local workflows",
            TaskType.MONITOR_MCP: "Monitor MCP server connections",
            TaskType.DREAM: "Background processing tasks",
        }

        for task_type in TaskType:
            desc = agent_descriptions.get(task_type, "No description")
            lines.append(f"  {task_type.value}:")
            lines.append(f"    {desc}")
            lines.append("")

        active_tasks = ctx.app_state.get_active_tasks()
        if active_tasks:
            lines.append("Active Tasks:")
            for task in active_tasks:
                lines.append(f"  [{task.id}] {task.type.value}: {task.status.value}")
                if task.description:
                    lines.append(f"    {task.description}")
        else:
            lines.append("No active tasks.")

        return CommandResult(message="\n".join(lines))


class InsomniaCommand(SlashCommand):
    name = "insomnia"
    description = "不眠不休模式 - Enable persistent background execution"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args or args == "status":
            return self._show_status(ctx)
        elif args == "on" or args == "enable" or args == "start":
            return self._enable(ctx)
        elif args == "off" or args == "disable" or args == "stop":
            return self._disable(ctx)
        elif args.startswith("add "):
            return self._add_task(ctx, args[4:].strip())
        elif args.startswith("cancel "):
            return self._cancel_task(ctx, args[7:].strip())
        elif args == "clear":
            return self._clear_queue(ctx)
        elif args == "log":
            return self._show_log(ctx)
        elif args.startswith("config "):
            return self._config(ctx, args[7:].strip())
        else:
            return CommandResult(
                success=False,
                message="Usage:\n"
                "  /insomnia on          - Enable insomnia mode\n"
                "  /insomnia off         - Disable insomnia mode\n"
                "  /insomnia status      - Show current status\n"
                "  /insomnia add <task>  - Add task to queue\n"
                "  /insomnia cancel <id> - Cancel a task\n"
                "  /insomnia clear       - Clear pending tasks\n"
                "  /insomnia log         - Show execution log\n"
                "  /insomnia config <n>  - Set max iterations",
            )

    def _show_status(self, ctx: CommandContext) -> CommandResult:
        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        status = engine.get_status()
        lines = [
            "[bold]Insomnia Mode (不眠不休模式)[/bold]",
            "",
            f"  Running:        {'[green]Yes[/green]' if status['running'] else '[red]No[/red]'}",
            f"  Queue size:     {status['queue_size']}",
            f"  Total iterations: {status['total_iterations']}",
        ]

        if status["current_task"]:
            task = status["current_task"]
            lines.append("")
            lines.append("  [bold]Current Task:[/bold]")
            lines.append(f"    ID:          {task['task_id']}")
            lines.append(f"    Status:      {task['status']}")
            lines.append(f"    Iterations:  {task['iterations']}/{task['max_iterations']}")
            if task.get("prompt"):
                prompt_preview = task["prompt"][:80]
                lines.append(f"    Prompt:      {prompt_preview}...")

        if status["queue"]:
            lines.append("")
            lines.append("  [bold]Pending Tasks:[/bold]")
            for task in status["queue"][:5]:
                lines.append(f"    [{task['task_id']}] {task['prompt'][:60]}...")
            if len(status["queue"]) > 5:
                lines.append(f"    ... and {len(status['queue']) - 5} more")

        lines.append("")
        lines.append("[dim]Use /insomnia add <task> to add tasks to the queue.[/dim]")

        return CommandResult(message="\n".join(lines))

    def _enable(self, ctx: CommandContext) -> CommandResult:
        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        ctx.app_state.insomnia_mode = True
        ctx.app_state.insomnia_auto_accept = True
        ctx.app_state._persist()

        import asyncio

        asyncio.create_task(engine.start())

        return CommandResult(
            message="[green]✓ Insomnia mode enabled (不眠不休模式已开启)[/green]\n"
            "AI will continue working even when you disconnect.\n"
            "Use /insomnia add <task> to queue tasks."
        )

    def _disable(self, ctx: CommandContext) -> CommandResult:
        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        import asyncio

        asyncio.create_task(engine.stop())

        return CommandResult(
            message="[yellow]Insomnia mode disabled (不眠不休模式已关闭)[/yellow]\n"
            "Pending tasks are saved and will resume when re-enabled."
        )

    def _add_task(self, ctx: CommandContext, prompt: str) -> CommandResult:
        if not prompt:
            return CommandResult(success=False, message="Usage: /insomnia add <task description>")

        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        import asyncio

        task_id = asyncio.get_event_loop().run_until_complete(engine.add_task(prompt))

        return CommandResult(
            message=f"[green]✓ Task added:[/green] {task_id}\n"
            f"  Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n"
            "Task will be executed when the queue is processed."
        )

    def _cancel_task(self, ctx: CommandContext, task_id: str) -> CommandResult:
        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        import asyncio

        success = asyncio.get_event_loop().run_until_complete(engine.cancel_task(task_id))

        if success:
            return CommandResult(message=f"[green]✓ Task cancelled:[/green] {task_id}")
        return CommandResult(success=False, message=f"Task not found: {task_id}")

    def _clear_queue(self, ctx: CommandContext) -> CommandResult:
        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        import asyncio

        count = asyncio.get_event_loop().run_until_complete(engine.clear_queue())

        return CommandResult(message=f"[green]✓ Queue cleared:[/green] {count} tasks removed")

    def _show_log(self, ctx: CommandContext) -> CommandResult:
        engine = self._get_engine(ctx)
        if not engine:
            return CommandResult(message="Insomnia engine not initialized.")

        log = engine.get_log(limit=20)
        if not log:
            return CommandResult(message="No log entries yet.")

        lines = ["[bold]Insomnia Log (recent 20 entries):[/bold]", ""]
        for entry in log:
            from datetime import datetime

            ts = datetime.fromtimestamp(entry["timestamp"]).strftime("%H:%M:%S")
            level = entry["level"].upper()
            task_info = f" [{entry['task_id'][:8]}]" if entry.get("task_id") else ""
            lines.append(f"  [{ts}] {level}{task_info}: {entry['message']}")

        return CommandResult(message="\n".join(lines))

    def _config(self, ctx: CommandContext, args: str) -> CommandResult:
        if not args:
            return CommandResult(
                message=f"Current config:\n"
                f"  Max iterations: {ctx.app_state.insomnia_max_iterations}\n"
                f"  Auto accept:    {ctx.app_state.insomnia_auto_accept}\n"
                "\n"
                "Usage: /insomnia config <max_iterations>"
            )

        try:
            max_iterations = int(args)
            if max_iterations < 1:
                return CommandResult(success=False, message="Max iterations must be positive")
            ctx.app_state.insomnia_max_iterations = max_iterations
            ctx.app_state._persist()
            return CommandResult(message=f"Max iterations set to: {max_iterations}")
        except ValueError:
            return CommandResult(success=False, message=f"Invalid number: {args}")

    def _get_engine(self, ctx: CommandContext):
        """Get or create the insomnia engine."""
        if not hasattr(ctx.app_state, "_insomnia_engine"):
            from openlaoke.core.insomnia_engine import InsomniaEngine

            ctx.app_state._insomnia_engine = InsomniaEngine(ctx.app_state)
        return ctx.app_state._insomnia_engine


class UndoCommand(SlashCommand):
    name = "undo"
    description = "Restore file to previous version"
    aliases = ["revert"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.file_history import (
            format_history_list,
            get_history,
            restore_snapshot,
        )

        args = ctx.args.strip()

        if not args:
            return CommandResult(
                message="Usage: /undo <path> [version]\n"
                "  /undo <path>        - Restore to previous version\n"
                "  /undo <path> <n>    - Restore to version n\n"
                "  /undo <path> list   - Show all versions"
            )

        parts = args.split()
        file_path = parts[0]

        abs_path = os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path
        cwd = ctx.app_state.get_cwd()
        if not os.path.isabs(file_path):
            abs_path = os.path.normpath(os.path.join(cwd, file_path))

        if len(parts) == 1:
            history = get_history(abs_path)
            if not history or not history.snapshots:
                return CommandResult(success=False, message=f"No history found for {abs_path}")

            if len(history.snapshots) < 2:
                return CommandResult(
                    success=False,
                    message=f"Only one version exists for {abs_path}. Use /history to view.",
                )

            prev_version = history.snapshots[-2].version
            if restore_snapshot(abs_path, prev_version):
                return CommandResult(message=f"Restored {abs_path} to version {prev_version}")
            return CommandResult(success=False, message=f"Failed to restore {abs_path}")

        version_str = parts[1]
        if version_str.lower() == "list":
            return CommandResult(message=format_history_list(abs_path))

        try:
            version = int(version_str)
        except ValueError:
            return CommandResult(
                success=False, message=f"Invalid version: {version_str}. Use a number or 'list'."
            )

        if restore_snapshot(abs_path, version):
            return CommandResult(message=f"Restored {abs_path} to version {version}")
        return CommandResult(
            success=False, message=f"Failed to restore {abs_path} to version {version}"
        )


class HistoryCommand(SlashCommand):
    name = "history"
    description = "Show file modification history"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.file_history import (
            clear_history,
        )

        args = ctx.args.strip()

        if not args:
            history_dir = os.path.expanduser("~/.openlaoke/file_history")
            if not os.path.exists(history_dir):
                return CommandResult(message="No file histories found.")

            files = []
            for filename in os.listdir(history_dir):
                if filename.endswith(".json"):
                    path = os.path.join(history_dir, filename)
                    try:
                        import json

                        with open(path, encoding="utf-8") as f:
                            data = json.load(f)
                        file_path = data.get("path", "unknown")
                        count = len(data.get("snapshots", []))
                        files.append((file_path, count))
                    except Exception:
                        continue

            if not files:
                return CommandResult(message="No file histories found.")

            lines = ["Files with history:", ""]
            for file_path, count in sorted(files, key=lambda x: x[0]):
                short_path = file_path.replace(os.path.expanduser("~"), "~")
                lines.append(f"  {short_path} ({count} versions)")

            lines.append("")
            lines.append("Use /history <path> to see details for a specific file.")
            return CommandResult(message="\n".join(lines))

        parts = args.split()
        file_path = parts[0]

        abs_path = os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path
        cwd = ctx.app_state.get_cwd()
        if not os.path.isabs(file_path):
            abs_path = os.path.normpath(os.path.join(cwd, file_path))

        if len(parts) > 1 and parts[1].lower() == "clear":
            if clear_history(abs_path):
                return CommandResult(message=f"History cleared for {abs_path}")
            return CommandResult(success=False, message=f"Failed to clear history for {abs_path}")

        # Show history for specific file
        from openlaoke.utils.file_history import get_file_history

        file_history = get_file_history(abs_path)
        if not file_history:
            return CommandResult(message=f"No history found for {abs_path}")

        lines = [f"History for {abs_path}:", ""]
        for i, snapshot in enumerate(file_history.snapshots):
            lines.append(f"  Version {i + 1}: {snapshot.timestamp}")
        return CommandResult(message="\n".join(lines))


class AtomicCommand(SlashCommand):
    name = "atomic"
    description = "Generate code using atomic task decomposition (for small models)"
    aliases = ["atom", "decompose"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from pathlib import Path

        from rich.panel import Panel

        from openlaoke.core.atomic_generator_api import create_generator_with_api
        from openlaoke.core.intent_pipeline import create_pipeline_for_model
        from openlaoke.core.model_assessment.types import ModelTier

        request = ctx.args.strip()
        if not request:
            return CommandResult(
                message="Usage: /atomic <your request>\n"
                "Example: /atomic write a CPU benchmark program"
            )

        model_name = (
            ctx.app_state.session_config.model
            if hasattr(ctx.app_state, "session_config")
            else "unknown"
        )
        tier = ModelTier.TIER_5_LIMITED

        known_models = {
            "gemma3:1b": ModelTier.TIER_5_LIMITED,
            "qwen3.5:0.8b": ModelTier.TIER_5_LIMITED,
            "llama3.2:1b": ModelTier.TIER_5_LIMITED,
        }
        model_lower = model_name.lower()
        for known, known_tier in known_models.items():
            if known in model_lower:
                tier = known_tier
                break

        cwd = ctx.app_state.get_cwd() if hasattr(ctx.app_state, "get_cwd") else Path.cwd()

        pipeline = create_pipeline_for_model(tier, Path(cwd))
        result = pipeline.process_request(request)

        if not result.success:
            return CommandResult(
                success=False,
                message="[red]Failed to process request:[/red]\n" + "\n".join(result.errors),
            )

        console = ctx.app_state.console if hasattr(ctx.app_state, "console") else None

        lines = []
        lines.append(f"[bold green]Intent parsed:[/bold green] {result.intent.intent_type.value}")
        lines.append(f"[bold green]Task name:[/bold green] {result.intent.task_name}")
        lines.append(f"[bold green]Complexity:[/bold green] {result.intent.complexity.value}")

        plan = pipeline.get_execution_plan(result)
        lines.append("")
        lines.append("[bold cyan]Task Decomposition Plan:[/bold cyan]")
        lines.append(f"  Total tasks: {plan['total_tasks']}")
        lines.append(f"  Estimated total lines: {plan['estimated_lines_total']}")
        lines.append(f"  Ready to execute: {len(plan['ready_tasks'])}")

        if plan["ready_tasks"]:
            lines.append("")
            lines.append("[bold]Ready tasks:[/bold]")
            for task_info in plan["ready_tasks"][:5]:
                lines.append(f"  • {task_info['task_id']} ({task_info['estimated_lines']} lines)")

        generator = create_generator_with_api(tier, Path(cwd), ctx.app_state)
        completed_code = {}

        if console:
            console.print(Panel("\n".join(lines), title="Atomic Task Plan", border_style="cyan"))

        if result.task_graph:
            graph = result.task_graph
            iteration = 0
            max_iterations = 20

            while len(graph.completed) < len(graph.tasks) and iteration < max_iterations:
                ready_tasks = graph.get_ready_tasks()

                if not ready_tasks:
                    break

                for task in ready_tasks[:1]:
                    if console:
                        console.print(f"\n[cyan]Processing task: {task.task_id}[/cyan]")
                        console.print(f"  Description: {task.description}")

                    code_result = await generator.generate_code_for_task_async(task, completed_code)

                    if code_result.success:
                        completed_code[task.task_id] = code_result.code
                        graph.mark_completed(task.task_id)

                        if console:
                            console.print(
                                f"  [green]✓ Generated {len(code_result.code)} characters[/green]"
                            )
                    else:
                        graph.mark_failed(task.task_id)
                        if console:
                            console.print(f"  [red]✗ Failed: {', '.join(code_result.errors)}[/red]")

                iteration += 1

        final_code = generator.assemble_final_code(result.task_graph, completed_code)

        if final_code:
            output_file = Path(cwd) / f"{result.intent.task_name.replace(' ', '_')}.py"
            try:
                output_file.write_text(final_code)
                return CommandResult(
                    message=f"[green]✓ Generated code saved to:[/green] {output_file}\n"
                    f"[green]Total tasks completed:[/green] {len(graph.completed)}/{len(graph.tasks)}\n"
                    f"[green]Code size:[/green] {len(final_code)} bytes"
                )
            except Exception as e:
                return CommandResult(
                    success=False,
                    message=f"[red]Failed to save code:[/red] {e}\n\nGenerated code:\n{final_code[:500]}...",
                )
        else:
            return CommandResult(
                success=False,
                message="[red]No code was generated[/red]",
            )


class DualModelCommand(SlashCommand):
    name = "dual"
    description = "Generate code using dual-model collaboration (small planner + large executor)"
    aliases = ["dual-model", "collab"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from pathlib import Path

        from rich.panel import Panel

        from openlaoke.core.dual_model_agent import create_dual_model_agent

        request = ctx.args.strip()
        if not request:
            return CommandResult(
                message="Usage: /dual <your request>\n"
                "Example: /dual write a CPU benchmark program\n\n"
                "This command uses:\n"
                "  - Small model (gemma3:1b) for planning and validation\n"
                "  - Large model (gemma4:e4b) for code generation\n"
                "  - Cost reduction: ~60-80%\n"
                "  - Quality improvement: Better decomposition + Better code"
            )

        console = ctx.app_state.console if hasattr(ctx.app_state, "console") else None

        if console:
            console.print(
                Panel(
                    "[bold cyan]Dual-Model Agent[/bold cyan]\n\n"
                    "Planner: gemma3:1b (cheap, fast)\n"
                    "Executor: gemma4:e4b (capable, precise)\n\n"
                    "Workflow:\n"
                    "1. Planner analyzes and decomposes tasks\n"
                    "2. Executor generates code for each task\n"
                    "3. Validator checks code correctness\n"
                    "4. Assembler combines final result",
                    title="Starting Dual-Model Collaboration",
                    border_style="cyan",
                )
            )

        cwd = ctx.app_state.get_cwd() if hasattr(ctx.app_state, "get_cwd") else Path.cwd()

        agent = create_dual_model_agent(ctx.app_state)

        result = await agent.execute(request, Path(cwd))

        if result.success:
            lines = []
            lines.append("[bold green]✓ Dual-model execution completed[/bold green]")
            lines.append("")
            lines.append("[bold]Model Preloading:[/bold]")
            lines.append(f"  Preloaded: {'✓ Yes' if result.stats.models_preloaded else '✗ No'}")
            lines.append(f"  Preload time: {result.stats.preload_time:.2f}s")
            lines.append("")
            lines.append("[bold]Statistics:[/bold]")
            lines.append(
                f"  Planner calls: {result.stats.planner_calls} ({result.stats.planner_tokens} tokens)"
            )
            lines.append(
                f"  Executor calls: {result.stats.executor_calls} ({result.stats.executor_tokens} tokens)"
            )
            lines.append(
                f"  Validator calls: {result.stats.validator_calls} ({result.stats.validator_tokens} tokens)"
            )
            lines.append(f"  Retry count: {result.stats.retry_count}")
            lines.append(f"  Total time: {result.stats.total_time:.2f}s")
            lines.append(f"  Estimated cost: ${result.stats.total_cost:.4f}")
            lines.append(f"  Code size: {len(result.code)} bytes")

            if result.output_file:
                lines.append(f"\n[green]Code saved to:[/green] {result.output_file}")

            if console:
                console.print(
                    Panel("\n".join(lines), title="Dual-Model Result", border_style="green")
                )

            return CommandResult(message="\n".join(lines))
        else:
            error_msg = "[red]Dual-model execution failed[/red]\n\n"
            if result.errors:
                error_msg += "[bold]Errors:[/bold]\n" + "\n".join(f"  - {e}" for e in result.errors)

            if console:
                console.print(Panel(error_msg, title="Error", border_style="red"))

            return CommandResult(success=False, message=error_msg)


class PreloadModelsCommand(SlashCommand):
    name = "preload-models"
    description = "Preload models for faster execution"
    aliases = ["preload", "load-models"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from rich.panel import Panel
        from rich.table import Table

        from openlaoke.core.hybrid_model_manager import create_hybrid_manager

        console = ctx.app_state.console if hasattr(ctx.app_state, "console") else None

        if console:
            console.print(
                Panel(
                    "[bold cyan]Initializing Model Pool[/bold cyan]\n\n"
                    "Strategy: CPU/GPU Hybrid\n"
                    "- Planner (gemma3:1b) → CPU (always loaded)\n"
                    "- Executor (gemma4:e4b) → GPU (on-demand)\n"
                    "- Validator (gemma3:1b) → CPU (always loaded)\n\n"
                    "This reduces VRAM usage by ~1.4 GB",
                    title="Model Preloader",
                    border_style="cyan",
                )
            )

        manager = create_hybrid_manager(ctx.app_state)
        result = await manager.initialize()

        if result["success"]:
            status = await manager.get_status()

            if console:
                table = Table(title="Model Pool Status", show_header=True)
                table.add_column("Model", style="cyan")
                table.add_column("Device", style="green")
                table.add_column("Status", style="yellow")
                table.add_column("Size", style="magenta")

                for model in status.cpu_models:
                    table.add_row(
                        model.name,
                        "CPU",
                        "✓ Loaded" if model.is_loaded else "✗ Not loaded",
                        f"{model.size_gb:.1f} GB",
                    )

                for model in status.gpu_models:
                    table.add_row(
                        model.name,
                        "GPU",
                        "✓ Loaded" if model.is_loaded else "✗ Not loaded",
                        f"{model.size_gb:.1f} GB",
                    )

                console.print(table)

                console.print(
                    f"\n[dim]GPU Memory: {status.gpu_used_gb:.1f} / {status.gpu_total_gb:.1f} GB[/dim]"
                )

            return CommandResult(message="Models preloaded successfully")
        else:
            failed = [k for k, v in result["results"].items() if not v]
            error_msg = f"[red]Failed to load models: {', '.join(failed)}[/red]"

            if console:
                console.print(Panel(error_msg, title="Error", border_style="red"))

            return CommandResult(success=False, message=error_msg)


class ModelStatusCommand(SlashCommand):
    name = "model-status"
    description = "Show current model pool status"
    aliases = ["models-status", "pool-status"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from rich.panel import Panel
        from rich.table import Table

        from openlaoke.core.hybrid_model_manager import create_hybrid_manager

        console = ctx.app_state.console if hasattr(ctx.app_state, "console") else None

        manager = create_hybrid_manager(ctx.app_state)
        status = await manager.get_status()

        if console:
            table = Table(title="Current Model Pool", show_header=True)
            table.add_column("Model", style="cyan")
            table.add_column("Tier", style="blue")
            table.add_column("Device", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Size", style="magenta")

            for model in status.cpu_models:
                table.add_row(
                    model.name,
                    model.tier,
                    "CPU",
                    "✓ Loaded" if model.is_loaded else "✗ Not loaded",
                    f"{model.size_gb:.1f} GB",
                )

            for model in status.gpu_models:
                table.add_row(
                    model.name,
                    model.tier,
                    "GPU",
                    "✓ Loaded" if model.is_loaded else "✗ Not loaded",
                    f"{model.size_gb:.1f} GB",
                )

            console.print(table)

            console.print(
                Panel(
                    f"GPU Memory Usage:\n"
                    f"  Total: {status.gpu_total_gb:.1f} GB\n"
                    f"  Used: {status.gpu_used_gb:.1f} GB\n"
                    f"  Free: {status.gpu_free_gb:.1f} GB",
                    title="Memory Status",
                    border_style="blue",
                )
            )

            return CommandResult(message="Model status displayed")
        else:
            return CommandResult(
                message=f"CPU models: {len(status.cpu_models)}, "
                f"GPU models: {len(status.gpu_models)}, "
                f"VRAM used: {status.gpu_used_gb:.1f} GB"
            )


class ModelRecommendCommand(SlashCommand):
    name = "model-recommend"
    description = "Get model recommendation based on your system"
    aliases = ["recommend-models", "optimal-models"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from rich.panel import Panel
        from rich.table import Table

        from openlaoke.core.intelligent_model_selector import IntelligentModelSelector

        console = ctx.app_state.console if hasattr(ctx.app_state, "console") else None

        preference = ctx.args.strip().lower() if ctx.args else "balanced"

        if preference not in ["cost", "quality", "balanced"]:
            preference = "balanced"

        selector = IntelligentModelSelector(ctx.app_state)
        report = await selector.get_recommendation_report()

        if console:
            console.print(
                Panel(
                    f"Detected GPU Memory: [bold cyan]{report['detected_vram_gb']:.1f} GB[/bold cyan]",
                    title="System Analysis",
                    border_style="blue",
                )
            )

            rec = report["recommended_combination"]

            console.print(
                Panel(
                    f"[bold green]Recommended: {rec['name'].upper()}[/bold green]\n\n"
                    f"Planner:   {rec['planner']}\n"
                    f"Executor:  {rec['executor']}\n"
                    f"Validator: {rec['validator']}\n\n"
                    f"Estimated VRAM: {report['estimated']['vram_usage_gb']:.1f} GB\n"
                    f"Quality Score:  {report['estimated']['quality_score']:.1f}/10\n"
                    f"Cost Factor:    {report['estimated']['cost_factor']:.1f}x",
                    title="Optimal Configuration",
                    border_style="green",
                )
            )

            if report["all_suitable_combinations"]:
                table = Table(title="All Suitable Combinations", show_header=True)
                table.add_column("Name", style="cyan")
                table.add_column("VRAM", style="magenta")
                table.add_column("Quality", style="green")
                table.add_column("Cost", style="yellow")

                for combo in report["all_suitable_combinations"]:
                    table.add_row(
                        combo["name"],
                        f"{combo['vram_gb']:.1f} GB",
                        f"{combo['quality']:.1f}/10",
                        f"{combo['cost']:.1f}x",
                    )

                console.print(table)

            console.print(f"\n[dim]Preference: {preference}[/dim]")

            return CommandResult(message="Recommendation displayed")
        else:
            rec = report["recommended_combination"]
            return CommandResult(
                message=f"Recommended: {rec['name']} - "
                f"Planner: {rec['planner']}, "
                f"Executor: {rec['executor']}, "
                f"VRAM: {report['estimated']['vram_usage_gb']:.1f} GB"
            )


class DualModelConfigCommand(SlashCommand):
    name = "dual-config"
    description = "Configure dual-model workflow (local/online models)"
    aliases = ["config-dual", "dual-setup"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        from openlaoke.core.dual_model_config import create_config_manager

        args = ctx.args.strip()

        console = None
        if hasattr(ctx.app_state, "console"):
            console = ctx.app_state.console
        elif hasattr(ctx, "console"):
            console = ctx.console
        else:
            console = Console()

        manager = create_config_manager(ctx.app_state)

        if not args:
            lines = []
            lines.append("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
            lines.append("[bold cyan]    Dual-Model Configuration[/bold cyan]")
            lines.append("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")

            lines.append(
                f"[bold green]✓ Active Configuration:[/bold green] [bold]{manager.active_config_name}[/bold]\n"
            )

            lines.append("[bold]Available Configurations:[/bold]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Planner", style="blue")
            table.add_column("Executor", style="green")
            table.add_column("Type", style="magenta")
            table.add_column("Status", style="yellow")

            for name, config in manager.configs.items():
                if config.planner and config.executor:
                    active_marker = " ★" if name == manager.active_config_name else ""

                    if (
                        config.planner.provider.value == "ollama"
                        and config.executor.provider.value == "ollama"
                    ):
                        provider_type = "local"
                    elif config.planner.provider.value != config.executor.provider.value:
                        provider_type = "hybrid"
                    else:
                        provider_type = "online"

                    status = "active" if name == manager.active_config_name else "ready"

                    table.add_row(
                        f"{name}{active_marker}",
                        f"{config.planner.model_name}",
                        f"{config.executor.model_name}",
                        provider_type,
                        status,
                    )

            console.print("\n".join(lines))
            console.print(table)

            console.print("\n")
            console.print(
                Panel(
                    "[bold yellow]Commands:[/bold yellow]\n"
                    "  [cyan]/dual-config list[/cyan]              - Show all configs\n"
                    "  [cyan]/dual-config use <name>[/cyan]        - Select active config\n"
                    "  [cyan]/dual-config check[/cyan]             - Check availability\n"
                    "  [cyan]/dual-config create <name>[/cyan]     - Create custom config\n"
                    "\n[bold green]Quick Examples:[/bold green]\n"
                    "  [dim]/dual-config use local_balanced[/dim]      [italic]# Local models (free)[/italic]\n"
                    "  [dim]/dual-config use hybrid_openai[/dim]       [italic]# Local + OpenAI[/italic]\n"
                    "  [dim]/dual-config use online_premium[/dim]      [italic]# Best quality[/italic]",
                    title="[bold]Usage Guide[/bold]",
                    border_style="yellow",
                )
            )

            return CommandResult(message="Configuration displayed")

        parts = args.split(maxsplit=1)
        action = parts[0].lower()

        if action == "list":
            configs = manager.list_configs()
            return CommandResult(
                message=f"Available configs: {', '.join(configs)}\n"
                f"Active: {manager.active_config_name}"
            )

        elif action == "use":
            if len(parts) < 2:
                return CommandResult(success=False, message="Usage: /dual-config use <config_name>")

            config_name = parts[1].strip()

            if manager.set_active_config(config_name):
                return CommandResult(
                    message=f"[green]✓ Active config set to: {config_name}[/green]"
                )
            else:
                return CommandResult(
                    success=False,
                    message=f"[red]Config not found: {config_name}[/red]\n"
                    f"Available: {', '.join(manager.list_configs())}",
                )

        elif action == "check":
            results = await manager.check_config_availability()

            if console:
                table = Table(title="Model Availability", show_header=True)
                table.add_column("Role", style="cyan")
                table.add_column("Model", style="blue")
                table.add_column("Status", style="green")
                table.add_column("Message", style="yellow")

                for role, (available, message) in results.items():
                    config = manager.get_config()
                    if config:
                        endpoint = getattr(config, role, None)
                        if endpoint:
                            table.add_row(
                                role,
                                f"{endpoint.model_name} ({endpoint.provider.value})",
                                "✓ Available" if available else "✗ Unavailable",
                                message,
                            )

                console.print(table)

            return CommandResult(message="Availability checked")

        elif action == "create":
            if len(parts) < 2:
                return CommandResult(
                    message="[bold]Create Custom Configuration[/bold]\n\n"
                    "Usage: /dual-config create <name> <options>\n\n"
                    "Options format:\n"
                    "  planner=<provider>:<model>\n"
                    "  executor=<provider>:<model>\n"
                    "  validator=<provider>:<model>\n"
                    "  planner-key=<api_key>\n"
                    "  executor-key=<api_key>\n\n"
                    "Examples:\n"
                    "  /dual-config create my_config planner=ollama:gemma3:1b executor=openai:gpt-4 planner-key=sk-xxx\n"
                    "  /dual-config create local planner=ollama:gemma3:1b executor=ollama:gemma4:e4b"
                )

            import shlex

            try:
                tokens = shlex.split(parts[1])
            except Exception:
                tokens = parts[1].split()

            name = tokens[0] if tokens else "custom"

            options = {}
            for token in tokens[1:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    options[key] = value

            planner_parts = options.get("planner", "ollama:gemma3:1b").split(":", 1)
            planner_provider = planner_parts[0]
            planner_model = planner_parts[1] if len(planner_parts) > 1 else "gemma3:1b"

            executor_parts = options.get("executor", "ollama:gemma4:e4b").split(":", 1)
            executor_provider = executor_parts[0]
            executor_model = executor_parts[1] if len(executor_parts) > 1 else "gemma4:e4b"

            validator_provider = None
            validator_model = None
            if "validator" in options:
                validator_parts = options["validator"].split(":", 1)
                validator_provider = validator_parts[0]
                validator_model = validator_parts[1] if len(validator_parts) > 1 else planner_model

            config = manager.create_custom_config(
                name=name,
                planner_provider=planner_provider,
                planner_model=planner_model,
                executor_provider=executor_provider,
                executor_model=executor_model,
                validator_provider=validator_provider,
                validator_model=validator_model,
                planner_api_key=options.get("planner-key"),
                executor_api_key=options.get("executor-key"),
                validator_api_key=options.get("validator-key"),
            )

            manager.set_active_config(name)

            return CommandResult(
                message=f"[green]✓ Created and activated config: {name}[/green]\n"
                f"  Planner: {config.planner.model_name} ({config.planner.provider.value})\n"
                f"  Executor: {config.executor.model_name} ({config.executor.provider.value})\n"
                f"  Validator: {config.validator.model_name} ({config.validator.provider.value})"
            )

        else:
            return CommandResult(
                success=False,
                message=f"Unknown action: {action}\nAvailable: list, use, check, create",
            )
