"""Interactive prompt input with autocomplete, model picker, and multiline support."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from openlaoke.commands.registry import get_all_commands, register_all
from openlaoke.core.skill_system import get_skill_registry, list_available_skills

HISTORY_FILE = Path.home() / ".openlaoke" / "command_history.txt"


class PromptAction(Enum):
    TEXT = "text"
    PICKER = "picker"
    EXIT = "exit"


@dataclass
class PromptResult:
    action: PromptAction = PromptAction.TEXT
    text: str = ""

    @property
    def is_picker(self) -> bool:
        return self.action == PromptAction.PICKER

    @property
    def is_exit(self) -> bool:
        return self.action == PromptAction.EXIT

    @property
    def is_text(self) -> bool:
        return self.action == PromptAction.TEXT


def _get_skill_source(path: Any) -> str:
    if not path:
        return ""
    path_str = str(path)
    if ".config/opencode" in path_str or ".opencode/" in path_str:
        return "[OpenCode]"
    if ".claude/" in path_str:
        return "[Claude]"
    if ".openlaoke/" in path_str:
        return "[Installed]"
    return ""


class OpenLaoKeCompleter(Completer):
    _options_cache: list[dict[str, str]] | None = None

    def _get_options(self) -> list[dict[str, str]]:
        if self._options_cache is not None:
            return self._options_cache

        options: list[dict[str, str]] = []
        register_all()
        seen: set[str] = set()
        for cmd in get_all_commands():
            if cmd.hidden:
                continue
            if cmd.name not in seen:
                seen.add(cmd.name)
                options.append(
                    {
                        "name": cmd.name,
                        "display": f"/{cmd.name}",
                        "description": cmd.description[:60] if cmd.description else "",
                        "type": "command",
                        "source": "",
                    }
                )
                for alias in cmd.aliases:
                    if alias not in seen:
                        seen.add(alias)
                        options.append(
                            {
                                "name": alias,
                                "display": f"/{alias}",
                                "description": f"Alias for /{cmd.name}",
                                "type": "command",
                                "source": "",
                            }
                        )

        registry = get_skill_registry()
        for skill_name in sorted(list_available_skills()):
            skill = registry.get_skill(skill_name)
            if skill:
                source = _get_skill_source(skill.path)
                desc = skill.description[:60].split("\n")[0] if skill.description else ""
                options.append(
                    {
                        "name": skill_name,
                        "display": f"/{skill_name}",
                        "description": f"{source} {desc}" if source else desc,
                        "type": "skill",
                        "source": source,
                    }
                )

        self._options_cache = options
        return options

    def get_completions(self, document: Any, complete_event: Any) -> Any:
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        search = text[1:].lower()
        all_options = self._get_options()

        seen: dict[str, dict[str, str]] = {}
        for opt in all_options:
            display = opt["display"]
            if display not in seen or (opt["type"] == "skill" and seen[display]["type"] != "skill"):
                seen[display] = opt
        unique_options = list(seen.values())

        matches: list[tuple[int, dict[str, str]]] = []
        for opt in unique_options:
            name_lower = opt["name"].lower()
            display_lower = opt["display"].lower()

            score = 0
            if name_lower.startswith(search):
                score = 100
            elif search in name_lower:
                score = 80
            elif display_lower.startswith(search):
                score = 60
            elif search in display_lower:
                score = 40
            elif self._fuzzy_match(search, name_lower):
                score = 20

            if score > 0:
                matches.append((score, opt))

        source_order = {"[OpenCode]": 0, "[Claude]": 1, "[Installed]": 2, "": 3}
        matches.sort(
            key=lambda x: (
                -x[0],
                source_order.get(x[1]["source"], 3),
                x[1]["display"],
            )
        )

        for _, opt in matches:
            meta_text = opt["description"] or ""
            yield Completion(
                opt["display"],
                start_position=-len(text),
                display=opt["display"],
                display_meta=meta_text,
            )

    def _fuzzy_match(self, query: str, text: str) -> bool:
        idx = 0
        for char in text:
            if idx < len(query) and char == query[idx]:
                idx += 1
        return idx == len(query)


class ModelPickerCompleter(Completer):
    def __init__(self, entries: list[dict[str, str]]) -> None:
        self._entries = entries

    def get_completions(self, document: Any, complete_event: Any) -> Any:
        text = document.text_before_cursor.lower()
        for i, entry in enumerate(self._entries, 1):
            display = entry["display"]
            if text and text not in display.lower():
                continue
            yield Completion(
                display,
                start_position=-len(document.text_before_cursor),
                display=f"[{i:2d}] {display}",
                display_meta=f"{entry['provider']}",
            )


def _collect_all_models() -> list[dict[str, str]]:
    from openlaoke.utils.config import load_config

    config = load_config()
    entries: list[dict[str, str]] = []

    for pname, provider in config.providers.providers.items():
        if not provider.enabled:
            continue
        if not provider.is_configured():
            continue
        for model in provider.models:
            entries.append(
                {
                    "provider": pname,
                    "model": model,
                    "display": f"{pname}/{model}",
                }
            )

    if config.providers.active_model:
        active = f"{config.providers.active_provider}/{config.providers.active_model}"
        entries.sort(key=lambda e: (0 if e["display"] == active else 1, e["display"]))
    return entries


async def run_model_picker_async() -> str | None:
    entries = _collect_all_models()
    if not entries:
        return None

    picker_style = Style.from_dict(
        {
            "prompt": "bold ansicyan",
            "completion": "ansigreen",
            "completion.selected": "bold ansigreen",
            "completion-meta": "ansibrightblack",
        }
    )

    picker_completer = ModelPickerCompleter(entries)
    picker_session = PromptSession(
        completer=picker_completer,
        style=picker_style,
        complete_while_typing=True,
    )

    try:
        from rich.console import Console

        console = Console()
        console.print()
        console.rule(
            "[bold cyan]Model Picker[/] (type to filter, Enter to select, Ctrl+C to cancel)"
        )
        for i, entry in enumerate(entries, 1):
            marker = "*" if entry["display"] == entries[0]["display"] else " "
            console.print(f"  [{marker}] [{i:2d}] {entry['display']}")
        console.print()

        choice = await picker_session.prompt_async("  Select > ")
        choice = choice.strip()

        if not choice:
            return entries[0]["display"]

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(entries):
                return entries[idx]["display"]
            return None

        for entry in entries:
            if choice.lower() in entry["display"].lower():
                return entry["display"]

        return None

    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        return None


class PromptSessionManager:
    def __init__(self, *, multiline: bool = False) -> None:
        self._multiline = multiline
        self._picker_requested = False
        self._session: PromptSession | None = None

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()
        manager = self

        @kb.add("c-p")
        def _ctrl_p(event: Any) -> None:
            manager._picker_requested = True
            event.app.exit(exception=EOFError())

        return kb

    def _build_style(self) -> Style:
        return Style.from_dict(
            {
                "prompt": "bold ansigreen",
                "completion": "ansicyan",
                "completion.selected": "bold ansicyan",
                "completion-meta": "ansibrightblack",
            }
        )

    def get_session(self) -> PromptSession:
        if self._session is None:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

            self._session = PromptSession(
                completer=OpenLaoKeCompleter(),
                style=self._build_style(),
                complete_while_typing=True,
                mouse_support=True,
                history=FileHistory(str(HISTORY_FILE)),
                enable_history_search=True,
                key_bindings=self._build_keybindings(),
                multiline=self._multiline,
                prompt_continuation="... ",
            )
        return self._session

    async def get_user_input(self) -> PromptResult:
        self._picker_requested = False
        session = self.get_session()
        try:
            result = await session.prompt_async("OpenLaoKe: ")
            if self._picker_requested:
                return PromptResult(action=PromptAction.PICKER)
            text = result.strip() if result else ""
            if not text:
                return PromptResult(action=PromptAction.TEXT, text="")
            return PromptResult(action=PromptAction.TEXT, text=text)
        except KeyboardInterrupt:
            return PromptResult(action=PromptAction.EXIT)
        except EOFError:
            return PromptResult(action=PromptAction.EXIT)


def create_prompt_session() -> PromptSession:
    manager = PromptSessionManager()
    return manager.get_session()


async def get_user_input(session: PromptSession) -> str | None:
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = PromptSessionManager()
    _fallback_manager._session = session
    result = await _fallback_manager.get_user_input()
    if result.is_picker:
        return "PICKER_TRIGGERED"
    if result.is_exit:
        return None
    return result.text if result.text else None


_fallback_manager: PromptSessionManager | None = None
