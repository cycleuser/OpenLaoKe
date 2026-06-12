"""Tests for i18n/language switching feature."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from openlaoke.core.i18n import (
    SUPPORTED_LANGUAGES,
    TUI_STRINGS,
    get_language_instruction,
    get_tui_text,
)
from openlaoke.core.prompt_input import PromptAction, PromptResult


class TestI18nModule:
    def test_supported_languages_has_en_and_zh(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert "zh" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["en"] == "English"
        assert SUPPORTED_LANGUAGES["zh"] == "中文"

    def test_get_tui_text_returns_english_for_known_key(self):
        text = get_tui_text("goodbye", "en")
        assert text == "Goodbye!"

    def test_get_tui_text_returns_chinese_for_known_key(self):
        text = get_tui_text("goodbye", "zh")
        assert text == "再见！"

    def test_get_tui_text_falls_back_to_english_for_unknown_lang(self):
        text = get_tui_text("goodbye", "fr")
        assert text == "Goodbye!"

    def test_get_tui_text_returns_key_for_unknown_key(self):
        text = get_tui_text("nonexistent_key_123", "en")
        assert text == "nonexistent_key_123"

    def test_get_tui_text_defaults_to_en_when_lang_is_none(self):
        text = get_tui_text("goodbye", None)
        assert text == "Goodbye!"

    def test_all_keys_have_english(self):
        for key in TUI_STRINGS:
            assert "en" in TUI_STRINGS[key], f"Key '{key}' missing English translation"

    def test_all_keys_have_chinese(self):
        for key in TUI_STRINGS:
            assert "zh" in TUI_STRINGS[key], f"Key '{key}' missing Chinese translation"

    def test_no_empty_translations(self):
        for key, langs in TUI_STRINGS.items():
            for lang, text in langs.items():
                assert text.strip(), f"Key '{key}' has empty {lang} translation"

    def test_get_language_instruction_returns_empty_for_english(self):
        inst = get_language_instruction("en")
        assert inst == ""

    def test_get_language_instruction_returns_nonempty_for_chinese(self):
        inst = get_language_instruction("zh")
        assert "Chinese" in inst
        assert "简体中文" in inst

    def test_get_language_instruction_returns_empty_for_unknown(self):
        inst = get_language_instruction("fr")
        assert inst == ""


class TestAppConfigLanguage:
    def test_default_language_is_en(self):
        from openlaoke.utils.config import AppConfig

        config = AppConfig()
        assert config.language == "en"

    def test_language_roundtrips_through_save_load(self):
        from openlaoke.utils.config import AppConfig, load_config, save_config

        with tempfile.TemporaryDirectory() as tmp:
            config_dir = os.path.join(tmp, ".openlaoke")
            config_path = os.path.join(config_dir, "config.json")

            with (
                patch("openlaoke.utils.config.CONFIG_DIR", Path(config_dir)),
                patch("openlaoke.utils.config.CONFIG_PATH", Path(config_path)),
            ):
                os.makedirs(config_dir, exist_ok=True)
                config = AppConfig()
                config.language = "zh"
                save_config(config)

                loaded = load_config()
                assert loaded.language == "zh"

    def test_language_persists_in_json(self):
        from openlaoke.utils.config import AppConfig, save_config

        with tempfile.TemporaryDirectory() as tmp:
            config_dir = os.path.join(tmp, ".openlaoke")
            config_path = os.path.join(config_dir, "config.json")

            with (
                patch("openlaoke.utils.config.CONFIG_DIR", Path(config_dir)),
                patch("openlaoke.utils.config.CONFIG_PATH", Path(config_path)),
            ):
                os.makedirs(config_dir, exist_ok=True)
                config = AppConfig()
                config.language = "zh"
                save_config(config)

                with open(config_path) as f:
                    data = json.load(f)

                assert data["language"] == "zh"


class TestPromptResultLanguageAction:
    def test_lang_picker_action_exists(self):
        assert PromptAction.LANG_PICKER.value == "lang_picker"

    def test_is_lang_picker_returns_true(self):
        result = PromptResult(action=PromptAction.LANG_PICKER)
        assert result.is_lang_picker is True
        assert result.is_text is False
        assert result.is_picker is False
        assert result.is_exit is False

    def test_is_lang_picker_returns_false_for_text(self):
        result = PromptResult(action=PromptAction.TEXT, text="hello")
        assert result.is_lang_picker is False
        assert result.is_text is True


class TestLangCommand:
    @pytest.mark.asyncio
    async def test_lang_command_shows_current_language(self):
        from openlaoke.commands.base import CommandContext, LangCommand
        from openlaoke.core.state import create_app_state

        state = create_app_state()
        state.language = "en"
        ctx = CommandContext(app_state=state, args="")
        cmd = LangCommand()

        result = await cmd.execute(ctx)
        assert result.success is not False
        assert "Current language:" in result.message or "English" in result.message

    @pytest.mark.asyncio
    async def test_lang_command_switches_to_chinese(self):
        from openlaoke.commands.base import CommandContext, LangCommand
        from openlaoke.core.state import create_app_state

        with tempfile.TemporaryDirectory() as tmp:
            config_dir = os.path.join(tmp, ".openlaoke")
            config_path = os.path.join(config_dir, "config.json")

            with (
                patch("openlaoke.utils.config.CONFIG_DIR", Path(config_dir)),
                patch("openlaoke.utils.config.CONFIG_PATH", Path(config_path)),
            ):
                os.makedirs(config_dir, exist_ok=True)

                state = create_app_state()
                state.language = "en"
                ctx = CommandContext(app_state=state, args="zh")
                cmd = LangCommand()

                result = await cmd.execute(ctx)
                assert result.success is not False
                assert state.language == "zh"

    @pytest.mark.asyncio
    async def test_lang_command_rejects_invalid_language(self):
        from openlaoke.commands.base import CommandContext, LangCommand
        from openlaoke.core.state import create_app_state

        state = create_app_state()
        state.language = "en"
        ctx = CommandContext(app_state=state, args="fr")
        cmd = LangCommand()

        result = await cmd.execute(ctx)
        assert result.success is False
        assert state.language == "en"

    @pytest.mark.asyncio
    async def test_lang_command_aliases(self):
        from openlaoke.commands.base import LangCommand

        cmd = LangCommand()
        assert "language" in cmd.aliases


class TestRunLangPickerAsync:
    @pytest.mark.asyncio
    async def test_returns_en_when_user_selects_english(self):
        with patch("builtins.input", return_value="1"):
            from openlaoke.core.prompt_input import run_lang_picker_async

            result = await run_lang_picker_async("en")
            assert result == "en"

    @pytest.mark.asyncio
    async def test_returns_zh_when_user_selects_chinese(self):
        with patch("builtins.input", return_value="2"):
            from openlaoke.core.prompt_input import run_lang_picker_async

            result = await run_lang_picker_async("en")
            assert result == "zh"

    @pytest.mark.asyncio
    async def test_returns_none_on_ctrl_c(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            from openlaoke.core.prompt_input import run_lang_picker_async

            result = await run_lang_picker_async("en")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_eof(self):
        with patch("builtins.input", side_effect=EOFError):
            from openlaoke.core.prompt_input import run_lang_picker_async

            result = await run_lang_picker_async("en")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_code_when_user_types_language_code(self):
        with patch("builtins.input", return_value="zh"):
            from openlaoke.core.prompt_input import run_lang_picker_async

            result = await run_lang_picker_async("en")
            assert result == "zh"


class TestAppStateLanguage:
    def test_app_state_defaults_to_en(self):
        from openlaoke.core.state import AppState

        state = AppState()
        assert state.language == "en"
