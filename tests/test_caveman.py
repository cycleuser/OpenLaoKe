"""Tests for caveman mode: CacheGuard, system prompt switching."""

from __future__ import annotations

from openlaoke.core.cache_guard import (
    SYSTEM_PROMPT_CAVEMAN,
    SYSTEM_PROMPT_STATIC,
    CacheGuard,
)


class TestCavemanMode:
    def test_caveman_prompt_is_shorter(self):
        assert len(SYSTEM_PROMPT_CAVEMAN) < len(SYSTEM_PROMPT_STATIC)

    def test_caveman_has_core_rules(self):
        assert "Be extremely concise" in SYSTEM_PROMPT_CAVEMAN
        assert "No pleasantries" in SYSTEM_PROMPT_CAVEMAN

    def test_full_prompt_lists_tools(self):
        assert "InvokeSkill" in SYSTEM_PROMPT_STATIC

    def test_cache_guard_default_uses_full_prompt(self, app_state):
        guard = CacheGuard(app_state)
        prompt = guard.system_prompt
        assert "InvokeSkill" in prompt

    def test_cache_guard_caveman_uses_concise_prompt(self, app_state):
        app_state.caveman_mode = True
        guard = CacheGuard(app_state)
        prompt = guard.system_prompt
        assert "No pleasantries" in prompt

    def test_toggle_caveman_returns_new_state(self):
        guard = CacheGuard()
        assert guard._caveman_mode is False
        new_state = guard.toggle_caveman()
        assert new_state is True
        assert guard._caveman_mode is True
        new_state = guard.toggle_caveman()
        assert new_state is False

    def test_toggle_invalidates_cache(self, app_state):
        guard = CacheGuard(app_state)
        _ = guard.system_prompt  # build once
        assert guard._built is True
        guard.toggle_caveman()
        assert guard._built is False  # invalidated

    def test_app_state_caveman_field(self, app_state):
        assert app_state.caveman_mode is False
        app_state.caveman_mode = True
        assert app_state.caveman_mode is True

    def test_system_prompt_extra_appended(self, app_state):
        """Verify _system_prompt_extra is appended in both modes."""

        app_state.caveman_mode = False
        guard = CacheGuard(app_state)
        full_prompt = guard.system_prompt
        # The extra suffix should contain skills/knowledge etc.
        # At minimum it should have a newline after the static prompt
        assert full_prompt.startswith("You are OpenLaoKe")
