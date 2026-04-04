"""Theme management for OpenLaoKe TUI."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.color import Color
from rich.style import Style
from rich.text import Text


@dataclass
class ThemeColors:
    """Color palette for a theme."""

    primary: str = "#00a8ff"
    secondary: str = "#9b59b6"
    accent: str = "#e74c3c"
    error: str = "#ff5555"
    warning: str = "#f1c40f"
    success: str = "#2ecc71"
    muted: str = "#6c757d"
    background: str = "#1a1a2e"
    foreground: str = "#eaeaea"

    def to_dict(self) -> dict[str, str]:
        return {
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "error": self.error,
            "warning": self.warning,
            "success": self.success,
            "muted": self.muted,
            "background": self.background,
            "foreground": self.foreground,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ThemeColors:
        return cls(
            primary=data.get("primary", "#00a8ff"),
            secondary=data.get("secondary", "#9b59b6"),
            accent=data.get("accent", "#e74c3c"),
            error=data.get("error", "#ff5555"),
            warning=data.get("warning", "#f1c40f"),
            success=data.get("success", "#2ecc71"),
            muted=data.get("muted", "#6c757d"),
            background=data.get("background", "#1a1a2e"),
            foreground=data.get("foreground", "#eaeaea"),
        )


@dataclass
class ThemeStyles:
    """Style definitions for UI components."""

    panel: str = "bold primary"
    message: str = "foreground"
    tool_use: str = "bold secondary"
    tool_result: str = "muted"
    user_message: str = "bold primary"
    assistant_message: str = "bold secondary"
    system_message: str = "dim"
    error_message: str = "bold error"

    def to_dict(self) -> dict[str, str]:
        return {
            "panel": self.panel,
            "message": self.message,
            "tool_use": self.tool_use,
            "tool_result": self.tool_result,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "system_message": self.system_message,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ThemeStyles:
        return cls(
            panel=data.get("panel", "bold primary"),
            message=data.get("message", "foreground"),
            tool_use=data.get("tool_use", "bold secondary"),
            tool_result=data.get("tool_result", "muted"),
            user_message=data.get("user_message", "bold primary"),
            assistant_message=data.get("assistant_message", "bold secondary"),
            system_message=data.get("system_message", "dim"),
            error_message=data.get("error_message", "bold error"),
        )


@dataclass
class Theme:
    """Complete theme definition."""

    name: str
    colors: ThemeColors
    styles: ThemeStyles
    is_dark: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "colors": self.colors.to_dict(),
            "styles": self.styles.to_dict(),
            "is_dark": self.is_dark,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Theme:
        colors = ThemeColors.from_dict(data.get("colors", {}))
        styles = ThemeStyles.from_dict(data.get("styles", {}))
        return cls(
            name=data.get("name", "custom"),
            colors=colors,
            styles=styles,
            is_dark=data.get("is_dark", True),
        )

    def get_color(self, name: str) -> str:
        color_map = {
            "primary": self.colors.primary,
            "secondary": self.colors.secondary,
            "accent": self.colors.accent,
            "error": self.colors.error,
            "warning": self.colors.warning,
            "success": self.colors.success,
            "muted": self.colors.muted,
            "background": self.colors.background,
            "foreground": self.colors.foreground,
        }
        return color_map.get(name, self.colors.foreground)

    def get_style(self, name: str) -> Style:
        style_str = getattr(self.styles, name, "foreground")
        return self._parse_style(style_str)

    def _parse_style(self, style_str: str) -> Style:
        parts = style_str.split()
        kwargs: dict[str, Any] = {}

        style_map = {
            "bold": "bold",
            "dim": "dim",
            "italic": "italic",
            "underline": "underline",
            "blink": "blink",
            "reverse": "reverse",
        }

        color_map = {
            "primary": self.colors.primary,
            "secondary": self.colors.secondary,
            "accent": self.colors.accent,
            "error": self.colors.error,
            "warning": self.colors.warning,
            "success": self.colors.success,
            "muted": self.colors.muted,
            "background": self.colors.background,
            "foreground": self.colors.foreground,
        }

        for part in parts:
            if part in style_map:
                kwargs[style_map[part]] = True
            elif part in color_map:
                kwargs["color"] = Color.parse(color_map[part])
            else:
                with contextlib.suppress(Exception):
                    kwargs["color"] = Color.parse(part)

        return Style(**kwargs)


BUILTIN_THEMES: dict[str, Theme] = {}

DARK_THEME = Theme(
    name="dark",
    colors=ThemeColors(
        primary="#00a8ff",
        secondary="#9b59b6",
        accent="#e74c3c",
        error="#ff5555",
        warning="#f1c40f",
        success="#2ecc71",
        muted="#6c757d",
        background="#1a1a2e",
        foreground="#eaeaea",
    ),
    styles=ThemeStyles(),
    is_dark=True,
)
BUILTIN_THEMES["dark"] = DARK_THEME

LIGHT_THEME = Theme(
    name="light",
    colors=ThemeColors(
        primary="#0066cc",
        secondary="#6c5ce7",
        accent="#d63031",
        error="#d63031",
        warning="#fdcb6e",
        success="#00b894",
        muted="#636e72",
        background="#ffffff",
        foreground="#2d3436",
    ),
    styles=ThemeStyles(
        panel="bold primary",
        message="foreground",
        tool_use="bold secondary",
        tool_result="muted",
        user_message="bold primary",
        assistant_message="bold secondary",
        system_message="dim",
        error_message="bold error",
    ),
    is_dark=False,
)
BUILTIN_THEMES["light"] = LIGHT_THEME

MONOKAI_THEME = Theme(
    name="monokai",
    colors=ThemeColors(
        primary="#66d9ef",
        secondary="#f92672",
        accent="#ae81ff",
        error="#f92672",
        warning="#e6db74",
        success="#a6e22e",
        muted="#75715e",
        background="#272822",
        foreground="#f8f8f2",
    ),
    styles=ThemeStyles(
        panel="bold primary",
        message="foreground",
        tool_use="bold secondary",
        tool_result="muted",
        user_message="bold primary",
        assistant_message="bold accent",
        system_message="dim",
        error_message="bold error",
    ),
    is_dark=True,
)
BUILTIN_THEMES["monokai"] = MONOKAI_THEME

DRACULA_THEME = Theme(
    name="dracula",
    colors=ThemeColors(
        primary="#bd93f9",
        secondary="#ff79c6",
        accent="#ffb86c",
        error="#ff5555",
        warning="#f1fa8c",
        success="#50fa7b",
        muted="#6272a4",
        background="#282a36",
        foreground="#f8f8f2",
    ),
    styles=ThemeStyles(
        panel="bold primary",
        message="foreground",
        tool_use="bold secondary",
        tool_result="muted",
        user_message="bold primary",
        assistant_message="bold secondary",
        system_message="dim",
        error_message="bold error",
    ),
    is_dark=True,
)
BUILTIN_THEMES["dracula"] = DRACULA_THEME

SOLARIZED_THEME = Theme(
    name="solarized",
    colors=ThemeColors(
        primary="#268bd2",
        secondary="#6c71c4",
        accent="#d33682",
        error="#dc322f",
        warning="#b58900",
        success="#859900",
        muted="#657b83",
        background="#002b36",
        foreground="#839496",
    ),
    styles=ThemeStyles(
        panel="bold primary",
        message="foreground",
        tool_use="bold secondary",
        tool_result="muted",
        user_message="bold primary",
        assistant_message="bold accent",
        system_message="dim",
        error_message="bold error",
    ),
    is_dark=True,
)
BUILTIN_THEMES["solarized"] = SOLARIZED_THEME

NORD_THEME = Theme(
    name="nord",
    colors=ThemeColors(
        primary="#88c0d0",
        secondary="#81a1c1",
        accent="#5e81ac",
        error="#bf616a",
        warning="#ebcb8b",
        success="#a3be8c",
        muted="#4c566a",
        background="#2e3440",
        foreground="#eceff4",
    ),
    styles=ThemeStyles(
        panel="bold primary",
        message="foreground",
        tool_use="bold secondary",
        tool_result="muted",
        user_message="bold primary",
        assistant_message="bold accent",
        system_message="dim",
        error_message="bold error",
    ),
    is_dark=True,
)
BUILTIN_THEMES["nord"] = NORD_THEME

GITHUB_THEME = Theme(
    name="github",
    colors=ThemeColors(
        primary="#0366d6",
        secondary="#6f42c1",
        accent="#d73a49",
        error="#cb2431",
        warning="#f9a825",
        success="#28a745",
        muted="#586069",
        background="#ffffff",
        foreground="#24292e",
    ),
    styles=ThemeStyles(
        panel="bold primary",
        message="foreground",
        tool_use="bold secondary",
        tool_result="muted",
        user_message="bold primary",
        assistant_message="bold secondary",
        system_message="dim",
        error_message="bold error",
    ),
    is_dark=False,
)
BUILTIN_THEMES["github"] = GITHUB_THEME

THEMES_DIR = Path.home() / ".openlaoke" / "themes"


def load_custom_themes() -> dict[str, Theme]:
    custom_themes: dict[str, Theme] = {}
    if not THEMES_DIR.exists():
        return custom_themes

    for theme_file in THEMES_DIR.glob("*.json"):
        try:
            with open(theme_file, encoding="utf-8") as f:
                data = json.load(f)
            theme = Theme.from_dict(data)
            custom_themes[theme.name] = theme
        except Exception:
            pass

    return custom_themes


def get_theme(name: str) -> Theme:
    all_themes = {**BUILTIN_THEMES, **load_custom_themes()}
    return all_themes.get(name, DARK_THEME)


def get_all_themes() -> dict[str, Theme]:
    return {**BUILTIN_THEMES, **load_custom_themes()}


def get_theme_names() -> list[str]:
    return sorted(get_all_themes().keys())


class ThemeManager:
    """Manages theme loading, switching, and persistence."""

    def __init__(self, current_theme: str = "dark"):
        self._current_theme_name = current_theme
        self._theme_cache: dict[str, Theme] = {}
        self._load_themes()

    def _load_themes(self) -> None:
        self._theme_cache = get_all_themes()

    @property
    def current_theme(self) -> Theme:
        if self._current_theme_name not in self._theme_cache:
            self._current_theme_name = "dark"
        return self._theme_cache.get(self._current_theme_name, DARK_THEME)

    @property
    def current_theme_name(self) -> str:
        return self._current_theme_name

    def set_theme(self, name: str) -> bool:
        if name not in self._theme_cache:
            self._load_themes()
        if name in self._theme_cache:
            self._current_theme_name = name
            return True
        return False

    def reload_themes(self) -> None:
        self._load_themes()

    def get_available_themes(self) -> list[str]:
        return sorted(self._theme_cache.keys())

    def is_dark_theme(self) -> bool:
        return self.current_theme.is_dark

    def color(self, name: str) -> str:
        return self.current_theme.get_color(name)

    def style(self, name: str) -> Style:
        return self.current_theme.get_style(name)

    def format_text(self, text: str, style_name: str) -> Text:
        style = self.style(style_name)
        return Text(text, style=style)

    def apply_to_rich(self) -> dict[str, Any]:
        theme = self.current_theme
        return {
            "style": Style(color=Color.parse(theme.colors.foreground)),
            "bgstyle": Style(color=Color.parse(theme.colors.background)),
        }
