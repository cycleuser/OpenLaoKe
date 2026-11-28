"""Bot mode: a roster of named agents with their own chats, models and rooms.

A bot is a small, persistent profile: a name, a title, a role description, an
optional model and a standing persona. Each bot owns one canonical chat that
survives restarts. Bots can message each other through an inbox, and several
bots can share a room where a user message starts a short, serial discussion.

What is deliberately small:

* No daemon and no new process. A bot turn runs through the same
  :func:`run_loop` the rest of OpenLaoKe uses, with the bot's own system prompt
  and its own message list.
* Bot-to-bot delivery is a JSON inbox. ``MessageAgent`` queues a message and
  returns; the receiving bot runs on the next drain, which the REPL performs
  after each user turn.
* A room is a bounded discussion: at most three rounds and ten replies per
  user message. Bots address teammates as ``@name``, address ``@user`` to stop
  and ask, or answer ``[SILENT]`` to pass.

Storage lives under ``~/.openlaoke/bots``::

    bots.json                     roster
    <bot>/chat.json               canonical chat
    <bot>/inbox.json              queued messages from other bots
    rooms/<room>/room.json        members and the shared log
    rooms/<room>/chats/<bot>.json each member's own view of the room
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
from typing import Any

BOTS_ROOT = os.path.join(os.path.expanduser("~"), ".openlaoke", "bots")
MAX_BOTS = 24
MAX_GROUP_MEMBERS = 6
MAX_GROUP_ROUNDS = 3
MAX_GROUP_MESSAGES = 10
MAX_CHAT_MESSAGES = 400
MAX_INBOX = 100
MAX_NAME = 40

SILENT_TOKENS = frozenset({"[SILENT]", "SILENT", "NO_REPLY", "[NO_REPLY]", "[NO REPLY]"})
USER_HANDLES = frozenset({"user", "human", "你", "用户"})

CURRENT_BOT: ContextVar[str] = ContextVar("openlaoke_bot", default="")
CURRENT_ROOM: ContextVar[str] = ContextVar("openlaoke_bot_room", default="")

_AVATARS = ("🦊", "🐼", "🦉", "🐙", "🦁", "🐧", "🐝", "🦄", "🐳", "🦖", "🐨", "🐸")

_AT = re.compile(r"@([^\s@,，。;；:：!！?？、()（）\[\]【】]+)")


def slug(name: str) -> str:
    """A filesystem- and handle-safe form of a bot or room name."""
    cleaned = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", name.strip().lower())
    return cleaned.strip("-")[:MAX_NAME] or "bot"


def avatar_for(name: str) -> str:
    total = sum(name.encode("utf-8"))
    return _AVATARS[total % len(_AVATARS)]


def parse_mentions(text: str) -> list[str]:
    """Handles mentioned in ``text``, deduplicated, without stray punctuation."""
    seen: list[str] = []
    for match in _AT.finditer(text or ""):
        handle = match.group(1).strip("-_`'\".,;:!?")
        if handle and handle not in seen:
            seen.append(handle)
    return seen


@dataclass
class BotProfile:
    """One named agent in the roster."""

    name: str
    title: str = ""
    description: str = ""
    model: str = ""
    provider: str = ""
    persona: str = ""
    skills: list[str] = field(default_factory=list)
    avatar: str = ""
    section: str = ""
    hidden: bool = False
    permission: str = "auto"  # auto | readonly
    created_at: float = 0.0

    @property
    def handle(self) -> str:
        return "@" + slug(self.name)

    @property
    def face(self) -> str:
        return self.avatar or avatar_for(self.name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BotProfile:
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in known})

    def describe(self) -> str:
        role = self.title or self.description or "no role set"
        model = self.model or "(session model)"
        flags = []
        if self.hidden:
            flags.append("hidden")
        if self.permission == "readonly":
            flags.append("readonly")
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        return f"{self.face} {self.handle:<16} {role[:34]:<34} {model}{suffix}"


@dataclass
class RoomTurn:
    member: str
    text: str
    round: int = 1


@dataclass
class Room:
    name: str
    members: list[str] = field(default_factory=list)
    log: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    needs_user: bool = False

    @property
    def handle(self) -> str:
        return "#" + slug(self.name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Room:
        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in known})

    def describe(self) -> str:
        members = ", ".join("@" + slug(name) for name in self.members) or "(empty)"
        marker = "  needs you" if self.needs_user else ""
        return f"{self.handle:<16} {len(self.members)} bot(s): {members}{marker}"


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: str, payload: Any) -> None:
    from openlaoke.utils.atomic_write import write_json_atomic

    write_json_atomic(path, payload, indent=1)


def _merge_consecutive(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-role neighbours so strict providers accept the history."""
    merged: list[dict[str, Any]] = []
    for message in messages:
        copy = dict(message)
        if not merged:
            merged.append(copy)
            continue
        previous = merged[-1]
        same_user = previous.get("role") == copy.get("role") == "user"
        same_assistant = (
            previous.get("role") == copy.get("role") == "assistant"
            and not previous.get("tool_calls")
            and not copy.get("tool_calls")
        )
        if same_user or same_assistant:
            previous["content"] = (
                str(previous.get("content") or "") + "\n\n" + str(copy.get("content") or "")
            ).strip()
        else:
            merged.append(copy)
    return merged


