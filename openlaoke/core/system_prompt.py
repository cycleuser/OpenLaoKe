"""System prompt builder for the AI model."""

from __future__ import annotations

import os
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


def build_system_prompt(app_state: AppState, tools_description: list[dict]) -> str:
    """Build the system prompt sent to the model."""
    parts = []

    parts.append(
        "You are OpenLaoKe, an expert AI coding assistant designed to help with "
        "software engineering tasks. You can read and write files, run shell commands, "
        "search codebases, and spawn sub-agents for parallel work.\n"
    )

    parts.append(
        "## Core Principles\n"
        "- Be concise and direct in your responses\n"
        "- Always verify your work after making changes\n"
        "- Read files before editing them to understand context\n"
        "- Use the Edit tool for targeted changes, Write for new files\n"
        "- Run tests to verify your changes work\n"
        "- Never commit secrets or API keys\n"
        "- Follow the existing code style and conventions\n"
    )

    parts.append(
        f"## Environment\n"
        f"- Platform: {platform.system()} {platform.release()}\n"
        f"- Python: {platform.python_version()}\n"
        f"- Working directory: {app_state.get_cwd()}\n"
        f"- Shell: {os.environ.get('SHELL', '/bin/bash')}\n"
    )

    git_branch = _get_git_branch(app_state.get_cwd())
    if git_branch:
        parts.append(f"- Git branch: {git_branch}\n")

    parts.append(
        "## Tool Usage Guidelines\n"
        "- Read files before editing to understand the current state\n"
        "- Use Glob to find files when you don't know the exact path\n"
        "- Use Grep to search for patterns across multiple files\n"
        "- Use Bash for running commands, tests, and git operations\n"
        "- Use Edit for small targeted changes, Write for new files\n"
        "- Use Agent to delegate independent parallel tasks\n"
        "\n"
        "IMPORTANT: When using tools, ALWAYS provide ALL required parameters:\n"
        "- Write tool: requires both 'file_path' AND 'content'\n"
        "- Edit tool: requires 'file_path', 'old_string', AND 'new_string'\n"
        "- Bash tool: requires 'command'\n"
        "- Read tool: requires 'file_path'\n"
        "Never omit required parameters. If you're unsure about a parameter, ask the user.\n"
    )

    parts.append(
        "## Response Format\n"
        "- Keep explanations concise and focused\n"
        "- Show relevant code snippets when explaining\n"
        "- Always explain what you're doing and why\n"
        "- If uncertain, say so and suggest how to verify\n"
    )

    if hasattr(app_state, "active_skills") and app_state.active_skills:
        from openlaoke.core.skill_system import get_skill_system_prompt

        skill_prompt = get_skill_system_prompt(app_state.active_skills)
        if skill_prompt:
            parts.append(f"\n## Active Skills\n{skill_prompt}")

    suffix = app_state.session_config.system_prompt_suffix
    if suffix:
        parts.append(f"\n## Additional Instructions\n{suffix}")

    return "\n".join(parts)


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
