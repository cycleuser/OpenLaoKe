"""pi-compatible slash commands.

Python implementations of the built-in commands shipped by pi
(https://github.com/earendil-works/pi), so the OpenLaoKe REPL exposes the
same command surface: ``new``, ``name``, ``session``, ``tree``, ``fork``,
``clone``, ``import``, ``share``, ``copy``, ``changelog``, ``hotkeys``,
``trust``, ``login``, ``logout``, ``reload``, ``scoped-models`` and
``prompt``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand

if TYPE_CHECKING:
    from openlaoke.core.state import AppState

_OPENLAOKE_DIR = Path.home() / ".openlaoke"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _session_name(session_id: str) -> str:
    meta = _read_json(_OPENLAOKE_DIR / "sessions" / f"{session_id}.meta.json", {})
    return str(meta.get("name", "")) if isinstance(meta, dict) else ""


def _set_session_name(session_id: str, name: str) -> None:
    path = _OPENLAOKE_DIR / "sessions" / f"{session_id}.meta.json"
    meta = _read_json(path, {})
    if not isinstance(meta, dict):
        meta = {}
    meta["name"] = name
    meta["session_id"] = session_id
    _write_json(path, meta)


def _snapshot_store(app_state: AppState) -> Any:
    store = getattr(app_state, "_snapshot_store", None)
    if store is not None:
        return store
    from openlaoke.snapshot.store import SnapshotStore

    store = SnapshotStore()
    app_state._snapshot_store = store
    return store


def _last_assistant_text(app_state: AppState) -> str:
    from openlaoke.types.core_types import AssistantMessage

    for message in reversed(app_state.messages):
        if isinstance(message, AssistantMessage) and getattr(message, "content", ""):
            return str(message.content)
    return ""


def _copy_to_clipboard(text: str) -> bool:
    for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["wl-copy"]):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def _changelog_path() -> Path | None:
    candidates = [
        Path.cwd() / "CHANGELOG.md",
        Path(__file__).resolve().parents[2] / "CHANGELOG.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _trust_path() -> Path:
    return _OPENLAOKE_DIR / "trust.json"


class NewCommand(SlashCommand):
    name = "new"
    description = "Start a new session"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.sessions import SessionManager

        manager = SessionManager()
        with suppress(Exception):
            manager.save_session(ctx.app_state)
        old = ctx.app_state.session_id
        ctx.app_state.messages.clear()
        ctx.app_state.tasks.clear()
        ctx.app_state.session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        ctx.app_state.set_persist_path(
            os.path.join(manager.session_dir, f"{ctx.app_state.session_id}.json")
        )
        return CommandResult(
            message=f"Started new session {ctx.app_state.session_id} (previous: {old})."
        )


class NameCommand(SlashCommand):
    name = "name"
    description = "Set or show the session display name"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            current = _session_name(ctx.app_state.session_id)
            return CommandResult(message=f"Session name: {current or '(unset)'}")
        _set_session_name(ctx.app_state.session_id, args)
        return CommandResult(message=f"Session renamed to: {args}")


class SessionCommand(SlashCommand):
    name = "session"
    description = "Show session info and stats"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        state = ctx.app_state
        usage = state.token_usage
        total_tokens = (
            usage.input_tokens
            + usage.output_tokens
            + usage.cache_read_tokens
            + usage.cache_creation_tokens
        )
        lines = [
            "Session",
            f"  id:      {state.session_id}",
            f"  name:    {_session_name(state.session_id) or '(unset)'}",
            f"  cwd:     {state.get_cwd()}",
            f"  model:   {state.session_config.model}",
            f"  persist: {state._persist_path or '(not persisted)'}",
            "",
            "Stats",
            f"  messages: {len(state.messages)}",
            f"  tasks:    {len(state.tasks)}",
            f"  tokens:   {total_tokens} (in {usage.input_tokens} / out {usage.output_tokens} / "
            f"cache-r {usage.cache_read_tokens} / cache-w {usage.cache_creation_tokens})",
            f"  cost:     {state.cost_info.total_cost:.4f}",
        ]
        return CommandResult(message="\n".join(lines))


class TreeCommand(SlashCommand):
    name = "tree"
    description = "Show recorded session turns; /tree <n> rewinds to turn n"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        store = _snapshot_store(ctx.app_state)
        session_id = ctx.app_state.session_id
        turns = store.all_turns(session_id)
        if not turns:
            return CommandResult(
                message="No recorded turns for this session yet (snapshots are captured per turn)."
            )

        args = ctx.args.strip()
        if args:
            if not args.isdigit():
                return CommandResult(success=False, message="Usage: /tree <turn-number>")
            target = int(args)
            from openlaoke.snapshot.rewind import rewind_both

            report = rewind_both(store, session_id, target, messages=ctx.app_state.messages)
            restored = sum(1 for v in report.files.values() if v == "restored")
            deleted = sum(1 for v in report.files.values() if v == "deleted")
            return CommandResult(
                message=(
                    f"Rewound to turn {target}: {report.turns_dropped} turn(s) dropped, "
                    f"{restored} file(s) restored, {deleted} deleted."
                )
            )

        lines = ["Session turns (* = current tip):"]
        tip = max(t.turn_index for t in turns)
        for turn in turns:
            marker = "*" if turn.turn_index == tip else " "
            lines.append(f" {marker} turn {turn.turn_index}: {len(turn.files)} file(s)")
        lines.append("")
        lines.append("Use /tree <n> to rewind, /fork <n> to branch from a turn.")
        return CommandResult(message="\n".join(lines))


class ForkCommand(SlashCommand):
    name = "fork"
    description = "Fork the session from a turn (default: tip)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        store = _snapshot_store(ctx.app_state)
        session_id = ctx.app_state.session_id
        args = ctx.args.strip()
        from openlaoke.snapshot.rewind import branch_tip, fork_from

        if args:
            if not args.isdigit():
                return CommandResult(success=False, message="Usage: /fork [turn-number]")
            info = fork_from(store, session_id, int(args))
        else:
            info = branch_tip(store, session_id)
        ctx.app_state.session_id = info["session_id"]
        return CommandResult(
            message=f"Forked session: {info['session_id']} (parent {session_id}, "
            f"turn {info['fork_turn']}). Now on the fork."
        )


class CloneCommand(SlashCommand):
    name = "clone"
    description = "Duplicate the current session at the current position"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        store = _snapshot_store(ctx.app_state)
        session_id = ctx.app_state.session_id
        from openlaoke.snapshot.rewind import branch_tip

        info = branch_tip(store, session_id, label="clone")
        return CommandResult(
            message=f"Cloned session: {info['session_id']} (from {session_id}). "
            f"Use /resume to switch back."
        )


class ImportCommand(SlashCommand):
    name = "import"
    description = "Import a session from an OpenLaoKe JSON or pi JSONL file"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        if not args:
            return CommandResult(success=False, message="Usage: /import <file>")
        path = Path(os.path.expanduser(args))
        if not path.exists():
            return CommandResult(success=False, message=f"File not found: {path}")

        from openlaoke.types.core_types import AssistantMessage, MessageRole, UserMessage

        imported: list[Any] = []
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".jsonl":
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    role = entry.get("role")
                    content = entry.get("content")
                    if isinstance(content, list):
                        content = " ".join(
                            part.get("text", "")
                            for part in content
                            if isinstance(part, dict) and part.get("type") == "text"
                        )
                    if role == "user" and content:
                        imported.append(UserMessage(role=MessageRole.USER, content=str(content)))
                    elif role == "assistant" and content:
                        imported.append(
                            AssistantMessage(role=MessageRole.ASSISTANT, content=str(content))
                        )
            else:
                data = json.loads(text)
                messages = data.get("messages", []) if isinstance(data, dict) else data
                from openlaoke.core.sessions import _message_from_dict

                for item in messages:
                    message = _message_from_dict(item)
                    if message is not None:
                        imported.append(message)
        except (OSError, json.JSONDecodeError) as exc:
            return CommandResult(success=False, message=f"Import failed: {exc}")

        if not imported:
            return CommandResult(success=False, message="No messages found to import.")
        ctx.app_state.messages.clear()
        ctx.app_state.messages.extend(imported)
        return CommandResult(message=f"Imported {len(imported)} message(s) from {path}.")


class ShareCommand(SlashCommand):
    name = "share"
    description = "Share the session as a secret GitHub gist"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        if shutil.which("gh") is None:
            return CommandResult(
                success=False,
                message="The GitHub CLI (gh) is required to share. Install from https://cli.github.com/ "
                "and run 'gh auth login'.",
            )
        data = {
            "session_id": ctx.app_state.session_id,
            "model": ctx.app_state.session_config.model,
            "messages": [m.to_dict() for m in ctx.app_state.messages],
        }
        tmp = Path(os.path.expanduser("~/.openlaoke")) / f"share_{ctx.app_state.session_id}.json"
        _write_json(tmp, data)
        try:
            result = subprocess.run(
                ["gh", "gist", "create", "--desc", f"OpenLaoKe session {ctx.app_state.session_id}", str(tmp)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return CommandResult(success=False, message=f"Share failed: {exc}")
        if result.returncode != 0:
            return CommandResult(success=False, message=f"Share failed: {result.stderr.strip()}")
        return CommandResult(message=f"Shared as secret gist: {result.stdout.strip()}")


class CopyCommand(SlashCommand):
    name = "copy"
    description = "Copy the last assistant message to the clipboard"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        text = _last_assistant_text(ctx.app_state)
        if not text:
            return CommandResult(success=False, message="No assistant message to copy.")
        if _copy_to_clipboard(text):
            return CommandResult(message=f"Copied {len(text)} char(s) to clipboard.")
        ctx.app_state.clipboard_content = text
        return CommandResult(
            message="No clipboard tool found; stored in session.clipboard_content instead."
        )


class ChangelogCommand(SlashCommand):
    name = "changelog"
    description = "Show changelog entries"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        path = _changelog_path()
        if path is None:
            return CommandResult(success=False, message="CHANGELOG.md not found.")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return CommandResult(success=False, message=f"Could not read changelog: {exc}")
        lines = text.splitlines()
        limit = 40
        if ctx.args.strip().isdigit():
            limit = max(1, int(ctx.args.strip()))
        return CommandResult(message="\n".join(lines[:limit]))


class HotkeysCommand(SlashCommand):
    name = "hotkeys"
    description = "Show keyboard shortcuts"

    _HOTKEYS = [
        ("Enter", "Send message"),
        ("Ctrl+P", "Model picker"),
        ("Ctrl+G", "Toggle / expand thinking display"),
        ("Ctrl+L", "Language picker"),
        ("Ctrl+C", "Interrupt the running agent (twice to exit)"),
        ("Up / Down", "Command history / autocomplete"),
        ("Tab", "Accept autocomplete suggestion"),
        ("Esc", "Cancel current input"),
    ]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        lines = ["Keyboard shortcuts:"]
        lines.extend(f"  {key:<14} {desc}" for key, desc in self._HOTKEYS)
        return CommandResult(message="\n".join(lines))


class TrustCommand(SlashCommand):
    name = "trust"
    description = "Save the project trust decision (on/off/status)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        project = str(Path(ctx.app_state.get_cwd()).resolve())
        trust = _read_json(_trust_path(), {})
        if not isinstance(trust, dict):
            trust = {}
        args = ctx.args.strip().lower()
        if not args or args == "status":
            return CommandResult(
                message=f"Project trust for {project}: {'trusted' if trust.get(project) else 'untrusted'}"
            )
        if args in ("on", "yes", "true", "trust"):
            trust[project] = True
        elif args in ("off", "no", "false", "untrust"):
            trust[project] = False
        else:
            return CommandResult(success=False, message="Usage: /trust [on|off|status]")
        _write_json(_trust_path(), trust)
        return CommandResult(message=f"Project trust for {project}: {'trusted' if trust[project] else 'untrusted'}.")


class LoginCommand(SlashCommand):
    name = "login"
    description = "Configure provider authentication (API key)"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.config import load_config, save_config

        config = load_config()
        providers = config.providers.providers
        parts = ctx.args.split(maxsplit=1)

        if not parts:
            lines = ["Providers:"]
            for key, provider in providers.items():
                status = "ready" if provider.is_configured() else "no key"
                lines.append(f"  {key:<20} {status}")
            lines.append("")
            lines.append("Usage: /login <provider> <api-key>")
            return CommandResult(message="\n".join(lines))

        key = parts[0]
        provider = providers.get(key)
        if provider is None:
            return CommandResult(success=False, message=f"Unknown provider: {key}")
        if len(parts) < 2 or not parts[1].strip():
            return CommandResult(
                message=f"Provider {key} configured. Usage: /login {key} <api-key>"
            )
        provider.api_key = parts[1].strip()
        config.providers.active_provider = key
        save_config(config)
        return CommandResult(message=f"Saved API key for {key}.")


class LogoutCommand(SlashCommand):
    name = "logout"
    description = "Remove provider authentication"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.utils.config import load_config, save_config

        config = load_config()
        providers = config.providers.providers
        key = ctx.args.strip()
        if not key:
            return CommandResult(success=False, message="Usage: /logout <provider>")
        provider = providers.get(key)
        if provider is None:
            return CommandResult(success=False, message=f"Unknown provider: {key}")
        provider.api_key = ""
        save_config(config)
        return CommandResult(message=f"Removed API key for {key}.")


class ReloadCommand(SlashCommand):
    name = "reload"
    description = "Reload skills and prompt templates"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.prompt_templates import rescan_prompt_templates
        from openlaoke.core.skill_system import rescan_skills

        skills = rescan_skills()
        templates = rescan_prompt_templates()
        return CommandResult(message=f"Reloaded: {skills} skill(s), {templates} prompt template(s).")


class ScopedModelsCommand(SlashCommand):
    name = "scoped-models"
    description = "List/add/remove models for quick cycling"

    def _path(self) -> Path:
        return _OPENLAOKE_DIR / "scoped_models.json"

    def _load(self) -> list[str]:
        data = _read_json(self._path(), [])
        return [str(item) for item in data] if isinstance(data, list) else []

    def _save(self, models: list[str]) -> None:
        _write_json(self._path(), models)

    async def execute(self, ctx: CommandContext) -> CommandResult:
        parts = ctx.args.split(maxsplit=1)
        action = parts[0].lower() if parts else "list"
        value = parts[1].strip() if len(parts) > 1 else ""
        models = self._load()

        if action in ("list", "") or not action:
            if not models:
                return CommandResult(message="No scoped models. Use /scoped-models add <model>.")
            return CommandResult(message="Scoped models:\n" + "\n".join(f"  {m}" for m in models))
        if action == "add":
            if not value:
                return CommandResult(success=False, message="Usage: /scoped-models add <model>")
            if value not in models:
                models.append(value)
                self._save(models)
            return CommandResult(message=f"Added {value}. Scoped models: {', '.join(models)}")
        if action == "remove":
            models = [m for m in models if m != value]
            self._save(models)
            return CommandResult(message=f"Removed {value}. Scoped models: {', '.join(models) or '(none)'}")
        if action == "clear":
            self._save([])
            return CommandResult(message="Cleared scoped models.")
        return CommandResult(success=False, message="Usage: /scoped-models [list|add|remove|clear] [model]")


class PromptCommand(SlashCommand):
    name = "prompt"
    description = "Expand a pi-style prompt template"

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.prompt_templates import (
            expand_prompt_template,
            list_prompt_templates,
        )

        parts = ctx.args.split(maxsplit=1)
        if not parts:
            names = list_prompt_templates()
            if not names:
                return CommandResult(
                    message="No prompt templates. Add Markdown files to ~/.openlaoke/prompts/."
                )
            return CommandResult(message="Prompt templates:\n" + "\n".join(f"  {n}" for n in names))

        name = parts[0]
        arguments = parts[1] if len(parts) > 1 else ""
        expanded = expand_prompt_template(name, arguments)
        if expanded is None:
            return CommandResult(
                success=False,
                message=f"No prompt template named '{name}'. Use /prompt to list.",
            )
        return CommandResult(message=expanded, submit_text=expanded)
