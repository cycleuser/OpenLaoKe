"""InvokeSkill tool — meta-tool for dynamic skill loading.

Instead of adding every skill as a separate tool (which bloats tool schemas
and breaks prompt cache), all skills are accessible through this single
meta-tool.  The model calls ``invoke_skill(skill_name="xxx")`` and the tool
reads the corresponding SKILL.md at runtime.

This keeps the core tool set stable (16-20 tools) regardless of how many
skills the user installs.  New skills are communicated to the model via
[session context] blocks, not system prompt or tool schema changes.

Design: keep the core tool set stable regardless of how many skills are installed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext
from openlaoke.types.core_types import ToolResultBlock


class InvokeSkillInput(BaseModel):
    skill_name: str = Field(description="Name of the skill to invoke")
    arguments: str = Field(
        default="",
        description="Arguments or task description to pass to the skill",
    )
    description: str = Field(
        default="",
        description="Brief description of what you want the skill to do",
    )


class InvokeSkillTool(Tool):
    """Invoke a skill by name — the skill is loaded at runtime.

    Only this tool appears in the tool schema.  All skills are accessed
    through it, keeping the core tool set small and cache-friendly.
    """

    name = "InvokeSkill"
    description = (
        "Invoke a skill by name. Skills provide specialized capabilities "
        "(code review, PPT generation, browser automation, etc.) without "
        "bloating the main tool list. Use this when a task matches a known "
        "skill. The skill's instructions are loaded at runtime."
    )
    input_schema = InvokeSkillInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    # ---- skill search paths -----------------------------------------------

    @staticmethod
    def _find_skill_file(skill_name: str) -> Path | None:
        """Search for a SKILL.md file by name."""
        search_dirs = [
            Path.home() / ".openlaoke" / "skills",
            Path.cwd() / ".openlaoke" / "skills",
            Path.home() / ".config" / "opencode" / "skills",
        ]
        for base in search_dirs:
            candidate = base / skill_name / "SKILL.md"
            if candidate.exists():
                return candidate
            candidate = base / f"{skill_name}.md"
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _list_available_skills() -> list[str]:
        """List all installed skill names."""
        skills: list[str] = []
        search_dirs = [
            Path.home() / ".openlaoke" / "skills",
            Path.cwd() / ".openlaoke" / "skills",
            Path.home() / ".config" / "opencode" / "skills",
        ]
        for base in search_dirs:
            if not base.exists():
                continue
            for entry in base.iterdir():
                if entry.is_dir() and (entry / "SKILL.md").exists():
                    skills.append(entry.name)
                elif entry.suffix == ".md":
                    skills.append(entry.stem)
        return sorted(set(skills))

    # ---- main handler -----------------------------------------------------

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        skill_name = kwargs.get("skill_name", "")
        arguments = kwargs.get("arguments", "")
        description = kwargs.get("description", "")

        if not skill_name.strip():
            available = self._list_available_skills()
            if available:
                skills_list = ", ".join(available[:30])
                hint = f" Available skills: {skills_list}"
                if len(available) > 30:
                    hint += f" (+{len(available) - 30} more)"
            else:
                hint = " No skills found. Install skills to ~/.openlaoke/skills/<name>/SKILL.md"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: skill_name is required.{hint}",
                is_error=True,
            )

        skill_name = skill_name.strip()
        skill_file = self._find_skill_file(skill_name)

        if not skill_file:
            available = self._list_available_skills()
            hint = ""
            if available:
                hint = f" Available: {', '.join(available[:20])}"
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Skill '{skill_name}' not found.{hint}",
                is_error=True,
            )

        try:
            skill_content = skill_file.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Failed to read skill '{skill_name}': {e}",
                is_error=True,
            )

        prompt = f"""[Skill: {skill_name}]
{skill_content}

[Task]
{arguments or description or 'Execute the skill as instructed.'}"""

        from openlaoke.core.task import TaskManager

        task_mgr = TaskManager(ctx.app_state)

        try:
            result = await task_mgr.run_agent(
                prompt=prompt,
                description=description or f"Skill: {skill_name}",
                tool_use_id=ctx.tool_use_id,
                subagent_type=f"skill:{skill_name}",
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Skill '{skill_name}' execution failed: {e}",
                is_error=True,
            )

        max_output = 20000
        if len(result) > max_output:
            result = (
                result[:max_output]
                + f"\n\n... (output truncated, {len(result) - max_output} chars omitted)"
            )

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Skill '{skill_name}' result:\n\n{result}",
            is_error=False,
        )
