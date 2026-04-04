"""HyperAuto command for autonomous operation modes."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand
from openlaoke.types.core_types import HyperAutoMode

if TYPE_CHECKING:
    pass


class HyperAutoCommand(SlashCommand):
    """Manage HyperAuto autonomous operation modes."""

    name = "hyperauto"
    description = "Start autonomous operation mode"
    aliases = ["ha", "auto", "hyper"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()

        # No args - show status
        if not args:
            return self._show_status(ctx)

        args_lower = args.lower()

        # Direct task description (most common usage)
        if args_lower.split()[0] not in [
            "start",
            "stop",
            "status",
            "progress",
            "config",
            "resume",
            "history",
            "learn",
            "clear",
            "on",
            "off",
            "enable",
            "disable",
        ]:
            return self._start_with_task(ctx, args)

        # Command-based operations
        if args_lower == "status":
            return self._show_status(ctx)
        elif args_lower in ["progress", "prog"]:
            return self._show_progress(ctx)
        elif args_lower in ["on", "enable"]:
            return self._enable_hyperauto(ctx)
        elif args_lower in ["off", "disable"]:
            return self._disable_hyperauto(ctx)
        elif args_lower == "start":
            return self._start_hyperauto(ctx, None)
        elif args_lower.startswith("start "):
            task_description = args[6:].strip()
            return self._start_with_task(ctx, task_description)
        elif args_lower == "stop":
            return self._stop_hyperauto(ctx)
        elif args_lower == "config":
            return self._show_config(ctx)
        elif args_lower.startswith("config "):
            return self._set_config(ctx, args[7:].strip())
        elif args_lower == "resume":
            return self._resume_task(ctx)
        elif args_lower == "history":
            return self._show_history(ctx)
        elif args_lower == "learn":
            return self._toggle_learning(ctx)
        elif args_lower == "clear":
            return self._clear_history(ctx)
        else:
            return self._show_help()

    def _show_help(self) -> CommandResult:
        lines = [
            "[bold]HyperAuto - Autonomous Operation Mode[/bold]",
            "",
            "[cyan]Quick Start:[/cyan]",
            "  /hyperauto <task>              Start autonomous task immediately",
            "  /hyperauto start <task>        Start with task description",
            "",
            "[cyan]Monitoring:[/cyan]",
            "  /hyperauto                     Show current status",
            "  /hyperauto progress            Show detailed progress",
            "",
            "[cyan]Control:[/cyan]",
            "  /hyperauto on                  Enable HyperAuto mode",
            "  /hyperauto off                 Disable HyperAuto mode",
            "  /hyperauto stop                Stop current task",
            "  /hyperauto resume              Resume last task",
            "",
            "[cyan]Configuration:[/cyan]",
            "  /hyperauto config              Show configuration",
            "  /hyperauto config <key>=<value> Set config option",
            "  /hyperauto learn               Toggle learning mode",
            "",
            "[cyan]History:[/cyan]",
            "  /hyperauto history             Show task history",
            "  /hyperauto clear               Clear history",
            "",
            "[dim]Examples:[/dim]",
            "  [dim]/hyperauto Refactor the authentication module[/dim]",
            "  [dim]/hyperauto start Convert project to C language[/dim]",
            "  [dim]/hyperauto config max_iterations=200[/dim]",
        ]
        return CommandResult(message="\n".join(lines))

    def _enable_hyperauto(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)
        hyperauto_config.enabled = True
        self._save_config(ctx, hyperauto_config)

        lines = [
            "[green]✓ HyperAuto enabled[/green]",
            "",
            f"Mode: {hyperauto_config.mode.value}",
            f"Max iterations: {hyperauto_config.max_iterations}",
            f"Timeout: {hyperauto_config.timeout_seconds}s",
            "",
            "[dim]Start a task: /hyperauto <task_description>[/dim]",
        ]
        return CommandResult(message="\n".join(lines))

    def _disable_hyperauto(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)
        hyperauto_config.enabled = False
        self._save_config(ctx, hyperauto_config)

        return CommandResult(message="[yellow]HyperAuto disabled[/yellow]")

    def _start_with_task(self, ctx: CommandContext, task_description: str) -> CommandResult:
        """Start HyperAuto with a specific task (auto-enable if needed)."""
        hyperauto_config = self._get_hyperauto_config(ctx)

        # Auto-enable if disabled
        if not hyperauto_config.enabled:
            hyperauto_config.enabled = True
            self._save_config(ctx, hyperauto_config)

        return self._start_hyperauto(ctx, task_description)

    def _show_status(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        status_icon = "[green]●[/green]" if hyperauto_config.enabled else "[red]○[/red]"
        status_text = "enabled" if hyperauto_config.enabled else "disabled"

        lines = [
            f"HyperAuto Status: {status_icon} {status_text}",
            "",
            f"  Mode:           {hyperauto_config.mode.value}",
            f"  Max Iterations: {hyperauto_config.max_iterations}",
            f"  Timeout:        {hyperauto_config.timeout_seconds}s",
            f"  Learning:       {'on' if hyperauto_config.learning_enabled else 'off'}",
            f"  Auto Save:      {'on' if hyperauto_config.auto_save else 'off'}",
            "",
        ]

        active_task = self._get_active_hyperauto_task(ctx)
        if active_task:
            lines.append("[bold]Active Task:[/bold]")
            lines.append(f"  ID:     {active_task.get('id', 'unknown')}")
            lines.append(f"  Status: {active_task.get('status', 'unknown')}")
            if active_task.get("description"):
                lines.append(f"  Task:   {active_task['description']}")
            lines.append(f"  Started: {active_task.get('start_time', 'unknown')}")
            lines.append(f"  Iterations: {active_task.get('iterations', 0)}")
        else:
            lines.append("[dim]No active task[/dim]")
            lines.append("")
            lines.append("[dim]Start a task: /hyperauto <task_description>[/dim]")

        return CommandResult(message="\n".join(lines))

    def _show_progress(self, ctx: CommandContext) -> CommandResult:
        """Show detailed progress of active task."""
        active_task = self._get_active_hyperauto_task(ctx)

        if not active_task:
            return CommandResult(
                message="[yellow]No active HyperAuto task[/yellow]\n\n[dim]Start a task: /hyperauto <task_description>[/dim]"
            )

        task_id = active_task.get("id", "unknown")
        status = active_task.get("status", "unknown")
        description = active_task.get("description", "No description")
        iterations = active_task.get("iterations", 0)
        max_iterations = self._get_hyperauto_config(ctx).max_iterations
        steps = active_task.get("steps", [])
        current_step = active_task.get("current_step", 0)
        completed_steps = active_task.get("completed_steps", [])

        # Calculate progress
        progress_pct = (iterations / max_iterations * 100) if max_iterations > 0 else 0
        duration = self._calculate_duration(active_task)

        # Progress bar
        bar_width = 30
        filled = int(progress_pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            "[bold]HyperAuto Task Progress[/bold]",
            "",
            f"  Task ID:  {task_id}",
            f"  Status:   {status}",
            f"  Duration: {duration}",
            "",
            f"  Task: {description[:60]}{'...' if len(description) > 60 else ''}",
            "",
            f"  Progress: [{bar}] {progress_pct:.1f}%",
            f"  Iterations: {iterations}/{max_iterations}",
            "",
        ]

        # Show steps if available
        if steps:
            lines.append("[bold]  Steps:[/bold]")
            for i, step in enumerate(steps[:10], 1):
                if i <= len(completed_steps):
                    icon = "[green]✓[/green]"
                elif i == current_step:
                    icon = "[yellow]●[/yellow]"
                else:
                    icon = "[dim]○[/dim]"

                step_text = step[:50] if len(step) > 50 else step
                lines.append(f"    {icon} {i}. {step_text}")

            if len(steps) > 10:
                lines.append(f"    [dim]... and {len(steps) - 10} more steps[/dim]")

        # Show recent actions
        recent_actions = active_task.get("recent_actions", [])
        if recent_actions:
            lines.append("")
            lines.append("[bold]  Recent Actions:[/bold]")
            for action in recent_actions[-5:]:
                lines.append(f"    • {action[:70]}")

        # Show errors if any
        errors = active_task.get("errors", [])
        if errors:
            lines.append("")
            lines.append(f"[red]  Errors: {len(errors)}[/red]")
            for error in errors[-3:]:
                lines.append(f"    [red]✗[/red] {error[:60]}")

        lines.extend(
            [
                "",
                "[dim]Commands:[/dim]",
                "  [dim]/hyperauto          - Show status[/dim]",
                "  [dim]/hyperauto progress - Show this progress view[/dim]",
                "  [dim]/hyperauto stop     - Stop the task[/dim]",
            ]
        )

        return CommandResult(message="\n".join(lines))

    def _start_hyperauto(self, ctx: CommandContext, task_description: str | None) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        # Auto-enable if disabled
        if not hyperauto_config.enabled:
            hyperauto_config.enabled = True
            self._save_config(ctx, hyperauto_config)

        active_task = self._get_active_hyperauto_task(ctx)
        if active_task:
            return CommandResult(
                success=False,
                message=f"Task already running (ID: {active_task.get('id')}).\nUse /hyperauto stop first.",
            )

        task_id = f"ha_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        task = {
            "id": task_id,
            "status": "initializing",
            "start_time": datetime.now().isoformat(),
            "mode": hyperauto_config.mode.value,
            "iterations": 0,
            "description": task_description or "Autonomous operation",
            "steps": [],
            "current_step": 0,
            "completed_steps": [],
            "recent_actions": [],
        }

        self._save_active_task(ctx, task)
        self._add_to_history(ctx, task)

        # Start async execution
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        asyncio.create_task(self._execute_hyperauto_task(ctx, task_id, task_description))

        lines = [
            "[green]✓ HyperAuto Started[/green]",
            "",
            f"  Task ID: {task_id}",
            f"  Mode:    {hyperauto_config.mode.value}",
        ]

        if task_description:
            desc = task_description[:60]
            if len(task_description) > 60:
                desc += "..."
            lines.append(f"  Task:    {desc}")

        lines.extend(
            [
                f"  Timeout: {hyperauto_config.timeout_seconds}s",
                "",
                "[dim]The AI is now working...[/dim]",
                "[dim]Use /hyperauto progress to monitor.[/dim]",
                "",
                "[bold cyan]Real-time output below:[/bold cyan]",
            ]
        )

        return CommandResult(message="\n".join(lines))

    def _stop_hyperauto(self, ctx: CommandContext) -> CommandResult:
        active_task = self._get_active_hyperauto_task(ctx)

        if not active_task:
            return CommandResult(message="[yellow]No active HyperAuto task to stop.[/yellow]")

        task_id = active_task.get("id", "unknown")
        active_task["status"] = "stopped"
        active_task["end_time"] = datetime.now().isoformat()

        self._update_history_task(ctx, active_task)
        self._clear_active_task(ctx)

        lines = [
            "[yellow]HyperAuto Stopped[/yellow]",
            "",
            f"  Task ID:    {task_id}",
            f"  Iterations: {active_task.get('iterations', 0)}",
            f"  Duration:   {self._calculate_duration(active_task)}",
            "",
            "[dim]Task saved to history. Use /hyperauto resume to continue.[/dim]",
        ]

        return CommandResult(message="\n".join(lines))

    def _show_config(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        lines = [
            "[bold]HyperAuto Configuration[/bold]",
            "",
            f"  mode:             {hyperauto_config.mode.value}",
            f"  enabled:          {hyperauto_config.enabled}",
            f"  max_iterations:   {hyperauto_config.max_iterations}",
            f"  timeout_seconds:  {hyperauto_config.timeout_seconds}",
            f"  auto_save:        {hyperauto_config.auto_save}",
            f"  learning_enabled: {hyperauto_config.learning_enabled}",
            f"  history_limit:    {hyperauto_config.history_limit}",
            "",
            "[dim]Change: /hyperauto config <key>=<value>[/dim]",
            "[dim]Example: /hyperauto config max_iterations=200[/dim]",
            "",
            "[bold]Modes:[/bold]",
            "  semi_auto   - AI suggests, user confirms",
            "  full_auto   - AI operates with safety checks",
            "  hyper_auto  - Full autonomous operation",
        ]

        return CommandResult(message="\n".join(lines))

    def _set_config(self, ctx: CommandContext, config_str: str) -> CommandResult:
        if "=" not in config_str:
            return CommandResult(
                success=False,
                message="Invalid format. Use: /hyperauto config <key>=<value>",
            )

        key, value = config_str.split("=", 1)
        key = key.strip()
        value = value.strip()

        hyperauto_config = self._get_hyperauto_config(ctx)

        valid_keys = {
            "mode",
            "enabled",
            "max_iterations",
            "timeout_seconds",
            "auto_save",
            "learning_enabled",
            "history_limit",
        }

        if key not in valid_keys:
            return CommandResult(
                success=False,
                message=f"Invalid key: {key}\nValid keys: {', '.join(sorted(valid_keys))}",
            )

        try:
            if key == "mode":
                hyperauto_config.mode = HyperAutoMode(value)
            elif key == "enabled":
                hyperauto_config.enabled = value.lower() in ("true", "1", "yes", "on")
            elif key == "max_iterations":
                hyperauto_config.max_iterations = int(value)
            elif key == "timeout_seconds":
                hyperauto_config.timeout_seconds = int(value)
            elif key == "auto_save":
                hyperauto_config.auto_save = value.lower() in ("true", "1", "yes", "on")
            elif key == "learning_enabled":
                hyperauto_config.learning_enabled = value.lower() in ("true", "1", "yes", "on")
            elif key == "history_limit":
                hyperauto_config.history_limit = int(value)

            self._save_config(ctx, hyperauto_config)

            return CommandResult(message=f"[green]✓[/green] Config updated: {key}={value}")
        except ValueError as e:
            return CommandResult(success=False, message=f"Invalid value: {e}")

    def _resume_task(self, ctx: CommandContext) -> CommandResult:
        history = self._load_history(ctx)

        if not history:
            return CommandResult(message="[yellow]No HyperAuto history to resume.[/yellow]")

        last_task = history[-1]
        if last_task.get("status") == "running":
            return CommandResult(
                message="Last task is still running.\nUse /hyperauto status to check."
            )

        task_id = f"ha_{datetime.now().strftime('%Y%m%d_%H%M%S')}_resumed"
        resumed_task = {
            "id": task_id,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "mode": last_task.get("mode", "semi_auto"),
            "iterations": 0,
            "description": last_task.get("description", "Resumed task"),
            "resumed_from": last_task.get("id"),
        }

        self._save_active_task(ctx, resumed_task)
        self._add_to_history(ctx, resumed_task)

        lines = [
            "[green]✓ HyperAuto Resumed[/green]",
            "",
            f"  New Task ID:  {task_id}",
            f"  Resumed From: {last_task.get('id')}",
            f"  Mode:         {resumed_task['mode']}",
            "",
            "[dim]Previous context restored. Use /hyperauto stop to halt.[/dim]",
        ]

        return CommandResult(message="\n".join(lines))

    def _show_history(self, ctx: CommandContext) -> CommandResult:
        history = self._load_history(ctx)

        lines = ["[bold]HyperAuto Task History[/bold]", ""]

        if not history:
            lines.append("[dim]No tasks in history.[/dim]")
            lines.append("[dim]Start a task: /hyperauto <task_description>[/dim]")
        else:
            lines.append(f"Total tasks: {len(history)}")
            lines.append("")

            for i, task in enumerate(history[-10:], 1):
                status = task.get("status", "unknown")
                status_icon = {
                    "running": "[green]●[/green]",
                    "stopped": "[yellow]●[/yellow]",
                    "completed": "[green]✓[/green]",
                    "failed": "[red]✗[/red]",
                }.get(status, "○")

                lines.append(f"{status_icon} [{i}] {task.get('id', 'unknown')}")
                lines.append(f"    Status: {status}, Mode: {task.get('mode', 'unknown')}")
                if task.get("description"):
                    desc = task["description"]
                    if len(desc) > 60:
                        desc = desc[:57] + "..."
                    lines.append(f"    Task: {desc}")
                lines.append(f"    Duration: {self._calculate_duration(task)}")
                lines.append("")

            if len(history) > 10:
                lines.append(f"[dim]... and {len(history) - 10} more tasks[/dim]")
                lines.append("[dim]Use /hyperauto clear to reset history[/dim]")

        return CommandResult(message="\n".join(lines))

    def _toggle_learning(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        hyperauto_config.learning_enabled = not hyperauto_config.learning_enabled
        self._save_config(ctx, hyperauto_config)

        status = (
            "[green]enabled[/green]"
            if hyperauto_config.learning_enabled
            else "[yellow]disabled[/yellow]"
        )

        lines = [
            f"Learning mode {status}",
            "",
            "When enabled, HyperAuto will:",
            "  • Learn from successful operations",
            "  • Adapt strategies based on patterns",
            "  • Store insights for future tasks",
        ]

        return CommandResult(message="\n".join(lines))

    def _clear_history(self, ctx: CommandContext) -> CommandResult:
        history_path = self._get_history_path(ctx)

        try:
            if os.path.exists(history_path):
                os.remove(history_path)
            return CommandResult(message="[green]✓[/green] HyperAuto history cleared.")
        except Exception as e:
            return CommandResult(success=False, message=f"Failed to clear history: {e}")

    def _get_hyperauto_config(self, ctx: CommandContext):
        if hasattr(ctx.app_state, "permission_config") and hasattr(
            ctx.app_state.permission_config, "hyperauto_config"
        ):
            return ctx.app_state.permission_config.hyperauto_config
        elif hasattr(ctx.app_state, "app_config") and ctx.app_state.app_config:
            return ctx.app_state.app_config.hyperauto_config
        else:
            from openlaoke.types.permissions import HyperAutoConfig

            return HyperAutoConfig()

    def _save_config(self, ctx: CommandContext, config) -> None:
        if hasattr(ctx.app_state, "permission_config") and hasattr(
            ctx.app_state.permission_config, "hyperauto_config"
        ):
            ctx.app_state.permission_config.hyperauto_config = config
        elif hasattr(ctx.app_state, "app_config") and ctx.app_state.app_config:
            ctx.app_state.app_config.hyperauto_config = config

        config_path = os.path.expanduser("~/.openlaoke/config.json")
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            existing_config = {}
            if os.path.exists(config_path):
                with open(config_path) as f:
                    existing_config = json.load(f)

            existing_config["hyperauto_config"] = {
                "mode": config.mode.value,
                "enabled": config.enabled,
                "max_iterations": config.max_iterations,
                "timeout_seconds": config.timeout_seconds,
                "auto_save": config.auto_save,
                "learning_enabled": config.learning_enabled,
                "history_limit": config.history_limit,
            }

            with open(config_path, "w") as f:
                json.dump(existing_config, f, indent=2)
        except Exception:
            pass

    def _get_history_path(self, ctx: CommandContext) -> str:
        return os.path.expanduser("~/.openlaoke/hyperauto_history.json")

    def _get_active_task_path(self, ctx: CommandContext) -> str:
        return os.path.expanduser("~/.openlaoke/hyperauto_active.json")

    def _load_history(self, ctx: CommandContext) -> list[dict[str, Any]]:
        history_path = self._get_history_path(ctx)
        try:
            if os.path.exists(history_path):
                with open(history_path) as f:
                    data = json.load(f)
                    return list(data) if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def _save_history(self, ctx: CommandContext, history: list) -> None:
        history_path = self._get_history_path(ctx)
        hyperauto_config = self._get_hyperauto_config(ctx)

        if len(history) > hyperauto_config.history_limit:
            history = history[-hyperauto_config.history_limit :]

        try:
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            with open(history_path, "w") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

    def _add_to_history(self, ctx: CommandContext, task: dict) -> None:
        history = self._load_history(ctx)
        history.append(task)
        self._save_history(ctx, history)

    def _update_history_task(self, ctx: CommandContext, task: dict) -> None:
        history = self._load_history(ctx)
        for i, h_task in enumerate(history):
            if h_task.get("id") == task.get("id"):
                history[i] = task
                break
        self._save_history(ctx, history)

    def _get_active_hyperauto_task(self, ctx: CommandContext) -> dict[str, Any] | None:
        active_path = self._get_active_task_path(ctx)
        try:
            if os.path.exists(active_path):
                with open(active_path) as f:
                    data = json.load(f)
                    return dict(data) if isinstance(data, dict) else None
        except Exception:
            pass
        return None

    def _save_active_task(self, ctx: CommandContext, task: dict) -> None:
        active_path = self._get_active_task_path(ctx)
        try:
            os.makedirs(os.path.dirname(active_path), exist_ok=True)
            with open(active_path, "w") as f:
                json.dump(task, f, indent=2)
        except Exception:
            pass

    def _clear_active_task(self, ctx: CommandContext) -> None:
        active_path = self._get_active_task_path(ctx)
        try:
            if os.path.exists(active_path):
                os.remove(active_path)
        except Exception:
            pass

    def _calculate_duration(self, task: dict) -> str:
        start_time = task.get("start_time")
        end_time = task.get("end_time")

        if not start_time:
            return "unknown"

        try:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time) if end_time else datetime.now()

            duration = end - start
            seconds = int(duration.total_seconds())
            minutes = seconds // 60
            secs = seconds % 60

            if minutes > 0:
                return f"{minutes}m {secs}s"
            return f"{secs}s"
        except Exception:
            return "unknown"

    async def _execute_hyperauto_task(
        self, ctx: CommandContext, task_id: str, task_description: str | None
    ) -> None:
        """Execute HyperAuto task in background and display output."""
        from rich.console import Console

        console = Console()

        try:
            # Update status to running
            task = self._get_active_hyperauto_task(ctx)
            if task:
                task["status"] = "running"
                task["steps"] = [
                    "Analyzing task requirements",
                    "Creating execution plan",
                    "Executing subtasks",
                    "Verifying results",
                    "Finalizing",
                ]
                task["recent_actions"] = ["Starting execution..."]
                self._save_active_task(ctx, task)

            console.print("\n[bold cyan]► HyperAuto Execution Started[/bold cyan]")
            console.print(f"[dim]Task: {task_description or 'Autonomous operation'}[/dim]\n")

            # Import and create HyperAuto agent
            from openlaoke.core.hyperauto.agent import HyperAutoAgent
            from openlaoke.core.hyperauto.config import HyperAutoConfig as HAutoConfig

            hyperauto_config = self._get_hyperauto_config(ctx)
            ha_config = HAutoConfig(
                mode=hyperauto_config.mode,
                max_iterations=hyperauto_config.max_iterations,
                timeout_per_task=hyperauto_config.timeout_seconds,
                learning_enabled=hyperauto_config.learning_enabled,
                reflection_enabled=True,
            )

            agent = HyperAutoAgent(ctx.app_state, ha_config)

            # Run the agent
            console.print("[yellow]▶ Running autonomous execution...[/yellow]\n")

            result = await agent.run(task_description or "Autonomous operation")

            # Update final status
            task = self._get_active_hyperauto_task(ctx)
            if task:
                if result.get("success"):
                    task["status"] = "completed"
                    task["completed_steps"] = task.get("steps", [])
                    task["iterations"] = result.get("context", {}).get("iteration", 0)

                    console.print("\n[bold green]✓ HyperAuto Completed Successfully![/bold green]")
                    console.print(f"[green]Task ID: {task_id}[/green]")
                    console.print(f"[green]Iterations: {task['iterations']}[/green]\n")
                else:
                    task["status"] = "failed"
                    error_msg = result.get("error", "Unknown error")
                    if "errors" not in task:
                        task["errors"] = []
                    task["errors"].append(error_msg)

                    console.print("\n[bold red]✗ HyperAuto Failed[/bold red]")
                    console.print(f"[red]Error: {error_msg}[/red]\n")

                task["end_time"] = datetime.now().isoformat()
                self._update_history_task(ctx, task)

        except Exception as e:
            console.print(f"\n[bold red]✗ HyperAuto Error: {e}[/bold red]\n")

            # Update task status
            task = self._get_active_hyperauto_task(ctx)
            if task:
                task["status"] = "failed"
                task["end_time"] = datetime.now().isoformat()
                if "errors" not in task:
                    task["errors"] = []
                task["errors"].append(str(e))
                self._update_history_task(ctx, task)
