"""Prompt cache splitting optimization.

Moves query-dependent context (memory, knowledge, skills) out of the system
prompt into a query block prepended to the latest user message. This keeps
the system prompt identical across turns, enabling KV-cache reuse on
llama.cpp and prefix caching on cloud APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptCacheSplit:
    _enabled: bool = True
    _cached_blocks: dict[str, str] = field(default_factory=dict)

    def tag(self, name: str, content: str) -> None:
        self._cached_blocks[name] = content

    def untag(self, name: str) -> None:
        self._cached_blocks.pop(name, None)

    def clear_tags(self) -> None:
        self._cached_blocks.clear()

    def build_context_block(self, user_message: str) -> str:
        if not self._enabled or not self._cached_blocks:
            return user_message
        parts = ["<sc:context>"]
        for name, content in self._cached_blocks.items():
            if content.strip():
                parts.append(f"<!-- {name} -->\n{content}")
        parts.append("</sc:context>")
        parts.append(user_message)
        return "\n\n".join(parts)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
