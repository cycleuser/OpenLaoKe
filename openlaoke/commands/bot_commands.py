"""Bot mode commands: roster, chats, rooms and routines."""

from __future__ import annotations

import shlex
import time

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand
from openlaoke.core.bot_mode import (
    MAX_GROUP_MEMBERS,
    BotMode,
    BotProfile,
    get_bot_mode,
    slug,
)
from openlaoke.core.scheduler import get_scheduler

USAGE = """Bot mode:
  /bot                              list the roster
  /bot new <name> [--title T] [--desc D] [--model M] [--provider P]
                 [--persona P] [--skills a,b] [--section S] [--avatar E] [--readonly]
  /bot use <name> | /bot off        enter or leave a bot chat
  /bot show <name>                  profile, chat size, pending mail
  /bot edit <name> key=value ...    title, description, model, provider, persona,
                                    section, avatar, skills=a,b, permission=readonly
  /bot hide <name> | /bot unhide <name>
  /bot rm <name>                    archive a bot (chat is kept under bots/archived)
  /bot history <name> [n] | /bot clear <name>
  /bot reload                       re-read bots.json from disk
  /bot dm <name> <text>             one private message, reply printed now
  /bot room list | /bot room new <room> <bot> <bot> ...
  /bot room use <room> | /bot room off | /bot room show <room> [n]
  /bot room add|remove <room> <bot> | /bot room rm <room>
  /bot routine add <bot> <when> <prompt...>   when: 'every 30m', 'daily 09:00'
  /bot routine list | /bot routine rm <name-or-id>
"""

_BOOL_FLAGS = {"readonly", "hidden"}
_VALUE_FLAGS = {
    "title",
    "desc",
    "description",
    "model",
    "provider",
    "persona",
    "skills",
    "section",
    "avatar",
    "permission",
}


