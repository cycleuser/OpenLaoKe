"""Tests for the system-prompt builders used by the headless and bot paths.

The interactive REPL freezes its prompt through CacheGuard; the CLI's
non-interactive run and bot mode still call build_system_prompt, so its output is
what those runs actually send to the model.
"""

from __future__ import annotations

import platform
import subprocess

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.system_prompt import (
    _get_git_branch,
    build_compact_system_prompt,
    build_system_prompt,
)


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path))


def test_prompt_carries_the_static_rules_and_the_environment(tmp_path, state) -> None:
    from openlaoke.core.cache_guard import SYSTEM_PROMPT_STATIC

    prompt = build_system_prompt(state, [])

    assert prompt.startswith(SYSTEM_PROMPT_STATIC[:80])
    assert "## Environment" in prompt
    assert f"Platform: {platform.system()} {platform.release()}" in prompt
    assert f"Python: {platform.python_version()}" in prompt
    assert f"Working directory: {tmp_path}" in prompt
    assert "Shell: " in prompt


def test_prompt_includes_the_harness_mode_directives(tmp_path, state) -> None:
    from openlaoke.core.harness_modes import mode_directives

    state.harness_mode = "pi"
    prompt = build_system_prompt(state, [])

    directives = mode_directives("pi")
    assert directives
    assert directives.strip()[:40] in prompt


def test_world_context_is_fenced_into_its_own_section(state) -> None:
    prompt = build_system_prompt(state, [], world_context="the sky is blue")

    assert "## Current Context" in prompt
    assert "the sky is blue" in prompt


def test_no_world_context_means_no_section(state) -> None:
    assert "## Current Context" not in build_system_prompt(state, [])


def test_session_prompt_suffix_is_appended_last(state) -> None:
    state.session_config.system_prompt_suffix = "Always answer in haiku."
    prompt = build_system_prompt(state, [])

    assert "## Additional Instructions" in prompt
    assert prompt.rstrip().endswith("Always answer in haiku.")


def test_active_skills_are_expanded_when_the_registry_knows_them(state, monkeypatch) -> None:
    import openlaoke.core.skill_system as skill_system

    monkeypatch.setattr(
        skill_system, "get_skill_system_prompt", lambda names: "## Skill: reviewer\n\nCheck it."
    )
    state.active_skills = ["reviewer"]

    prompt = build_system_prompt(state, [])

    assert "## Active Skills" in prompt
    assert "Check it." in prompt


def test_no_active_skills_means_no_section(state, monkeypatch) -> None:
    import openlaoke.core.skill_system as skill_system

    monkeypatch.setattr(skill_system, "get_skill_system_prompt", lambda names: "")
    state.active_skills = ["empty-skill"]

    assert "## Active Skills" not in build_system_prompt(state, [])


def test_language_instruction_is_added_for_a_non_english_session(state) -> None:
    state.language = "zh"
    prompt = build_system_prompt(state, [])

    from openlaoke.core.i18n import get_language_instruction

    assert get_language_instruction("zh") in prompt


def test_english_session_gets_no_language_instruction(state) -> None:
    state.language = "en"
    assert "中文" not in build_system_prompt(state, [])


def test_git_branch_is_reported_inside_a_repository(state, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="feature/x\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert "- Git branch: feature/x" in build_system_prompt(state, [])


def test_no_git_branch_line_outside_a_repository(state, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 128, stdout="", stderr="not a repo")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert "Git branch:" not in build_system_prompt(state, [])


def test_a_missing_git_binary_is_ignored(state, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("git not installed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _get_git_branch(str(state.get_cwd())) is None


def test_get_git_branch_reads_the_real_repository_root() -> None:
    # The test suite runs inside the project repository.
    assert _get_git_branch(".") not in (None, "")


def test_get_git_branch_of_a_directory_that_does_not_exist() -> None:
    assert _get_git_branch("/definitely/not/a/directory") is None


def test_compact_prompt_is_the_cache_guard_one(state) -> None:
    from openlaoke.core.cache_guard import CacheGuard

    assert build_compact_system_prompt(state, "list the files") == (
        CacheGuard.build_compact_prompt(state, "list the files")
    )


def test_prompt_is_stable_for_the_same_state(state, monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 128, "", "")
    )
    assert build_system_prompt(state, []) == build_system_prompt(state, [])
