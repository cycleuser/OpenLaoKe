"""System prompt builder for the headless and bot paths.

Two builders live here:

* :func:`build_system_prompt` — a full prompt assembled from the static rules,
  the harness mode, the environment and any session extras. The interactive REPL
  does not use it: it freezes a prompt through ``CacheGuard`` so the prefix stays
  byte-stable. The non-interactive run (``entrypoints/cli.py``) and bot mode do
  use it, once per run, which is why it is not dead code.
* :func:`build_compact_system_prompt` — a thin delegation to CacheGuard's small
  model prompt.

When a caller passes ``max_tokens`` the blocks go through
:mod:`openlaoke.core.prompt_budget`, which keeps every ``required`` block and
drops only optional ones: the rules that keep the agent honest are never traded
for a longer environment blurb.
"""

from __future__ import annotations

import os
import platform
from typing import TYPE_CHECKING

from openlaoke.core.prompt_budget import OPTIONAL, REQUIRED, AssemblyReport, PromptBlock, assemble

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


def system_prompt_blocks(
    app_state: AppState,
    world_context: str = "",
) -> list[PromptBlock]:
    """The prompt as ordered, tiered blocks (required first, in prompt order)."""
    from openlaoke.core.cache_guard import SYSTEM_PROMPT_STATIC
    from openlaoke.core.harness_modes import mode_directives

    blocks = [
        PromptBlock("rules", SYSTEM_PROMPT_STATIC, REQUIRED),
        PromptBlock(
            "mode", mode_directives(getattr(app_state, "harness_mode", "balanced")), REQUIRED
        ),
    ]

    if world_context:
        blocks.append(
            PromptBlock("context", f"## Current Context\n{world_context}", OPTIONAL)
        )

    environment = [
        "## Environment",
        f"- Platform: {platform.system()} {platform.release()}",
        f"- Python: {platform.python_version()}",
        f"- Working directory: {app_state.get_cwd()}",
        f"- Shell: {os.environ.get('SHELL', '/bin/bash')}",
    ]
    git_branch = _get_git_branch(app_state.get_cwd())
    if git_branch:
        environment.append(f"- Git branch: {git_branch}")
    blocks.append(PromptBlock("environment", "\n".join(environment), OPTIONAL))

    if hasattr(app_state, "active_skills") and app_state.active_skills:
        from openlaoke.core.skill_system import get_skill_system_prompt

        skill_prompt = get_skill_system_prompt(app_state.active_skills)
        if skill_prompt:
            blocks.append(PromptBlock("skills", f"## Active Skills\n{skill_prompt}", REQUIRED))

    suffix = app_state.session_config.system_prompt_suffix
    if suffix:
        blocks.append(
            PromptBlock("instructions", f"## Additional Instructions\n{suffix}", REQUIRED)
        )

    if hasattr(app_state, "language") and app_state.language != "en":
        from openlaoke.core.i18n import get_language_instruction

        lang_inst = get_language_instruction(app_state.language)
        if lang_inst:
            blocks.append(PromptBlock("language", lang_inst, REQUIRED))

    return blocks


def assemble_system_prompt(
    app_state: AppState,
    world_context: str = "",
    *,
    max_tokens: int | None = None,
) -> tuple[str, AssemblyReport]:
    """Build the prompt and report what fit and what did not."""
    return assemble(system_prompt_blocks(app_state, world_context), max_tokens=max_tokens)


def build_system_prompt(
    app_state: AppState,
    tools_description: list[dict],
    world_context: str = "",
    *,
    max_tokens: int | None = None,
) -> str:
    """Build the system prompt sent to the model.

    Rebuilt on every call, which breaks a cached prefix: the interactive REPL
    therefore goes through ``CacheGuard.system_prompt`` instead, and this is used
    by the one-shot paths that build a prompt once per run.

    ``tools_description`` is accepted for callers that pass it; the tool list is
    already inside the static rules, so it is not re-rendered here.
    """
    prompt, report = assemble_system_prompt(app_state, world_context, max_tokens=max_tokens)
    if report.over_budget:
        import logging

        logging.getLogger(__name__).warning(
            "System prompt is %s tokens with a %s-token budget; required blocks were kept",
            report.used_tokens,
            max_tokens,
        )
    return prompt


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