def _parse_flags(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    positional: list[str] = []
    flags: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            name, has_inline, inline = token[2:].partition("=")
            if name in _BOOL_FLAGS:
                flags[name] = inline if has_inline else "true"
                index += 1
                continue
            if name in _VALUE_FLAGS:
                if has_inline:
                    flags[name] = inline
                    index += 1
                    continue
                if index + 1 >= len(tokens):
                    raise ValueError(f"--{name} needs a value")
                flags[name] = tokens[index + 1]
                index += 2
                continue
            raise ValueError(f"unknown flag --{name}")
        positional.append(token)
        index += 1
    return positional, flags


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _profile_text(mode: BotMode, profile: BotProfile) -> str:
    lines = [
        f"{profile.face} {profile.handle}  ({profile.name})",
        f"  title:       {profile.title or '-'}",
        f"  description: {profile.description or '-'}",
        f"  model:       {profile.model or '(session model)'}",
        f"  provider:    {profile.provider or '(active provider)'}",
        f"  section:     {profile.section or '-'}",
        f"  permission:  {profile.permission}",
        f"  skills:      {', '.join(profile.skills) if profile.skills else '-'}",
        f"  chat:        {len(mode.history(profile.name))} message(s)",
        f"  inbox:       {len(mode.inbox(profile.name))} pending",
    ]
    if profile.persona:
        lines.append(f"  persona:     {profile.persona[:300]}")
    return "\n".join(lines)


class BotCommand(SlashCommand):
    name = "bot"
    description = "Bot mode: named agents, group rooms and routines"
    aliases = ["bots", "botmode"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        mode = get_bot_mode(ctx.app_state)
        try:
            tokens = shlex.split(ctx.args)
        except ValueError as exc:
            return CommandResult(success=False, message=f"Error: {exc}")
        if not tokens:
            return CommandResult(message=mode.roster_text())
        head = tokens[0].lower()
        rest = tokens[1:]

        try:
            if head in ("list", "ls"):
                include_hidden = any(item in ("all", "--all") for item in rest)
                return CommandResult(message=mode.roster_text(include_hidden=include_hidden))
            if head == "reload":
                mode.load()
                return CommandResult(
                    message=f"Reloaded the roster from {mode.root} ({len(mode.list_bots(include_hidden=True))} bot(s))."
                )
            if head in ("help", "?"):
                return CommandResult(message=USAGE)
            if head == "new":
                return self._new(mode, rest)
            if head in ("use", "chat", "on"):
                return self._use(mode, rest)
            if head in ("off", "exit", "quit"):
                mode.deactivate()
                return CommandResult(message="Bot mode off; normal agent restored.")
            if head == "show":
                return self._show(mode, rest)
            if head == "edit":
                return self._edit(mode, rest)
            if head == "hide":
                return self._hide(mode, rest, True)
            if head == "unhide":
                return self._hide(mode, rest, False)
            if head in ("rm", "remove", "delete"):
                return self._remove(mode, rest)
            if head == "history":
                return self._history(mode, rest)
            if head == "clear":
                return self._clear(mode, rest)
            if head == "dm":
                return await self._dm(mode, rest)
            if head in ("room", "rooms", "group"):
                return await self._room(mode, rest)
            if head == "routine":
                return self._routine(ctx, mode, rest)
        except ValueError as exc:
            return CommandResult(success=False, message=f"Error: {exc}")

        return CommandResult(
            success=False,
            message=f"Unknown /bot subcommand '{head}'.\n{USAGE}",
        )

    # -- roster ------------------------------------------------------------

    def _new(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot new <name> [--title T] [--desc D] ...")
        positional, flags = _parse_flags(tokens)
        if not positional:
            raise ValueError("a bot needs a name")
        name = positional[0]
        title = flags.get("title", " ".join(positional[1:]))
        permission = (
            "readonly" if _truthy(flags.get("readonly", "")) else flags.get("permission", "auto")
        )
        skills = [item for item in flags.get("skills", "").split(",") if item.strip()]
        profile = mode.create_bot(
            name=name,
            title=title,
            description=flags.get("desc", flags.get("description", "")),
            model=flags.get("model", ""),
            provider=flags.get("provider", ""),
            persona=flags.get("persona", ""),
            skills=skills,
            avatar=flags.get("avatar", ""),
            section=flags.get("section", ""),
            permission=permission,
        )
        return CommandResult(
            message=(
                f"Created {profile.face} {profile.handle}.\n"
                f"Talk to it with /bot use {profile.name}, or send it a one-off message "
                f"with /bot dm {profile.name} <text>."
            )
        )

    def _use(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot use <name>")
        profile = mode.activate_bot(tokens[0])
        return CommandResult(
            message=(
                f"Now talking to {profile.face} {profile.handle}. "
                "Plain messages go to this bot; /bot off restores the normal agent."
            )
        )

    def _show(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot show <name>")
        return CommandResult(message=_profile_text(mode, mode.require_bot(tokens[0])))

    def _edit(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot edit <name> key=value ...")
        profile = mode.require_bot(tokens[0])
        changes: dict[str, object] = {}
        for token in tokens[1:]:
            if "=" not in token:
                raise ValueError(f"expected key=value, got '{token}'")
            key, value = token.split("=", 1)
            key = key.strip().lower()
            if key == "desc":
                key = "description"
            if key == "skills":
                changes[key] = [item for item in value.split(",") if item.strip()]
            elif key == "hidden":
                changes[key] = _truthy(value)
            elif key == "permission":
                if value not in ("auto", "readonly"):
                    raise ValueError("permission must be auto or readonly")
                changes[key] = value
            else:
                changes[key] = value
        if not changes:
            raise ValueError("nothing to change")
        profile = mode.update_bot(profile.name, **changes)
        return CommandResult(message=f"Updated {profile.handle}.\n{_profile_text(mode, profile)}")

    def _hide(self, mode: BotMode, tokens: list[str], hidden: bool) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot hide <name> | /bot unhide <name>")
        profile = mode.hide_bot(tokens[0], hidden=hidden)
        state = "hidden" if hidden else "visible"
        return CommandResult(message=f"{profile.handle} is now {state}.")

    def _remove(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot rm <name>")
        profile = mode.require_bot(tokens[0])
        archived = mode.remove_bot(profile.name)
        where = f" Chat archived at {archived}." if archived else ""
        return CommandResult(message=f"Removed {profile.handle} from the roster.{where}")

    def _history(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot history <name> [n]")
        limit = 12
        if len(tokens) > 1 and tokens[1].isdigit():
            limit = max(1, min(100, int(tokens[1])))
        return CommandResult(message=mode.history_text(tokens[0], limit=limit))

    def _clear(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens:
            raise ValueError("usage: /bot clear <name>")
        profile = mode.require_bot(tokens[0])
        archived = mode.clear_history(profile.name)
        where = f" Archived to {archived}." if archived else " There was no chat to archive."
        return CommandResult(message=f"Started a fresh chat with {profile.handle}.{where}")

    async def _dm(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if len(tokens) < 2:
            raise ValueError("usage: /bot dm <name> <text>")
        profile = mode.require_bot(tokens[0])
        text = " ".join(tokens[1:])
        reply = await mode.ask(profile.name, text)
        body = reply or "(no reply: the bot chose to stay silent)"
        return CommandResult(message=f"{profile.face} {profile.handle}:\n{body}")

    # -- rooms -------------------------------------------------------------

    async def _room(self, mode: BotMode, tokens: list[str]) -> CommandResult:
        if not tokens or tokens[0] in ("list", "ls"):
            return CommandResult(message=mode.rooms_text())
        action = tokens[0].lower()
        rest = tokens[1:]

        if action == "new":
            if len(rest) < 3:
                raise ValueError(
                    f"usage: /bot room new <room> <bot> <bot> ... (up to {MAX_GROUP_MEMBERS})"
                )
            room = mode.create_room(rest[0], rest[1:])
            return CommandResult(
                message=(
                    f"Created room {room.handle} with "
                    + ", ".join("@" + slug(name) for name in room.members)
                    + f". Enter it with /bot room use {room.name}."
                )
            )
        if action == "use":
            if not rest:
                raise ValueError("usage: /bot room use <room>")
            room = mode.activate_room(rest[0])
            return CommandResult(
                message=(
                    f"Now in room {room.handle} with "
                    + ", ".join("@" + slug(name) for name in room.members)
                    + ". Plain messages go to the room; /bot off leaves."
                )
            )
        if action == "off":
            mode.deactivate()
            return CommandResult(message="Left the room; normal agent restored.")
        if action in ("show", "log"):
            if not rest:
                raise ValueError("usage: /bot room show <room> [n]")
            limit = 20
            if len(rest) > 1 and rest[1].isdigit():
                limit = max(1, min(200, int(rest[1])))
            return CommandResult(message=mode.room_log_text(rest[0], limit=limit))
        if action in ("add", "remove", "rm-member"):
            if len(rest) < 2:
                raise ValueError("usage: /bot room add|remove <room> <bot>")
            room = mode.require_room(rest[0])
            profile = mode.require_bot(rest[1])
            if action == "add":
                if profile.name in room.members:
                    return CommandResult(message=f"{profile.handle} is already in {room.handle}.")
                if len(room.members) >= MAX_GROUP_MEMBERS:
                    raise ValueError(f"a room holds at most {MAX_GROUP_MEMBERS} bots")
                room.members.append(profile.name)
                mode.save_room(room)
                return CommandResult(message=f"Added {profile.handle} to {room.handle}.")
            if profile.name not in room.members:
                return CommandResult(message=f"{profile.handle} is not in {room.handle}.")
            if len(room.members) <= 2:
                raise ValueError("a room needs at least two bots; remove the room instead")
            room.members.remove(profile.name)
            mode.save_room(room)
            return CommandResult(message=f"Removed {profile.handle} from {room.handle}.")
        if action in ("rm", "remove-room", "delete"):
            if not rest:
                raise ValueError("usage: /bot room rm <room>")
            room = mode.require_room(rest[0])
            archived = mode.remove_room(room.name)
            where = f" Log archived at {archived}." if archived else ""
            return CommandResult(message=f"Removed room {room.handle}.{where}")

        raise ValueError(f"unknown room action '{action}'; try /bot room list")

    # -- routines ----------------------------------------------------------

    def _routine(self, ctx: CommandContext, mode: BotMode, tokens: list[str]) -> CommandResult:
        scheduler = get_scheduler(ctx.app_state)
        action = tokens[0].lower() if tokens else "list"
        rest = tokens[1:]

        if action in ("list", "ls"):
            rows = [entry for entry in scheduler.entries if BotMode.routine_bot(entry.name)]
            if not rows:
                return CommandResult(message="No bot routines yet.")
            return CommandResult(
                message="Bot routines\n" + "\n".join(entry.describe() for entry in rows)
            )
        if action == "add":
            if len(rest) < 3:
                raise ValueError(
                    "usage: /bot routine add <bot> <when> <prompt...>  "
                    "(when: 'every 30m', 'daily 09:00', '2026-11-12T08:30')"
                )
            profile = mode.require_bot(rest[0])
            when = rest[1]
            prompt = " ".join(rest[2:])
            name = BotMode.routine_name(profile.name, prompt[:40])
            entry = scheduler.add(name=name, when=when, prompt=prompt)
            next_at = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.next_run))
                if entry.next_run
                else "-"
            )
            return CommandResult(
                message=(
                    f"Routine {entry.id} for {profile.handle} runs {entry.when}; "
                    f"next {next_at}. Results land in that bot's chat. "
                    f"Remove with /bot routine rm {entry.id}."
                )
            )
        if action in ("rm", "remove", "cancel"):
            if not rest:
                raise ValueError("usage: /bot routine rm <name-or-id>")
            match = next(
                (
                    entry
                    for entry in scheduler.entries
                    if BotMode.routine_bot(entry.name)
                    and (entry.id == rest[0] or entry.name == rest[0])
                ),
                None,
            )
            if match is None:
                raise ValueError(f"no bot routine matching '{rest[0]}'")
            scheduler.cancel(match.id)
            return CommandResult(message=f"Removed routine {match.id}.")

        raise ValueError(f"unknown routine action '{action}'; try /bot routine list")


__all__ = ["BotCommand"]
