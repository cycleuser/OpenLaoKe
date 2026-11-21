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
    TOGGLE_THINKING = "toggle_thinking"
    LANG_PICKER = "lang_picker"


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

    @property
    def is_toggle_thinking(self) -> bool:
        return self.action == PromptAction.TOGGLE_THINKING

    @property
    def is_lang_picker(self) -> bool:
        return self.action == PromptAction.LANG_PICKER


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


_PICKER_ROWS = 16


def _collect_all_models(config: Any | None = None) -> list[dict[str, Any]]:
    from openlaoke.utils.config import load_config

    config = config or load_config()
    providers = config.providers.providers
    active_provider = config.providers.active_provider
    active_model = config.providers.active_model
    if active_provider in providers and not active_model:
        active_model = providers[active_provider].get_default_model()

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pname, provider in providers.items():
        if not getattr(provider, "enabled", True) or not provider.is_ready():
            continue
        models: list[str] = []
        for model in [*provider.models, provider.get_default_model()]:
            if model and model not in models:
                models.append(model)
        if pname == active_provider and active_model and active_model not in models:
            models.append(active_model)
        for model in models:
            display = f"{pname}/{model}"
            if display in seen:
                continue
            seen.add(display)
            entries.append(
                {
                    "provider": pname,
                    "model": model,
                    "display": display,
                    "active": pname == active_provider and model == active_model,
                }
            )

    entries.sort(
        key=lambda entry: (
            0 if entry["active"] else 1,
            str(entry["provider"]).lower(),
            str(entry["model"]).lower(),
        )
    )
    return entries


