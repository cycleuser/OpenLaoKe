"""Universal language translation for intent processing.

Translates all non-English requests to English for processing,
then translates results back to the original language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Language(StrEnum):
    ENGLISH = "en"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"
    PORTUGUESE = "pt"
    ITALIAN = "it"


@dataclass
class TranslationResult:
    original: str
    translated: str
    source_language: Language
    target_language: Language
    confidence: float = 1.0


class LanguageDetector:
    """Detect language of input text."""

    LANGUAGE_PATTERNS = {
        Language.CHINESE: [
            r"[\u4e00-\u9fff]",  # CJK Unified Ideographs
            r"写|创建|实现|定义|调试|修复",
        ],
        Language.JAPANESE: [
            r"[\u3040-\u309f]",  # Hiragana
            r"[\u30a0-\u30ff]",  # Katakana
        ],
        Language.KOREAN: [
            r"[\uac00-\ud7af]",  # Hangul
        ],
        Language.RUSSIAN: [
            r"[а-яА-ЯёЁ]",
        ],
        Language.FRENCH: [
            r"\b(le|la|les|un|une|des|et|ou|pour|avec|dans|sur)\b",
        ],
        Language.GERMAN: [
            r"\b(der|die|das|und|oder|für|mit|auf|ist|sind)\b",
        ],
        Language.SPANISH: [
            r"\b(el|la|los|las|un|una|y|o|para|con|en)\b",
        ],
        Language.PORTUGUESE: [
            r"\b(o|a|os|as|um|uma|e|ou|para|com|em)\b",
        ],
        Language.ITALIAN: [
            r"\b(il|lo|la|i|gli|le|un|una|e|o|per|con|in)\b",
        ],
    }

    @classmethod
    def detect(cls, text: str) -> Language:
        """Detect the language of input text."""
        if not text or not text.strip():
            return Language.ENGLISH

        text.lower()

        if re.search(r"[\u4e00-\u9fff]", text):
            return Language.CHINESE

        if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text):
            return Language.JAPANESE

        if re.search(r"[\uac00-\ud7af]", text):
            return Language.KOREAN

        if re.search(r"[а-яА-ЯёЁ]", text):
            return Language.RUSSIAN

        return Language.ENGLISH


class UniversalTranslator:
    """Translate between languages using simple pattern matching."""

    COMMON_PROGRAMMING_TERMS = {
        Language.CHINESE: {
            "写": "write",
            "创建": "create",
            "编写": "write",
            "实现": "implement",
            "程序": "program",
            "应用": "application",
            "脚本": "script",
            "函数": "function",
            "方法": "method",
            "类": "class",
            "调试": "debug",
            "修复": "fix",
            "测试": "test",
            "分析": "analyze",
            "优化": "optimize",
            "单文件": "single file",
            "计算": "calculate",
            "处理器": "processor",
            "核心": "core",
            "算力": "performance",
            "真实": "real",
            "估算": "estimate",
            "不能": "must not",
            "必须": "must",
            "一个": "a",
            "当前": "current",
            "设备": "device",
            "多核心": "multi-core",
            "单核心": "single-core",
            "性能": "performance",
            "基准测试": "benchmark",
            "快速排序": "quicksort",
            "排序": "sort",
            "搜索": "search",
            "查找": "find",
            "错误": "error",
            "代码": "code",
            "这段": "this",
            "文件": "file",
            "接口": "interface",
            "API": "API",
            "REST": "REST",
            "数据库": "database",
            "连接": "connect",
            "查询": "query",
            "结果": "result",
            "显示": "display",
            "输出": "output",
            "输入": "input",
            "处理": "process",
            "数据": "data",
            "字符串": "string",
            "列表": "list",
            "所有": "all",
            "目录": "directory",
            "包含": "contain",
            "操作": "operation",
            "获取": "get",
            "设置": "set",
            "配置": "config",
            "初始化": "initialize",
            "加载": "load",
            "卸载": "uninstall",
            "启动": "start",
            "停止": "stop",
            "重启": "restart",
            "安装": "install",
            "更新": "update",
            "版本": "version",
            "日志": "log",
            "异常": "exception",
            "警告": "warning",
            "信息": "info",
        },
        Language.JAPANESE: {
            "書": "write",
            "作成": "create",
            "実装": "implement",
            "プログラム": "program",
            "アプリ": "application",
            "関数": "function",
            "クラス": "class",
            "テスト": "test",
        },
        Language.KOREAN: {
            "쓰": "write",
            "만들": "create",
            "구현": "implement",
            "프로그램": "program",
            "함수": "function",
            "클래스": "class",
        },
    }

    @classmethod
    def translate_to_english(cls, text: str, source_lang: Language) -> str:
        """Translate non-English text to English."""
        if source_lang == Language.ENGLISH:
            return text

        if source_lang not in cls.COMMON_PROGRAMMING_TERMS:
            return text

        terms = cls.COMMON_PROGRAMMING_TERMS[source_lang]
        result = text

        sorted_terms = sorted(terms.items(), key=lambda x: len(x[0]), reverse=True)

        for native, english in sorted_terms:
            result = result.replace(native, f" {english} ")

        result = re.sub(r"\s+", " ", result).strip()

        result = re.sub(r"\s+([,.!?;:])", r"\1", result)
        result = re.sub(r"([,.!?;:])\s*", r"\1 ", result)

        return result

    @classmethod
    def translate_from_english(cls, text: str, target_lang: Language) -> str:
        """Translate English text back to target language."""
        if target_lang == Language.ENGLISH:
            return text

        if target_lang not in cls.COMMON_PROGRAMMING_TERMS:
            return text

        terms = cls.COMMON_PROGRAMMING_TERMS[target_lang]

        reverse_terms = {v: k for k, v in terms.items()}

        result = text

        sorted_terms = sorted(reverse_terms.items(), key=lambda x: len(x[0]), reverse=True)

        for english, native in sorted_terms:
            result = re.sub(r"\b" + re.escape(english) + r"\b", native, result, flags=re.IGNORECASE)

        return result


class TranslationPipeline:
    """Complete translation pipeline for multilingual support."""

    def __init__(self) -> None:
        self.detector = LanguageDetector()
        self.translator = UniversalTranslator()

    def prepare_for_processing(self, user_input: str) -> tuple[str, Language]:
        """Translate input to English for processing.

        Returns:
            (english_text, original_language)
        """
        source_lang = self.detector.detect(user_input)

        if source_lang == Language.ENGLISH:
            return user_input, source_lang

        english_text = self.translator.translate_to_english(user_input, source_lang)

        return english_text, source_lang

    def prepare_for_output(
        self, output_text: str, target_lang: Language, is_code: bool = False
    ) -> str:
        """Translate output back to user's language.

        Args:
            output_text: Text to translate
            target_lang: Target language
            is_code: If True, don't translate (code is universal)
        """
        if is_code or target_lang == Language.ENGLISH:
            return output_text

        return self.translator.translate_from_english(output_text, target_lang)

    def translate_code_comments(self, code: str, target_lang: Language) -> str:
        """Translate code comments to target language.

        Preserves code structure, only translates comments.
        """
        if target_lang == Language.ENGLISH:
            return code

        lines = code.split("\n")
        translated_lines = []

        for line in lines:
            stripped = line.lstrip()

            if stripped.startswith("#"):
                indent = line[: len(line) - len(stripped)]
                comment = stripped[1:].strip()

                translated = self.translator.translate_from_english(comment, target_lang)

                translated_lines.append(f"{indent}# {translated}")
            elif '"""' in line or "'''" in line:
                translated_lines.append(line)
            else:
                translated_lines.append(line)

        return "\n".join(translated_lines)


def create_translation_pipeline() -> TranslationPipeline:
    """Create a translation pipeline instance."""
    return TranslationPipeline()


def translate_request_to_english(user_input: str) -> tuple[str, Language]:
    """Convenience function to translate request to English.

    Returns:
        (english_text, original_language)
    """
    pipeline = TranslationPipeline()
    return pipeline.prepare_for_processing(user_input)


def translate_output_to_language(output: str, target_lang: Language, is_code: bool = False) -> str:
    """Convenience function to translate output."""
    pipeline = TranslationPipeline()
    return pipeline.prepare_for_output(output, target_lang, is_code)
