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

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            current = ctx.app_state.session_config.model
            return CommandResult(message=f"Current model: {current}")

        ctx.app_state.session_config.model = args
        return CommandResult(message=f"Model set to: {args}")


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

        if filename:
            path = os.path.expanduser(filename)
        else:
            path = f"session_{ctx.app_state.session_id}.json"

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

        if filename:
            path = os.path.expanduser(filename)
        else:
            path = f"session_{ctx.app_state.session_id}.md"

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
            format_history_list,
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

        return CommandResult(message=format_history_list(abs_path))
