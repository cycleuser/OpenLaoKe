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
    description = "Manage HyperAuto autonomous operation mode"
    aliases = ["ha", "auto"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()

        if not args or args == "status":
            return self._show_status(ctx)
        elif args == "start":
            return self._start_hyperauto(ctx)
        elif args == "stop":
            return self._stop_hyperauto(ctx)
        elif args == "config":
            return self._show_config(ctx)
        elif args.startswith("config "):
            return self._set_config(ctx, args[7:].strip())
        elif args == "resume":
            return self._resume_task(ctx)
        elif args == "history":
            return self._show_history(ctx)
        elif args == "learn":
            return self._toggle_learning(ctx)
        elif args == "clear":
            return self._clear_history(ctx)
        else:
            return CommandResult(
                success=False,
                message="Usage: /hyperauto [start|stop|status|config|resume|history|learn]\n"
                "  /hyperauto          - Show current status\n"
                "  /hyperauto start    - Start HyperAuto mode\n"
                "  /hyperauto stop     - Stop current task\n"
                "  /hyperauto config   - Show configuration\n"
                "  /hyperauto config <key>=<value> - Set config\n"
                "  /hyperauto resume   - Resume last task\n"
                "  /hyperauto history  - Show task history\n"
                "  /hyperauto learn    - Toggle learning mode\n"
                "  /hyperauto clear    - Clear history",
            )

    def _show_status(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        lines = [
            "HyperAuto Status:",
            "",
            f"  Mode:          {hyperauto_config.mode.value}",
            f"  Enabled:       {hyperauto_config.enabled}",
            f"  Learning:      {hyperauto_config.learning_enabled}",
            f"  Max Iterations: {hyperauto_config.max_iterations}",
            f"  Timeout:       {hyperauto_config.timeout_seconds}s",
            f"  Auto Save:     {hyperauto_config.auto_save}",
            f"  History Limit: {hyperauto_config.history_limit}",
            "",
        ]

        active_task = self._get_active_hyperauto_task(ctx)
        if active_task:
            lines.append("Active Task:")
            lines.append(f"  ID:        {active_task.get('id', 'unknown')}")
            lines.append(f"  Status:    {active_task.get('status', 'unknown')}")
            lines.append(f"  Started:   {active_task.get('start_time', 'unknown')}")
            if active_task.get("description"):
                lines.append(f"  Desc:      {active_task['description']}")
        else:
            lines.append("No active HyperAuto task.")

        return CommandResult(message="\n".join(lines))

    def _start_hyperauto(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        if not hyperauto_config.enabled:
            return CommandResult(
                success=False,
                message="HyperAuto is disabled. Enable it first with /hyperauto config enabled=true",
            )

        active_task = self._get_active_hyperauto_task(ctx)
        if active_task:
            return CommandResult(
                success=False,
                message=f"HyperAuto task already running (ID: {active_task.get('id')}). Use /hyperauto stop first.",
            )

        task_id = f"ha_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        task = {
            "id": task_id,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "mode": hyperauto_config.mode.value,
            "iterations": 0,
            "description": "HyperAuto autonomous operation",
        }

        self._save_active_task(ctx, task)
        self._add_to_history(ctx, task)

        lines = [
            "HyperAuto Started:",
            "",
            f"  Task ID:  {task_id}",
            f"  Mode:     {hyperauto_config.mode.value}",
            f"  Timeout:  {hyperauto_config.timeout_seconds}s",
            "",
            "The AI will operate autonomously within configured limits.",
            "Use /hyperauto stop to halt execution.",
        ]

        return CommandResult(message="\n".join(lines))

    def _stop_hyperauto(self, ctx: CommandContext) -> CommandResult:
        active_task = self._get_active_hyperauto_task(ctx)

        if not active_task:
            return CommandResult(message="No active HyperAuto task to stop.")

        task_id = active_task.get("id", "unknown")
        active_task["status"] = "stopped"
        active_task["end_time"] = datetime.now().isoformat()

        self._update_history_task(ctx, active_task)
        self._clear_active_task(ctx)

        lines = [
            "HyperAuto Stopped:",
            "",
            f"  Task ID:     {task_id}",
            f"  Iterations:  {active_task.get('iterations', 0)}",
            f"  Duration:    {self._calculate_duration(active_task)}",
            "",
            "Task saved to history. Use /hyperauto resume to continue.",
        ]

        return CommandResult(message="\n".join(lines))

    def _show_config(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        lines = [
            "HyperAuto Configuration:",
            "",
            f"  mode:            {hyperauto_config.mode.value}",
            f"  enabled:         {hyperauto_config.enabled}",
            f"  max_iterations:  {hyperauto_config.max_iterations}",
            f"  timeout_seconds: {hyperauto_config.timeout_seconds}",
            f"  auto_save:       {hyperauto_config.auto_save}",
            f"  learning_enabled: {hyperauto_config.learning_enabled}",
            f"  history_limit:   {hyperauto_config.history_limit}",
            "",
            "Change with: /hyperauto config <key>=<value>",
            "Example: /hyperauto config max_iterations=200",
            "",
            "Modes:",
            "  semi_auto   - AI suggests, user confirms major decisions",
            "  full_auto   - AI operates independently with safety checks",
            "  hyper_auto  - Full autonomous operation with minimal oversight",
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
                message=f"Invalid key: {key}. Valid keys: {', '.join(valid_keys)}",
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

            return CommandResult(message=f"Config updated: {key}={value}")
        except ValueError as e:
            return CommandResult(success=False, message=f"Invalid value: {e}")

    def _resume_task(self, ctx: CommandContext) -> CommandResult:
        history = self._load_history(ctx)

        if not history:
            return CommandResult(message="No HyperAuto history to resume.")

        last_task = history[-1]
        if last_task.get("status") == "running":
            return CommandResult(message="Last task is still running. Use /hyperauto status.")

        task_id = f"ha_{datetime.now().strftime('%Y%m%d_%H%M%S')}_resumed"
        resumed_task = {
            "id": task_id,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "mode": last_task.get("mode", "semi_auto"),
            "iterations": 0,
            "description": f"Resumed from {last_task.get('id')}",
            "resumed_from": last_task.get("id"),
        }

        self._save_active_task(ctx, resumed_task)
        self._add_to_history(ctx, resumed_task)

        lines = [
            "HyperAuto Resumed:",
            "",
            f"  New Task ID:    {task_id}",
            f"  Resumed From:   {last_task.get('id')}",
            f"  Mode:           {resumed_task['mode']}",
            "",
            "Previous context restored. Use /hyperauto stop to halt.",
        ]

        return CommandResult(message="\n".join(lines))

    def _show_history(self, ctx: CommandContext) -> CommandResult:
        history = self._load_history(ctx)

        lines = ["HyperAuto Task History:", ""]

        if not history:
            lines.append("  No tasks in history.")
            lines.append("  Start a task with /hyperauto start")
        else:
            lines.append(f"  Total tasks: {len(history)}")
            lines.append("")
            for i, task in enumerate(history[-10:], 1):
                status = task.get("status", "unknown")
                mode = task.get("mode", "unknown")
                start = task.get("start_time", "unknown")
                duration = self._calculate_duration(task)
                lines.append(f"  [{i}] {task.get('id', 'unknown')}")
                lines.append(f"      Status: {status}, Mode: {mode}")
                lines.append(f"      Started: {start}, Duration: {duration}")
                if task.get("description"):
                    lines.append(f"      Desc: {task['description']}")
                lines.append("")

            if len(history) > 10:
                lines.append(f"  ... and {len(history) - 10} more tasks")
                lines.append("  Use /hyperauto clear to reset history")

        return CommandResult(message="\n".join(lines))

    def _toggle_learning(self, ctx: CommandContext) -> CommandResult:
        hyperauto_config = self._get_hyperauto_config(ctx)

        hyperauto_config.learning_enabled = not hyperauto_config.learning_enabled
        self._save_config(ctx, hyperauto_config)

        status = "enabled" if hyperauto_config.learning_enabled else "disabled"
        lines = [
            f"Learning mode {status}:",
            "",
            "When enabled, HyperAuto will:",
            "  - Learn from successful operations",
            "  - Adapt strategies based on patterns",
            "  - Store insights for future tasks",
            "",
            f"Current status: {status}",
        ]

        return CommandResult(message="\n".join(lines))

    def _clear_history(self, ctx: CommandContext) -> CommandResult:
        history_path = self._get_history_path(ctx)

        try:
            if os.path.exists(history_path):
                os.remove(history_path)
            return CommandResult(message="HyperAuto history cleared.")
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
