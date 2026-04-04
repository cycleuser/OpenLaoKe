"""Interactive prompt input with real-time autocomplete menu."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from openlaoke.commands.registry import get_all_commands, register_all
from openlaoke.core.skill_system import get_skill_registry, list_available_skills

# History file location
HISTORY_FILE = Path.home() / ".openlaoke" / "command_history.txt"


def _get_skill_source(path) -> str:
    """Determine skill source from path."""
    if not path:
        return ""
    path_str = str(path)
    if ".config/opencode" in path_str or ".opencode/" in path_str:
        return "[OpenCode]"
    elif ".claude/" in path_str:
        return "[Claude]"
    elif ".openlaoke/" in path_str:
        return "[Installed]"
    return ""


class OpenLaoKeCompleter(Completer):
    """Custom completer for commands and skills."""

    def _get_options(self):
        """Get all available options, refreshing skills each time."""
        options = []

        # Commands
        register_all()
        seen = set()
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

        # Skills - always refresh to pick up newly installed
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

        return options

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if not text.startswith("/"):
            return

        # Get search text after /
        search = text[1:].lower()

        all_options = self._get_options()

        # Deduplicate by display name, preferring skills over commands
        # (skills have source tags, commands don't)
        seen = {}
        for opt in all_options:
            display = opt["display"]
            if display not in seen:
                seen[display] = opt
            elif opt["type"] == "skill" and seen[display]["type"] != "skill":
                # Prefer skill over command alias
                seen[display] = opt
        unique_options = list(seen.values())

        # Filter and sort
        matches = []
        for opt in unique_options:
            name_lower = opt["name"].lower()
            display_lower = opt["display"].lower()

            # Score matching
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

        # Sort by score, then by source (OpenCode first, then Claude, then Installed)
        source_order = {"[OpenCode]": 0, "[Claude]": 1, "[Installed]": 2, "": 3}
        matches.sort(
            key=lambda x: (
                -x[0],
                source_order.get(x[1]["source"], 3),
                x[1]["display"],
            )
        )

        # Return all matching completions (no artificial limit)
        for _, opt in matches:
            meta_text = opt["description"] or ""
            yield Completion(
                opt["display"],
                start_position=-len(text),
                display=opt["display"],
                display_meta=meta_text,
            )

    def _fuzzy_match(self, query, text):
        """Simple fuzzy match."""
        idx = 0
        for char in text:
            if idx < len(query) and char == query[idx]:
                idx += 1
        return idx == len(query)


def create_prompt_session():
    """Create a PromptSession with autocomplete and history."""
    # Ensure history directory exists
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    style = Style.from_dict(
        {
            "prompt": "bold ansigreen",
            "completion": "ansicyan",
            "completion.selected": "bold ansicyan",
            "completion-meta": "ansibrightblack",
        }
    )

    completer = OpenLaoKeCompleter()

    # Create file-based history for persistence
    history = FileHistory(str(HISTORY_FILE))

    session = PromptSession(
        completer=completer,
        style=style,
        complete_while_typing=True,
        mouse_support=True,
        history=history,
        enable_history_search=True,  # Enable up/down arrow navigation
    )

    return session


async def get_user_input(session: PromptSession) -> str | None:
    """Get input from user with autocomplete support."""
    try:
        result = await session.prompt_async("OpenLaoKe: ")
        return result.strip()
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