def _build_model_picker_app(
    entries: list[dict[str, Any]],
    *,
    input: Any = None,
    output: Any = None,
) -> Any:
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import Frame, TextArea

    selected = [0]
    active_display = next(
        (entry["display"] for entry in entries if entry["active"]),
        entries[0]["display"] if entries else "",
    )

    filter_field = TextArea(
        height=1,
        prompt="Filter: ",
        multiline=False,
        style="class:filter",
        name="filter",
    )

    def visible() -> list[dict[str, Any]]:
        query = filter_field.text.strip().lower()
        if not query:
            return entries
        return [entry for entry in entries if query in entry["display"].lower()]

    def on_filter_changed(_event: Any = None) -> None:
        selected[0] = 0

    filter_field.buffer.on_text_changed += on_filter_changed

    def render_header() -> list[tuple[str, str]]:
        return [
            ("class:title", " Model Picker\n"),
            (
                "class:hint",
                f" ↑/↓ select · Enter confirm · Esc cancel · type to filter · {len(visible())} shown\n",
            ),
        ]

    def render_rows() -> list[tuple[str, str]]:
        rows = visible()
        if not rows:
            return [("class:hint", "  (no matching models)\n")]
        selected[0] = max(0, min(selected[0], len(rows) - 1))
        start = max(0, selected[0] - _PICKER_ROWS // 2)
        start = min(start, max(0, len(rows) - _PICKER_ROWS))
        end = min(len(rows), start + _PICKER_ROWS)
        text: list[tuple[str, str]] = []
        if start > 0:
            text.append(("class:hint", f"  ↑ {start} more\n"))
        for index in range(start, end):
            entry = rows[index]
            marker = "*" if entry["active"] else " "
            if index == selected[0]:
                style = "class:selected"
            elif entry["display"] == active_display:
                style = "class:active"
            else:
                style = "class:row"
            text.append((style, f" {marker} {entry['display']}\n"))
        if end < len(rows):
            text.append(("class:hint", f"  ↓ {len(rows) - end} more\n"))
        return text

    def move(delta: int) -> None:
        rows = visible()
        if rows:
            selected[0] = (selected[0] + delta) % len(rows)

    kb = KeyBindings()

    @kb.add("up", eager=True)
    @kb.add("c-p", eager=True)
    def _up(event: Any) -> None:
        move(-1)

    @kb.add("down", eager=True)
    @kb.add("c-n", eager=True)
    def _down(event: Any) -> None:
        move(1)

    @kb.add("pageup", eager=True)
    def _page_up(event: Any) -> None:
        move(-_PICKER_ROWS)

    @kb.add("pagedown", eager=True)
    def _page_down(event: Any) -> None:
        move(_PICKER_ROWS)

    @kb.add("home", eager=True)
    def _home(event: Any) -> None:
        selected[0] = 0

    @kb.add("end", eager=True)
    def _end(event: Any) -> None:
        selected[0] = max(0, len(visible()) - 1)

    @kb.add("enter", eager=True)
    def _accept(event: Any) -> None:
        rows = visible()
        if not rows:
            event.app.exit(result=None)
            return
        selected[0] = max(0, min(selected[0], len(rows) - 1))
        event.app.exit(result=rows[selected[0]]["display"])

    @kb.add("escape", eager=True)
    @kb.add("c-c", eager=True)
    def _cancel(event: Any) -> None:
        event.app.exit(result=None)

    body = HSplit(
        [
            Window(FormattedTextControl(render_header), height=2),
            filter_field,
            Frame(
                Window(FormattedTextControl(render_rows), height=_PICKER_ROWS + 4),
                title="Models",
            ),
        ]
    )
    return Application(
        layout=Layout(body, focused_element=filter_field),
        key_bindings=kb,
        style=Style.from_dict(
            {
                "title": "bold ansicyan",
                "hint": "ansibrightblack",
                "filter": "ansicyan",
                "row": "",
                "active": "ansigreen",
                "selected": "bold reverse ansigreen",
            }
        ),
        full_screen=True,
        mouse_support=False,
        input=input,
        output=output,
    )


async def _run_model_picker_text(entries: list[dict[str, Any]]) -> str | None:
    import asyncio

    from rich.console import Console

    console = Console()
    console.print()
    console.rule("[bold cyan]Model Picker[/] (number or name, Ctrl+C to cancel)")
    for i, entry in enumerate(entries, 1):
        marker = "*" if entry["active"] else " "
        console.print(f"  [{marker}] [{i:2d}] {entry['display']}")
    console.print()
    try:
        choice = (await asyncio.to_thread(input, "  Select > ")).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not choice:
        return entries[0]["display"]
    if choice.isdigit():
        index = int(choice) - 1
        return entries[index]["display"] if 0 <= index < len(entries) else None
    lowered = choice.lower()
    for entry in entries:
        if lowered in entry["display"].lower():
            return entry["display"]
    return None


async def run_model_picker_async() -> str | None:
    from openlaoke.types.providers import probe_local_providers
    from openlaoke.utils.config import load_config

    config = load_config()
    await probe_local_providers(config.providers.providers)
    entries = _collect_all_models(config)
    if not entries:
        return None
    try:
        app = _build_model_picker_app(entries)
        result = await app.run_async()
        return str(result) if result else None
    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        return await _run_model_picker_text(entries)


async def run_lang_picker_async(current_lang: str = "en") -> str | None:
    """Show language picker and return selected language code."""
    from openlaoke.core.i18n import SUPPORTED_LANGUAGES, get_tui_text

    languages = [(code, name) for code, name in SUPPORTED_LANGUAGES.items()]
    if not languages:
        return None

    try:
        from rich.console import Console

        console = Console()
        console.print()
        console.rule(
            f"[bold cyan]{get_tui_text('lang_picker_title', current_lang)}[/] "
            f"({get_tui_text('lang_picker_hint', current_lang)})"
        )
        for i, (code, name) in enumerate(languages, 1):
            marker = "*" if code == current_lang else " "
            console.print(f"  [{marker}] [{i:2d}] {name} ({code})")
        console.print()

        choice = input(f"  {get_tui_text('select_language', current_lang)} > ").strip()

        if not choice:
            return None

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(languages):
                return languages[idx][0]
            return None

        for code, name in languages:
            if choice.lower() == code.lower() or choice.lower() in name.lower():
                return code

        return None

    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        return None


class PromptSessionManager:
    def __init__(self, *, multiline: bool = False) -> None:
        self._multiline = multiline
        self._picker_requested = False
        self._toggle_thinking_requested = False
        self._lang_picker_requested = False
        self._session: PromptSession | None = None

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()
        manager = self

        @kb.add("c-p")
        def _ctrl_p(event: Any) -> None:
            manager._picker_requested = True
            event.app.exit(exception=EOFError())

        @kb.add("c-g")
        def _ctrl_g(event: Any) -> None:
            manager._toggle_thinking_requested = True
            event.app.exit(exception=EOFError())

        @kb.add("c-l")
        def _ctrl_l(event: Any) -> None:
            manager._lang_picker_requested = True
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
                mouse_support=False,
                history=FileHistory(str(HISTORY_FILE)),
                enable_history_search=True,
                key_bindings=self._build_keybindings(),
                multiline=self._multiline,
                prompt_continuation="... ",
            )
        return self._session

    async def get_user_input(self) -> PromptResult:
        self._picker_requested = False
        self._toggle_thinking_requested = False
        self._lang_picker_requested = False
        session = self.get_session()

        prompt_text = "OpenLaoKe: "
        try:
            result = await session.prompt_async(prompt_text)
            if self._picker_requested:
                return PromptResult(action=PromptAction.PICKER)
            if self._lang_picker_requested:
                return PromptResult(action=PromptAction.LANG_PICKER)
            text = result.strip() if result else ""
            if not text:
                return PromptResult(action=PromptAction.TEXT, text="")
            return PromptResult(action=PromptAction.TEXT, text=text)
        except KeyboardInterrupt:
            return PromptResult(action=PromptAction.EXIT)
        except EOFError:
            if self._picker_requested:
                return PromptResult(action=PromptAction.PICKER)
            if self._toggle_thinking_requested:
                return PromptResult(action=PromptAction.TOGGLE_THINKING)
            if self._lang_picker_requested:
                return PromptResult(action=PromptAction.LANG_PICKER)
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
