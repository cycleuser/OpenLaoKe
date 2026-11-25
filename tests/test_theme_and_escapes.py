"""Tests for small UI/repair utilities: escape normalisation and the theme
system (built-ins, custom theme loading, style parsing, ThemeManager).
"""

from __future__ import annotations

import json

import pytest
from rich.text import Text

from openlaoke.utils import theme as theme_mod
from openlaoke.utils.text_escapes import normalize_model_escapes
from openlaoke.utils.theme import (
    BUILTIN_THEMES,
    DARK_THEME,
    Theme,
    ThemeColors,
    ThemeManager,
    ThemeStyles,
    get_all_themes,
    get_theme,
    get_theme_names,
    load_custom_themes,
)

# --------------------------------------------------------------------------- #
# normalize_model_escapes
# --------------------------------------------------------------------------- #


def test_empty_text_is_returned_as_is() -> None:
    assert normalize_model_escapes("") == ""


def test_real_newlines_are_left_alone() -> None:
    text = "line1\nline2\\nline3"
    assert normalize_model_escapes(text) == text


def test_carriage_returns_also_mark_real_text() -> None:
    text = "a\rb\\nc\\nd"
    assert normalize_model_escapes(text) == text


def test_single_literal_escape_is_not_enough_to_fire() -> None:
    text = "print('hi\\nthere')"
    assert normalize_model_escapes(text) == text


def test_document_with_two_literal_newlines_is_repaired() -> None:
    assert normalize_model_escapes("line1\\nline2\\nline3") == "line1\nline2\nline3"


def test_crlf_tab_and_cr_are_repaired_together() -> None:
    text = "a\\r\\nb\\nc\\rd\\te"
    assert normalize_model_escapes(text) == "a\nb\nc\nd\te"


def test_other_escapes_are_treated_as_intentional() -> None:
    doubled = "path\\\\to\\nfile\\nname"
    assert normalize_model_escapes(doubled) == doubled
    quoted = 'say \\"hi\\"\\nplease\\nnow'
    assert normalize_model_escapes(quoted) == quoted


# --------------------------------------------------------------------------- #
# Theme dataclasses
# --------------------------------------------------------------------------- #


def test_colors_round_trip() -> None:
    colors = ThemeColors(primary="#111111", muted="#222222")
    restored = ThemeColors.from_dict(colors.to_dict())
    assert restored == colors


def test_colors_from_dict_uses_defaults_for_missing_keys() -> None:
    colors = ThemeColors.from_dict({"primary": "#abcdef"})
    assert colors.primary == "#abcdef"
    assert colors.foreground == ThemeColors().foreground


def test_styles_round_trip_and_defaults() -> None:
    styles = ThemeStyles(panel="bold accent")
    assert ThemeStyles.from_dict(styles.to_dict()) == styles
    assert ThemeStyles.from_dict({}).panel == "bold primary"


def test_theme_round_trip_through_dict() -> None:
    theme = Theme(name="mine", colors=ThemeColors(), styles=ThemeStyles(), is_dark=False)
    restored = Theme.from_dict(theme.to_dict())
    assert restored.name == "mine"
    assert restored.is_dark is False
    assert restored.colors == theme.colors


def test_theme_from_dict_defaults() -> None:
    theme = Theme.from_dict({})
    assert theme.name == "custom"
    assert theme.is_dark is True


def test_get_color_known_and_unknown_names() -> None:
    assert DARK_THEME.get_color("primary") == DARK_THEME.colors.primary
    assert DARK_THEME.get_color("muted") == DARK_THEME.colors.muted
    # Unknown names fall back to the foreground colour.
    assert DARK_THEME.get_color("nope") == DARK_THEME.colors.foreground


def test_parse_style_maps_attributes_and_palette_names() -> None:
    theme = Theme(
        name="t",
        colors=ThemeColors(primary="#00ff00"),
        styles=ThemeStyles(panel="bold underline primary"),
    )
    style = theme.get_style("panel")
    assert style.bold is True
    assert style.underline is True
    assert style.color is not None


def test_parse_style_accepts_raw_color_literals_and_ignores_garbage() -> None:
    theme = Theme(name="t", colors=ThemeColors(), styles=ThemeStyles(message="red dim"))
    style = theme.get_style("message")
    assert style.dim is True
    assert style.color is not None

    garbage = Theme(name="t", colors=ThemeColors(), styles=ThemeStyles(message="@@@"))
    # An unparsable token is swallowed rather than raising.
    assert garbage.get_style("message") is not None