def _trim(messages: list[dict[str, Any]], limit: int = MAX_CHAT_MESSAGES) -> list[dict[str, Any]]:
    """Drop whole leading turns, never a lone tool result without its call."""
    if len(messages) <= limit:
        return messages
    cut = 0
    for index in range(len(messages) - limit, len(messages)):
        if messages[index].get("role") == "user":
            cut = index
            break
    return messages[cut:] if cut else messages[-limit:]


class BotMode:
    """Roster, chats, rooms and inboxes for one OpenLaoKe session."""

    def __init__(
        self,
        app_state: Any,
        root: str | None = None,
        client_factory: Callable[[Any], Any] | None = None,
        max_iterations: int = 40,
    ) -> None:
        self.app_state = app_state
        self.root = os.path.abspath(os.path.expanduser(root or BOTS_ROOT))
        self.active_bot: str = ""
        self.active_room: str = ""
        self.max_iterations = max_iterations
        self._client_factory = client_factory
        self._locks: dict[str, asyncio.Lock] = {}
        self._registry_obj: Any = None
        self._bots: dict[str, BotProfile] = {}
        self.load()

    # -- roster ------------------------------------------------------------

    def load(self) -> None:
        payload = _read_json(os.path.join(self.root, "bots.json"), {})
        raw = payload.get("bots") if isinstance(payload, dict) else payload
        self._bots = {}
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            try:
                profile = BotProfile.from_dict(item)
            except (TypeError, ValueError):
                # A roster entry without a name is not worth losing the roster.
                continue
            if profile.name and slug(profile.name) not in self._bots:
                self._bots[slug(profile.name)] = profile
        if self.active_bot and self.active_bot not in self._bots:
            self.active_bot = ""

    def save(self) -> None:
        _write_json(
            os.path.join(self.root, "bots.json"),
            {
                "version": 1,
                "bots": [profile.to_dict() for profile in self._bots.values()],
            },
        )

    def create_bot(
        self,
        name: str,
        title: str = "",
        description: str = "",
        model: str = "",
        provider: str = "",
        persona: str = "",
        skills: list[str] | None = None,
        avatar: str = "",
        section: str = "",
        permission: str = "auto",
    ) -> BotProfile:
        cleaned = (name or "").strip().lstrip("@")
        if not cleaned:
            raise ValueError("a bot needs a name")
        if len(cleaned) > MAX_NAME:
            raise ValueError(f"name is longer than {MAX_NAME} characters")
        if slug(cleaned) in self._bots:
            raise ValueError(f"a bot named '{cleaned}' already exists")
        if len(self._bots) >= MAX_BOTS:
            raise ValueError(f"the roster is full at {MAX_BOTS} bots")
        if permission not in ("auto", "readonly"):
            raise ValueError("permission must be 'auto' or 'readonly'")
        profile = BotProfile(
            name=cleaned,
            title=title.strip(),
            description=description.strip(),
            model=model.strip(),
            provider=provider.strip(),
            persona=persona.strip(),
            skills=[skill.strip() for skill in (skills or []) if skill.strip()],
            avatar=avatar.strip(),
            section=section.strip(),
            permission=permission,
            created_at=time.time(),
        )
        self._bots[slug(cleaned)] = profile
        self.save()
        return profile

    def get_bot(self, handle: str) -> BotProfile | None:
        key = slug(handle.strip().lstrip("@"))
        profile = self._bots.get(key)
        if profile is not None:
            return profile
        for candidate in self._bots.values():
            if slug(candidate.title) == key and candidate.title:
                return candidate
        return None

    def require_bot(self, handle: str) -> BotProfile:
        profile = self.get_bot(handle)
        if profile is None:
            raise ValueError(f"no bot named '@{slug(handle)}'")
        return profile

    def list_bots(self, include_hidden: bool = False) -> list[BotProfile]:
        return [profile for profile in self._bots.values() if include_hidden or not profile.hidden]

    def update_bot(self, handle: str, **fields: Any) -> BotProfile:
        profile = self.require_bot(handle)
        allowed = {
            "title",
            "description",
            "model",
            "provider",
            "persona",
            "avatar",
            "section",
            "permission",
            "hidden",
            "skills",
        }
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"cannot set '{key}'")
            setattr(profile, key, value)
        self.save()
        return profile

    def hide_bot(self, handle: str, hidden: bool = True) -> BotProfile:
        return self.update_bot(handle, hidden=hidden)

    def remove_bot(self, handle: str) -> str:
        """Drop a bot from the roster; its chat is archived, never deleted."""
        profile = self.require_bot(handle)
        key = slug(profile.name)
        archived = ""
        source = os.path.join(self.root, key)
        if os.path.isdir(source):
            target = os.path.join(self.root, "archived", f"{key}-{int(time.time())}")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(source, target)
            archived = target
        self._bots.pop(key, None)
        self.save()
        for room in self.list_rooms():
            if profile.name in room.members:
                room.members.remove(profile.name)
                self.save_room(room)
        if self.active_bot == key:
            self.active_bot = ""
        return archived

    def roster_text(self, include_hidden: bool = False) -> str:
        bots = self.list_bots(include_hidden=include_hidden)
        if not bots:
            return (
                "No bots yet. Create one with /bot new <name> [title], "
                "then /bot use <name> to talk to it."
            )
        lines = [f"Bots ({len(bots)})"]
        sections: dict[str, list[BotProfile]] = {}
        for profile in bots:
            sections.setdefault(profile.section, []).append(profile)
        for section in sorted(sections):
            if section:
                lines.append(f"  [{section}]")
            for profile in sections[section]:
                active = ""
                if self.active_bot and slug(profile.name) == self.active_bot:
                    active = "  <- active"
                lines.append(f"  {profile.describe()}{active}")
        if self.active_room:
            lines.append(f"Active room: #{self.active_room}")
        elif self.active_bot:
            lines.append(f"Active bot: @{self.active_bot} (send a message to talk to it)")
        else:
            lines.append("Bot mode is off; /bot use <name> or /bot room use <room> to enter.")
        return "\n".join(lines)

    # -- chats -------------------------------------------------------------

    def _bot_dir(self, profile: BotProfile) -> str:
        return os.path.join(self.root, slug(profile.name))

    def _chat_path(self, profile: BotProfile) -> str:
        return os.path.join(self._bot_dir(profile), "chat.json")

    def history(self, handle: str) -> list[dict[str, Any]]:
        profile = self.require_bot(handle)
        payload = _read_json(self._chat_path(profile), {})
        raw = payload.get("messages") if isinstance(payload, dict) else []
        return [item for item in raw or [] if isinstance(item, dict)]

    def save_history(self, handle: str, messages: list[dict[str, Any]]) -> None:
        profile = self.require_bot(handle)
        _write_json(
            self._chat_path(profile),
            {
                "version": 1,
                "bot": profile.name,
                "updated_at": time.time(),
                "messages": _trim(messages),
            },
        )

    def clear_history(self, handle: str) -> str:
        """Archive the canonical chat and start a fresh one."""
        profile = self.require_bot(handle)
        source = self._chat_path(profile)
        archived = ""
        if os.path.exists(source):
            archived = source.replace(".json", f".{int(time.time())}.json")
            os.replace(source, archived)
        return archived

    def history_text(self, handle: str, limit: int = 12) -> str:
        messages = self.history(handle)
        if not messages:
            return f"No messages with @{slug(handle)} yet."
        rows: list[str] = []
        for message in messages[-limit:]:
            role = message.get("role")
            content = str(message.get("content") or "").strip()
            if role not in ("user", "assistant") or not content:
                continue
            label = "you" if role == "user" else "@" + slug(handle)
            rows.append(f"{label}: {content[:300]}")
        return "\n".join(rows) or f"No displayable messages with @{slug(handle)}."

    # -- activation --------------------------------------------------------

    def activate_bot(self, handle: str) -> BotProfile:
        profile = self.require_bot(handle)
        self.active_bot = slug(profile.name)
        self.active_room = ""
        return profile

    def activate_room(self, name: str) -> Room:
        room = self.require_room(name)
        self.active_room = slug(room.name)
        self.active_bot = ""
        return room

    def deactivate(self) -> None:
        self.active_bot = ""
        self.active_room = ""

    @property
    def enabled(self) -> bool:
        return bool(self.active_bot or self.active_room)

    # -- prompts -----------------------------------------------------------

    def system_prompt(self, profile: BotProfile) -> str:
        from openlaoke.core.system_prompt import build_system_prompt

        base = build_system_prompt(self.app_state, [])
        base = base.replace(
            "You are OpenLaoKe, a coding agent running in the terminal.",
            f"You are {profile.name} ({profile.handle}), a named bot inside OpenLaoKe, "
            "a coding agent running in the terminal.",
            1,
        )
        parts = [base]
        identity = [
            "",
            "## Your bot identity",
            f"You are **{profile.name}** ({profile.handle}), one named bot on the user's team.",
        ]
        if profile.title:
            identity.append(f"Title: {profile.title}")
        if profile.description:
            identity.append(f"Role: {profile.description}")
        if profile.permission == "readonly":
            identity.append(
                "You are a read-only bot: inspect and explain, but do not modify files or run "
                "commands that change the machine."
            )
        parts.append("\n".join(identity))

        if profile.persona:
            parts.append(f"\n## Persona and standing instructions\n{profile.persona}")

        if profile.skills:
            from openlaoke.core.skill_system import get_skill_system_prompt

            skill_prompt = get_skill_system_prompt(profile.skills)
            if skill_prompt:
                parts.append("\n## Your skills" + skill_prompt)

        teammates = [
            other
            for other in self.list_bots(include_hidden=True)
            if slug(other.name) != slug(profile.name)
        ]
        if teammates:
            rows = [
                f"- {other.handle} — {other.title or 'teammate'}"
                + (f": {other.description}" if other.description else "")
                for other in teammates
            ]
            parts.append(
                "\n## Teammates\n" + "\n".join(rows) + "\n\nMessage a teammate with "
                '`MessageAgent(target="<handle>", message="...")`. Delivery is queued; '
                "their reply arrives as a later notification. Do not forward the user's "
                "words verbatim — write your own message."
            )

        parts.append(
            "\n## Bot protocol\n"
            "- Stay in character and answer as this bot, not as the harness.\n"
            "- In a shared room, mention a teammate as @handle to hand work over, "
            "or @user when a decision needs the human.\n"
            "- If you have nothing to add, answer exactly [SILENT]; it will not be shown.\n"
            "- Keep replies short enough to read in a terminal."
        )
        return "\n".join(part for part in parts if part)

    # -- one bot turn ------------------------------------------------------

    def _make_client(self, profile: BotProfile) -> Any:
        if self._client_factory is not None:
            return self._client_factory(profile)
        from openlaoke.core.config_wizard import get_proxy_url
        from openlaoke.core.multi_provider_api import MultiProviderClient

        config = getattr(self.app_state, "multi_provider_config", None)
        if config is None or not config.is_configured():
            raise ValueError("no provider is configured; run `openlaoke --config`")
        if profile.provider:
            if profile.provider not in config.providers:
                raise ValueError(
                    f"bot {profile.handle} asks for provider '{profile.provider}' "
                    "which is not configured"
                )
            config = replace(config, active_provider=profile.provider)
        app_config = getattr(self.app_state, "app_config", None)
        proxy = get_proxy_url(app_config) if app_config is not None else None
        return MultiProviderClient(config, proxy=proxy)

    def _registry(self) -> Any:
        if self._registry_obj is not None:
            return self._registry_obj
        from openlaoke.core.tool import ToolRegistry
        from openlaoke.tools.message_agent_tool import MessageAgentTool
        from openlaoke.tools.register import register_all_tools

        registry = ToolRegistry()
        register_all_tools(registry)
        registry.register(MessageAgentTool(mode=self))
        registry.freeze()
        self._registry_obj = registry
        return registry

    def _lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def is_busy(self, handle: str) -> bool:
        profile = self.require_bot(handle)
        lock = self._locks.get("chat:" + slug(profile.name))
        return bool(lock and lock.locked())

    async def ask(
        self,
        handle: str,
        message: str,
        sender: str = "user",
        on_text: Callable[[str], None] | None = None,
        history: list[dict[str, Any]] | None = None,
        save: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> str:
        """Run one turn for a bot and return its reply (empty when silent)."""
        profile = self.require_bot(handle)
        text = (message or "").strip()
        if not text:
            return ""

        if sender and sender != "user":
            author = sender if sender.startswith("@") else "@" + slug(sender)
            text = f"Message from 🤖 {sender} ({author}):\n{text}"

        async with self._lock("chat:" + slug(profile.name)):
            messages = list(history) if history is not None else self.history(profile.name)
            messages.append({"role": "user", "content": text})
            messages = _merge_consecutive(messages)
            saver = save or (lambda items: self.save_history(profile.name, items))
            reply, failed = await self._run_turn(profile, messages, on_text=on_text)
            saver(messages)
            if failed:
                return reply
            return "" if reply.strip().upper() in SILENT_TOKENS else reply

    async def _run_turn(
        self,
        profile: BotProfile,
        messages: list[dict[str, Any]],
        on_text: Callable[[str], None] | None = None,
    ) -> tuple[str, bool]:
        from openlaoke.core.engine import STOP_ERROR, EnginePolicy, run_loop

        token = CURRENT_BOT.set(slug(profile.name))
        api: Any = None
        try:
            api = self._make_client(profile)
            registry = self._registry()
            from openlaoke.core.harness_modes import engine_kwargs, get_mode

            policy_kwargs = engine_kwargs(get_mode(getattr(self.app_state, "harness_mode", None)))
            policy_kwargs.pop("max_iterations", None)
            policy = EnginePolicy(
                **policy_kwargs,  # type: ignore[arg-type]
                max_iterations=self.max_iterations,
                tools=registry.get_all_for_prompt(),
                allow_tools=self._allowed_tools(profile),
                on_text=on_text,
            )
            model = profile.model
            if not model:
                config = getattr(self.app_state, "multi_provider_config", None)
                if config is not None and hasattr(config, "get_active_model"):
                    model = config.get_active_model()
            model = model or getattr(getattr(self.app_state, "session_config", None), "model", "")
            result = await run_loop(
                app_state=self.app_state,
                api=api,
                registry=registry,
                system_prompt=self.system_prompt(profile),
                messages=messages,
                policy=policy,
                model=model,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the bot's reply
            return f"[bot @{slug(profile.name)} error: {exc}]", True
        finally:
            CURRENT_BOT.reset(token)
            if api is not None and hasattr(api, "close"):
                with contextlib.suppress(Exception):
                    await api.close()

        if result.stop_reason == STOP_ERROR:
            return f"[bot @{slug(profile.name)} error: {result.error}]", True
        return result.text.strip(), False

    @staticmethod
    def _allowed_tools(profile: BotProfile) -> set[str] | None:
        if profile.permission != "readonly":
            return None
        return {
            "Read",
            "Grep",
            "Glob",
            "ListDirectory",
            "WebFetch",
            "WebSearch",
            "Memory",
            "Todo",
            "SessionSearch",
            "ConversationSearch",
            "InvokeSkill",
            "MessageAgent",
        }

    # -- bot-to-bot delivery ----------------------------------------------

    def _inbox_path(self, profile: BotProfile) -> str:
        return os.path.join(self._bot_dir(profile), "inbox.json")

    def enqueue(self, sender: str, target: str, text: str) -> dict[str, Any]:
        profile = self.require_bot(target)
        body = (text or "").strip()
        if not body:
            raise ValueError("a message needs some text")
        envelope = {
            "id": "m" + uuid.uuid4().hex[:12],
            "from": slug(sender.lstrip("@")) if sender else "",
            "text": body,
            "created_at": time.time(),
            "status": "pending",
            "reply": "",
        }
        payload = _read_json(self._inbox_path(profile), {})
        messages = payload.get("messages") if isinstance(payload, dict) else []
        messages = [item for item in messages or [] if isinstance(item, dict)]
        messages.append(envelope)
        messages = messages[-MAX_INBOX:]
        _write_json(
            self._inbox_path(profile),
            {"version": 1, "messages": messages},
        )
        return envelope

    def inbox(self, handle: str, status: str = "pending") -> list[dict[str, Any]]:
        profile = self.require_bot(handle)
        payload = _read_json(self._inbox_path(profile), {})
        messages = payload.get("messages") if isinstance(payload, dict) else []
        return [
            item
            for item in messages or []
            if isinstance(item, dict) and (status == "all" or item.get("status") == status)
        ]

    def _update_inbox(self, profile: BotProfile, envelope: dict[str, Any], **fields: Any) -> None:
        path = self._inbox_path(profile)
        payload = _read_json(path, {})
        messages = payload.get("messages") if isinstance(payload, dict) else []
        for item in messages or []:
            if isinstance(item, dict) and item.get("id") == envelope.get("id"):
                item.update(fields)
        _write_json(path, {"version": 1, "messages": messages})

    async def deliver(
        self, handle: str, on_text: Callable[[str], None] | None = None
    ) -> list[dict[str, Any]]:
        """Run every pending message for one bot, oldest first."""
        profile = self.require_bot(handle)
        delivered: list[dict[str, Any]] = []
        for envelope in self.inbox(profile.name):
            sender = str(envelope.get("from") or "teammate")
            reply = await self.ask(
                profile.name,
                str(envelope.get("text") or ""),
                sender=sender,
                on_text=on_text,
            )
            self._update_inbox(profile, envelope, status="delivered", reply=reply)
            delivered.append({"bot": profile.name, "from": sender, "reply": reply})
        return delivered

    async def drain(self, on_text: Callable[[str], None] | None = None) -> list[dict[str, Any]]:
        """Deliver pending messages for every bot on the roster."""
        delivered: list[dict[str, Any]] = []
        for profile in list(self._bots.values()):
            if not self.inbox(profile.name):
                continue
            delivered.extend(await self.deliver(profile.name, on_text=on_text))
        return delivered

    # -- rooms -------------------------------------------------------------

    def _rooms_dir(self) -> str:
        return os.path.join(self.root, "rooms")

    def _room_path(self, name: str) -> str:
        return os.path.join(self._rooms_dir(), slug(name), "room.json")

    def create_room(self, name: str, members: list[str]) -> Room:
        cleaned = (name or "").strip().lstrip("#")
        if not cleaned:
            raise ValueError("a room needs a name")
        if self.get_room(cleaned) is not None:
            raise ValueError(f"a room named '{cleaned}' already exists")
        resolved: list[str] = []
        for member in members:
            profile = self.require_bot(member)
            if profile.name not in resolved:
                resolved.append(profile.name)
        if len(resolved) < 2:
            raise ValueError("a room needs at least two bots")
        if len(resolved) > MAX_GROUP_MEMBERS:
            raise ValueError(f"a room holds at most {MAX_GROUP_MEMBERS} bots")
        room = Room(name=cleaned, members=resolved, created_at=time.time())
        self.save_room(room)
        return room

    def get_room(self, name: str) -> Room | None:
        direct = self._room_path(name)
        payload = _read_json(direct, None)
        if isinstance(payload, dict):
            try:
                return Room.from_dict(payload)
            except (TypeError, ValueError):
                # A room file without a name cannot be reconstructed, so this is
                # "no such room" rather than an exception out of /room.
                return None
        key = slug(name)
        for candidate in self.list_rooms():
            if slug(candidate.name) == key:
                return candidate
        return None

    def require_room(self, name: str) -> Room:
        room = self.get_room(name)
        if room is None:
            raise ValueError(f"no room named '#{slug(name)}'")
        return room

    def list_rooms(self) -> list[Room]:
        base = self._rooms_dir()
        if not os.path.isdir(base):
            return []
        rooms: list[Room] = []
        for entry in sorted(os.listdir(base)):
            payload = _read_json(os.path.join(base, entry, "room.json"), None)
            if isinstance(payload, dict):
                try:
                    rooms.append(Room.from_dict(payload))
                except (TypeError, ValueError):
                    # One unreadable room must not hide every other room.
                    continue
        return rooms

    def save_room(self, room: Room) -> None:
        _write_json(self._room_path(room.name), room.to_dict())

    def remove_room(self, name: str) -> str:
        room = self.require_room(name)
        source = self._room_path(room.name)
        archived = ""
        if os.path.exists(source):
            archived = source.replace("room.json", f"room-{int(time.time())}.json")
            os.replace(source, archived)
        if self.active_room == slug(room.name):
            self.active_room = ""
            self.active_bot = ""
        return archived

    def rooms_text(self) -> str:
        rooms = self.list_rooms()
        if not rooms:
            return "No rooms yet. Create one with /bot room new <room> <bot> <bot> ..."
        lines = [f"Rooms ({len(rooms)})"]
        for room in rooms:
            active = "  <- active" if self.active_room == slug(room.name) else ""
            lines.append(f"  {room.describe()}{active}")
        return "\n".join(lines)

    def mentioned(self, text: str, room: Room | None = None) -> list[str]:
        """Resolve handles in ``text`` to bot names (or ``user``)."""
        found: list[str] = []
        names = room.members if room is not None else [bot.name for bot in self._bots.values()]
        for handle in parse_mentions(text):
            key = slug(handle)
            if key in USER_HANDLES or key == "user":
                if "user" not in found:
                    found.append("user")
                continue
            for name in names:
                if slug(name) == key:
                    if name not in found:
                        found.append(name)
                    break
        return found

    def _room_chat_path(self, room: Room, profile: BotProfile) -> str:
        return os.path.join(
            self._rooms_dir(), slug(room.name), "chats", f"{slug(profile.name)}.json"
        )

    def room_history(self, room: Room, profile: BotProfile) -> list[dict[str, Any]]:
        payload = _read_json(self._room_chat_path(room, profile), {})
        raw = payload.get("messages") if isinstance(payload, dict) else []
        return [item for item in raw or [] if isinstance(item, dict)]

    def _save_room_history(
        self, room: Room, profile: BotProfile, messages: list[dict[str, Any]]
    ) -> None:
        _write_json(
            self._room_chat_path(room, profile),
            {
                "version": 1,
                "room": room.name,
                "bot": profile.name,
                "updated_at": time.time(),
                "messages": _trim(messages),
            },
        )

    async def room_send(
        self,
        name: str,
        message: str,
        on_text: Callable[[str], None] | None = None,
        max_rounds: int = MAX_GROUP_ROUNDS,
    ) -> list[RoomTurn]:
        """One user message, up to ``max_rounds`` serial rounds of bot replies.

        Every member speaks at most once per user message: a later round exists
        only to bring in bots named by someone in the previous round.
        """
        room = self.require_room(name)
        text = (message or "").strip()
        if not text or not room.members:
            return []
        room.needs_user = False
        room.log.append({"from": "user", "text": text, "at": time.time(), "round": 0})

        turns: list[RoomTurn] = []
        spoken: set[str] = set()
        speakers = [name for name in self.mentioned(text, room) if name != "user"]
        if not speakers:
            speakers = list(room.members)
        pending = text
        rounds = 0

        while speakers and rounds < max(1, max_rounds) and len(turns) < MAX_GROUP_MESSAGES:
            rounds += 1
            next_speakers: list[str] = []
            for speaker in speakers:
                if len(turns) >= MAX_GROUP_MESSAGES:
                    break
                profile = self.get_bot(speaker)
                if profile is None or slug(profile.name) in spoken:
                    continue
                roster = ", ".join("@" + slug(item) for item in room.members)
                content = (
                    f'[room "{room.name}" · round {rounds}/{max_rounds} · members: {roster}]\n'
                    f"{pending}"
                )
                reply = await self._room_turn(room, profile, content, on_text=on_text)
                if not reply:
                    spoken.add(slug(profile.name))
                    continue
                spoken.add(slug(profile.name))
                room.log.append(
                    {"from": profile.name, "text": reply, "at": time.time(), "round": rounds}
                )
                turns.append(RoomTurn(member=profile.name, text=reply, round=rounds))
                mentions = self.mentioned(reply, room)
                if "user" in mentions:
                    room.needs_user = True
                for mentioned in mentions:
                    if (
                        mentioned != "user"
                        and slug(mentioned) not in spoken
                        and mentioned not in next_speakers
                    ):
                        next_speakers.append(mentioned)

            pending = "\n".join(
                f"{turn.member}: {turn.text}" for turn in turns if turn.round == rounds
            )
            speakers = next_speakers
            if room.needs_user or not pending:
                break

        self.save_room(room)
        return turns

    async def _room_turn(
        self,
        room: Room,
        profile: BotProfile,
        content: str,
        on_text: Callable[[str], None] | None = None,
    ) -> str:
        history = self.room_history(room, profile)
        token = CURRENT_ROOM.set(slug(room.name))
        try:
            reply = await self.ask(
                profile.name,
                content,
                sender="user",
                on_text=on_text,
                history=history,
                save=lambda items: self._save_room_history(room, profile, items),
            )
        finally:
            CURRENT_ROOM.reset(token)
        return reply

    def room_log_text(self, name: str, limit: int = 20) -> str:
        room = self.require_room(name)
        lines = [f"#{slug(room.name)} — {', '.join('@' + slug(m) for m in room.members)}"]
        if not room.log:
            lines.append("(no messages yet)")
            return "\n".join(lines)
        for item in room.log[-limit:]:
            speaker = item.get("from") or "?"
            label = "you" if speaker == "user" else "@" + slug(speaker)
            lines.append(f"{label}: {str(item.get('text') or '')[:400]}")
        if room.needs_user:
            lines.append("(this room is waiting on you)")
        return "\n".join(lines)

    # -- routines ----------------------------------------------------------

    @staticmethod
    def routine_name(bot: str, text: str) -> str:
        return f"[bot:{slug(bot)}] {text}".strip()

    @staticmethod
    def routine_bot(name: str) -> str:
        match = re.match(r"^\[bot:([^\]]+)\]", name or "")
        return slug(match.group(1)) if match else ""


def get_bot_mode(app_state: Any, root: str | None = None) -> BotMode:
    """One BotMode per session, cached on AppState."""
    existing = getattr(app_state, "_bot_mode", None)
    if isinstance(existing, BotMode):
        return existing
    mode = BotMode(app_state, root=root)
    app_state._bot_mode = mode
    return mode


def current_bot() -> str:
    return CURRENT_BOT.get()


__all__ = [
    "BOTS_ROOT",
    "BotMode",
    "BotProfile",
    "CURRENT_BOT",
    "CURRENT_ROOM",
    "MAX_GROUP_MEMBERS",
    "MAX_GROUP_MESSAGES",
    "MAX_GROUP_ROUNDS",
    "Room",
    "RoomTurn",
    "avatar_for",
    "current_bot",
    "get_bot_mode",
    "parse_mentions",
    "slug",
]
