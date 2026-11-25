"""Tests for CacheGuard: the byte-stable system prompt, the per-turn session
context block, and the Anthropic cache breakpoints.

These are the three things that decide whether a session keeps its prompt cache
or pays full price on every turn, so the invariants matter:

- the system prompt is built once and frozen (no date/model/cwd inside);
- the session context is injected only on a real change (first turn, new day,
  model switch, forced);
- cache markers land on the last two real messages, never on the ephemeral
  session-context blocks.
"""

from __future__ import annotations

import subprocess

import pytest

from openlaoke.core import cache_guard as mod
from openlaoke.core.cache_guard import (
    SYSTEM_PROMPT_CAVEMAN,
    SYSTEM_PROMPT_STATIC,
    CacheGuard,
    _build_session_context,
    _os_command_guidance,
)


class FakeAppState:
    """Minimal stand-in for AppState's prompt-relevant surface."""

    def __init__(self, **kwargs) -> None:
        self.cwd = kwargs.pop("cwd", "/tmp/project")
        self.harness_mode = kwargs.pop("harness_mode", "balanced")
        self.active_skills = kwargs.pop("active_skills", [])
        self.language = kwargs.pop("language", "en")
        self.caveman_mode = kwargs.pop("caveman_mode", False)
        self.session_config = kwargs.pop(
            "session_config", type("SC", (), {"system_prompt_suffix": ""})()
        )
        self.knowledge_loader = kwargs.pop("knowledge_loader", None)
        for key, value in kwargs.items():
            setattr(self, key, value)


# --------------------------------------------------------------------------- #
# _os_command_guidance
# --------------------------------------------------------------------------- #


def test_os_guidance_bans_linux_only_commands_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(mod.platform, "system", lambda: "Darwin")
    text = _os_command_guidance()
    assert "macOS" in text
    assert "lscpu" in text  # named as the trap
    assert "Do NOT use Linux-only" in text


def test_os_guidance_for_linux_and_windows(monkeypatch) -> None:
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")
    linux = _os_command_guidance()
    assert "Linux" in linux
    assert "free -h" in linux

    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    windows = _os_command_guidance()
    assert "PowerShell" in windows
    assert "Get-CimInstance" in windows


def test_os_guidance_falls_back_for_other_platforms(monkeypatch) -> None:
    monkeypatch.setattr(mod.platform, "system", lambda: "FreeBSD")
    assert "FreeBSD" in _os_command_guidance()
    assert "native to this platform" in _os_command_guidance()


# --------------------------------------------------------------------------- #
# _build_session_context
# --------------------------------------------------------------------------- #


@pytest.fixture()
def fake_git(monkeypatch):
    def install(stdout: str = "main\n", returncode: int = 0, exc: Exception | None = None):
        calls: list[list] = []

        def _run(cmd, **kwargs):
            calls.append(cmd)
            if exc is not None:
                raise exc
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

        monkeypatch.setattr(subprocess, "run", _run)
        return calls

    return install


def test_session_context_includes_date_model_os_cwd_and_branch(fake_git) -> None:
    fake_git(stdout="feature/ctx\n")
    state = FakeAppState(cwd="/tmp/project")
    text = _build_session_context(state, model="claude-sonnet-4-6", date_str="2026-03-04, Wednesday")
    assert "2026-03-04, Wednesday" in text
    assert "claude-sonnet-4-6" in text
    assert "/tmp/project" in text
    assert "Git branch: feature/ctx." in text


def test_session_context_omits_branch_when_git_fails(fake_git) -> None:
    fake_git(returncode=128)
    text = _build_session_context(FakeAppState(), model="m", date_str="d")
    assert "Git branch" not in text


def test_session_context_omits_detached_head(fake_git) -> None:
    fake_git(stdout="HEAD\n")
    text = _build_session_context(FakeAppState(), model="m", date_str="d")
    assert "Git branch" not in text


def test_session_context_survives_git_being_absent(fake_git) -> None:
    fake_git(exc=FileNotFoundError("git"))
    text = _build_session_context(FakeAppState(), model="m", date_str="d")
    assert "Git branch" not in text
    assert "/tmp/project" in text


def test_session_context_defaults_date_and_cwd(fake_git, monkeypatch) -> None:
    fake_git()
    monkeypatch.setattr(mod.time, "strftime", lambda fmt: "2026-01-02, Friday")
    monkeypatch.setattr(mod.os, "getcwd", lambda: "/fallback/dir")
    state = FakeAppState(cwd="")
    text = _build_session_context(state, model="m")
    assert "2026-01-02, Friday" in text
    assert "/fallback/dir" in text


# --------------------------------------------------------------------------- #
# System prompt lifecycle
# --------------------------------------------------------------------------- #


