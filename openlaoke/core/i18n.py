"""Internationalization (i18n) support for OpenLaoKe TUI.

Provides language-aware text lookup for all user-visible strings
in the REPL interface. Supports runtime language switching via
Ctrl+L shortcut or /lang slash command.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "zh": "中文",
}

TUI_STRINGS: dict[str, dict[str, str]] = {
    "app_subtitle": {
        "en": "Open-source AI coding assistant",
        "zh": "开源AI编程助手",
    },
    "provider_label": {
        "en": "Provider:",
        "zh": "服务商：",
    },
    "model_label": {
        "en": "Model:",
        "zh": "模型：",
    },
    "working_dir_label": {
        "en": "Working directory:",
        "zh": "工作目录：",
    },
    "mode_label": {
        "en": "Mode:",
        "zh": "模式：",
    },
    "mode_online": {
        "en": "Online",
        "zh": "在线",
    },
    "mode_local": {
        "en": "Local (atomic decomposition)",
        "zh": "本地（原子分解）",
    },
    "tools_label": {
        "en": "Tools:",
        "zh": "工具：",
    },
    "tools_available": {
        "en": "available",
        "zh": "个可用",
    },
    "skills_label": {
        "en": "Skills:",
        "zh": "技能：",
    },
    "skills_available": {
        "en": "available (Tab to complete)",
        "zh": "个可用（Tab补全）",
    },
    "welcome_hint": {
        "en": "Type /help for commands, Tab for completion, or just start chatting.",
        "zh": "输入 /help 查看命令，Tab 补全，或直接开始对话。",
    },
    "prompt_label": {
        "en": "OpenLaoKe: ",
        "zh": "老克：",
    },
    "goodbye": {
        "en": "Goodbye!",
        "zh": "再见！",
    },
    "no_provider_error": {
        "en": "Error: No provider configured.",
        "zh": "错误：未配置服务商。",
    },
    "run_config_hint": {
        "en": "Run 'openlaoke --config' to set up a provider.",
        "zh": "请运行 'openlaoke --config' 配置服务商。",
    },
    "insomnia_resuming": {
        "en": "Insomnia mode: Resuming background tasks...",
        "zh": "Insomnia模式：恢复后台任务...",
    },
    "task_queued": {
        "en": "Task queued in insomnia mode:",
        "zh": "任务已加入Insomnia队列：",
    },
    "allow_tool": {
        "en": "Always allow the AI to run",
        "zh": "始终允许AI运行",
    },
    "unknown_command": {
        "en": "Unknown command:",
        "zh": "未知命令：",
    },
    "type_help": {
        "en": "Type /help for available commands.",
        "zh": "输入 /help 查看可用命令。",
    },
    "provider_not_found": {
        "en": "Provider not found:",
        "zh": "未找到服务商：",
    },
    "switched_to": {
        "en": "Switched to:",
        "zh": "已切换到：",
    },
    "skill_activated": {
        "en": "Skill activated:",
        "zh": "技能已激活：",
    },
    "language_set": {
        "en": "Language set to:",
        "zh": "界面语言已设置为：",
    },
    "current_language": {
        "en": "Current language:",
        "zh": "当前语言：",
    },
    "available_languages": {
        "en": "Available languages:",
        "zh": "可用语言：",
    },
    "select_language": {
        "en": "Select language",
        "zh": "选择语言",
    },
    "model_picker_title": {
        "en": "Model Picker",
        "zh": "模型选择器",
    },
    "model_picker_hint": {
        "en": "type to filter, Enter to select, Ctrl+C to cancel",
        "zh": "输入过滤，回车选择，Ctrl+C取消",
    },
    "lang_picker_title": {
        "en": "Language Picker",
        "zh": "语言选择器",
    },
    "lang_picker_hint": {
        "en": "Enter number or code, Ctrl+C to cancel",
        "zh": "输入编号或代码，Ctrl+C取消",
    },
}


def get_tui_text(key: str, lang: str | None = None) -> str:
    """Look up a TUI string in the given language.

    Falls back to English if the key or language is missing.
    """
    if lang is None:
        lang = "en"
    entry = TUI_STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry.get("en", key))


def get_language_instruction(lang: str) -> str:
    """Return a system prompt snippet telling the AI which language to use.

    Only emits a non-empty instruction for non-English languages.
    """
    if lang == "zh":
        return (
            "\n## Language\n"
            "You MUST respond in Chinese (简体中文). "
            "All user-facing text, explanations, code comments, and documentation "
            "must be written in Chinese. Keep code identifiers, technical terms, "
            "and file paths in their original form. "
            "The user prefers all communication in Chinese.\n"
        )
    return ""
