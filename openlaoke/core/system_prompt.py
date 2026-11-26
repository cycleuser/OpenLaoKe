"""System prompt builder for the headless and bot paths.

Two builders live here:

* :func:`build_system_prompt` — a full prompt assembled from the static rules,
  the harness mode, the environment and any session extras. The interactive REPL
  does not use it: it freezes a prompt through ``CacheGuard`` so the prefix stays
  byte-stable. The non-interactive run (``entrypoints/cli.py``) and bot mode do
  use it, once per run, which is why it is not dead code.
* :func:`build_compact_system_prompt` — a thin delegation to CacheGuard's small
  model prompt.
"""

from __future__ import annotations

import os
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


def build_system_prompt(
    app_state: AppState,
    tools_description: list[dict],
    world_context: str = "",
) -> str:
    """Build the system prompt sent to the model.

    Rebuilt on every call, which breaks a cached prefix: the interactive REPL
    therefore goes through ``CacheGuard.system_prompt`` instead, and this is used
    by the one-shot paths that build a prompt once per run.
    """
    from openlaoke.core.cache_guard import SYSTEM_PROMPT_STATIC

    parts = [SYSTEM_PROMPT_STATIC]

    from openlaoke.core.harness_modes import mode_directives

    parts.append(f"\n{mode_directives(getattr(app_state, 'harness_mode', 'balanced'))}\n")

    if world_context:
        parts.append(f"\n## Current Context\n{world_context}\n")

    parts.append(
        f"\n## Environment\n"
        f"- Platform: {platform.system()} {platform.release()}\n"
        f"- Python: {platform.python_version()}\n"
        f"- Working directory: {app_state.get_cwd()}\n"
        f"- Shell: {os.environ.get('SHELL', '/bin/bash')}\n"
    )

    git_branch = _get_git_branch(app_state.get_cwd())
    if git_branch:
        parts.append(f"- Git branch: {git_branch}\n")

    if hasattr(app_state, "active_skills") and app_state.active_skills:
        from openlaoke.core.skill_system import get_skill_system_prompt

        skill_prompt = get_skill_system_prompt(app_state.active_skills)
        if skill_prompt:
            parts.append(f"\n## Active Skills\n{skill_prompt}")

    suffix = app_state.session_config.system_prompt_suffix
    if suffix:
        parts.append(f"\n## Additional Instructions\n{suffix}")

    if hasattr(app_state, "language") and app_state.language != "en":
        from openlaoke.core.i18n import get_language_instruction

        lang_inst = get_language_instruction(app_state.language)
        if lang_inst:
            parts.append(lang_inst)

    return "\n".join(parts)


def build_compact_system_prompt(
    app_state: AppState,
    user_input: str = "",
    world_context: str = "",
) -> str:
    """Build a minimal system prompt for small local models with limited context.

    Delegates to CacheGuard.build_compact_prompt() for consistency.
    """
    from openlaoke.core.cache_guard import CacheGuard

    return CacheGuard.build_compact_prompt(app_state, user_input)


def _get_git_branch(cwd: str) -> str | None:
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