def test_system_prompt_is_built_once_and_frozen() -> None:
    guard = CacheGuard(FakeAppState())
    first = guard.system_prompt
    assert first.startswith(SYSTEM_PROMPT_STATIC)
    assert guard._built is True
    # A second access does not rebuild.
    guard._system_prompt = "SENTINEL"
    assert guard.system_prompt.startswith("SENTINEL")


def test_build_is_idempotent() -> None:
    guard = CacheGuard(FakeAppState())
    assert guard.build() == guard.build()
    assert guard._built is True


def test_invalidate_forces_a_rebuild() -> None:
    guard = CacheGuard(FakeAppState())
    assert guard.system_prompt.startswith(SYSTEM_PROMPT_STATIC)
    guard.invalidate()
    assert guard._built is False
    assert guard._system_prompt == ""
    assert guard._system_prompt_extra == ""
    # Next access rebuilds to the static prompt again.
    assert guard.system_prompt.startswith(SYSTEM_PROMPT_STATIC)


def test_caveman_toggle_flips_state_and_invalidates() -> None:
    guard = CacheGuard(FakeAppState())
    assert guard.system_prompt.startswith(SYSTEM_PROMPT_STATIC)
    assert guard.toggle_caveman() is True
    assert guard._built is False
    assert guard.system_prompt.startswith(SYSTEM_PROMPT_CAVEMAN)
    assert guard.toggle_caveman() is False
    assert guard.system_prompt.startswith(SYSTEM_PROMPT_STATIC)


def test_app_state_caveman_flag_also_switches_the_base_prompt() -> None:
    guard = CacheGuard(FakeAppState(caveman_mode=True))
    assert guard.system_prompt.startswith(SYSTEM_PROMPT_CAVEMAN)


def test_app_state_property_is_settable() -> None:
    guard = CacheGuard()
    assert guard.app_state is None
    state = FakeAppState()
    guard.app_state = state
    assert guard.app_state is state


# --------------------------------------------------------------------------- #
# _build_extra (frozen session suffix)
# --------------------------------------------------------------------------- #


def test_extra_is_empty_without_app_state() -> None:
    assert CacheGuard(None)._build_extra() == ""


def test_extra_contains_mode_directives() -> None:
    extra = CacheGuard(FakeAppState(harness_mode="pi"))._build_extra()
    assert extra.strip()  # every mode contributes its directives


def test_extra_includes_active_skills(monkeypatch) -> None:
    monkeypatch.setattr(
        "openlaoke.core.skill_system.get_skill_system_prompt", lambda names: "SKILL BODY"
    )
    extra = CacheGuard(FakeAppState(active_skills=["tdd"]))._build_extra()
    assert "## Active Skills" in extra
    assert "SKILL BODY" in extra


def test_extra_includes_configured_suffix() -> None:
    state = FakeAppState(
        session_config=type("SC", (), {"system_prompt_suffix": "Always answer in Chinese."})()
    )
    extra = CacheGuard(state)._build_extra()
    assert "## Additional Instructions" in extra
    assert "Always answer in Chinese." in extra


def test_extra_includes_knowledge_block() -> None:
    loader = type("KL", (), {"format_for_prompt": lambda _self, _q: "KNOWLEDGE"})()
    extra = CacheGuard(FakeAppState(knowledge_loader=loader))._build_extra()
    assert "KNOWLEDGE" in extra


def test_extra_swallows_knowledge_loader_errors() -> None:
    def boom(_self, _q):
        raise RuntimeError("index missing")

    loader = type("KL", (), {"format_for_prompt": boom})()
    # Must not propagate: the system prompt has to stay buildable.
    assert "KNOWLEDGE" not in CacheGuard(FakeAppState(knowledge_loader=loader))._build_extra()


def test_extra_adds_language_instruction_for_non_english() -> None:
    extra = CacheGuard(FakeAppState(language="zh"))._build_extra()
    assert extra.strip()
    english = CacheGuard(FakeAppState(language="en"))._build_extra()
    assert "Chinese" not in english


# --------------------------------------------------------------------------- #
# ensure_session_context
# --------------------------------------------------------------------------- #


def test_first_call_injects_the_block(fake_git) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    block = guard.ensure_session_context(model="m1")
    assert block is not None
    assert "/tmp/project" in block
    assert guard._last_session_context_model == "m1"


def test_same_day_same_model_injects_nothing(fake_git) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    guard.ensure_session_context(model="m1")
    assert guard.ensure_session_context(model="m1") is None


def test_model_switch_reinjects(fake_git) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    guard.ensure_session_context(model="m1")
    block = guard.ensure_session_context(model="m2")
    assert block is not None
    assert "m2" in block
    assert guard._last_session_context_model == "m2"


