"""Language registry for multi-language code capabilities."""

from __future__ import annotations

from openlaoke.core.langs.spec import DEFAULT_SPECS, LanguageSpec


class LangRegistry:
    _instance: LangRegistry | None = None
    _specs: dict[str, LanguageSpec]

    def __new__(cls) -> LangRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._specs = {}
            for spec in DEFAULT_SPECS:
                cls._instance._specs[spec.name] = spec
        return cls._instance

    def register(self, spec: LanguageSpec) -> None:
        self._specs[spec.name] = spec

    def get_spec(self, name: str) -> LanguageSpec | None:
        return self._specs.get(name)

    def list_supported(self) -> list[str]:
        return list(self._specs.keys())

    def is_supported(self, name: str) -> bool:
        return name in self._specs


def get_registry() -> LangRegistry:
    return LangRegistry()
