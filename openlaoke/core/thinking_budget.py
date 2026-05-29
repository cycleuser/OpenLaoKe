"""Thinking budget control for reasoning models.

Caps thinking tokens per call across providers (Anthropic budget_tokens,
OpenAI reasoning_effort, Qwen enable_thinking). Prevents trivial tasks from
consuming thousands of tokens on reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThinkingBudget:
    soft_budget: int = 2000
    hard_cap: int = 8000
    _enabled: bool = True
    _disable_thinking: bool = False

    def get_anthropic_config(self) -> dict:
        if not self._enabled:
            return {}
        if self._disable_thinking:
            return {"thinking": {"type": "disabled"}}
        return {
            "thinking": {
                "type": "enabled",
                "budget_tokens": self.soft_budget,
            }
        }

    def get_openai_config(self) -> dict:
        if not self._enabled:
            return {}
        if self._disable_thinking:
            return {}
        if self.soft_budget <= 500:
            return {"reasoning_effort": "low"}
        elif self.soft_budget <= 2000:
            return {"reasoning_effort": "medium"}
        return {"reasoning_effort": "high"}

    def get_qwen_config(self) -> dict:
        if not self._enabled:
            return {}
        if self._disable_thinking:
            return {"enable_thinking": False}
        return {"enable_thinking": True, "thinking_budget": self.soft_budget}

    def get_llama_cpp_config(self) -> dict:
        if not self._enabled:
            return {}
        if self._disable_thinking:
            return {"chat_template_kwargs": {"enable_thinking": False}}
        return {
            "chat_template_kwargs": {
                "enable_thinking": True,
                "thinking_budget": self.soft_budget,
            }
        }

    def truncate_thinking(self, content: str) -> str:
        """Hard-truncate oversize thinking blocks."""
        if not self._enabled or len(content) <= self.hard_cap:
            return content
        keep_head = int(self.hard_cap * 0.4)
        keep_tail = int(self.hard_cap * 0.2)
        return content[:keep_head] + "\n\n... [thinking truncated] ...\n\n" + content[-keep_tail:]

    def disable_for_repair(self) -> None:
        """Disable thinking for repair attempts."""
        self._disable_thinking = True

    def enable_for_repair(self) -> None:
        self._disable_thinking = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