def test_day_change_reinjects(fake_git, monkeypatch) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    guard.ensure_session_context(model="m1")

    monkeypatch.setattr(mod.time, "strftime", lambda fmt: "2099-12-31" if fmt == "%Y-%m-%d" else "d")
    assert guard.ensure_session_context(model="m1") is not None


def test_force_reinjects(fake_git) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    guard.ensure_session_context(model="m1")
    assert guard.ensure_session_context(model="m1", force=True) is not None


def test_empty_model_does_not_clear_the_recorded_model(fake_git) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    guard.ensure_session_context(model="m1")
    guard.ensure_session_context(model="")
    assert guard._last_session_context_model == "m1"


def test_ensure_session_context_builds_the_prompt_if_needed(fake_git) -> None:
    fake_git()
    guard = CacheGuard(FakeAppState())
    guard.ensure_session_context(model="m1")
    assert guard._built is True


# --------------------------------------------------------------------------- #
# apply_cache_markers
# --------------------------------------------------------------------------- #


def test_markers_mark_the_last_two_real_messages() -> None:
    messages = [
        {"role": "user", "content": f"m{i}"} for i in range(5)
    ]
    out = CacheGuard.apply_cache_markers(messages)
    marked = [
        i
        for i, m in enumerate(out)
        if isinstance(m["content"], list) and m["content"][0].get("cache_control")
    ]
    assert marked == [3, 4]


def test_markers_skip_system_injected_blocks() -> None:
    messages = [
        {"role": "user", "content": "a"},
        {"role": "user", "content": "[session context]", "system_injected": True},
        {"role": "user", "content": "b"},
        {"role": "user", "content": "[session context]", "system_injected": True},
    ]
    out = CacheGuard.apply_cache_markers(messages)
    assert isinstance(out[0]["content"], list)
    assert out[1]["content"] == "[session context]"  # untouched
    assert out[3]["content"] == "[session context]"
    # The second marker goes to the earlier real message since only two exist.
    assert isinstance(out[2]["content"], list)


def test_markers_leave_empty_and_all_injected_lists_alone() -> None:
    assert CacheGuard.apply_cache_markers([]) == []
    all_injected = [{"role": "user", "content": "x", "system_injected": True}]
    assert CacheGuard.apply_cache_markers(all_injected) == all_injected


def test_markers_preserve_tool_fields_when_wrapping_strings() -> None:
    messages = [{"role": "assistant", "content": "hello", "tool_calls": [{"id": "c"}], "name": "n"}]
    out = CacheGuard.apply_cache_markers(messages)
    assert out[0]["tool_calls"] == [{"id": "c"}]
    assert out[0]["name"] == "n"
    assert out[0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_markers_do_not_double_wrap_a_marked_message() -> None:
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "x", "cache_control": {"type": "ephemeral"}}]},
        {"role": "user", "content": "y"},
    ]
    out = CacheGuard.apply_cache_markers(messages)
    assert isinstance(out[0]["content"], list)
    assert out[0]["content"][0]["text"] == "x"


def test_markers_add_cache_control_to_the_last_text_block() -> None:
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "keep"}, {"type": "text", "text": "mark me"}]},
        {"role": "user", "content": "second"},
    ]
    out = CacheGuard.apply_cache_markers(messages)
    blocks = out[0]["content"]
    assert "cache_control" not in blocks[0]
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}


def test_markers_fall_back_to_the_last_non_text_block() -> None:
    messages = [
        {"role": "user", "content": [{"type": "image", "source": "x"}]},
        {"role": "user", "content": "second"},
    ]
    out = CacheGuard.apply_cache_markers(messages)
    assert out[0]["content"][-1]["cache_control"] == {"type": "ephemeral"}


def test_markers_skip_empty_string_content() -> None:
    messages = [{"role": "assistant", "content": ""}, {"role": "user", "content": "real"}]
    out = CacheGuard.apply_cache_markers(messages)
    assert out[0]["content"] == ""  # nothing to mark
    assert isinstance(out[1]["content"], list)


# --------------------------------------------------------------------------- #
# build_compact_prompt
# --------------------------------------------------------------------------- #


def test_compact_prompt_names_tools_os_and_cwd(monkeypatch) -> None:
    monkeypatch.setattr(mod.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mod.platform, "release", lambda: "23.0")
    text = CacheGuard.build_compact_prompt(FakeAppState(cwd="/tmp/x"))
    assert "OpenLaoKe" in text
    assert "Darwin 23.0" in text
    assert "/tmp/x" in text
    assert "output DONE on its own line" in text
    # Discourages tool use for conversational turns.
    assert "WITHOUT using any tools" in text


def test_compact_prompt_falls_back_to_cwd_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(mod.os, "getcwd", lambda: "/fallback")
    text = CacheGuard.build_compact_prompt(FakeAppState(cwd=""))
    assert "/fallback" in text
