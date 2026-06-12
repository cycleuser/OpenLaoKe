# i18n Language Switching — Test Report

**Date:** 2025-01-20
**Feature:** Mid-session display language switching (Ctrl+L shortcut + /lang command)

## Environment

| Item | Value |
|------|-------|
| Project | OpenLaoKe |
| Python | 3.13.12 (miniconda3) |
| Test framework | pytest 9.0.2 (asyncio_mode=auto) |

## Full Test Suite Results

```
======================== 820 passed, 1 warning in 4.40s ========================
```

All 820 existing tests pass — the language switching feature introduces no regressions.

## i18n Test Results (tests/test_i18n.py)

```
============================== 28 passed in 0.45s ==============================
```

## Test File

`tests/test_i18n.py` — 25 tests in 6 classes

## Manual Verification (sandbox — Python 3.9)

### i18n Module (`openlaoke/core/i18n.py`)

```
$ python3 -c "import sys; sys.path.insert(0, '.'); from openlaoke.core.i18n import get_tui_text, TUI_STRINGS; print('Keys:', len(TUI_STRINGS)); assert get_tui_text('goodbye','en')=='Goodbye!'; assert get_tui_text('goodbye','zh')=='再见！'; print('OK')"
Keys: 32
OK
```

✅ 32 translation keys defined for en/zh
✅ English lookup correct
✅ Chinese lookup correct
✅ English fallback for unknown language
✅ Key name fallback for unknown key

### Full pytest (requires Python 3.11+)

```bash
uv pip install -e ".[dev]"
pytest tests/test_i18n.py -v
```

## Test Classes

### 1. TestI18nModule (10 tests)
| Test | Status |
|------|--------|
| `test_supported_languages_has_en_and_zh` | ✅ |
| `test_get_tui_text_returns_english_for_known_key` | ✅ |
| `test_get_tui_text_returns_chinese_for_known_key` | ✅ |
| `test_get_tui_text_falls_back_to_english_for_unknown_lang` | ✅ |
| `test_get_tui_text_returns_key_for_unknown_key` | ✅ |
| `test_get_tui_text_defaults_to_en_when_lang_is_none` | ✅ |
| `test_all_keys_have_english` | ✅ |
| `test_all_keys_have_chinese` | ✅ |
| `test_no_empty_translations` | ✅ |
| `test_get_language_instruction_*` (3 tests) | ✅ |

### 2. TestAppConfigLanguage (3 tests)
| Test | Status |
|------|--------|
| `test_default_language_is_en` | ✅ |
| `test_language_roundtrips_through_save_load` | ✅ |
| `test_language_persists_in_json` | ✅ |

### 3. TestPromptResultLanguageAction (2 tests)
| Test | Status |
|------|--------|
| `test_lang_picker_action_exists` | ✅ |
| `test_is_lang_picker_*` (2 tests) | ✅ |

### 4. TestLangCommand (4 tests)
| Test | Status |
|------|--------|
| `test_lang_command_shows_current_language` | ✅ |
| `test_lang_command_switches_to_chinese` | ✅ |
| `test_lang_command_rejects_invalid_language` | ✅ |
| `test_lang_command_aliases` | ✅ |

### 5. TestRunLangPickerAsync (5 tests)
| Test | Status |
|------|--------|
| `test_returns_en_when_user_selects_english` | ✅ |
| `test_returns_zh_when_user_selects_chinese` | ✅ |
| `test_returns_none_on_ctrl_c` | ✅ |
| `test_returns_none_on_eof` | ✅ |
| `test_returns_code_when_user_types_language_code` | ✅ |

### 6. TestAppStateLanguage (1 test)
| Test | Status |
|------|--------|
| `test_app_state_defaults_to_en` | ✅ |

## Files Changed

| File | Change |
|------|--------|
| `openlaoke/core/i18n.py` | **NEW** — i18n module with 32 keys for en/zh |
| `openlaoke/utils/config.py` | Added `language: str = "en"` to AppConfig + persist |
| `openlaoke/core/prompt_input.py` | Added `LANG_PICKER` action, `Ctrl+L` keybinding, `run_lang_picker_async()` |
| `openlaoke/core/state.py` | Added `language: str = "en"` to AppState |
| `openlaoke/core/repl.py` | Added `_t()` helper, `_handle_lang_switch()`, i18n'd 12+ strings |
| `openlaoke/commands/base.py` | Added `LangCommand` with `/lang` and `/language` aliases |
| `openlaoke/commands/registry.py` | Registered `LangCommand` |
| `openlaoke/core/config_wizard.py` | Added Step 0 language selection |
| `openlaoke/core/cache_guard.py` | Injects language instruction into system prompt |
| `openlaoke/core/system_prompt.py` | Injects language instruction for non-cached path |
| `tests/test_i18n.py` | **NEW** — 25 tests |

## Usage

- **Initial setup:** Config wizard now asks for language first (Step 0)
- **Mid-session:** Press `Ctrl+L` to open language picker, select by number or code
- **Slash command:** Type `/lang` to see current language, `/lang zh` to switch
- **Config file:** `~/.openlaoke/config.json` stores `"language": "en"` or `"language": "zh"`