def test_get_style_falls_back_for_unknown_style_names() -> None:
    style = DARK_THEME.get_style("not_a_style")
    assert style is not None  # parsed from the "foreground" default


# --------------------------------------------------------------------------- #
# Custom themes
# --------------------------------------------------------------------------- #


@pytest.fixture()
def themes_dir(tmp_path, monkeypatch):
    directory = tmp_path / "themes"
    directory.mkdir()
    monkeypatch.setattr(theme_mod, "THEMES_DIR", directory)
    monkeypatch.setattr(theme_mod, "_CUSTOM_THEMES_CACHE", None)
    yield directory
    monkeypatch.setattr(theme_mod, "_CUSTOM_THEMES_CACHE", None)


def write_theme(directory, filename: str, payload) -> None:
    (directory / filename).write_text(
        payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
    )


def test_load_custom_themes_returns_empty_without_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(theme_mod, "THEMES_DIR", tmp_path / "missing")
    assert load_custom_themes() == {}


def test_load_custom_themes_reads_valid_files(themes_dir) -> None:
    write_theme(themes_dir, "mine.json", {"name": "mine", "is_dark": False})
    loaded = load_custom_themes()
    assert set(loaded) == {"mine"}
    assert loaded["mine"].is_dark is False


def test_load_custom_themes_skips_broken_files(themes_dir) -> None:
    write_theme(themes_dir, "good.json", {"name": "good"})
    write_theme(themes_dir, "bad.json", "{not json")
    loaded = load_custom_themes()
    assert set(loaded) == {"good"}


def test_get_theme_merges_custom_over_builtin(themes_dir) -> None:
    write_theme(themes_dir, "dark.json", {"name": "dark", "is_dark": False})
    theme = get_theme("dark")
    assert theme.name == "dark"
    assert theme.is_dark is False


def test_get_theme_falls_back_to_the_dark_theme(themes_dir) -> None:
    assert get_theme("does-not-exist") is DARK_THEME


def test_theme_names_are_sorted_and_include_builtins(themes_dir) -> None:
    write_theme(themes_dir, "zzz.json", {"name": "zzz"})
    names = get_theme_names()
    assert names == sorted(names)
    assert "zzz" in names
    assert set(BUILTIN_THEMES).issubset(names)


def test_get_all_themes_includes_builtin_and_custom(themes_dir) -> None:
    write_theme(themes_dir, "custom.json", {"name": "custom"})
    all_themes = get_all_themes()
    assert "custom" in all_themes
    assert "dark" in all_themes


# --------------------------------------------------------------------------- #
# ThemeManager
# --------------------------------------------------------------------------- #


def test_manager_defaults_to_the_dark_theme(themes_dir) -> None:
    manager = ThemeManager()
    assert manager.current_theme_name == "dark"
    assert manager.current_theme.name == "dark"
    assert manager.is_dark_theme() is True


def test_manager_set_theme_switches_and_reports_success(themes_dir) -> None:
    manager = ThemeManager()
    assert manager.set_theme("github") is True
    assert manager.current_theme_name == "github"
    assert manager.is_dark_theme() is False
    assert manager.set_theme("nope") is False
    assert manager.current_theme_name == "github"


def test_manager_set_theme_picks_up_a_newly_written_file(themes_dir) -> None:
    manager = ThemeManager()
    write_theme(themes_dir, "late.json", {"name": "late"})
    # Not in the initial cache, so set_theme reloads before giving up.
    assert manager.set_theme("late") is True
    assert manager.current_theme.name == "late"


def test_manager_reload_themes_sees_new_files(themes_dir) -> None:
    manager = ThemeManager()
    write_theme(themes_dir, "fresh.json", {"name": "fresh"})
    manager.reload_themes()
    assert "fresh" in manager.get_available_themes()


def test_manager_recovers_from_an_unknown_current_theme(themes_dir) -> None:
    manager = ThemeManager(current_theme="ghost")
    assert manager.current_theme_name == "dark"
    assert manager.current_theme.name == "dark"


def test_manager_color_and_style_helpers(themes_dir) -> None:
    manager = ThemeManager()
    assert manager.color("primary") == manager.current_theme.colors.primary
    assert manager.style("panel").bold is True


def test_manager_format_text_returns_rich_text(themes_dir) -> None:
    manager = ThemeManager()
    text = manager.format_text("hello", "user_message")
    assert isinstance(text, Text)
    assert text.plain == "hello"


def test_manager_apply_to_rich_returns_fg_and_bg_styles(themes_dir) -> None:
    applied = ThemeManager().apply_to_rich()
    assert set(applied) == {"style", "bgstyle"}
    assert applied["style"].color is not None
