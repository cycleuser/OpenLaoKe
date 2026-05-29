"""Per-tool trust score decay.

Tracks consecutive failures per tool within a session. Tools that fail repeatedly
are soft-demoted (schema list back) then hard-dropped from the schema entirely.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrustDecay:
    warn_threshold: int = 3
    drop_threshold: int = 5
    _consecutive_failures: dict[str, int] = field(default_factory=dict)
    _dropped_tools: set[str] = field(default_factory=set)
    _demoted_tools: set[str] = field(default_factory=set)
    _enabled: bool = True

    @property
    def dropped(self) -> set[str]:
        return self._dropped_tools

    @property
    def demoted(self) -> set[str]:
        return self._demoted_tools

    def record_failure(self, tool_name: str) -> None:
        if not self._enabled:
            return
        count = self._consecutive_failures.get(tool_name, 0) + 1
        self._consecutive_failures[tool_name] = count
        if count >= self.drop_threshold:
            self._dropped_tools.add(tool_name)
        elif count >= self.warn_threshold:
            self._demoted_tools.add(tool_name)

    def record_success(self, tool_name: str) -> None:
        if not self._enabled:
            return
        self._consecutive_failures.pop(tool_name, None)
        self._demoted_tools.discard(tool_name)
        self._dropped_tools.discard(tool_name)

    def is_dropped(self, tool_name: str) -> bool:
        return tool_name in self._dropped_tools

    def is_demoted(self, tool_name: str) -> bool:
        return tool_name in self._demoted_tools

    def get_failure_count(self, tool_name: str) -> int:
        return self._consecutive_failures.get(tool_name, 0)

    def filter_tool_schemas(self, schemas: list[dict]) -> list[dict]:
        """Remove dropped tools, push demoted tools to end."""
        if not self._enabled:
            return schemas
        visible = [s for s in schemas if s.get("name") not in self._dropped_tools]
        demoted = [s for s in visible if s.get("name") in self._demoted_tools]
        kept = [s for s in visible if s.get("name") not in self._demoted_tools]
        return kept + demoted

    def reset(self) -> None:
        self._consecutive_failures.clear()
        self._dropped_tools.clear()
        self._demoted_tools.clear()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self.reset()
