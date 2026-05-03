"""Language subsystem for multi-language code capabilities."""

from __future__ import annotations

from openlaoke.core.langs.registry import LangRegistry
from openlaoke.core.langs.spec import LanguageSpec

__all__ = [
    "LanguageSpec",
    "LangRegistry",
    "get_registry",
]

_default_registry: LangRegistry | None = None


def get_registry() -> LangRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = LangRegistry()
    return _default_registry
